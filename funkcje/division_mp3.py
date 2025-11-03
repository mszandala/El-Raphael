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
    
    # 🔧 Znacznie ulepszona funkcja do znajdowania pozycji
    def find_better_position(text, rough_position, search_phrase):
        """Znajdź lepszą pozycję dla separatora - zawsze na początku słowa/zdania"""
        
        # Sprawdź kilka pozycji wokół rough_position
        search_range = 100  # zwiększony zakres
        start = max(0, rough_position - search_range)
        end = min(len(text), rough_position + search_range)
        
        fragment = text[start:end]
        search_phrase_lower = search_phrase.lower().strip()
        
        # Szukaj dokładnej frazy w fragmencie
        phrase_pos = fragment.lower().find(search_phrase_lower)
        if phrase_pos != -1:
            exact_pos = start + phrase_pos
            # Sprawdź czy to początek słowa
            if exact_pos == 0 or not text[exact_pos-1].isalnum():
                return exact_pos
        
        # Jeśli nie ma dokładnej frazy, szukaj pierwszego słowa
        pierwsze_slowo = search_phrase_lower.split()[0] if search_phrase_lower.split() else ""
        if not pierwsze_slowo or len(pierwsze_slowo) < 3:
            return rough_position
        
        # Znajdź wszystkie wystąpienia pierwszego słowa w fragmencie
        word_positions = []
        pos = 0
        while True:
            pos = fragment.lower().find(pierwsze_slowo, pos)
            if pos == -1:
                break
            
            absolute_pos = start + pos
            
            # ✅ KLUCZOWE: Sprawdź czy to POCZĄTEK słowa
            is_word_start = (absolute_pos == 0 or 
                            not text[absolute_pos-1].isalnum() or
                            text[absolute_pos-1] in ' \n\t—.!?')
            
            # ✅ KLUCZOWE: Sprawdź czy to NIE jest środek słowa
            is_not_word_middle = True
            if absolute_pos > 0 and absolute_pos < len(text) - 1:
                prev_char = text[absolute_pos-1]
                next_char = text[absolute_pos + len(pierwsze_slowo)]
                # Jeśli poprzedni i następny znak to litery - to środek słowa
                if prev_char.isalnum() and next_char.isalnum():
                    is_not_word_middle = False
            
            if is_word_start and is_not_word_middle:
                word_positions.append(absolute_pos)
                
            pos += 1
        
        if not word_positions:
            # Jeśli nie znaleziono dobrej pozycji, znajdź najbliższą granicę słowa
            return find_nearest_word_boundary(text, rough_position)
        
        # Znajdź najlepszą pozycję z preferencjami
        best_pos = word_positions[0]
        best_score = -1
        
        for word_pos in word_positions:
            score = 0
            
            # Sprawdź co jest przed pozycją
            if word_pos == 0:
                score += 100  # początek tekstu
            elif word_pos > 0:
                before_char = text[word_pos-1]
                if before_char == '\n' and word_pos > 1 and text[word_pos-2] == '\n':
                    score += 90  # nowy akapit
                elif before_char == '—' or (word_pos > 1 and text[word_pos-2:word_pos] == '— '):
                    score += 80  # początek dialogu
                elif before_char in '.!?':
                    score += 70  # po końcu zdania
                elif before_char == '\n':
                    score += 60  # nowa linia
                elif before_char == ' ':
                    score += 30  # po spacji
            
            # Preferuj pozycje bliższe oryginalnemu rough_position
            distance = abs(word_pos - rough_position)
            if distance <= 20:
                score += 20
            elif distance <= 50:
                score += 10
            
            if score > best_score:
                best_score = score
                best_pos = word_pos
        
        return best_pos
    
    # 🔧 NOWA funkcja pomocnicza
    def find_nearest_word_boundary(text, position):
        """Znajdź najbliższą granicę słowa (początek lub koniec)"""
        
        # Sprawdź czy jesteśmy już na granicy słowa
        if position == 0 or position >= len(text):
            return max(0, min(position, len(text) - 1))
        
        if not text[position-1].isalnum() or not text[position].isalnum():
            return position
        
        # Szukaj w obu kierunkach
        left_boundary = position
        while left_boundary > 0 and text[left_boundary-1].isalnum():
            left_boundary -= 1
        
        right_boundary = position
        while right_boundary < len(text) and text[right_boundary].isalnum():
            right_boundary += 1
        
        # Wybierz bliższą granicę
        if position - left_boundary <= right_boundary - position:
            return left_boundary
        else:
            return right_boundary
    
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
    
    # 🔧 Powrót do poprzedniej wersji z poprawkami
    def wstaw_entery_z_fuzzy(text, frazy, prog=50):
        znalezione, nie_znalezione = [], []
        new_text = text
        przesuniecie = 0

        for idx, item in enumerate(frazy, start=1):
            fraza = item["fraza"].strip()
            plik = item["plik"]
            
            # Najpierw sprawdź dokładne dopasowanie (case-insensitive)
            text_fragment = new_text[przesuniecie:].lower()
            fraza_lower = fraza.lower()
            pos = text_fragment.find(fraza_lower)
            
            if pos != -1:
                rough_position = pos + przesuniecie
                # 🔧 Znajdź lepszą pozycję dla separatora
                better_position = find_better_position(new_text, rough_position, fraza)
                separator = f"\n\n\n[{idx}] >>>>>>>>>>>>>>>\n\n"
                new_text = new_text[:better_position] + separator + new_text[better_position:]
                przesuniecie = better_position + len(separator)
                print(f"✅ [DOKŁADNE] [{idx}] ({plik}) '{fraza}' (100.0%)")
                znalezione.append((plik, fraza, 100.0))
                continue
            
            # Fuzzy matching z lepszą tolerancją błędów
            najlepszy_score = 0
            najlepsza_pozycja = -1
            
            # Podziel tekst na fragmenty po 200 znaków z przesunięciem co 50 znaków
            fragment_size = 200
            step = 50
            pozostaly_tekst = new_text[przesuniecie:]
            
            for i in range(0, len(pozostaly_tekst) - len(fraza) + 1, step):
                fragment = pozostaly_tekst[i:i + fragment_size]
                
                # Normalizuj dla lepszego dopasowania
                fraza_norm = normalize_for_matching(fraza)
                fragment_norm = normalize_for_matching(fragment)
                
                # Sprawdź podobieństwo z frazą
                score = fuzz.partial_ratio(fraza_norm, fragment_norm)
                
                # Dodatkowe sprawdzenie - czy pierwsze słowo się zgadza
                pierwsze_slowo = fraza_norm.split()[0] if fraza_norm.split() else ""
                if pierwsze_slowo and pierwsze_slowo in fragment_norm:
                    score += 20  # bonus za dopasowanie pierwszego słowa
                
                if score > najlepszy_score:
                    najlepszy_score = score
                    rough_pos = przesuniecie + i
                    # 🔧 Znajdź lepszą pozycję dla separatora
                    najlepsza_pozycja = find_better_position(new_text, rough_pos, fraza)
            
            # Sprawdź czy znaleziono wystarczająco dobre dopasowanie
            if najlepszy_score >= prog and najlepsza_pozycja != -1:
                separator = f"\n\n\n[{idx}] >>>>>>>>>>>>>>>\n\n"
                new_text = new_text[:najlepsza_pozycja] + separator + new_text[najlepsza_pozycja:]
                przesuniecie = najlepsza_pozycja + len(separator)
                print(f"✅ [FUZZY] [{idx}] ({plik}) '{fraza}' ({najlepszy_score:.1f}%)")
                znalezione.append((plik, fraza, najlepszy_score))
            else:
                print(f"❌ [{idx}] ({plik}) Brak dopasowania >= {prog}% dla: '{fraza}' (najlepsze: {najlepszy_score:.1f}%)")
                nie_znalezione.append((plik, fraza))

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