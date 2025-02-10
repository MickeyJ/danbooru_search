import urllib.request
import nltk
import ssl


def download_english_words():
    """Download a comprehensive list of English words using NLTK"""
    print("Downloading English word list...")

    try:
        # Handle SSL certificate verification for NLTK downloads
        try:
            _create_unverified_https_context = ssl._create_unverified_context
        except AttributeError:
            pass
        else:
            ssl._create_default_https_context = _create_unverified_https_context

        # Download the words corpus if not already present
        nltk.download("words", quiet=True)
        from nltk.corpus import words

        # Get all words and convert to lowercase
        word_list = set(word.lower() for word in words.words())
        print(f"Downloaded {len(word_list)} words from NLTK corpus")
        return word_list

    except Exception as e:
        print(f"Error downloading English words: {e}")
        # Fallback to the Google word list if NLTK fails
        word_url = "https://raw.githubusercontent.com/first20hours/google-10000-english/master/google-10000-english.txt"
        try:
            response = urllib.request.urlopen(word_url)
            words = response.read().decode("utf-8").splitlines()
            return set(word.lower() for word in words if len(word) > 2)
        except Exception as e:
            print(f"Fallback also failed: {e}")
            return set()


def get_anime_terms():
    """Return a set of essential anime/Japanese terms"""
    return {
        # Common Japanese honorifics
        "chan",
        "kun",
        "san",
        "sama",
        "sensei",
        "senpai",
        "kouhai",
        # Common anime/manga terms
        "chibi",
        "kawaii",
        "moe",
        "bishonen",
        "bishojo",
        "manga",
        "anime",
        "doujin",
        "doujinshi",
        "kemono",
        "nekomimi",
        "neko",
        "kitsune",
        "tsundere",
        "yandere",
        "kuudere",
        "deredere",
        "ahoge",
        "kemonomimi",
        "meganekko",
        # Common Japanese clothing
        "kimono",
        "yukata",
        "hakama",
        "obi",
        "geta",
        "seifuku",
        "pantsu",
        "megane",
    }


def create_wordlist():
    """Create the common_words.txt file"""
    # Get both English and anime terms
    all_words = download_english_words()
    print(f"Got {len(all_words)} common English words")

    anime_terms = get_anime_terms()
    print(f"Adding {len(anime_terms)} anime/Japanese terms")
    all_words.update(anime_terms)

    # Write to file
    output_file = "common_words.txt"
    with open(output_file, "w", encoding="utf-8") as f:
        for word in sorted(all_words):
            f.write(word + "\n")

    print(f"\nCreated {output_file} with {len(all_words)} total words")
    print("\nYou can add additional terms directly to the file as needed.")


if __name__ == "__main__":
    create_wordlist()
