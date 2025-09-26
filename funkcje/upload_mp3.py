import os
import shutil

BASE_DIR = "/content/El-Raphael"
mp3_dir = os.path.join(BASE_DIR, "temp", "mp3")
os.makedirs(mp3_dir, exist_ok=True)

def upload_mp3_to_chapter(mp3_files):
    """
    Zapisuje pliki do BASE_DIR/temp/mp3.
    Dla lokalnych ścieżek: kopiuje i (jeśli pochodzi z BASE_DIR) usuwa oryginał.
    Dla upload z Colab (tuple filename, bytes): zapisuje do mp3_dir.
    """
    count = 0
    for mp3_file in mp3_files:
        if isinstance(mp3_file, tuple) and len(mp3_file) == 2:
            filename, data = mp3_file
            dest_path = os.path.join(mp3_dir, filename)
            with open(dest_path, "wb") as f:
                f.write(data)
            count += 1
        else:
            # lokalna ścieżka
            src = mp3_file
            dest_path = os.path.join(mp3_dir, os.path.basename(src))
            shutil.copy2(src, dest_path)
            count += 1

            # jeśli plik pochodził z BASE_DIR, usuń oryginał żeby nie było kopii
            try:
                if os.path.commonpath([os.path.abspath(src), os.path.abspath(BASE_DIR)]) == os.path.abspath(BASE_DIR):
                    os.remove(src)
            except Exception:
                # commonpath może rzucić, więc ignorujemy błędy usuwania
                pass

    print(f"🎵 Wgrano {count} plików do: {mp3_dir}")


def run():
    mp3_files = []
    uploaded = None

    # Colab upload - zmieniamy cwd na /tmp żeby Colab nie zapisywał uploadów w /content/El-Raphael
    try:
        from google.colab import files
        print("📂 Wybierz pliki MP3 do wgrania (Colab upload):")

        orig_cwd = os.getcwd()
        upload_cwd = "/tmp"
        os.makedirs(upload_cwd, exist_ok=True)
        os.chdir(upload_cwd)            # teraz files.upload() zapisze pliki w /tmp
        uploaded = files.upload()       # uploaded: dict filename -> bytes
        os.chdir(orig_cwd)              # przywracamy cwd

        if uploaded:
            mp3_files = list(uploaded.items())  # (filename, bytes)
    except Exception:
        pass

    # lokalny wybór przez tkinter (jeśli nie uploadowano przez Colab)
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

        # po zapisaniu do mp3_dir - usuń automatyczne kopie które Colab zapisał w /tmp
        if uploaded:
            for fname in uploaded.keys():
                tmp_path = os.path.join("/tmp", fname)
                try:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
                except Exception:
                    pass
    else:
        print("⚠️ Nie wybrano plików.")
