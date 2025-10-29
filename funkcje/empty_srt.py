# funkcje/empty_srt.py
"""
Kompatybilne z Colab i lokalnie:
 - jeśli działa google.colab.files -> poprosi o upload pliku .txt (Colab)
 - jeśli dostępny GUI (tkinter + DISPLAY) -> użyje filedialog
 - w przeciwnym razie wypisze znalezione .txt w repo i poprosi o wybór
Generuje empty.srt w tym samym katalogu co ten moduł.
"""

import os
import glob
import re

TEMP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "temp"))
os.makedirs(TEMP_DIR, exist_ok=True)

def seconds_to_srt_time(sec):
    """
    Przyjmuje liczbę sekund (float), zwraca 'HH:MM:SS,mmm'
    Bardziej stabilna niż używanie timedelta dla float.
    """
    try:
        total_ms = int(round(float(sec) * 1000))
    except Exception:
        total_ms = 0
    hours = total_ms // 3_600_000
    minutes = (total_ms % 3_600_000) // 60_000
    seconds = (total_ms % 60_000) // 1000
    milliseconds = total_ms % 1000
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"

def txt_to_srt(txt_file, srt_file):
    with open(txt_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    with open(srt_file, "w", encoding="utf-8") as f:
        idx = 1
        for raw in lines:
            line = raw.strip()
            if not line:
                continue
            # spróbuj znaleźć dwie liczby (start, end) w linii
            tokens = line.split()
            floats = []
            float_indices = []
            for i, t in enumerate(tokens):
                try:
                    floats.append(float(t.replace(',', '.')))
                    float_indices.append(i)
                except Exception:
                    pass
                if len(floats) == 2:
                    break
            if len(floats) < 2:
                # jeśli nie ma dwóch liczb, pomiń (możesz zmienić zachowanie)
                print(f"⚠️ Pomijam linię (nie znaleziono 2 liczb): {line}")
                continue
            start, end = floats
            # Nie pomijamy etykiet ani opisu — każda linia posiadająca dwie liczby
            # (start i end) będzie zapisana jako pusty wpis SRT. Tekst po liczbach
            # jest ignorowany przy tworzeniu napisu.
            # sanity check: end >= start
            if end < start:
                print(f"⚠️ Uwaga: end < start w linii: {line} — przełączam miejscami.")
                start, end = end, start

            start_time = seconds_to_srt_time(start)
            end_time = seconds_to_srt_time(end)

            f.write(f"{idx}\n")
            f.write(f"{start_time} --> {end_time}\n")
            f.write("\n")
            idx += 1

def _choose_txt_file():
    """
    Próbuje w kolejności:
     1) Colab upload (google.colab.files.upload)
     2) tkinter filedialog (jeśli dostępny i DISPLAY jest ustawiony)
     3) lista plików .txt w repo (użytkownik wybiera indeks)
     4) poprosi o ręczne wklejenie ścieżki
    Zwraca absolutną ścieżkę lub None.
    """
    # 1) Colab
    try:
        from google.colab import files
        print("📎 Środowisko Colab wykryte — proszę wybrać/ przesłać plik .txt")
        uploaded = files.upload()
        if uploaded:
            name = next(iter(uploaded.keys()))
            path = os.path.abspath(name)
            print(f"📥 Odebrano plik: {path}")
            return path
    except Exception:
        # nie Colab lub upload nie powiódł się
        pass

    # 2) tkinter (GUI)
    try:
        # sprawdź czy DISPLAY jest ustawione (headless -> brak)
        if os.environ.get("DISPLAY"):
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            print("📂 Wybierz plik TXT z czasami (okno dialogowe)...")
            fn = filedialog.askopenfilename(filetypes=[("Pliki tekstowe", "*.txt")])
            root.destroy()
            if fn:
                return os.path.abspath(fn)
        else:
            # brak DISPLAY -> prawdopodobnie Colab / server
            pass
    except Exception:
        pass

    # 3) lista plików .txt w repo (rekursywnie)
    candidates = sorted(glob.glob("**/*.txt", recursive=True))
    if candidates:
        print("Znalezione pliki .txt:")
        for i, c in enumerate(candidates):
            print(f"{i}: {c}")
        try:
            choice = input("Wprowadź numer pliku który chcesz użyć (lub naciśnij Enter by wpisać ścieżkę): ").strip()
            if choice != "":
                idx = int(choice)
                if 0 <= idx < len(candidates):
                    return os.path.abspath(candidates[idx])
        except Exception:
            pass

    # 4) fallback - ręczna ścieżka
    path = input("Podaj ścieżkę do pliku .txt (lub Enter aby anulować): ").strip()
    if path:
        return os.path.abspath(path)

    return None


def run():
    txt_file = _choose_txt_file()
    srt_file = os.path.join(TEMP_DIR, "empty.srt")

    if txt_file:
        try:
            txt_to_srt(txt_file, srt_file)
            print(f"✅ Plik {srt_file} został utworzony.")

            # jeśli plik pochodzi z Colaba (/content), usuń go
            if txt_file.startswith("/content/"):
                try:
                    os.remove(txt_file)
                    print(f"🗑️ Tymczasowy plik źródłowy usunięty: {txt_file}")
                except Exception as e:
                    print(f"⚠️ Nie udało się usunąć tymczasowego pliku: {e}")

        except Exception as e:
            print("❌ Wystąpił błąd podczas tworzenia SRT:", e)
    else:
        print("⚠️ Nie wybrano pliku. Anulowano.")

