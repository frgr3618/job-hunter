"""English-vs-Swedish detection used by the `english_only` filter."""

from __future__ import annotations

from job_hunter.language import is_english

ENGLISH_AD = """
We are looking for a data scientist to join our team in Stockholm. You will
work with machine learning models and you will be responsible for the whole
pipeline. This is a great opportunity for you to grow with us and our clients.
"""

SWEDISH_AD = """
Vi söker en dataanalytiker som vill arbeta med maskininlärning hos oss i
Stockholm. Du kommer att arbeta med hela kedjan och det är en stor fördel om du
har erfarenhet av Python. Vi erbjuder dig en trygg anställning och bra förmåner.
"""


def test_detects_english() -> None:
    assert is_english(ENGLISH_AD) is True


def test_detects_swedish() -> None:
    assert is_english(SWEDISH_AD) is False


def test_short_text_is_kept() -> None:
    """Under the word threshold we can't tell, so we keep the ad rather than
    silently drop a real job on a coin flip."""
    assert is_english("Vi söker en utvecklare") is True


def test_swedish_letters_do_not_break_tokenizing() -> None:
    """å/ä/ö must count as word characters, or Swedish stopwords never match."""
    assert is_english("är för på av det " * 10) is False
