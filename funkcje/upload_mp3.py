import os
import shutil
from tkinter import Tk, filedialog

def upload_mp3_to_chapter(mp3_files, chapter_folder):
    """
    Kopiuje pliki mp3 do podfolderu 'mp3' w chapter_folder.
    """
    mp3_dir = os.path.join(chapter_folder, "mp3")
    os.makedirs(mp3_dir, exist_ok=True)
    count = 0

    for mp3_file in mp3_files:
        shutil.copy2(mp3_file, mp3_dir)
        count += 1


    print(f"🎵 Wgrano {count} plików do: {mp3_dir}")

def run():
    root = Tk()
    root.withdraw()  # ukryj okno główne

    # wybór plików
    print("📂 Wybierz pliki MP3 do wgrania:")
    mp3_files = filedialog.askopenfilenames(filetypes=[("Pliki MP3", "*.mp3")])

    # statyczny folder docelowy 'audio' w folderze programu
    chapter_folder = os.path.join(os.path.dirname(__file__), "audio")
    os.makedirs(chapter_folder, exist_ok=True)

    if mp3_files and chapter_folder:
        upload_mp3_to_chapter(mp3_files, chapter_folder)
    else:
        print("⚠️ Nie wybrano plików lub folderu.")
