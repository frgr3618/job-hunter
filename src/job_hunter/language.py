"""Lightweight, dependency-free English-vs-Swedish detection for job ads.

We deliberately avoid a language-detection library (extra install + disk). For
the narrow job of "is this ad English or Swedish?", counting each language's
most common function words is accurate enough and fully transparent: whichever
language contributes more stopwords wins.
"""

from __future__ import annotations

import re

# The most frequent function words in each language. These carry almost no
# meaning individually but are extremely reliable language fingerprints.
_ENGLISH = {
    "the", "and", "to", "of", "a", "in", "is", "you", "we", "for", "with",
    "as", "are", "our", "your", "will", "on", "be", "this", "that", "or", "an",
}
_SWEDISH = {
    "och", "att", "är", "för", "med", "som", "en", "ett", "på", "av", "det",
    "inte", "vi", "du", "till", "den", "har", "om", "kommer", "eller", "hos",
    "dig", "vår", "vara",
}

# Words = runs of letters, including the Swedish å/ä/ö.
_WORD = re.compile(r"[a-zåäö]+")

# Below this many words we can't reliably tell, so we don't drop the ad.
_MIN_WORDS = 20


def is_english(text: str) -> bool:
    """Best-effort guess: True if `text` reads as English (or is too short to tell)."""
    words = _WORD.findall(text.lower())
    if len(words) < _MIN_WORDS:
        return True  # not enough signal — keep it rather than wrongly drop
    english_hits = sum(w in _ENGLISH for w in words)
    swedish_hits = sum(w in _SWEDISH for w in words)
    return english_hits >= swedish_hits
