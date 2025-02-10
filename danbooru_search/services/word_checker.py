from ..models import CommonWord
from asgiref.sync import sync_to_async


def is_likely_typo(word, common_words, max_distance=1):
    """Check if a word is likely a typo"""
    if len(word) <= 2:
        return False, None

    if any(c * 3 in word for c in "abcdefghijklmnopqrstuvwxyz"):
        return True, None

    if word in common_words:
        return False, None

    return True, None


async def get_common_words():
    """Get set of common words from database"""
    return set(
        await sync_to_async(
            lambda: list(CommonWord.objects.values_list("word", flat=True))
        )()
    )
