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
    
    # Pobierz listę plików z transkrypcjami
    frazy = pobierz_frazy_do_wyszukania(text_file)
    
    # Wstaw entery w odpowiednich miejscach
    fragmenty = wstaw_entery_z_podwojna_weryfikacja(text, frazy, prog)
    
    # Ładuj plik MP3
    audio = AudioSegment.from_mp3(plik_mp3)
    
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


def pobierz_frazy_do_wyszukania(text_file):
    """
    Skanuje folder z transkrypcjami i tworzy listę fraz do wyszukania
    """
    # Ustal ścieżkę do folderu z transkrypcjami
    base_dir = os.path.dirname(text_file)
    transkrypcje_folder = os.path.join(base_dir, "transkrypcje")
    
    if not os.path.exists(transkrypcje_folder):
        print(f"❌ Folder z transkrypcjami nie istnieje: {transkrypcje_folder}")
        return []
    
    frazy = []
    pliki_txt = sorted([f for f in os.listdir(transkrypcje_folder) if f.endswith('.txt')])
    
    print(f"📂 Znaleziono {len(pliki_txt)} plików z transkrypcjami")
    
    for plik in pliki_txt:
        sciezka = os.path.join(transkrypcje_folder, plik)
        
        try:
            with open(sciezka, 'r', encoding='utf-8') as f:
                tresc = f.read().strip()
            
            if not tresc:
                print(f"⚠️  Pusty plik: {plik}")
                continue
            
            # Wyciągnij timestamp z nazwy pliku (format: fragment_XXXX_YYYY.txt)
            match = re.search(r'fragment_(\d+)_(\d+)', plik)
            if match:
                start_ms = int(match.group(1))
                end_ms = int(match.group(2))
            else:
                print(f"⚠️  Nie można wyciągnąć timestampu z: {plik}")
                continue
            
            frazy.append({
                'plik': plik,
                'transkrypcja': tresc,
                'start_ms': start_ms,
                'end_ms': end_ms
            })
            
        except Exception as e:
            print(f"❌ Błąd podczas czytania {plik}: {e}")
            continue
    
    print(f"✅ Załadowano {len(frazy)} transkrypcji")
    return frazy


def wstaw_entery_z_podwojna_weryfikacja(text, frazy, prog=40):
    """
    Wstawia entery w tekście bazując na transkrypcjach.
    Używa podwójnej weryfikacji: START i END każdego fragmentu.
    
    ✅ ZMIENIONY DOMYŚLNY PRÓG: 50 → 40
    """
    fragmenty = []
    last_search_pos = 0
    
    print(f"\n{'='*80}")
    print(f"🔍 ROZPOCZYNAM WYSZUKIWANIE FRAZ (próg: {prog})")
    print(f"{'='*80}\n")
    
    for idx, item in enumerate(frazy):
        plik = item['plik']
        pelna_transkrypcja = item['transkrypcja']
        
        # Podziel transkrypcję na słowa
        slowa = pelna_transkrypcja.split()
        
        if len(slowa) < 5:
            print(f"⚠️  [{idx}] {plik} - za mało słów ({len(slowa)}), pomijam")
            fragmenty.append({
                'found': False,
                'plik': plik,
                'reason': 'za_krotka_transkrypcja'
            })
            continue
        
        # ✅ Pierwsze 20 słów zamiast 8
        fraza_start = ' '.join(slowa[:min(20, len(slowa))])
        
        # ✅ Ostatnie 20 słów
        fraza_end = ' '.join(slowa[-min(20, len(slowa)):]) if len(slowa) >= 20 else pelna_transkrypcja
        
        print(f"🔍 [{idx}] Szukam fragmentu: {plik}")
        print(f"   📝 Znormalizowana START: '{normalize_for_matching(fraza_start)[:80]}'")
        print(f"   🎯 Pierwsze 5 słów: {' '.join(fraza_start.split()[:5])}")
        print(f"   🔍 Szukam od pozycji: {last_search_pos}")
        
        # Szukaj START z NIŻSZYM progiem
        (pos_start, pos_start_end), score_start = find_phrase_with_sliding_window(
            text, fraza_start, last_search_pos, threshold=40  # ✅ było 50
        )
        
        if pos_start is None:
            print(f"   ⚠️  Nie znaleziono START (score: {score_start:.1f})")
            # Próbuj z JESZCZE krótszą frazą (pierwsze 8 słów) i NIŻSZYM progiem
            shorter_phrase = ' '.join(fraza_start.split()[:8])
            print(f"   🔄 Próbuję z krótszą frazą (8 słów)...")
            (pos_start, pos_start_end), score_start = find_phrase_with_sliding_window(
                text, shorter_phrase, last_search_pos, threshold=30  # ✅ było 40
            )
            
            if pos_start is None:
                print(f"   ❌ Nie znaleziono START nawet z krótszą frazą (score: {score_start:.1f})")
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
        print(f"   ✅ START znaleziony na {pos_start} (score: {score_start:.1f})")
        print(f"      Kontekst: '{context[:100]}'")
        
        # Szukaj END (od pozycji START)
        (pos_end, pos_end_end), score_end = find_phrase_with_sliding_window(
            text, fraza_end, pos_start, threshold=40
        )
        
        if pos_end is None:
            print(f"   ⚠️  Nie znaleziono END (score: {score_end:.1f})")
            # ✅ FALLBACK: spróbuj z ostatnimi 10 słowami
            shorter_end = ' '.join(fraza_end.split()[-10:])
            print(f"   🔄 Próbuję z krótszym END (10 słów)...")
            (pos_end, pos_end_end), score_end = find_phrase_with_sliding_window(
                text, shorter_end, pos_start, threshold=30
            )
            
            if pos_end is None:
                # ✅ OSTATNIA SZANSA: szukaj w większym oknie
                print(f"   ⚠️  Próbuję większe okno dla END...")
                (pos_end, pos_end_end), score_end = find_phrase_with_sliding_window(
                    text, fraza_end, pos_start, threshold=25
                )
                
                if pos_end is None:
                    print(f"   ❌ Nie znaleziono END nawet z fallback (score: {score_end:.1f})")
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
        print(f"   ✅ END znaleziony na {pos_end} (score: {score_end:.1f})")
        print(f"      Kontekst: '{context_end_text[:100]}'")
        
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
        
        # Sukces!
        fragmenty.append({
            'found': True,
            'plik': plik,
            'pos_start': pos_start,
            'pos_end': pos_end_end,
            'score_start': score_start,
            'score_end': score_end,
            'text': text[pos_start:pos_end_end]
        })
        
        # Aktualizuj pozycję dla następnego wyszukiwania
        last_search_pos = pos_end_end
        
        print(f"   ✅ Fragment dodany: {pos_start} → {pos_end_end}")
        print()
    
    # Podsumowanie
    znalezione = sum(1 for f in fragmenty if f.get('found', False))
    print(f"\n{'='*80}")
    print(f"📊 PODSUMOWANIE: Znaleziono {znalezione}/{len(fragmenty)} fragmentów ({znalezione/len(fragmenty)*100:.1f}%)")
    print(f"{'='*80}\n")
    
    return fragmenty


def utworz_fragmenty_mp3(audio, fragmenty, output_folder):
    """
    Wycina fragmenty audio na podstawie znalezionych pozycji w tekście
    """
    print(f"\n{'='*80}")
    print(f"✂️  TWORZĘ FRAGMENTY MP3")
    print(f"{'='*80}\n")
    
    utworzone = 0
    
    for idx, fragment in enumerate(fragmenty):
        if not fragment.get('found', False):
            print(f"⏭️  [{idx}] Pomijam {fragment['plik']} - nie znaleziono w tekście")
            continue
        
        start_ms = fragment.get('start_ms', 0)
        end_ms = fragment.get('end_ms', len(audio))
        
        # Wytnij fragment
        fragment_audio = audio[start_ms:end_ms]
        
        # Zapisz
        output_path = os.path.join(output_folder, fragment['plik'].replace('.txt', '.mp3'))
        fragment_audio.export(output_path, format="mp3")
        
        utworzone += 1
        dlugosc = (end_ms - start_ms) / 1000
        print(f"✅ [{idx}] Utworzono: {fragment['plik'].replace('.txt', '.mp3')} ({dlugosc:.1f}s)")
    
    print(f"\n{'='*80}")
    print(f"📊 Utworzono {utworzone} fragmentów MP3")
    print(f"{'='*80}\n")
    
    return utworzone