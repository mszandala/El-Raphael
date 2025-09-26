import re
import os

def get_chapter(input_file, chapter_number):
    """Wyciąga jeden rozdział z pliku TXT i zapisuje do pliku w katalogu programu."""
    with open(input_file, "r", encoding="utf-8") as f:
        text = f.read()

    # Podział na rozdziały wg nagłówków
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
        return output_path
    else:
        print(f"⚠️ Brak rozdziału nr {chapter_number}. Dostępnych: {len(parsed)}")
        return None


def run(chapter_number=None):
    """Uruchamia moduł w trybie interaktywnym (dla Colaba lub lokalnie)."""
    input_file = "/content/El-Raphael/w-pustyni-i-w-puszczy.txt"
    if not os.path.exists(input_file):
        print(f"⚠️ Nie znaleziono pliku: {input_file}")
        return

    if chapter_number is None:
        try:
            chapter_number = int(input("📖 Podaj numer rozdziału do wycięcia: ").strip())
        except ValueError:
            print("⚠️ Musisz wpisać liczbę!")
            return

    return get_chapter(input_file, chapter_number)
