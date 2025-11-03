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
    
    # ✅ POPRAWIONE ŚCIEŻKI
    temp_folder = "temp"  # Folder z plikiem rozdziału
    mp3_folder = os.path.join(temp_folder, "mp3")  # Podfolder temp/mp3/ z MP3
    
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
    
    # ✅ Sortowanie numeryczne (wewnątrz funkcji run())
    def extract_number(filename):
        match = re.search(r'(\d+)', filename)
        return int(match.group(1)) if match else 0
    
    mp3_files.sort(key=extract_number)
    
    print(f"🎵 Znaleziono {len(mp3_files)} plików MP3 w {mp3_folder}")
    print()
    
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
    
    # ✅ POPRAWIONA funkcja - używa regex do dokładnego mapowania
    def find_first_word_position_in_window(window, first_word_norm):
        """
        Znajduje pozycję pierwszego słowa z DOKŁADNYM mapowaniem.
        Nie polega na liczeniu słów, tylko na regex match.
        """
        # Znajdź wszystkie słowa z ich pozycjami w ORYGINALNYM oknie
        word_pattern = re.compile(r'\b\w+\b')
        
        for match in word_pattern.finditer(window):
            word = match.group()
            # Normalizuj TYLKO to jedno słowo do porównania
            word_normalized = normalize_for_matching(word)
            
            if word_normalized == first_word_norm:
                return match.start()  # ✅ Dokładna pozycja w oryginalnym tekście
        
        return None
    
    # 🔧 ULEPSZONA FUNKCJA - sliding window z fuzzy matching
    def find_phrase_with_sliding_window(original_text, search_phrase, start_offset=0, threshold=50):
        """
        Znajduje frazę używając sliding window i fuzzy matching.
        Zwraca ((pos_start, pos_end), score) lub ((None, None), 0).
        """
        if not search_phrase or len(search_phrase) < 3:
            return (None, None), 0

        phrase_norm = normalize_for_matching(search_phrase)
        phrase_words = phrase_norm.split()

        if not phrase_words:
            return (None, None), 0

        window_size = max(30, len(search_phrase) * 3)
        step_size = 20

        best_pos_start = None
        best_pos_end = None
        best_score = 0

        search_text = original_text[start_offset:]
        max_start = max(0, len(search_text) - window_size)
        i = 0
        
        while i <= max_start:
            window = search_text[i:i + window_size]
            window_norm = normalize_for_matching(window)
            score = fuzz.partial_ratio(phrase_norm, window_norm)

            if phrase_words and phrase_words[0] in window_norm.split():
                score = min(100, score + 10)

            if score > best_score:
                best_score = score
                first_word_pos = find_first_word_position_in_window(window, phrase_words[0]) if phrase_words else None
                
                if first_word_pos is not None:
                    best_pos_start = start_offset + i + first_word_pos
                    # ✅ Szacuj koniec dopasowania
                    best_pos_end = best_pos_start + len(search_phrase)
                else:
                    best_pos_start = start_offset + i
                    best_pos_end = best_pos_start + len(search_phrase)

                if score >= 95:
                    break

            i += step_size

        # Sprawdź ostatnie okno
        if len(search_text) > 0 and i < len(search_text):
            window = search_text[-window_size:]
            window_norm = normalize_for_matching(window)
            score = fuzz.partial_ratio(phrase_norm, window_norm)
            if phrase_words and phrase_words[0] in window_norm.split():
                score = min(100, score + 10)
            if score > best_score:
                best_score = score
                last_window_start = start_offset + max(0, len(search_text) - window_size)
                first_word_pos = find_first_word_position_in_window(window, phrase_words[0]) if phrase_words else None
                if first_word_pos is not None:
                    best_pos_start = last_window_start + first_word_pos
                    best_pos_end = best_pos_start + len(search_phrase)
                else:
                    best_pos_start = last_window_start
                    best_pos_end = best_pos_start + len(search_phrase)

        if best_score >= threshold:
            return (best_pos_start, best_pos_end), best_score

        return (None, None), best_score
    
    # 🆕 FUNKCJA: Znajdź najlepsze miejsce na separator MIĘDZY dwoma pozycjami
    def find_best_separator_between(text, pos_end_prev, pos_start_next):
        """
        Znajdź najlepsze miejsce na separator MIĘDZY końcem poprzedniego fragmentu a początkiem następnego.
        Priorytet: myślnik dialogu > akapit > koniec zdania > początek linii
        """
        if pos_end_prev >= pos_start_next:
            # Błąd - pozycje się pokrywają
            return pos_end_prev
        
        best_pos = pos_end_prev
        best_score = 0
        
        # Szukaj w zakresie między końcem poprzedniego a początkiem następnego
        for i in range(pos_end_prev, pos_start_next):
            score = 0
            
            char = text[i] if i < len(text) else ''
            prev_char = text[i-1] if i > 0 else ''
            next_chars = text[i:i+2] if i+1 < len(text) else text[i:]
            
            # Myślnik dialogu z enterem
            if next_chars.startswith('— ') and prev_char == '\n':
                score = 150
            # Myślnik dialogu bez entera
            elif next_chars.startswith('— '):
                score = 140
            # Nowy akapit (dwa entery)
            elif char == '\n' and i > 0 and text[i-1] == '\n':
                score = 100
            # Po końcu zdania z enterem
            elif char == '\n' and i > 0 and text[i-1] in '.!?':
                score = 85
            # Po końcu zdania
            elif prev_char in '.!?' and char in ' \n\t':
                score = 80
            # Początek linii
            elif prev_char == '\n':
                score = 70
            # Po spacji
            elif prev_char == ' ' and char.isalnum():
                score = 50
            
            # Preferuj środek zakresu
            distance_from_middle = abs((pos_end_prev + pos_start_next) / 2 - i)
            max_distance = (pos_start_next - pos_end_prev) / 2
            if max_distance > 0:
                proximity_bonus = int(20 * (1 - distance_from_middle / max_distance))
                score += proximity_bonus
            
            if score > best_score:
                best_score = score
                best_pos = i
                
                if score >= 140:  # Znaleziono myślnik
                    break
        
        return best_pos
    
    # 🆕 TRANSKRYPCJA: Transkrybuj CAŁY plik (początek + koniec)
    frazy = []
    for i, mp3_file in enumerate(mp3_files, 1):
        mp3_path = os.path.join(mp3_folder, mp3_file)
        print(f"🎧 [{i}] Przetwarzam nagranie: {mp3_file}")
        
        # ✅ TRANSKRYBUJ CAŁY PLIK z obsługą błędów
        print(f"   🔹 Transkrybuję CAŁY plik...")
        try:
            result = model.transcribe(mp3_path, language="pl")
            pelna_transkrypcja = result["text"].strip()
        except Exception as e:
            print(f"      ❌ Błąd transkrypcji: {e}")
            print(f"      ⚠️  Pomijam plik")
            print()
            continue
        
        slowa = pelna_transkrypcja.split()
        
        # Pierwsze 8 słów
        fraza_start = ' '.join(slowa[:min(8, len(slowa))])
        
        # Ostatnie 8 słów
        fraza_end = ' '.join(slowa[-min(8, len(slowa)):]) if len(slowa) >= 8 else pelna_transkrypcja
        
        print(f"      💬 Pełna transkrypcja ({len(slowa)} słów): {pelna_transkrypcja[:100]}...")
        print(f"      🎯 START (pierwsze 8): {fraza_start}")
        print(f"      🎯 END (ostatnie 8): {fraza_end}")
        
        # Walidacja
        if len(slowa) < 3:
            print(f"      ⚠️  Transkrypcja zbyt krótka - pomijam plik")
            print()
            continue
        
        if not fraza_start or not fraza_end:
            print(f"      ⚠️  Puste frazy - pomijam plik")
            print()
            continue
        
        frazy.append({
            "plik": mp3_file,
            "fraza_start": fraza_start,
            "fraza_end": fraza_end
        })
        
        print()
    
    print(f"📋 Podsumowanie: przetworzone {len(frazy)} plików (pełna transkrypcja)\n")
    
    # 🆕 FUNKCJA wstawiania enterów z PODWÓJNĄ WERYFIKACJĄ
    def wstaw_entery_z_podwojna_weryfikacja(text, frazy, prog=50):
        """
        Wstawia separatory używając PODWÓJNEJ WERYFIKACJI:
        - Koniec fragmentu [i] musi pasować do początku fragmentu [i+1]
        - Separator wstawiany jest MIĘDZY nimi
        """
        print(f"{'='*80}")
        print(f"🔍 ETAP 1: Wyszukiwanie fraz POCZĄTKOWYCH...")
        print(f"{'='*80}\n")

        pozycje_start = []  # Lista: (pos_start, idx, plik, fraza_start, score)
        pozycje_end = []    # Lista: (pos_end, pos_end_end, idx, plik, fraza_end, score)
        
        last_pos = 0
        
        # KROK 1: Znajdź wszystkie pozycje START
        for idx, item in enumerate(frazy, start=1):
            fraza_start = item["fraza_start"].strip()
            plik = item["plik"]
            
            print(f"🔍 [{idx}] START: '{fraza_start[:50]}...'")
            
            (pos_start, pos_start_end), score = find_phrase_with_sliding_window(text, fraza_start, last_pos, threshold=prog)
            
            if pos_start is None:
                print(f"❌ [{idx}] Nie znaleziono początku (score={score:.1f}%)")
                continue
            
            if pos_start < last_pos:
                print(f"⚠️  [{idx}] Pozycja wstecz! Pomijam.")
                continue
            
            pozycje_start.append((pos_start, idx, plik, fraza_start, score))
            last_pos = pos_start
            print(f"✅ [{idx}] START znaleziony na pozycji {pos_start} (score={score:.1f}%)")
        
        # KROK 2: Znajdź wszystkie pozycje END
        print(f"\n{'='*80}")
        print(f"🔍 ETAP 2: Wyszukiwanie fraz KOŃCOWYCH...")
        print(f"{'='*80}\n")
        
        for idx, item in enumerate(frazy, start=1):
            fraza_end = item["fraza_end"].strip()
            plik = item["plik"]
            
            # ✅ Użyj None zamiast 0
            search_from = None
            for pos_start, idx_start, _, _, _ in pozycje_start:
                if idx_start == idx:
                    search_from = pos_start
                    break
            
            if search_from is None:
                print(f"⚠️  [{idx}] Brak pozycji START - pomijam END")
                continue
            
            print(f"🔍 [{idx}] END: '{fraza_end[:50]}...' (szukam od {search_from})")
            
            (pos_end, pos_end_end), score = find_phrase_with_sliding_window(text, fraza_end, search_from, threshold=prog)
            
            if pos_end is None:
                print(f"❌ [{idx}] Nie znaleziono końca (score={score:.1f}%)")
                continue
            
            # ✅ Zapisz KONIEC dopasowania
            pozycje_end.append((pos_end, pos_end_end, idx, plik, fraza_end, score))
            print(f"✅ [{idx}] END znaleziony na pozycji {pos_end}-{pos_end_end} (score={score:.1f}%)")
        
        # KROK 3: WERYFIKACJA i wstawianie separatorów
        print(f"\n{'='*80}")
        print(f"🔍 ETAP 3: WERYFIKACJA i wyznaczanie pozycji separatorów...")
        print(f"{'='*80}\n")
        
        separatory = []  # Lista: (separator_pos, idx, plik)
        znalezione = []
        nie_znalezione = []
        
        for i in range(len(pozycje_start)):
            pos_start_i, idx_i, plik_i, fraza_start_i, score_start_i = pozycje_start[i]
            
            # Znajdź koniec tego samego fragmentu
            pos_end_i = None
            pos_end_end_i = None
            for pos_end, pos_end_end, idx_end, _, _, score_end in pozycje_end:
                if idx_end == idx_i:
                    pos_end_i = pos_end
                    pos_end_end_i = pos_end_end
                    break
            
            if pos_end_i is None:
                print(f"⚠️  [{idx_i}] Brak END - pomijam")
                nie_znalezione.append((plik_i, fraza_start_i, score_start_i))
                continue
            
            # Sprawdź czy jest następny fragment
            if i + 1 < len(pozycje_start):
                pos_start_next, idx_next, plik_next, fraza_start_next, score_start_next = pozycje_start[i + 1]
                
                # ✅ WERYFIKACJA: Koniec frazy [i] < Początek [i+1]?
                if pos_end_end_i < pos_start_next:
                    separator_pos = find_best_separator_between(text, pos_end_end_i, pos_start_next)
                    
                    separatory.append((separator_pos, idx_i, plik_i))
                    znalezione.append((plik_i, fraza_start_i, score_start_i))
                    
                    context = text[separator_pos:separator_pos+50].replace('\n', '↵')
                    print(f"✅ [{idx_i}] WERYFIKACJA OK:")
                    print(f"   END[{idx_i}] na {pos_end_i}-{pos_end_end_i} < START[{idx_next}] na {pos_start_next}")
                    print(f"   📍 Separator na {separator_pos}: '{context}...'")
                else:
                    print(f"❌ [{idx_i}] WERYFIKACJA FAILED:")
                    print(f"   END[{idx_i}] na {pos_end_i}-{pos_end_end_i} >= START[{idx_next}] na {pos_start_next}")
                    print(f"   Fragment {idx_i} kończy się PO początku fragmentu {idx_next}!")
                    nie_znalezione.append((plik_i, fraza_start_i, score_start_i))
            else:
                # Ostatni fragment - nie ma weryfikacji
                znalezione.append((plik_i, fraza_start_i, score_start_i))
                print(f"ℹ️  [{idx_i}] Ostatni fragment - brak weryfikacji")
        
        # KROK 4: Wstaw separatory (od końca do początku)
        print(f"\n{'='*80}")
        print(f"✏️  ETAP 4: Wstawianie separatorów...")
        print(f"{'='*80}\n")
        
        separatory.sort(reverse=True, key=lambda x: x[0])
        
        new_text = text
        for separator_pos, idx, plik in separatory:
            separator = f"\n\n\n[{idx}] >>>>>>>>>>>>>>>\n\n"
            new_text = new_text[:separator_pos] + separator + new_text[separator_pos:]
            print(f"✏️  Wstawiono separator [{idx}] na pozycji {separator_pos}")
        
        return new_text, znalezione, nie_znalezione
    
    # Wstaw entery z podwójną weryfikacją
    new_text, znalezione, nie_znalezione = wstaw_entery_z_podwojna_weryfikacja(text, frazy)
    
    # Podsumowanie
    print(f"\n{'='*80}")
    print(f"📊 PODSUMOWANIE:")
    print(f"✅ Znalezione i zweryfikowane: {len(znalezione)}/{len(frazy)} ({len(znalezione)*100//len(frazy) if len(frazy) > 0 else 0}%)")
    
    if znalezione:
        print(f"\n✅ ZNALEZIONE ({len(znalezione)}):")
        for plik, fraza, score in znalezione:
            icon = "🎯" if score >= 90 else "✅"
            print(f"   {icon} {plik}: {fraza[:60]}... ({score:.1f}%)")
    
    if nie_znalezione:
        print(f"\n❌ NIE ZNALEZIONE LUB NIEZWERYFIKOWANE ({len(nie_znalezione)}):")
        for plik, fraza, score in nie_znalezione:
            print(f"   ❌ {plik}: {fraza[:60]}... ({score:.1f}%)")
    
    # Zapisz wynik
    output_path = os.path.join(temp_folder, "z_enterami.txt")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(new_text)
    
    print(f"\n✅ Gotowe! Wynik zapisano do: {output_path}")
    print(f"{'='*80}")

if __name__ == "__main__":
    run()