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
            'staś': 'stas'
        }
        
        for wrong, correct in replacements.items():
            text = text.replace(wrong, correct)
            
        return text
    
    # 🔧 NOWA FUNKCJA - znajduje frazę w oryginalnym tekście
    def find_phrase_in_original_text(original_text, search_phrase, start_offset=0, threshold=70):
        """
        Znajduje frazę w oryginalnym tekście (NIE znormalizowanym).
        Zwraca pozycję POCZĄTKU pierwszego słowa frazy.
        """
        # Najpierw spróbuj dokładnego dopasowania (case-insensitive)
        search_lower = search_phrase.lower()
        text_from_offset = original_text[start_offset:]
        
        # Szukaj dokładnej frazy
        pos = text_from_offset.lower().find(search_lower)
        if pos != -1:
            absolute_pos = start_offset + pos
            # Sprawdź czy to początek słowa
            if absolute_pos == 0 or not original_text[absolute_pos-1].isalnum():
                return absolute_pos, 100.0
        
        # Jeśli nie znaleziono dokładnie, użyj fuzzy matching
        phrase_norm = normalize_for_matching(search_phrase)
        first_word = phrase_norm.split()[0] if phrase_norm.split() else ""
        
        if not first_word or len(first_word) < 3:
            return None, 0
        
        best_pos = None
        best_score = 0
        
        # Szukaj pierwszego słowa w tekście
        search_text = original_text[start_offset:]
        pos = 0
        
        while pos < len(search_text):
            # Znajdź następne wystąpienie pierwszej litery pierwszego słowa
            char_pos = search_text[pos:].lower().find(first_word[0])
            if char_pos == -1:
                break
            
            pos += char_pos
            absolute_pos = start_offset + pos
            
            # Sprawdź czy to początek słowa
            if absolute_pos > 0 and original_text[absolute_pos-1].isalnum():
                pos += 1
                continue
            
            # Wyciągnij fragment tekstu dla porównania
            fragment_len = max(len(search_phrase) * 3, 300)
            fragment = original_text[absolute_pos:absolute_pos + fragment_len]
            
            # Oblicz podobieństwo na znormalizowanych tekstach
            fragment_norm = normalize_for_matching(fragment)
            score = fuzz.partial_ratio(phrase_norm, fragment_norm)
            
            # Dodatkowy bonus jeśli pierwsze słowo dokładnie pasuje
            fragment_words = fragment_norm.split()
            if fragment_words and fragment_words[0] == first_word:
                score = min(100, score + 15)
            
            if score > best_score:
                best_score = score
                best_pos = absolute_pos
                
                # Jeśli znaleziono bardzo dobre dopasowanie, przestań szukać
                if score >= 95:
                    break
            
            pos += 1
        
        if best_score >= threshold:
            return best_pos, best_score
        
        return None, 0
    
    # 🔧 POPRAWIONA FUNKCJA - znajduje najlepsze miejsce na separator
    def find_best_separator_position(text, phrase_position):
        """
        Znajdź najlepsze miejsce na separator PRZED frazą.
        Priorytet: początek akapitu > początek zdania > początek linii > początek słowa
        """
        if phrase_position == 0:
            return 0
        
        # Sprawdź różne pozycje wstecz od phrase_position
        search_back = min(150, phrase_position)
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
            elif char == ' ' and (i >= len(text) or text[i].isalnum()):
                score = 50
            # Początek słowa bez spacji
            elif not char.isalnum() and (i >= len(text) or text[i].isalnum()):
                score = 40
            
            # Preferuj pozycje bliżej frazy
            distance = phrase_position - i
            if distance <= 10:
                score += 20
            elif distance <= 30:
                score += 10
            elif distance <= 50:
                score += 5
            
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
        fraza = ' '.join(slowa[:6])  # zwiększone z 4 do 6 słów
        
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
    def wstaw_entery_z_fuzzy(text, frazy, prog=60):
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
            
            # Znajdź frazę w oryginalnym tekście (z uwzględnieniem offset)
            phrase_pos, score = find_phrase_in_original_text(new_text, fraza, offset, threshold=prog)
            
            if phrase_pos is None:
                print(f"❌ [{idx}] ({plik}) Brak dopasowania >= {prog}% dla: '{fraza}' (najlepsze: {score:.1f}%)")
                nie_znalezione.append((plik, fraza))
                continue
            
            # Znajdź najlepsze miejsce na separator (przed frazą)
            separator_pos = find_best_separator_position(new_text, phrase_pos)
            
            # Wstaw separator
            separator = f"\n\n\n[{idx}] >>>>>>>>>>>>>>>\n\n"
            new_text = new_text[:separator_pos] + separator + new_text[separator_pos:]
            
            # Zaktualizuj offset
            offset = separator_pos + len(separator)
            
            # Wyświetl informację o dopasowaniu
            match_type = "DOKŁADNE" if score == 100.0 else "FUZZY"
            print(f"✅ [{match_type}] [{idx}] ({plik}) '{fraza}' ({score:.1f}%)")
            znalezione.append((plik, fraza, score))
        
        return new_text, znalezione, nie_znalezione
    
    # Wstaw entery
    new_text, znalezione, nie_znalezione = wstaw_entery_z_fuzzy(text, frazy)
    
    # Podsumowanie
    print(f"\n📊 PODSUMOWANIE:")
    print(f"✅ Znalezione dopasowania: {len(znalezione)}")
    for plik, fraza, score in znalezione:
        print(f"   ✅ {plik}: {fraza} ({score:.1f}%)")
    
    if nie_znalezione:
        print(f"❌ Nie znalezione: {len(nie_znalezione)}")
        for plik, fraza in nie_znalezione:
            print(f"   ❌ {plik}: {fraza}")
    
    # Zapisz wynik
    output_path = os.path.join(temp_folder, "z_enterami.txt")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(new_text)
    
    print(f"\n✅ Gotowe! Wynik zapisano do: {output_path}")

if __name__ == "__main__":
    run()