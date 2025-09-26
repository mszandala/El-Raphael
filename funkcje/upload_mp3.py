import os
import shutil

def upload_mp3_to_chapter(mp3_files, chapter_folder):
    """
    Kopiuje pliki mp3 do podfolderu 'mp3' w chapter_folder.
    """
    mp3_dir = os.path.join(chapter_folder, "mp3")
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
            # normalna ścieżka (lokalnie)
            shutil.copy2(mp3_file, mp3_dir)
            count += 1

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
        upload_mp3_to_chapter(mp3_files, chapter_folder)
    else:
        print("⚠️ Nie wybrano plików.")
