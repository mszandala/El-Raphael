import re
import os

def get_chapter(input_file, chapter_number):
    """Wyciąga jeden rozdział z pliku TXT i zapisuje do pliku w katalogu programu."""
    with open(input_file, "r", encoding="utf-8") as f:
        text = f.read()

    # Podział na rozdziały: ['', 'ROZDZIAŁ I', 'treść...', 'ROZDZIAŁ II', 'treść...']
    chapters = re.split(r'(ROZDZIAŁ [IVXLCDM]+)', text)

    parsed = []
    for i in range(1, len(chapters), 2):
        title = chapters[i].strip()
        content = chapters[i] + "\n" + chapters[i+1]
        parsed.append((title, content))

    if 1 <= chapter_number <= len(parsed):
        title, content = parsed[chapter_number - 1]
        file_name = title.replace(" ", "_") + ".txt"
        output_path = os.path.join(os.getcwd(), file_name)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"✅ Zapisano rozdział {chapter_number}: {output_path}")
    else:
        print(f"⚠️ Brak rozdziału nr {chapter_number}. Dostępnych: {len(parsed)}")


def run():
    """Uruchamia moduł w trybie interaktywnym (dla main.py)."""
    input_file = "w-pustyni-i-w-puszczy.txt"
    if not os.path.exists(input_file):
        print("⚠️ Nie znaleziono pliku!")
        return

    try:
        chapter_number = int(input("📖 Podaj numer rozdziału do wycięcia: ").strip())
    except ValueError:
        print("⚠️ Musisz wpisać liczbę!")
        return

    get_chapter(input_file, chapter_number)
