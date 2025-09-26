import re
import os

empty_srt = "/content/El-Raphael/temp/empty.srt"
txt_file = "/content/El-Raphael/temp/z_enterami.txt"
output_dir = "/content/El-Raphael/"


def run():
    # Wczytaj pusty plik SRT
    with open(empty_srt, "r", encoding="utf-8") as f:
        srt_lines = f.read().strip().split("\n\n")

    # Wczytaj teksty z pliku txt
    with open(txt_file, "r", encoding="utf-8") as f:
        txt_content = f.read()

    # Podziel na bloki wg [n] >>>>>>>>
    blocks = re.split(r"\[\d+\]\s*>{5,}", txt_content)
    blocks = [b.strip() for b in blocks if b.strip()]

    # Ustal nazwę pliku wynikowego na podstawie pierwszego bloku
    chapter_match = re.search(r"(ROZDZIAŁ_\w+)", txt_content)
    if chapter_match:
        output_filename = chapter_match.group(1) + ".srt"
    else:
        output_filename = "output.srt"

    output_path = os.path.join(output_dir, output_filename)

    # Łączenie pustego SRT z tekstami
    final_srt = []
    for i, srt_block in enumerate(srt_lines):
        if i < len(blocks):
            text = blocks[i]
        else:
            text = ""
        final_srt.append(srt_block.strip() + "\n" + text)

    # Zapisz wynik
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(final_srt))

    print("✅ Zapisano plik:", output_path)
