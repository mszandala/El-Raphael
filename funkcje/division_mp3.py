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
    def przytnij_do_poczatku(file_path, sekundy=8):  # zwiększone z 5 do 8 sekund
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
    
    # Funkcja do znajdowania początku słowa
    def find_word_start(text, rough_position):
        """Znajdź początek słowa w pobliżu pozycji"""
        if rough_position == 0 or not text[rough_position-1].isalnum():
            return rough_position
            
        pos = rough_position
        while pos > 0 and text[pos-1].isalnum():
            pos -= 1
            
        return pos
    
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
    
    # Funkcja do wstawiania enterów z fuzzy matching
    def wstaw_entery_z_fuzzy(text, frazy, prog=50):
        znalezione, nie_znalezione = [], []
        new_text = text
        przesuniecie = 0

        # 🔧 Funkcja do znajdowania początku zdania/wypowiedzi
        def find_sentence_start(text, rough_position):
            """Znajdź początek zdania w pobliżu pozycji"""
            # Sprawdź czy jesteśmy już na początku zdania
            if rough_position == 0:
                return 0
                
            # Szukaj wstecz znaczników początku zdania
            pos = rough_position
            while pos > 0:
                char = text[pos-1]
                # Znaki oznaczające koniec poprzedniego zdania
                if char in '.!?':
                    # Przejdź przez spacje i nowe linie
                    while pos < len(text) and text[pos] in ' \n\t':
                        pos += 1
                    return pos
                # Myślnik na początku linii (dialog)
                elif char == '\n' and pos < len(text) and text[pos] == '—':
                    return pos
                # Początek nowego akapitu
                elif char == '\n' and pos > 1 and text[pos-2] == '\n':
                    return pos
                pos -= 1
                
            return max(0, rough_position)

        for idx, item in enumerate(frazy, start=1):
            fraza = item["fraza"].strip()
            plik = item["plik"]
            
            # 🔧 Ulepszone dokładne dopasowanie - szukaj na początku zdań
            text_fragment = new_text[przesuniecie:].lower()
            fraza_lower = fraza.lower()
            
            # Szukaj wszystkich wystąpień frazy
            search_pos = 0
            found_exact = False
            
            while True:
                pos = text_fragment.find(fraza_lower, search_pos)
                if pos == -1:
                    break
                    
                # Sprawdź czy to jest na początku zdania
                real_pos = pos + przesuniecie
                sentence_start = find_sentence_start(new_text, real_pos)
                
                # Sprawdź czy fraza zaczyna się w pobliżu początku zdania (tolerancja 10 znaków)
                if abs(real_pos - sentence_start) <= 10:
                    separator = f"\n\n\n[{idx}] >>>>>>>>>>>>>>>\n\n"
                    new_text = new_text[:sentence_start] + separator + new_text[sentence_start:]
                    przesuniecie = sentence_start + len(separator)
                    print(f"✅ [DOKŁADNE] [{idx}] ({plik}) '{fraza}' (100.0%)")
                    znalezione.append((plik, fraza, 100.0))
                    found_exact = True
                    break
                    
                search_pos = pos + 1
            
            if found_exact:
                continue
            
            # 🔧 Fuzzy matching - szukaj na początku zdań/akapitów
            najlepszy_score = 0
            najlepsza_pozycja = -1
            
            # Znajdź wszystkie początki zdań w pozostałym tekście
            pozostaly_tekst = new_text[przesuniecie:]
            sentence_starts = []
            
            # Dodaj pozycję 0 (początek tekstu)
            sentence_starts.append(0)
            
            # Znajdź wszystkie początki zdań
            for i in range(len(pozostaly_tekst)):
                char = pozostaly_tekst[i]
                if i > 0:
                    prev_char = pozostaly_tekst[i-1]
                    # Koniec zdania + nowe zdanie
                    if prev_char in '.!?' and char not in ' \n\t':
                        sentence_starts.append(i)
                    # Myślnik na początku linii (dialog)
                    elif prev_char == '\n' and char == '—':
                        sentence_starts.append(i)
                    # Nowy akapit
                    elif i > 1 and pozostaly_tekst[i-2:i] == '\n\n' and char not in ' \n\t':
                        sentence_starts.append(i)
            
            # Sprawdź każdy początek zdania
            for start_pos in sentence_starts:
                if start_pos + 200 <= len(pozostaly_tekst):
                    fragment = pozostaly_tekst[start_pos:start_pos + 200]
                else:
                    fragment = pozostaly_tekst[start_pos:]
                    
                if len(fragment) < len(fraza):
                    continue
                
                # Normalizuj dla lepszego dopasowania
                fraza_norm = normalize_for_matching(fraza)
                fragment_norm = normalize_for_matching(fragment)
                
                # Sprawdź podobieństwo z początkiem fragmentu
                score = fuzz.partial_ratio(fraza_norm, fragment_norm[:len(fraza_norm)*2])
                
                # Bonus za dopasowanie pierwszego słowa
                pierwsze_slowo = fraza_norm.split()[0] if fraza_norm.split() else ""
                if pierwsze_slowo and fragment_norm.startswith(pierwsze_slowo):
                    score += 30  # zwiększony bonus
                
                if score > najlepszy_score:
                    najlepszy_score = score
                    najlepsza_pozycja = przesuniecie + start_pos
            
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