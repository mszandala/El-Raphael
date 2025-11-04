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
    
    # ✅ POPRAWIONE: Pobierz frazy bezpośrednio z plików MP3
    frazy = pobierz_frazy_z_mp3(text_file)
    
    # ✅ POPRAWIONE: Przekaż text_file do funkcji
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
    Normalizuje tekst do porównywania (lowercase, bez znaków specjalnych, polskie formy)
    """
    text = text.lower()
    
    # ✅ Usuń myślniki PRZED innymi znakami
    text = text.replace('—', ' ').replace('–', ' ').replace('-', ' ')
    
    # ✅ Usuń wszystkie znaki interpunkcyjne (zachowaj polskie znaki)
    text = re.sub(r'[^\w\sąćęłńóśźżĄĆĘŁŃÓŚŹŻ]', ' ', text)
    
    # ✅ Normalizuj wielokrotne spacje
    text = re.sub(r'\s+', ' ', text).strip()
    
    # ✅ ROZSZERZONE zamienniki dla polskich form
    replacements = {
        # Formy czasowników
        'tys': 'ty',
        'jes': 'jest',
        'byś': 'by',
        'cobyś': 'coby',
        'jakis': 'jaki',
        'jakiś': 'jaki',
        
        # Formy rzeczowników
        'koszałek opałek': 'koszałek opałek',
        'koszałek opałka': 'koszałek opałek',
        'koszałka opałka': 'koszałek opałek',
        'koszałkiem opałkiem': 'koszałek opałek',
        
        # Czasowniki mówienia
        'odpowiedział': 'powiedział',
        'rzekł': 'powiedział',
        'rzecze': 'powiedział',
        'odparł': 'powiedział',
        'odrzekł': 'powiedział',
        
        # Znane błędy Whisper
        'idry': 'idrys',
        'gebhr': 'gebr',
        'nalektura': 'nel',
        
        # Inne częste formy
        'więc': 'wiec',
        'cóż': 'coz',
        'jakże': 'jakze',
    }
    
    for wrong, correct in replacements.items():
        text = text.replace(wrong, correct)
        
    return text


def find_phrase_with_sliding_window(original_text, search_phrase, start_offset=0, threshold=50):
    """
    Znajduje frazę używając sliding window + fuzzy matching z adaptacyjnymi progami
    
    Returns:
        tuple: ((start_pos, end_pos), score) lub ((None, None), 0) jeśli nie znaleziono
    """
    if not search_phrase or len(search_phrase) < 3:
        return (None, None), 0

    phrase_norm = normalize_for_matching(search_phrase)
    phrase_words = phrase_norm.split()
    words_count = len(phrase_words)

    # ✅ ZWIĘKSZONE OKNO - więcej kontekstu
    window_size = max(800, len(search_phrase) * 40)
    step_size = max(15, window_size // 15)
    
    # ✅ ADAPTACYJNY PRÓG - im krótsza fraza, tym wyższy próg
    if words_count < 10:
        adaptive_threshold = min(70, threshold + 10)
    else:
        adaptive_threshold = threshold

    search_text = original_text[start_offset:]
    max_start = len(search_text) - window_size if len(search_text) > window_size else 0

    best_pos_start = None
    best_pos_end = None
    best_score = 0

    i = 0
    while i <= max_start:
        window = search_text[i:i + window_size]
        window_norm = normalize_for_matching(window)

        # ✅ KOMBINACJA 3 METRYK z wagami
        score_partial = fuzz.partial_ratio(phrase_norm, window_norm)
        
        try:
            score_token = fuzz.token_set_ratio(phrase_norm, window_norm)
            score_sort = fuzz.token_sort_ratio(phrase_norm, window_norm)
        except Exception:
            score_token = 0
            score_sort = 0
        
        # ✅ Średnia ważona (partial ma największą wagę)
        score = (score_partial * 0.5 + score_token * 0.3 + score_sort * 0.2)

        # ✅ Bonus za dokładne dopasowanie pierwszego słowa
        if phrase_words and len(phrase_words) > 0:
            first_word = phrase_words[0]
            if first_word in window_norm.split():
                score = min(100, score + 10)
            
            # ✅ DODATKOWY bonus za dopasowanie 2-3 pierwszych słów
            if len(phrase_words) >= 3:
                first_three = ' '.join(phrase_words[:3])
                if first_three in window_norm:
                    score = min(100, score + 15)

        if score > best_score:
            best_score = score
            best_pos_start = start_offset + i
            
            # Szukaj dokładnego końca frazy w oknie
            phrase_len_estimate = len(search_phrase)
            best_pos_end = best_pos_start + phrase_len_estimate

        i += step_size

    if best_score >= adaptive_threshold:
        return (best_pos_start, best_pos_end), best_score
    else:
        return (None, None), best_score


def pobierz_frazy_z_mp3(text_file):
    """
    ✅ NOWA FUNKCJA: Skanuje folder temp/mp3 i transkrybuje pliki przez Whisper
    """
    import whisper
    
    # Ustal ścieżkę do folderu z MP3
    base_dir = os.path.dirname(text_file)
    mp3_folder = os.path.join(base_dir, "mp3")
    
    if not os.path.exists(mp3_folder):
        print(f"❌ Folder z plikami MP3 nie istnieje: {mp3_folder}")
        return []
    
    frazy = []
    pliki_mp3 = sorted([f for f in os.listdir(mp3_folder) if f.endswith('.mp3')])
    
    print(f"📂 Znaleziono {len(pliki_mp3)} plików MP3")
    print(f"🎤 Ładuję model Whisper...")
    
    # Załaduj model Whisper (możesz użyć 'base', 'small', 'medium', 'large')
    model = whisper.load_model("base")
    
    for idx, plik in enumerate(pliki_mp3):
        sciezka = os.path.join(mp3_folder, plik)
        
        try:
            print(f"🎵 [{idx+1}/{len(pliki_mp3)}] Transkrybuję: {plik}")
            
            # Transkrybuj przez Whisper
            result = model.transcribe(sciezka, language="pl")
            transkrypcja = result["text"].strip()
            
            if not transkrypcja:
                print(f"   ⚠️  Pusta transkrypcja")
                continue
            
            # Pobierz długość pliku MP3
            audio = AudioSegment.from_mp3(sciezka)
            dlugosc_ms = len(audio)
            
            print(f"   ✅ Transkrypcja ({len(transkrypcja)} znaków): {transkrypcja[:80]}...")
            
            frazy.append({
                'plik': plik,
                'transkrypcja': transkrypcja,
                'start_ms': 0,  # Każdy plik zaczyna się od 0
                'end_ms': dlugosc_ms
            })
            
        except Exception as e:
            print(f"   ❌ Błąd podczas transkrypcji {plik}: {e}")
            continue
    
    print(f"✅ Zatranskrybowano {len(frazy)} plików")
    return frazy


def wstaw_entery_z_podwojna_weryfikacja(text, frazy, prog=40, text_file=None):
    """
    Wstawia separatory [XX] >>>>>>>> w tekście bazując na transkrypcjach.
    Używa podwójnej weryfikacji: START i END każdego fragmentu.
    
    ✅ ZMIENIONY DOMYŚLNY PRÓG: 50 → 40
    """
    fragmenty = []
    last_search_pos = 0
    
    print(f"\n{'='*80}")
    print(f"🔍 ROZPOCZYNAM WYSZUKIWANIE FRAZ (próg: {prog})")
    print(f"{'='*80}\n")
    
    # ✅ Sprawdź czy są frazy
    if not frazy or len(frazy) == 0:
        print("⚠️  BRAK FRAZ DO WYSZUKANIA")
        return fragmenty
    
    # Lista pozycji do wstawienia separatorów
    pozycje_separatorow = []
    
    for idx, item in enumerate(frazy):
        plik = item['plik']
        pelna_transkrypcja = item['transkrypcja']
        
        # Podziel transkrypcję na słowa
        slowa = pelna_transkrypcja.split()
        
        if len(slowa) < 5:
            print(f"⚠️  [{idx+1}] {plik} - za mało słów ({len(slowa)}), pomijam")
            fragmenty.append({
                'found': False,
                'plik': plik,
                'reason': 'za_krotka_transkrypcja'
            })
            continue
        
        # ✅ Pierwsze 8 słów (ORYGINALNIE)
        fraza_start = ' '.join(slowa[:min(8, len(slowa))])
        
        # ✅ Ostatnie 8 słów (ORYGINALNIE)
        fraza_end = ' '.join(slowa[-min(8, len(slowa)):]) if len(slowa) >= 8 else pelna_transkrypcja
        
        print(f"🔍 [{idx+1}/{len(frazy)}] {plik}")
        print(f"   📝 Transkrypcja: {pelna_transkrypcja[:100]}...")
        print(f"   🎯 Pierwsze 8 słów: {fraza_start}")
        print(f"   🎯 Ostatnie 8 słów: {fraza_end}")
        print(f"   🔍 Szukam od pozycji: {last_search_pos}")
        
        # Szukaj START z NIŻSZYM progiem
        (pos_start, pos_start_end), score_start = find_phrase_with_sliding_window(
            text, fraza_start, last_search_pos, threshold=40
        )
        
        if pos_start is None:
            print(f"   ⚠️  Nie znaleziono START (score: {score_start:.1f})")
            # Próbuj z JESZCZE krótszą frazą (pierwsze 5 słów)
            shorter_phrase = ' '.join(fraza_start.split()[:5])
            print(f"   🔄 Próbuję z 5 słowami...")
            (pos_start, pos_start_end), score_start = find_phrase_with_sliding_window(
                text, shorter_phrase, last_search_pos, threshold=30
            )
            
            if pos_start is None:
                print(f"   ❌ Nie znaleziono START (score: {score_start:.1f})")
                fragmenty.append({
                    'found': False,
                    'plik': plik,
                    'fraza_start': fraza_start,
                    'score_start': score_start
                })
                continue
        
        # ✅ Pokaż kontekst znalezienia
        context_start = max(0, pos_start - 30)
        context_end = min(len(text), pos_start + 100)
        context = text[context_start:context_end].replace('\n', '↵')
        print(f"   ✅ START: pozycja {pos_start} (score: {score_start:.1f})")
        print(f"      Kontekst: '{context[:80]}...'")
        
        # Szukaj END (od pozycji START)
        (pos_end, pos_end_end), score_end = find_phrase_with_sliding_window(
            text, fraza_end, pos_start, threshold=40
        )
        
        if pos_end is None:
            print(f"   ⚠️  Nie znaleziono END (score: {score_end:.1f})")
            # ✅ FALLBACK: spróbuj z ostatnimi 5 słowami
            shorter_end = ' '.join(fraza_end.split()[-5:])
            print(f"   🔄 Próbuję z 5 słowami...")
            (pos_end, pos_end_end), score_end = find_phrase_with_sliding_window(
                text, shorter_end, pos_start, threshold=30
            )
            
            if pos_end is None:
                print(f"   ❌ Nie znaleziono END (score: {score_end:.1f})")
                fragmenty.append({
                    'found': False,
                    'plik': plik,
                    'fraza_end': fraza_end,
                    'pos_start': pos_start,
                    'score_end': score_end
                })
                continue
        
        # ✅ Pokaż kontekst końca
        context_end_start = max(0, pos_end - 30)
        context_end_end = min(len(text), pos_end + 100)
        context_end_text = text[context_end_start:context_end_end].replace('\n', '↵')
        print(f"   ✅ END: pozycja {pos_end} (score: {score_end:.1f})")
        print(f"      Kontekst: '{context_end_text[:80]}...'")
        
        # Sprawdź czy END jest za START
        if pos_end <= pos_start:
            print(f"   ❌ END ({pos_end}) jest przed START ({pos_start})!")
            fragmenty.append({
                'found': False,
                'plik': plik,
                'reason': 'end_przed_start',
                'pos_start': pos_start,
                'pos_end': pos_end
            })
            continue
        
        # ✅ Zapisz pozycję separatora
        pozycje_separatorow.append({
            'numer': idx + 1,
            'pozycja': pos_start,
            'plik': plik
        })
        
        # Sukces!
        fragmenty.append({
            'found': True,
            'plik': plik,
            'pos_start': pos_start,
            'pos_end': pos_end_end,
            'score_start': score_start,
            'score_end': score_end,
            'text': text[pos_start:pos_end_end],
            'start_ms': item['start_ms'],
            'end_ms': item['end_ms']
        })
        
        # Aktualizuj pozycję dla następnego wyszukiwania
        last_search_pos = pos_end_end
        
        print(f"   ✅ Fragment znaleziony: tekst[{pos_start}:{pos_end_end}]")
        print()
    
    # ✅ WSTAW separatory w tekście
    if pozycje_separatorow and text_file:
        print(f"\n{'='*80}")
        print(f"📝 WSTAWIAM SEPARATORY W TEKŚCIE")
        print(f"{'='*80}\n")
        
        # Sortuj od końca, żeby pozycje się nie zmieniały przy wstawianiu
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
        
        # ✅ POPRAWIONE: Zapisz jako _z_enterami.txt
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
    else:
        print(f"\n{'='*80}")
        print(f"📊 PODSUMOWANIE: Brak fragmentów")
        print(f"{'='*80}\n")
    
    return fragmenty


def utworz_fragmenty_mp3(audio, fragmenty, output_folder):
    """
    ✅ POPRAWIONE: Kopiuje pliki MP3 zamiast wycinać z jednego dużego
    """
    print(f"\n{'='*80}")
    print(f"✂️  KOPIUJĘ FRAGMENTY MP3")
    print(f"{'='*80}\n")
    
    utworzone = 0
    
    for idx, fragment in enumerate(fragmenty):
        if not fragment.get('found', False):
            print(f"⏭️  [{idx+1}] Pomijam {fragment['plik']} - nie znaleziono w tekście")
            continue
        
        # Pobierz oryginalny plik MP3
        base_dir = os.path.dirname(output_folder)
        mp3_source = os.path.join(base_dir, "mp3", fragment['plik'])
        
        if not os.path.exists(mp3_source):
            print(f"   ❌ Nie znaleziono pliku źródłowego: {mp3_source}")
            continue
        
        # Skopiuj do folderu wyjściowego
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
    
    # Ustal ścieżki
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # ✅ NIE SZUKAMY już jednego dużego pliku MP3!
    # Małe pliki są w temp/mp3/
    
    # ✅ Szukaj pliku tekstowego w formacie ROZDZIAŁ_LICZBA.txt
    temp_folder = os.path.join(base_dir, "temp")
    
    text_files = []
    for f in os.listdir(temp_folder):
        if f.endswith('.txt'):
            match = re.match(r'ROZDZIA[ŁL]_([IVXLCDM0-9]+)\.txt', f, re.IGNORECASE)
            if match:
                text_files.append(f)
    
    if not text_files:
        print(f"❌ Brak plików tekstowych w folderze: {temp_folder}")
        print(f"   Szukam plików w formacie: ROZDZIAŁ_[liczba].txt")
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
    
    # Folder wyjściowy
    output_folder = os.path.join(base_dir, "temp", "fragmenty")
    print(f"📂 Folder wyjściowy: {output_folder}")
    
    # Uruchom podział
    print(f"\n{'='*80}")
    print(f"🚀 ROZPOCZYNAM PRZETWARZANIE")
    print(f"{'='*80}\n")
    
    try:
        fragmenty = podziel_na_fragmenty_z_enterami(
            plik_mp3=None,  # Nie potrzebujemy jednego dużego pliku
            text_file=text_file,
            output_folder=output_folder,
            prog=40
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