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
    def wstaw_entery_z_fuzzy(text, frazy, prog=50):  # zmniejszony próg z 65 na 50
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
                pozycja = pos + przesuniecie
                # Znajdź początek słowa
                pozycja = find_word_start(new_text, pozycja)
                separator = f"\n\n\n[{idx}] >>>>>>>>>>>>>>>\n\n"
                new_text = new_text[:pozycja] + separator + new_text[pozycja:]
                przesuniecie = pozycja + len(separator)
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
                    # Znajdź pozycję pierwszego słowa w oryginalnym fragmencie
                    word_pos = fragment.lower().find(fraza.lower().split()[0]) if fraza.lower().split() else 0
                    if word_pos == -1:
                        word_pos = 0
                    pozycja = przesuniecie + i + word_pos
                    najlepsza_pozycja = find_word_start(new_text, pozycja)
            
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