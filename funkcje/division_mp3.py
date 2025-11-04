import os
import re
from pydub import AudioSegment
from fuzzywuzzy import fuzz

def podziel_na_fragmenty_z_enterami(plik_mp3, text_file, output_folder="fragmenty", prog=50):
    """
    Funkcja dzieli plik MP3 na fragmenty zgodnie z enterami w pliku tekstowym.
    
    Args:
        plik_mp3 (str): Ścieżka do głównego pliku MP3
        text_file (str): Ścieżka do pliku tekstowego z enterami
        output_folder (str): Folder docelowy dla fragmentów
        prog (int): Próg dopasowania (0-100)
    """
    # Wczytaj tekst
    with open(text_file, 'r', encoding='utf-8') as f:
        text = f.read()
    
    # Pobierz frazy bezpośrednio z plików MP3
    frazy = pobierz_frazy_z_mp3(text_file)
    
    # Wstaw entery z podwójną weryfikacją
    fragmenty = wstaw_entery_z_podwojna_weryfikacja(text, frazy, prog, text_file)
    
    # Ładuj plik MP3 - jeśli jest przekazany
    if plik_mp3 and os.path.exists(plik_mp3):
        audio = AudioSegment.from_mp3(plik_mp3)
    else:
        audio = None
    
    # Utwórz folder wyjściowy
    os.makedirs(output_folder, exist_ok=True)
    
    # Wytnij i zapisz fragmenty
    utworz_fragmenty_mp3(audio, fragmenty, output_folder)
    
    return fragmenty


def normalize_for_matching(text):
    """
    ✅ ULEPSZONA normalizacja - bardziej agresywna
    """
    text = text.lower()
    
    # Usuń myślniki
    text = text.replace('—', ' ').replace('–', ' ').replace('-', ' ')
    
    # Usuń wszystkie znaki interpunkcyjne (zachowaj polskie znaki)
    text = re.sub(r'[^\w\sąćęłńóśźżĄĆĘŁŃÓŚŹŻ]', ' ', text)
    
    # Normalizuj wielokrotne spacje
    text = re.sub(r'\s+', ' ', text).strip()
    
    # ✅ ROZSZERZONE zamienniki - dodaj typowe błędy Whisper
    replacements = {
        # Błędy Whisper dla nazwisk
        'roli są': 'rawlison',
        'rolison': 'rawlison',
        'rolyson': 'rawlison',
        'panorolicon': 'pan rawlison',
        'panrolyson': 'pan rawlison',
        'kupantarkowski': 'pan tarkowski',
        
        # Błędy nazw miejsc
        'lfhn': 'el fachen',
        'elfhn': 'el fachen',
        'medinet': 'medinet',
        'medinę': 'medinet',
        'medinu': 'medinet',
        'elwasta': 'el wasta',
        'el wasta': 'el wasta',
        'elgarak': 'el gharak',
        'el garak': 'el gharak',
        'gara k': 'el gharak',
        
        # Błędy imion
        'nel': 'nel',
        'nell': 'nel',
        'staś': 'stas',
        'stać': 'stas',
        'ustasia': 'stasia',
        
        # Błędy słów arabskich
        'chami': 'chamis',
        'hamis': 'chamis',
        'hamiz': 'chamis',
        'idr': 'idrys',
        'idry': 'idrys',
        'gebr': 'gebhr',
        'geber': 'gebhr',
        
        # Czasowniki
        'odpowiedział': 'powiedzial',
        'rzekł': 'powiedzial',
        'rzecze': 'powiedzial',
        'ozwał się': 'powiedzial',
        'odparł': 'powiedzial',
        
        # Inne częste formy
        'więc': 'wiec',
        'cóż': 'coz',
        'jakże': 'jakze',
        'żeby': 'zeby',
        'gdyż': 'gdyz',
    }
    
    for wrong, correct in replacements.items():
        text = text.replace(wrong, correct)
        
    return text


def find_phrase_with_sliding_window(original_text, search_phrase, start_offset=0, threshold=40):
    """
    ✅ PRZEPISANA funkcja - lepsze dopasowanie + szukanie granic słów
    """
    if not search_phrase or len(search_phrase) < 3:
        return (None, None), 0

    phrase_norm = normalize_for_matching(search_phrase)
    phrase_words = phrase_norm.split()
    
    if len(phrase_words) == 0:
        return (None, None), 0

    search_text = original_text[start_offset:]
    search_norm = normalize_for_matching(search_text)
    
    if len(search_norm) == 0:
        return (None, None), 0
    
    # ✅ Zwiększ okno dla lepszego dopasowania
    window_size = max(len(search_phrase) * 5, 500)
    step_size = 10  # Mniejszy krok = dokładniejsze szukanie
    
    best_score = 0
    best_pos = None
    
    # ✅ Szukaj po znormalizowanym tekście
    i = 0
    max_start = len(search_norm) - len(phrase_norm)
    
    while i <= max_start:
        window = search_norm[i:i + window_size]
        
        # Użyj różnych metod dopasowania
        score_partial = fuzz.partial_ratio(phrase_norm, window)
        score_token = fuzz.token_set_ratio(phrase_norm, window)
        
        # Średnia ważona
        score = score_partial * 0.7 + score_token * 0.3
        
        # Bonus za dokładne dopasowanie początku
        if window.startswith(phrase_words[0]):
            score += 10
        
        if score > best_score:
            best_score = score
            best_pos = i
        
        i += step_size
    
    if best_score < threshold:
        return (None, None), best_score
    
    # ✅ Znajdź rzeczywistą pozycję w oryginalnym tekście
    # Musimy przeliczyć pozycję ze znormalizowanego na oryginalny tekst
    real_pos = map_normalized_to_original(search_text, search_norm, best_pos)
    
    if real_pos is None:
        return (None, None), best_score
    
    # ✅ Znajdź granicę słowa (początek zdania/akapitu)
    real_start = start_offset + real_pos
    
    # Szukaj początku zdania (wielka litera po kropce/enterze)
    for j in range(max(0, real_start - 100), real_start + 50):
        if j >= len(original_text):
            break
        
        # Sprawdź czy to początek akapitu
        if j == 0 or (j > 0 and original_text[j-1] == '\n'):
            if original_text[j].isupper() or original_text[j] in '—"':
                real_start = j
                break
        
        # Sprawdź czy to początek zdania
        if j > 0 and original_text[j-1] in '.!?' and original_text[j] == ' ':
            if j+1 < len(original_text) and original_text[j+1].isupper():
                real_start = j + 1
                break
    
    # Oszacuj długość na podstawie transkrypcji
    estimated_length = len(search_phrase) * 2  # Mnożnik bezpieczny
    real_end = min(len(original_text), real_start + estimated_length)
    
    return (real_start, real_end), best_score


def map_normalized_to_original(original_text, normalized_text, norm_pos):
    """
    ✅ NOWA FUNKCJA: Mapuje pozycję ze znormalizowanego tekstu na oryginalny
    """
    if norm_pos >= len(normalized_text):
        return None
    
    # Znajdź fragment znormalizowanego tekstu wokół pozycji
    search_window = normalized_text[max(0, norm_pos-10):norm_pos+50]
    
    # Znormalizuj oryginalny tekst fragmentami i porównaj
    best_match_pos = None
    best_match_score = 0
    
    for i in range(len(original_text) - len(search_window)):
        fragment = original_text[i:i+len(search_window)]
        fragment_norm = normalize_for_matching(fragment)
        
        score = fuzz.ratio(search_window, fragment_norm)
        
        if score > best_match_score:
            best_match_score = score
            best_match_pos = i
    
    return best_match_pos


def pobierz_frazy_z_mp3(text_file):
    """
    Skanuje folder temp/mp3 i transkrybuje pliki przez Whisper
    """
    import whisper
    
    base_dir = os.path.dirname(text_file)
    mp3_folder = os.path.join(base_dir, "mp3")
    
    if not os.path.exists(mp3_folder):
        print(f"❌ Folder z plikami MP3 nie istnieje: {mp3_folder}")
        return []
    
    frazy = []
    pliki_mp3 = sorted([f for f in os.listdir(mp3_folder) if f.endswith('.mp3')])
    
    print(f"📂 Znaleziono {len(pliki_mp3)} plików MP3")
    print(f"🎤 Ładuję model Whisper...")
    
    model = whisper.load_model("base")
    
    for idx, plik in enumerate(pliki_mp3):
        sciezka = os.path.join(mp3_folder, plik)
        
        try:
            print(f"🎵 [{idx+1}/{len(pliki_mp3)}] Transkrybuję: {plik}")
            
            result = model.transcribe(sciezka, language="pl")
            transkrypcja = result["text"].strip()
            
            if not transkrypcja:
                print(f"   ⚠️  Pusta transkrypcja - POMIJAM")
                continue
            
            audio = AudioSegment.from_mp3(sciezka)
            dlugosc_ms = len(audio)
            
            print(f"   ✅ \"{transkrypcja[:60]}...\"")
            
            frazy.append({
                'plik': plik,
                'transkrypcja': transkrypcja,
                'start_ms': 0,
                'end_ms': dlugosc_ms
            })
            
        except Exception as e:
            print(f"   ❌ Błąd podczas transkrypcji {plik}: {e}")
    
    print(f"✅ Zatranskrybowano {len(frazy)} plików")
    return frazy


def wstaw_entery_z_podwojna_weryfikacja(text, frazy, prog=40, text_file=None):
    """
    ✅ PRZEPISANA funkcja - lepsza logika dzielenia
    """
    fragmenty = []
    last_search_pos = 0
    
    print(f"\n{'='*80}")
    print(f"🔍 ROZPOCZYNAM WYSZUKIWANIE FRAZ")
    print(f"📊 Długość tekstu: {len(text)} znaków")
    print(f"📊 Liczba fragmentów MP3: {len(frazy)}")
    print(f"{'='*80}\n")
    
    if not frazy:
        print("⚠️  BRAK FRAZ DO WYSZUKANIA")
        return fragmenty
    
    pozycje_separatorow = []
    
    for idx, item in enumerate(frazy):
        plik = item['plik']
        transkrypcja = item['transkrypcja']
        
        # Pomiń zbyt krótkie transkrypcje
        if len(transkrypcja.split()) < 3:
            print(f"⚠️  [{idx+1}] {plik} - za krótka transkrypcja, pomijam")
            fragmenty.append({
                'found': False,
                'plik': plik,
                'reason': 'za_krotka_transkrypcja'
            })
            continue
        
        print(f"🔍 [{idx+1}/{len(frazy)}] {plik}")
        print(f"   📝 \"{transkrypcja[:80]}...\"")
        
        # ✅ Szukaj CAŁEJ transkrypcji (nie tylko początku/końca)
        (pos_start, pos_end), score = find_phrase_with_sliding_window(
            text, transkrypcja, last_search_pos, threshold=35
        )
        
        if pos_start is None:
            print(f"   ❌ Nie znaleziono (score: {score:.1f})")
            
            # ✅ Spróbuj z pierwszymi 10 słowami
            shorter = ' '.join(transkrypcja.split()[:10])
            print(f"   🔄 Próbuję z początkiem (10 słów)...")
            (pos_start, pos_end), score = find_phrase_with_sliding_window(
                text, shorter, last_search_pos, threshold=30
            )
            
            if pos_start is None:
                print(f"   ❌ Nie znaleziono (score: {score:.1f})")
                fragmenty.append({
                    'found': False,
                    'plik': plik,
                    'reason': 'nie_znaleziono'
                })
                continue
        
        # ✅ Znaleziono fragment
        context = text[max(0, pos_start-30):pos_start+80].replace('\n', '↵')
        print(f"   ✅ Znaleziono na pozycji {pos_start} (score: {score:.1f})")
        print(f"      Kontekst: \"{context[:70]}...\"")
        
        # ✅ Znajdź koniec fragmentu (następny akapit lub szacowana długość)
        estimated_length = len(transkrypcja) * 3
        search_end = min(len(text), pos_start + estimated_length)
        
        # Szukaj końca akapitu
        next_para = text.find('\n\n', pos_start + 50, search_end)
        if next_para != -1:
            pos_end = next_para
        else:
            pos_end = search_end
        
        # Zapisz separator
        pozycje_separatorow.append({
            'numer': idx + 1,
            'pozycja': pos_start,
            'plik': plik
        })
        
        fragmenty.append({
            'found': True,
            'plik': plik,
            'pos_start': pos_start,
            'pos_end': pos_end,
            'score': score,
            'text': text[pos_start:pos_end],
            'start_ms': item['start_ms'],
            'end_ms': item['end_ms']
        })
        
        last_search_pos = pos_end
        print()
    
    # Wstaw separatory
    if pozycje_separatorow and text_file:
        print(f"\n{'='*80}")
        print(f"📝 WSTAWIAM SEPARATORY W TEKŚCIE")
        print(f"{'='*80}\n")
        
        pozycje_separatorow.sort(key=lambda x: x['pozycja'], reverse=True)
        
        tekst_z_separatorami = text
        for sep in pozycje_separatorow:
            separator = f"\n\n[{sep['numer']:02d}] >>>>>>>>>>>>\n\n"
            tekst_z_separatorami = (
                tekst_z_separatorami[:sep['pozycja']] + 
                separator + 
                tekst_z_separatorami[sep['pozycja']:]
            )
            print(f"✅ Wstawiono separator [{sep['numer']:02d}] na pozycji {sep['pozycja']}")
        
        output_text_file = text_file.replace('.txt', '_z_enterami.txt')
        with open(output_text_file, 'w', encoding='utf-8') as f:
            f.write(tekst_z_separatorami)
        print(f"\n💾 Zapisano tekst z separatorami: {output_text_file}")
    
    # Podsumowanie
    znalezione = sum(1 for f in fragmenty if f.get('found', False))
    
    if len(fragmenty) > 0:
        procent = znalezione / len(fragmenty) * 100
        print(f"\n{'='*80}")
        print(f"📊 PODSUMOWANIE: Znaleziono {znalezione}/{len(fragmenty)} fragmentów ({procent:.1f}%)")
        print(f"{'='*80}\n")
    
    return fragmenty


def utworz_fragmenty_mp3(audio, fragmenty, output_folder):
    """
    Kopiuje pliki MP3 zamiast wycinać z jednego dużego
    """
    print(f"\n{'='*80}")
    print(f"✂️  KOPIUJĘ FRAGMENTY MP3")
    print(f"{'='*80}\n")
    
    utworzone = 0
    
    for idx, fragment in enumerate(fragmenty):
        if not fragment.get('found', False):
            print(f"⏭️  [{idx+1}] Pomijam {fragment['plik']} - nie znaleziono w tekście")
            continue
        
        base_dir = os.path.dirname(output_folder)
        mp3_source = os.path.join(base_dir, "mp3", fragment['plik'])
        
        if not os.path.exists(mp3_source):
            print(f"   ❌ Nie znaleziono pliku źródłowego: {mp3_source}")
            continue
        
        output_path = os.path.join(output_folder, fragment['plik'])
        
        import shutil
        shutil.copy2(mp3_source, output_path)
        
        utworzone += 1
        dlugosc = (fragment['end_ms'] - fragment['start_ms']) / 1000
        print(f"✅ [{idx+1}] Skopiowano: {fragment['plik']} ({dlugosc:.1f}s)")
    
    print(f"\n{'='*80}")
    print(f"📊 Skopiowano {utworzone} fragmentów MP3")
    print(f"{'='*80}\n")
    
    return utworzone


def run():
    """
    Główna funkcja uruchamiająca proces podziału MP3 na fragmenty
    """
    import os
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    temp_folder = os.path.join(base_dir, "temp")
    
    # Szukaj pliku tekstowego
    text_files = []
    for f in os.listdir(temp_folder):
        if f.endswith('.txt'):
            match = re.match(r'ROZDZIA[ŁL]_([IVXLCDM0-9]+)\.txt', f, re.IGNORECASE)
            if match:
                text_files.append(f)
    
    if not text_files:
        print(f"❌ Brak plików tekstowych w folderze: {temp_folder}")
        return
    
    text_file = os.path.join(temp_folder, text_files[0])
    print(f"📄 Plik tekstowy: {text_file}")
    
    # Sprawdź folder z MP3
    mp3_folder = os.path.join(temp_folder, "mp3")
    if not os.path.exists(mp3_folder):
        print(f"❌ Folder z plikami MP3 nie istnieje: {mp3_folder}")
        return
    
    pliki_mp3 = [f for f in os.listdir(mp3_folder) if f.endswith('.mp3')]
    if not pliki_mp3:
        print(f"❌ Brak plików MP3 w folderze: {mp3_folder}")
        return
    
    print(f"📁 Folder MP3: {mp3_folder} ({len(pliki_mp3)} plików)")
    
    output_folder = os.path.join(base_dir, "temp", "fragmenty")
    print(f"📂 Folder wyjściowy: {output_folder}")
    
    print(f"\n{'='*80}")
    print(f"🚀 ROZPOCZYNAM PRZETWARZANIE")
    print(f"{'='*80}\n")
    
    try:
        fragmenty = podziel_na_fragmenty_z_enterami(
            plik_mp3=None,
            text_file=text_file,
            output_folder=output_folder,
            prog=35  # ✅ Obniżony próg dla lepszego dopasowania
        )
        
        print(f"\n{'='*80}")
        print(f"✅ ZAKOŃCZONO POMYŚLNIE")
        print(f"{'='*80}\n")
        
        return fragmenty
        
    except Exception as e:
        print(f"\n{'='*80}")
        print(f"❌ BŁĄD: {e}")
        print(f"{'='*80}\n")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    run()