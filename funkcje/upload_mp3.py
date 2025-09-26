import os
import shutil

TEMP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "temp"))
os.makedirs(TEMP_DIR, exist_ok=True)

def upload_mp3_to_chapter(mp3_files):
    mp3_dir = os.path.join(TEMP_DIR, "mp3")
    os.makedirs(mp3_dir, exist_ok=True)
    count = 0

    for mp3_file in mp3_files:
        # jeśli pliki pochodzą z Colaba (dictionary z files.upload)
        if isinstance(mp3_file, tuple) and len(mp3_file) == 2:
            filename, data = mp3_file
            dest_path = os.path.join(mp3_dir, filename)
            with open(dest_path, "wb") as f:
                f.write(data)
            count += 1
        else:
            # normalna ścieżka (lokalnie / albo pliki w /content)
            dest_path = os.path.join(mp3_dir, os.path.basename(mp3_file))
            shutil.copy2(mp3_file, dest_path)
            count += 1
            # jeśli plik był w /content, usuń oryginał
            try:
                if mp3_file.startswith("/content/"):
                    os.remove(mp3_file)
            except Exception:
                pass

    print(f"🎵 Wgrano {count} plików do: {mp3_dir}")



def run():
    mp3_files = []

    # Najpierw spróbuj Colaba
    try:
        from google.colab import files
        print("📂 Wybierz pliki MP3 do wgrania (Colab upload):")
        uploaded = files.upload()
        if uploaded:
            mp3_files = list(uploaded.items())  # (filename, data)
    except Exception:
        pass

    # Jeśli nie Colab → spróbuj tkinter
    if not mp3_files:
        try:
            from tkinter import Tk, filedialog
            root = Tk()
            root.withdraw()
            print("📂 Wybierz pliki MP3 do wgrania (lokalnie):")
            mp3_files = filedialog.askopenfilenames(filetypes=[("Pliki MP3", "*.mp3")])
        except Exception as e:
            print("⚠️ Nie udało się otworzyć dialogu plików:", e)
            return

    # folder docelowy
    chapter_folder = os.path.join(os.path.dirname(__file__), "audio")
    os.makedirs(chapter_folder, exist_ok=True)

    if mp3_files:
        upload_mp3_to_chapter(mp3_files)
    else:
        print("⚠️ Nie wybrano plików.")
