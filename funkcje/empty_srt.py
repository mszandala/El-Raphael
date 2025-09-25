import datetime
from tkinter import Tk, filedialog
import os

def seconds_to_srt_time(sec):
    td = datetime.timedelta(seconds=sec)
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    milliseconds = int((td.total_seconds() - total_seconds) * 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"

def txt_to_srt(txt_file, srt_file):
    with open(txt_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    with open(srt_file, "w", encoding="utf-8") as f:
        for i, line in enumerate(lines, start=1):
            line = line.strip()
            if not line:
                continue
            start, end = map(float, line.split())
            start_time = seconds_to_srt_time(start)
            end_time = seconds_to_srt_time(end)

            f.write(f"{i}\n")
            f.write(f"{start_time} --> {end_time}\n")
            f.write("\n")

def run():
    root = Tk()
    root.withdraw()  # ukryj okno główne

    print("📂 Wybierz plik TXT z czasami:")
    txt_file = filedialog.askopenfilename(filetypes=[("Pliki tekstowe", "*.txt")])
    srt_file = os.path.join(os.path.dirname(__file__), "empty.srt")
    

    if txt_file and srt_file:
        txt_to_srt(txt_file, srt_file)
        print(f"✅ Plik {srt_file} został utworzony.")
    else:
        print("⚠️ Nie wybrano pliku.")
