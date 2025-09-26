import os
import shutil

# katalog wynikowy w temp
TEMP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "temp"))
mp3_dir = os.path.join(TEMP_DIR, "mp3")
os.makedirs(mp3_dir, exist_ok=True)

def upload_mp3_to_chapter(mp3_files):
    """
    Kopiuje pliki mp3 do TEMP_DIR/mp3.
    Obsługuje Colab (plik jako tuple) i lokalne ścieżki.
    """
    count = 0

    for mp3_file in mp3_files:
        if isinstance(mp3_file, tuple) and len(mp3_file) == 2:
            # Colab: (filename, data)
            filename, data = mp3_file
            dest_path = os.path.join(mp3_dir, filename)
            with open(dest_path, "wb") as f:
                f.write(data)
            count += 1
        else:
            # lokalna ścieżka – kopiujemy tylko do TEMP_DIR/mp3
            # pomijamy oryginał w /content
            if not mp3_file.startswith("/content/"):
                dest_path = os.path.join(mp3_dir, os.path.basename(mp3_file))
                import shutil
                shutil.copy2(mp3_file, dest_path)
                count += 1

    print(f"🎵 Wgrano {count} plików do: {mp3_dir}")


def run():
    mp3_files = []

    # Colab upload
    try:
        from google.colab import files
        print("📂 Wybierz pliki MP3 do wgrania (Colab upload):")
        uploaded = files.upload()
        if uploaded:
            mp3_files = list(uploaded.items())
    except Exception:
        pass

    # lokalny wybór przez tkinter
    if not mp3_files:
        try:
            from tkinter import Tk, filedialog
            root = Tk()
            root.withdraw()
            print("📂 Wybierz pliki MP3 (lokalnie):")
            mp3_files = filedialog.askopenfilenames(filetypes=[("Pliki MP3", "*.mp3")])
        except Exception:
            pass

    if mp3_files:
        upload_mp3_to_chapter(mp3_files)
    else:
        print("⚠️ Nie wybrano plików.")
