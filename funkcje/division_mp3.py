import os
import re
from pydub import AudioSegment
import whisper
from fuzzywuzzy import fuzz
from fuzzywuzzy import process

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
    def przytnij_do_poczatku(file_path, sekundy=10):  # zwiększone z 5 do 10 sekund
        audio = AudioSegment.from_file(file_path)
        return audio[:sekundy * 1000]
    
    # Analizuj każdy plik MP3
    frazy = []
    for i, mp3_file in enumerate(mp3_files, 1):
        mp3_path = os.path.join(mp3_folder, mp3_file)
        print(f"🎧 [{i}] Przetwarzam początek nagrania: {mp3_file}")
        
        # Przytnij do pierwszych 10 sekund
        audio_segment = przytnij_do_poczatku(mp3_path)
        
        # Zapisz tymczasowo przycięty fragment
        temp_audio_path = os.path.join(temp_folder, "temp_audio.wav")
        audio_segment.export(temp_audio_path, format="wav")
        
        # Transkrypcja z Whisper
        result = model.transcribe(temp_audio_path, language="pl")
        fraza = result["text"].strip()
        
        print(f"🔎 [{i}] Znalezione pierwsze słowa: {fraza}")
        
        frazy.append({
            "plik": mp3_file,
            "fraza": fraza
        })
        
        # Usuń tymczasowy plik
        if os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)
    
    print(f"\n📋 Podsumowanie transkrypcji: znaleziono {len(frazy)} fraz z {len(mp3_files)} plików")
    
    # Funkcja do wstawiania enterów z fuzzy matching
    def wstaw_entery_z_fuzzy(text, frazy, prog=75):  # zwiększony próg z 50 do 75
        znalezione, nie_znalezione = [], []
        new_text = text
        przesuniecie = 0

        for idx, item in enumerate(frazy, start=1):
            fraza = item["fraza"].strip()
            plik = item["plik"]
            
            # Normalizacja dla lepszego dopasowania
            fraza_norm = ' '.join(fraza.lower().split())
            
            # Szukaj w fragmentach tekstu
            pozostaly_tekst = new_text[przesuniecie:].lower()
            najlepsza_pozycja = -1
            najlepszy_score = 0
            
            # Przeszukuj tekst fragment po fragmencie
            for i in range(0, len(pozostaly_tekst) - len(fraza_norm), 10):
                fragment = pozostaly_tekst[i:i + len(fraza_norm) + 50]
                score = fuzz.partial_ratio(fraza_norm, fragment)
                
                if score > najlepszy_score:
                    najlepszy_score = score
                    najlepsza_pozycja = i + przesuniecie

            if najlepszy_score >= prog:
                # TYLKO WSTAW SEPARATOR - nie zmieniaj tekstu!
                separator = f"\n\n\n[{idx}] >>>>>>>>>>>>>>>\n\n"
                new_text = new_text[:najlepsza_pozycja] + separator + new_text[najlepsza_pozycja:]
                przesuniecie = najlepsza_pozycja + len(separator)
                
                znalezione.append((plik, fraza, najlepszy_score))
                print(f"✅ [{idx}] ({plik}) Separator wstawiony ({najlepszy_score:.1f}%)")
            else:
                nie_znalezione.append((plik, fraza))
                print(f"❌ [{idx}] ({plik}) Brak dopasowania >= {prog}% dla: '{fraza}' (najlepsze: {najlepszy_score:.1f}%)")

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