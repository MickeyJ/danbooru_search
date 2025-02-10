from django.core.management.base import BaseCommand
from danbooru_search.models import CommonWord
import nltk
from nltk.corpus import words
import urllib.request
import json


class Command(BaseCommand):
    help = "Initialize the common words database"

    def download_scowl_words(self):
        """Download SCOWL word list (60 size, English variant)"""
        print("Downloading SCOWL words...")
        url = "https://raw.githubusercontent.com/en-wl/wordlist/master/final/english-words.60"
        try:
            response = urllib.request.urlopen(url)
            return set(
                word.decode("utf-8").strip().lower() for word in response.readlines()
            )
        except Exception as e:
            print(f"Error downloading SCOWL words: {e}")
            return set()

    def download_wiktionary_words(self):
        """Download frequent English words from Wiktionary"""
        print("Downloading Wiktionary frequent words...")
        url = "https://en.wiktionary.org/wiki/Wiktionary:Frequency_lists/PG/2006/04/1-10000"
        try:
            response = urllib.request.urlopen(url)
            # Parse the HTML to extract words (simplified example)
            text = response.read().decode("utf-8")
            # Extract words from the frequency list (would need proper HTML parsing)
            words = set()
            for line in text.split("\n"):
                if " " in line:
                    word = line.split(" ")[1].strip().lower()
                    if word.isalpha():
                        words.add(word)
            return words
        except Exception as e:
            print(f"Error downloading Wiktionary words: {e}")
            return set()

    def handle(self, *args, **options):
        # Get words from all sources
        all_words = set()

        # 1. NLTK words
        print("Downloading NLTK words...")
        nltk.download("words", quiet=True)
        
        all_words.update(word.lower() for word in words.words())
        print(f"Got {len(all_words)} words from NLTK")

        # 2. SCOWL words
        scowl_words = self.download_scowl_words()
        all_words.update(scowl_words)
        print(f"Added {len(scowl_words)} words from SCOWL")

        # 3. Wiktionary frequent words
        wiktionary_words = self.download_wiktionary_words()
        all_words.update(wiktionary_words)
        print(f"Added {len(wiktionary_words)} words from Wiktionary")

        # Add all English words to database
        print("\nAdding English words to database...")
        for word in all_words:
            CommonWord.objects.get_or_create(
                word=word, defaults={"category": "english"}
            )

        # Add anime/Japanese terms
        print("\nAdding Japanese/anime terms...")
        japanese_terms = {
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
        for word in japanese_terms:
            CommonWord.objects.get_or_create(
                word=word, defaults={"category": "japanese"}
            )

        print(f"\nFinished! Added {CommonWord.objects.count()} total words to database")
