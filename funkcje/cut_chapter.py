import re
import os

TEMP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "temp"))
os.makedirs(TEMP_DIR, exist_ok=True)


def parse_chapters_with_titles(text):
    """
    Wyszukuje rozdziały w formacie:
    ROZDZIAŁ I
    Tytuł rozdziału
    """
    pattern = r"(ROZDZIAŁ\s+[IVXLCDM]+)\s*\n([^\n]+)"
    chapters = []
    for m in re.finditer(pattern, text):
        header = m.group(1).strip()
        title = m.group(2).strip()
        start = m.start()
        chapters.append({"header": header, "title": title, "start": start})
    # dodaj koniec każdego rozdziału
    for i in range(len(chapters)):
        chapters[i]["end"] = chapters[i+1]["start"] if i+1 < len(chapters) else len(text)
    return chapters


def parse_subchapters(text):
    """
    Wyszukuje podrozdziały w rozdziale: linia z rzymską liczbą i tytuł w następnej linii.
    """
    pattern = r"\n([IVXLCDM]+)\s*\n([^\n]+)"
    subs = []
    for m in re.finditer(pattern, text):
        roman = m.group(1).strip()
        title = m.group(2).strip()
        start = m.start()
        subs.append({"roman": roman, "title": title, "start": start})
    for i in range(len(subs)):
        subs[i]["end"] = subs[i+1]["start"] if i+1 < len(subs) else len(text)
    return subs


def save_content(title, content):
    """Zapisuje fragment tekstu do pliku w katalogu temp"""
    file_name = title.replace(" ", "_") + ".txt"
    output_path = os.path.join(TEMP_DIR, file_name)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"✅ Zapisano: {output_path}")
    return output_path


def run(chapter_number=None):
    """Uruchamia moduł w trybie interaktywnym."""

    print("📚 Wybierz książkę:")
    print("1 – W pustyni i w puszczy")
    print("2 – O krasnoludkach i sierotce Marysi")
    choice = input("👉 Podaj numer [1/2]: ").strip()

    if choice == "1":
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

        # prosty split jak wcześniej
        with open(input_file, "r", encoding="utf-8") as f:
            text = f.read()

        chapters = re.split(r'(ROZDZIAŁ [IVXLCDM]+)', text)
        parsed = []
        for i in range(1, len(chapters), 2):
            title = chapters[i].strip()
            content = chapters[i] + "\n" + chapters[i+1]
            parsed.append((title, content))

        if 1 <= chapter_number <= len(parsed):
            title, content = parsed[chapter_number - 1]
            return save_content(title, content)
        else:
            print(f"⚠️ Brak rozdziału nr {chapter_number}. Dostępnych: {len(parsed)}")
            return None

    elif choice == "2":
        input_file = "/content/El-Raphael/o-krasnoludkach-i-sierotce-marysi.txt"

        if not os.path.exists(input_file):
            print(f"⚠️ Nie znaleziono pliku: {input_file}")
            return

        with open(input_file, "r", encoding="utf-8") as f:
            text = f.read()

        chapters = parse_chapters_with_titles(text)
        if not chapters:
            print("⚠️ Nie znaleziono rozdziałów w pliku.")
            return

        print("\n📖 Lista rozdziałów:")
        for i, ch in enumerate(chapters, start=1):
            print(f"  {i}. {ch['header']} – {ch['title']}")

        try:
            nr = int(input("\n👉 Wybierz numer rozdziału: ").strip())
            if not (1 <= nr <= len(chapters)):
                raise ValueError
        except ValueError:
            print("⚠️ Niepoprawny numer.")
            return

        chosen = chapters[nr-1]
        chap_text = text[chosen["start"]:chosen["end"]]

        subs = parse_subchapters(chap_text)
        if subs:
            print(f"\n🔹 Ten rozdział ma {len(subs)} podrozdział(ów):")
            for i, s in enumerate(subs, start=1):
                print(f"  {i}. {s['roman']} – {s['title']}")
            wybor = input("\n👉 Wybierz numer podrozdziału (ENTER = cały rozdział): ").strip()
            if wybor:
                try:
                    idx = int(wybor)
                    if 1 <= idx <= len(subs):
                        sel = subs[idx-1]
                        fragment = chap_text[sel["start"]:sel["end"]]
                        return save_content(f"{chosen['header']}_{sel['roman']}", fragment)
                except ValueError:
                    print("⚠️ Zły numer, zapisuję cały rozdział.")
        return save_content(chosen["header"], chap_text)

    else:
        print("⚠️ Niepoprawny wybór.")
        return
