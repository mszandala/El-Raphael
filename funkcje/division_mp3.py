import os
import re
import whisper
from pydub import AudioSegment
from rapidfuzz import fuzz, process


# Ścieżki bazowe
BASE_DIR = "/content/El-Raphael/temp"
SRT_FILE = os.path.join(BASE_DIR, "empty.srt")  # obecnie nieużywany, ale dostępny
MP3_DIR = os.path.join(BASE_DIR, "mp3")

def znajdz_plik_rozdzialu(base_dir):
    """Znajduje plik txt z ROZDZIAŁ_ w nazwie w folderze base_dir"""
    for f in os.listdir(base_dir):
        if f.endswith(".txt") and "ROZDZIAŁ_" in f.upper():
            return os.path.join(base_dir, f)
    raise FileNotFoundError(f"❌ Nie znaleziono pliku z rozdziałem w {base_dir}")

def run():
    TXT_FILE = znajdz_plik_rozdzialu(BASE_DIR)
    print(f"📄 Znaleziono plik rozdziału: {TXT_FILE}")

    # 🔹 1. Ładowanie modelu Whisper
    print("⏳ Ładowanie modelu Whisper...")
    model = whisper.load_model("small")  # small/base/medium/large

    # 🔹 2. Wczytanie tekstu
    with open(TXT_FILE, "r", encoding="utf-8") as f:
        text = f.read()

    # 🔹 3. Przygotowanie listy plików MP3
    mp3_files = sorted(
        [os.path.join(MP3_DIR, f) for f in os.listdir(MP3_DIR) if f.endswith(".mp3")]
    )
    print(f"🎵 Znaleziono {len(mp3_files)} plików MP3 w {MP3_DIR}")

    frazy = []  # [{"plik": "plik1.mp3", "fraza": "tekst"}]

    # 🔧 Funkcja przycinająca audio do pierwszych X sekund
    def przytnij_do_poczatku(file_path, sekundy=5):
        audio = AudioSegment.from_file(file_path)
        return audio[:sekundy * 1000]  # milisekundy

    # 🔹 4. Transkrypcja tylko początku plików MP3
    for idx, mp3 in enumerate(mp3_files, start=1):
        nazwa = os.path.basename(mp3)
        print(f"\n🎧 [{idx}] Przetwarzam początek nagrania: {nazwa}")
        
        try:
            temp_file = os.path.join(BASE_DIR, f"cut_{idx}_{nazwa}")
            
            # Przetnij audio i zapisz
            przytnij_do_poczatku(mp3, 8).export(temp_file, format="mp3")

            # Transkrypcja
            result = model.transcribe(
                temp_file,
                fp16=False,
                language="pl",
                temperature=0,
                condition_on_previous_text=False
            )

            words = result["text"].strip().split()
            pierwsze_slowa = " ".join(words[:7]) if len(words) >= 7 else " ".join(words)

            if pierwsze_slowa:
                print(f"🔎 [{idx}] Znalezione pierwsze słowa: {pierwsze_slowa}")
                frazy.append({"plik": nazwa, "fraza": pierwsze_slowa})
            else:
                print(f"⚠️ [{idx}] Nie udało się rozpoznać początku nagrania.")
            
            # Usuń tymczasowy plik
            if os.path.exists(temp_file):
                os.remove(temp_file)
                
        except Exception as e:
            print(f"❌ [{idx}] Błąd przy przetwarzaniu {nazwa}: {e}")
            continue

    print(f"\n📋 Podsumowanie transkrypcji: znaleziono {len(frazy)} fraz z {len(mp3_files)} plików")

    # 🔧 Funkcja wstawiająca entery z fuzzy matching
    def wstaw_entery_z_fuzzy(text, frazy, prog=50):
        znalezione, nie_znalezione = [], []
        new_text = text
        przesuniecie = 0

        for idx, item in enumerate(frazy, start=1):
            fraza = item["fraza"]
            plik = item["plik"]

            # Podziel tekst na zdania
            zdania = re.split(r'(?<=[\.\!\?])\s+', new_text[przesuniecie:])
            
            if not zdania:
                print(f"❌ [{idx}] ({plik}) Brak zdań do przeszukania")
                nie_znalezione.append((plik, fraza))
                continue

            # Znajdź najlepsze dopasowanie
            match = process.extractOne(fraza, zdania, scorer=fuzz.partial_ratio)

            if match and match[1] >= prog:
                najlepsze_dopasowanie = match[0]
                pos = new_text.find(najlepsze_dopasowanie, przesuniecie)

                if pos != -1:
                    numer = f"\n\n\n[{idx}] >>>>>>>>>>>>>>>\n\n"
                    new_text = new_text[:pos] + numer + new_text[pos:]
                    przesuniecie = pos + len(numer) + len(najlepsze_dopasowanie)
                    print(f"✅ [{idx}] ({plik}) Separator przed: '{najlepsze_dopasowanie[:40]}...' ({match[1]:.1f}%)")
                    znalezione.append((plik, fraza, match[1]))
                else:
                    print(f"❌ [{idx}] ({plik}) Nie znaleziono pozycji dla: '{fraza}'")
                    nie_znalezione.append((plik, fraza))
            else:
                score = match[1] if match else 0
                print(f"❌ [{idx}] ({plik}) Brak dopasowania >= {prog}% dla frazy: '{fraza}' (najlepsze: {score:.1f}%)")
                nie_znalezione.append((plik, fraza))

        # Podsumowanie
        print("\n📊 PODSUMOWANIE:")
        print(f"✅ Znalezione dopasowania: {len(znalezione)}")
        for plik, fraza, score in znalezione:
            print(f"   ✅ {plik}: {fraza} ({score:.1f}%)")
        
        print(f"❌ Nie znalezione: {len(nie_znalezione)}")
        for plik, fraza in nie_znalezione:
            print(f"   ❌ {plik}: {fraza}")

        return new_text

    # 🔧 Funkcja poprawiająca myślniki
    def popraw_myslniki(tekst):
        tekst = re.sub(r'([^\n])\n—', r'\1\n\n—', tekst)
        tekst = re.sub(r'—\s*\n\n+', '— ', tekst)
        return tekst

    # 🔹 5. Wstawianie separatorów + poprawa myślników
    if frazy:
        text = wstaw_entery_z_fuzzy(text, frazy, prog=50)
        text = popraw_myslniki(text)
    else:
        print("⚠️ Brak fraz do dopasowania!")

    # 🔹 6. Zapis wyniku
    OUTPUT_FILE = os.path.join(BASE_DIR, "z_enterami.txt")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(text)

    print(f"\n✅ Gotowe! Wynik zapisano do: {OUTPUT_FILE}")
