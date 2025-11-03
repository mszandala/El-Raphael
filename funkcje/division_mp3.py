import os
import re
from pydub import AudioSegment
import whisper

# Użyj rapidfuzz zamiast fuzzywuzzy
try:
    from rapidfuzz import fuzz, process
except ImportError:
    print("📦 Instaluję rapidfuzz...")
    os.system("pip install rapidfuzz")
    from rapidfuzz import fuzz, process 

def run():
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
    def przytnij_do_poczatku(file_path, sekundy=5):
        audio = AudioSegment.from_file(file_path)
        return audio[:sekundy * 1000]
    
    # Analizuj każdy plik MP3
    frazy = []
    for i, mp3_file in enumerate(mp3_files, 1):
        mp3_path = os.path.join(mp3_folder, mp3_file)
        print(f"🎧 [{i}] Przetwarzam początek nagrania: {mp3_file}")
        
        # Przytnij do pierwszych 5 sekund
        audio_segment = przytnij_do_poczatku(mp3_path, 5)
        
        # Zapisz tymczasowo przycięty fragment
        temp_audio_path = os.path.join(temp_folder, "temp_audio.wav")
        audio_segment.export(temp_audio_path, format="wav")
        
        # Transkrypcja z Whisper
        result = model.transcribe(temp_audio_path, language="pl")
        fraza_pelna = result["text"].strip()
        
        # Weź tylko pierwsze 4 słowa
        slowa = fraza_pelna.split()
        fraza = ' '.join(slowa[:4])  # tylko pierwsze 4 słowa
        
        print(f"🔎 [{i}] Znalezione pierwsze słowa: {fraza}")
        
        frazy.append({
            "plik": mp3_file,
            "fraza": fraza
        })
        
        # Usuń tymczasowy plik
        if os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)
    
    print(f"\n📋 Podsumowanie transkrypcji: znaleziono {len(frazy)} fraz z {len(mp3_files)} plików")
    
    # Funkcja pomocnicza do znajdowania rzeczywistej pozycji
    def find_real_position(original_text, norm_pos):
        # Uproszczona wersja - po prostu zwróć przybliżoną pozycję
        return min(norm_pos, len(original_text) - 1)
    
    # Funkcja do wstawiania enterów z fuzzy matching
    def wstaw_entery_z_fuzzy(text, frazy, prog=65):
        znalezione, nie_znalezione = [], []
        new_text = text
        przesuniecie = 0

        # Funkcja normalizacji tekstu
        def normalize_text(txt):
            # Usuń znaki interpunkcyjne, zmień na małe litery, usuń wielokrotne spacje
            txt = re.sub(r'[^\w\s]', ' ', txt.lower())
            txt = re.sub(r'\s+', ' ', txt.strip())
            return txt

        # 🔧 NOWA funkcja do znajdowania początku słowa
        def find_word_start(text, rough_position):
            """Znajdź początek słowa w pobliżu pozycji"""
            # Sprawdź czy jesteśmy na początku słowa
            if rough_position == 0 or not text[rough_position-1].isalnum():
                return rough_position
                
            # Cofnij się do początku słowa
            pos = rough_position
            while pos > 0 and text[pos-1].isalnum():
                pos -= 1
                
            return pos

        for idx, item in enumerate(frazy, start=1):
            fraza = item["fraza"].strip()
            plik = item["plik"]
            
            # Normalizuj frazę
            fraza_norm = normalize_text(fraza)
            
            # Najpierw sprawdź dokładne dopasowanie
            text_fragment = new_text[przesuniecie:].lower()
            pos = text_fragment.find(fraza.lower())
            if pos != -1:
                pozycja = pos + przesuniecie
                # 🔧 Znajdź początek słowa
                pozycja = find_word_start(new_text, pozycja)
                separator = f"\n\n\n[{idx}] >>>>>>>>>>>>>>>\n\n"
                new_text = new_text[:pozycja] + separator + new_text[pozycja:]
                przesuniecie = pozycja + len(separator)
                print(f"✅ [DOKŁADNE] [{idx}] ({plik}) Separator wstawiony na pozycji {pozycja}")
                znalezione.append((plik, fraza, 100.0))
                continue
            
            # 🔧 NOWA METODA: Szukaj w całym tekście po fragmentach
            pozostaly_tekst = new_text[przesuniecie:]
            text_norm = normalize_text(pozostaly_tekst)
            
            najlepszy_score = 0
            najlepsza_pozycja = -1
            
            # Przeszukuj cały tekst fragmentami po 150 znaków z przesunięciem co 30 znaków
            fragment_size = 150
            step = 30
            
            for i in range(0, len(text_norm) - len(fraza_norm) + 1, step):
                fragment = text_norm[i:i + fragment_size]
                if len(fragment) < len(fraza_norm):
                    break
                    
                score = fuzz.partial_ratio(fraza_norm, fragment)
                
                if score > najlepszy_score:
                    najlepszy_score = score
                    # Znajdź pozycję pierwszego słowa frazy w fragmencie
                    pierwsze_slowo = fraza_norm.split()[0] if fraza_norm.split() else ""
                    if pierwsze_slowo and pierwsze_slowo in fragment:
                        # Pozycja pierwszego słowa w znormalizowanym fragmencie
                        word_pos_in_fragment = fragment.find(pierwsze_slowo)
                        # Przybliżona pozycja w znormalizowanym tekście
                        approx_pos = i + word_pos_in_fragment
                        # Konwertuj na pozycję w oryginalnym tekście
                        real_pos = find_real_position_in_text(pozostaly_tekst, text_norm, approx_pos)
                        # 🔧 Znajdź początek słowa w oryginalnym tekście
                        word_start = find_word_start(pozostaly_tekst, real_pos)
                        najlepsza_pozycja = przesuniecie + word_start

            # Jeśli nie znaleziono dobrego dopasowania, sprawdź jeszcze akapity (backup)
            if najlepszy_score < prog:
                akapity = pozostaly_tekst.split('\n\n')
                current_pos = przesuniecie
                
                for akapit in akapity:
                    if len(akapit.strip()) > 0:
                        akapit_norm = normalize_text(akapit[:150])
                        score = fuzz.partial_ratio(fraza_norm, akapit_norm)
                        
                        if score > najlepszy_score:
                            najlepszy_score = score
                            najlepsza_pozycja = current_pos
                
                current_pos += len(akapit) + 2

        if najlepszy_score >= prog and najlepsza_pozycja != -1:
            separator = f"\n\n\n[{idx}] >>>>>>>>>>>>>>>\n\n"
            new_text = new_text[:najlepsza_pozycja] + separator + new_text[najlepsza_pozycja:]
            przesuniecie = najlepsza_pozycja + len(separator)
            print(f"✅ [FUZZY] [{idx}] ({plik}) Separator wstawiony ({najlepszy_score:.1f}%)")
            znalezione.append((plik, fraza, najlepszy_score))
        else:
            nie_znalezione.append((plik, fraza))
            print(f"❌ [{idx}] ({plik}) Brak dopasowania >= {prog}% dla: '{fraza}' (najlepsze: {najlepszy_score:.1f}%)")

        return new_text, znalezione, nie_znalezione

    # 🔧 NOWA funkcja pomocnicza
    def find_real_position_in_text(original_text, normalized_text, norm_position):
        """Konwertuje pozycję w znormalizowanym tekście na pozycję w oryginalnym tekście"""
        chars_counted = 0
        norm_chars_counted = 0
        
        for i, char in enumerate(original_text):
            # Sprawdź czy to "liczący się" znak w znormalizowanym tekście
            if char.isalnum() or char.isspace():
                if norm_chars_counted >= norm_position:
                    return i
                if not (char.isspace() and (i == 0 or original_text[i-1].isspace())):
                    norm_chars_counted += 1
        
        return min(norm_position, len(original_text) - 1)

    
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