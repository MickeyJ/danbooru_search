from django.core.management.base import BaseCommand
from danbooru_search.models import CommonWord
import nltk
from nltk.corpus import words, wordnet
import urllib.request
from django.db import transaction


class Command(BaseCommand):
    help = "Initialize the common words database"

    def download_wordnet_words(self):
        """Get words from NLTK's WordNet"""
        print("Downloading WordNet...")
        nltk.download("wordnet", quiet=True)
        
        words = set()
        for synset in wordnet.all_synsets():
            # Add the lemma names (base forms of words)
            words.update(word.lower() for word in synset.lemma_names())

        print(f"Successfully downloaded WordNet dictionary")
        return words

    def handle(self, *args, **options):
        # Get all words from sources
        all_words = set()  # Using set to remove duplicates immediately

        # 1. NLTK words
        print("Downloading NLTK words...")
        nltk.download("words", quiet=True)
        all_words.update(word.lower() for word in words.words())
        print(f"Got {len(all_words)} words from NLTK")

        # 2. WordNet words
        wordnet_words = self.download_wordnet_words()
        all_words.update(wordnet_words)
        print(f"Added {len(wordnet_words)} words from WordNet")

        # 3. Add anime/Japanese terms
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
        all_words.update(japanese_terms)
        print(f"Total unique words: {len(all_words)}")

        # Bulk insert in batches
        print("\nInserting words into database...")
        batch_size = 5000
        words_to_create = [
            CommonWord(word=word, category="english") for word in all_words
        ]

        total_inserted = 0
        with transaction.atomic():  # Single transaction for all inserts
            for i in range(0, len(words_to_create), batch_size):
                batch = words_to_create[i : i + batch_size]
                CommonWord.objects.bulk_create(
                    batch, ignore_conflicts=True  # Skip duplicates
                )
                total_inserted += len(batch)
                print(f"Inserted {total_inserted}/{len(words_to_create)} words...")

        print(f"\nFinished! Added {total_inserted} total words to database")
