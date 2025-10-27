import funkcje.empty_srt as empty_srt
import funkcje.cut_chapter as cut_chapter
import funkcje.upload_mp3 as upload_mp3

# Program wymaga pliku w-pustyni-i-w-puszczy.txt w tym samym katalogu

def menu():
    print("\n=== El Raphael ===")
    """
    Etap 1: Utworzenie pustego pliku SRT z czasami
    """
    print("\nETAP 1: Utworzenie pustego pliku SRT z czasami")
    #empty_srt.run()
    """
    Etap 2: Wybranie rozdziału
    """
    print("\nEtap2: Wybranie rozdziału")
    #cut_chapter.run()
    """
    Etap 3: Wgranie plików .mp3
    """
    print("\nETAP 3: Wgranie plików .mp3")
    #upload_mp3.run()
    """
    Etap 4: Podział rozdziału
    """
    print("\nETAP 4: Podział rozdziału")
    


if __name__ == "__main__":
    menu()
