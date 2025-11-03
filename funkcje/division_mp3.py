import os
import re
import warnings
from pydub import AudioSegment
import whisper

# Wycisz ostrzeżenia FP16
warnings.filterwarnings("ignore", message="FP16 is not supported on CPU")

# Użyj rapidfuzz zamiast fuzzywuzzy
try:
    from rapidfuzz import fuzz, process
except ImportError:
    print("📦 Instaluję rapidfuzz...")
    os.system("pip install rapidfuzz")
    from rapidfuzz import fuzz, process 

def run():
    # Wycisz ostrzeżenia na początku
    warnings.filterwarnings("ignore", message="FP16 is not supported on CPU")
    
    # Ścieżki
    temp_folder = "temp"
    mp3_folder = os.path.join(temp_folder, "mp3")
    
    # Znajdź plik rozdziału
    txt_files = [f for f in os.listdir(temp_folder) if f.startswith("ROZDZIAŁ_") and f.endswith(".txt")]
    if not txt_files:
        print("❌ Nie znaleziono pliku rozdziału w folderze temp/")
        return
    
    txt_file = txt_files[0]
    txt_path = os.path.join(temp_folder, txt_file)
    
    print(f"📄 Znaleziono plik rozdziału: {txt_path}")
    
    # Wczytaj tekst
    with open(txt_path, 'r', encoding='utf-8') as f:
        text = f.read()
    
    # Załaduj model Whisper
    print("⏳ Ładowanie modelu Whisper...")
    model = whisper.load_model("base")
    
    # Znajdź pliki MP3
    mp3_files = [f for f in os.listdir(mp3_folder) if f.endswith('.mp3')]
    mp3_files.sort()  # Sortuj alfabetycznie
    
    print(f"🎵 Znaleziono {len(mp3_files)} plików MP3 w {mp3_folder}")
    print()
    
    # Funkcja do przycięcia audio do pierwszych sekund
    def przytnij_do_poczatku(file_path, sekundy=8):
        audio = AudioSegment.from_file(file_path)
        return audio[:sekundy * 1000]
    
    # Funkcja normalizacji z tolerancją błędów
    def normalize_for_matching(text):
        """Normalizuje tekst z tolerancją na częste błędy transkrypcji"""
        text = text.lower()
        # Usuń znaki interpunkcyjne
        text = re.sub(r'[^\w\s]', ' ', text)
        # Usuń wielokrotne spacje
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Popraw częste błędy transkrypcji
        replacements = {
            'idry': 'idrys',
            'sudańczycy': 'sudańczycy',
            'gebhr': 'gebr',
            'ibleś': 'iblis',
            'iblis': 'iblis',
            'chams': 'chamis',
            'staś': 'stas',
            'nalektura': 'nel',
            'aydryz': 'idrys',
        }
        
        for wrong, correct in replacements.items():
            text = text.replace(wrong, correct)
            
        return text
    
    # 🔧 NOWA ULEPSZONA FUNKCJA - sliding window z fuzzy matching
    def find_phrase_with_sliding_window(original_text, search_phrase, start_offset=0, threshold=50):
        """
        Znajduje frazę używając sliding window i fuzzy matching.
        Zwraca (pozycja_w_oryginalnym_tekście, score) lub (None, 0).
        """
        if not search_phrase or len(search_phrase) < 3:
            return None, 0
        
        # Normalizuj frazę do wyszukiwania
        phrase_norm = normalize_for_matching(search_phrase)
        phrase_words = phrase_norm.split()
        
        if not phrase_words:
            return None, 0
        
        # Parametry sliding window
        window_size = len(search_phrase) * 3  # Okno 3x większe niż fraza
        step_size = 20  # Krok co 20 znaków
        
        best_pos = None
        best_score = 0
        best_match_info = ""
        
        # Iteruj po tekście od start_offset
        search_text = original_text[start_offset:]
        
        for i in range(0, len(search_text) - window_size, step_size):
            # Wyciągnij fragment
            window = search_text[i:i + window_size]
            window_norm = normalize_for_matching(window)
            
            # Oblicz podobieństwo
            score = fuzz.partial_ratio(phrase_norm, window_norm)
            
            # Dodatkowe punkty jeśli pierwsze słowo frazy jest w oknie
            if phrase_words and phrase_words[0] in window_norm.split():
                score = min(100, score + 10)
            
            # Sprawdź czy to lepsze dopasowanie
            if score > best_score:
                best_score = score
                # Znajdź dokładną pozycję pierwszego słowa w oryginalnym oknie
                first_word_pos = find_first_word_position_in_window(window, phrase_words[0])
                if first_word_pos is not None:
                    best_pos = start_offset + i + first_word_pos
                else:
                    best_pos = start_offset + i
                
                best_match_info = window[:100]
                
                # Jeśli znaleziono bardzo dobre dopasowanie, przestań szukać
                if score >= 95:
                    break
        
        # Debugowanie
        if best_score >= threshold:
            print(f"   🎯 Najlepsze dopasowanie ({best_score:.1f}%): '{best_match_info[:50]}...'")
        
        if best_score >= threshold:
            return best_pos, best_score
        
        return None, best_score
    
    # Pomocnicza funkcja do znajdowania pozycji pierwszego słowa
    def find_first_word_position_in_window(window, first_word_norm):
        """
        Znajduje pozycję pierwszego słowa (znormalizowanego) w oknie (oryginalnym).
        Zwraca pozycję w oryginalnym oknie lub None.
        """
        # Normalizuj okno i znajdź pozycję pierwszego słowa
        window_norm = normalize_for_matching(window)
        words_norm = window_norm.split()
        
        if first_word_norm not in words_norm:
            return None
        
        # Znajdź indeks słowa w znormalizowanym tekście
        word_index = words_norm.index(first_word_norm)
        
        # Teraz znajdź odpowiednią pozycję w oryginalnym oknie
        # Liczymy ile słów jest przed tym słowem
        words_before = word_index
        
        # Przechodzimy przez oryginalne okno szukając n-tego słowa
        current_word = 0
        in_word = False
        
        for i, char in enumerate(window):
            if char.isalnum() and not in_word:
                # Początek nowego słowa
                if current_word == words_before:
                    return i
                in_word = True
            elif not char.isalnum() and in_word:
                # Koniec słowa
                current_word += 1
                in_word = False
        
        return None
    
    # 🔧 POPRAWIONA FUNKCJA - znajduje najlepsze miejsce na separator
    def find_best_separator_position(text, phrase_position):
        """
        Znajdź najlepsze miejsce na separator PRZED frazą.
        Priorytet: początek akapitu > początek zdania > początek linii > początek słowa
        """
        if phrase_position == 0:
            return 0
        
        # Sprawdź różne pozycje wstecz od phrase_position
        search_back = min(200, phrase_position)  # Zwiększone z 150 na 200
        start = phrase_position - search_back
        
        best_pos = phrase_position
        best_score = 0
        
        # Szukaj najlepszego miejsca
        for i in range(phrase_position, start - 1, -1):
            score = 0
            
            # Początek tekstu
            if i == 0:
                return 0
            
            char = text[i-1]
            prev_char = text[i-2] if i >= 2 else ''
            
            # Nowy akapit (dwa entery)
            if char == '\n' and prev_char == '\n':
                score = 100
            # Początek dialogu
            elif char == '—' or (i >= 2 and text[i-2:i] == '— '):
                score = 90
            # Po końcu zdania z enterem
            elif char == '\n' and i >= 2 and prev_char in '.!?':
                score = 85
            # Po końcu zdania
            elif char in '.!?' and (i >= len(text) or text[i] in ' \n\t'):
                score = 80
            # Początek linii
            elif char == '\n':
                score = 70
            # Po spacji (początek słowa)
            elif char == ' ' and (i < len(text) and text[i].isalnum()):
                score = 50
            # Początek słowa bez spacji
            elif not char.isalnum() and (i < len(text) and text[i].isalnum()):
                score = 40
            
            # Preferuj pozycje bliżej frazy (ale nie za bardzo)
            distance = phrase_position - i
            if distance <= 5:
                score += 25  # Bardzo blisko
            elif distance <= 20:
                score += 15  # Blisko
            elif distance <= 50:
                score += 10  # Średnio
            elif distance <= 100:
                score += 5   # Daleko
            
            if score > best_score:
                best_score = score
                best_pos = i
                
                # Jeśli znaleziono idealną pozycję (nowy akapit), użyj jej
                if score >= 100:
                    break
        
        return best_pos
    
    # Analizuj każdy plik MP3
    frazy = []
    for i, mp3_file in enumerate(mp3_files, 1):
        mp3_path = os.path.join(mp3_folder, mp3_file)
        print(f"🎧 [{i}] Przetwarzam początek nagrania: {mp3_file}")
        
        # Przytnij do pierwszych 8 sekund
        audio_segment = przytnij_do_poczatku(mp3_path, 8)
        
        # Zapisz tymczasowo przycięty fragment
        temp_audio_path = os.path.join(temp_folder, "temp_audio.wav")
        audio_segment.export(temp_audio_path, format="wav")
        
        # Transkrypcja z Whisper
        result = model.transcribe(temp_audio_path, language="pl")
        fraza_pelna = result["text"].strip()
        
        # Weź więcej słów z transkrypcji dla lepszego dopasowania
        slowa = fraza_pelna.split()
        fraza = ' '.join(slowa[:8])  # zwiększone z 6 do 8 słów
        
        # Wyświetl pełną transkrypcję dla debugowania
        print(f"🔎 [{i}] Pełna transkrypcja: {fraza_pelna}")
        print(f"🔎 [{i}] Używana fraza: {fraza}")
        
        frazy.append({
            "plik": mp3_file,
            "fraza": fraza
        })
        
        # Usuń tymczasowy plik
        if os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)
    
    print(f"\n📋 Podsumowanie transkrypcji: znaleziono {len(frazy)} fraz z {len(mp3_files)} plików")
    
    # 🔧 CAŁKOWICIE PRZEPISANA funkcja wstawiania enterów
    def wstaw_entery_z_fuzzy(text, frazy, prog=50):  # Obniżony próg z 60 do 50
        """
        Wstawia separatory w tekście na podstawie znalezionych fraz.
        Zawsze wstawia separator PRZED pierwszym słowem frazy.
        """
        znalezione = []
        nie_znalezione = []
        new_text = text
        offset = 0  # Przesunięcie spowodowane wstawionymi separatorami
        
        for idx, item in enumerate(frazy, start=1):
            fraza = item["fraza"].strip()
            plik = item["plik"]
            
            print(f"\n🔍 [{idx}] Szukam: '{fraza[:50]}...'")
            
            # Znajdź frazę w oryginalnym tekście (z uwzględnieniem offset)
            phrase_pos, score = find_phrase_with_sliding_window(new_text, fraza, offset, threshold=prog)
            
            if phrase_pos is None:
                print(f"❌ [{idx}] ({plik}) Brak dopasowania >= {prog}% dla: '{fraza}' (najlepsze: {score:.1f}%)")
                nie_znalezione.append((plik, fraza, score))
                continue
            
            # Znajdź najlepsze miejsce na separator (przed frazą)
            separator_pos = find_best_separator_position(new_text, phrase_pos)
            
            # Wstaw separator
            separator = f"\n\n\n[{idx}] >>>>>>>>>>>>>>>\n\n"
            new_text = new_text[:separator_pos] + separator + new_text[separator_pos:]
            
            # Zaktualizuj offset
            offset = separator_pos + len(separator)
            
            # Wyświetl informację o dopasowaniu
            match_type = "DOKŁADNE" if score >= 95 else "FUZZY"
            print(f"✅ [{match_type}] [{idx}] ({plik}) '{fraza[:40]}...' ({score:.1f}%)")
            znalezione.append((plik, fraza, score))
        
        return new_text, znalezione, nie_znalezione
    
    # Wstaw entery
    new_text, znalezione, nie_znalezione = wstaw_entery_z_fuzzy(text, frazy)
    
    # Podsumowanie
    print(f"\n{'='*80}")
    print(f"📊 PODSUMOWANIE:")
    print(f"✅ Znalezione dopasowania: {len(znalezione)}/{len(frazy)} ({len(znalezione)*100//len(frazy)}%)")
    
    if znalezione:
        print(f"\n✅ ZNALEZIONE ({len(znalezione)}):")
        for plik, fraza, score in znalezione:
            icon = "🎯" if score >= 90 else "✅"
            print(f"   {icon} {plik}: {fraza[:60]}... ({score:.1f}%)")
    
    if nie_znalezione:
        print(f"\n❌ NIE ZNALEZIONE ({len(nie_znalezione)}):")
        for plik, fraza, score in nie_znalezione:
            print(f"   ❌ {plik}: {fraza[:60]}... (najlepsze: {score:.1f}%)")
    
    # Zapisz wynik
    output_path = os.path.join(temp_folder, "z_enterami.txt")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(new_text)
    
    print(f"\n✅ Gotowe! Wynik zapisano do: {output_path}")
    print(f"{'='*80}")

if __name__ == "__main__":
    run()