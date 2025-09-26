import shutil
import os

def run():
    folder = "/content/El-Raphael/temp"
    if os.path.exists(folder):
        input("👉 Naciśnij Enter, aby usunąć folder temp... ")
        shutil.rmtree(folder)
        print(f"✅ Usunięto folder: {folder}")
    else:
        print(f"⚠️ Folder {folder} nie istnieje.")
