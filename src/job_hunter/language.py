"""Detect whether a job ad *requires* Swedish.

The ad's own language is deliberately not a filter. Plenty of Swedish-written
ads are happy with an English-speaking applicant, and dropping them throws away
the least-contested half of the market — Swedish-domestic employers who get
fewer international applicants. What actually rules you out is a stated Swedish
requirement, and that can appear in an English ad just as easily.

So we look for two things together:

1. a mention of *Swedish as a language skill* ("flytande svenska", "fluent in
   Swedish") — not merely the word "svenska", which also shows up in "svenska
   kunder" and "the Swedish market";
2. the absence of a softener near it. "Svenska är meriterande" and "Swedish is
   a plus" are invitations, not requirements, and Swedish ads use that phrasing
   constantly.

A dependency-free pair of regexes is enough here and stays transparent: you can
read exactly why an ad was dropped.
"""

from __future__ import annotations

import re

# Swedish named as a *language skill*. Each branch pairs the language with a
# competence word, so "vi säljer till svenska kunder" doesn't match.
# [^.\n]{0,30} keeps the pair inside one sentence rather than spanning the ad.
_SWEDISH_SKILL = re.compile(
    r"""
      (?:flytande|obehindrat?|behärska\w*|mycket\ god[at]?|goda?|utmärkt|
         talar|skriver|kommunicera\w*|kunskaper\ i|krav\ på)
        [^.\n]{0,30}\bsvenska\b
    | \bsvenska\b[^.\n]{0,30}
        (?:i\ både\ tal|flytande|obehindrat|språket|är\ ett\ krav|krävs)
    # "i tal och skrift" is a language demand almost by definition, so it gets
    # a longer leash: "svenska behöver du behärska båda språken i tal och skrift".
    | \bsvenska\b[^.\n]{0,60}i\ tal\ och\ skrift
    | \bsvenska\ språket\b
    | (?:fluent|fluency|proficien\w+|native|command\ of|knowledge\ of|
         speak|spoken|write|written|verbal|communicate\w*)
        [^.\n]{0,30}\bswedish\b
    | \bswedish\b[^.\n]{0,30}
        (?:required|is\ a\ must|mandatory|essential|fluen\w+|speaker|
           language\ skills?|in\ speech\ and\ writing)
    | \bswedish\ language\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Phrasings that turn a requirement into a preference. If one of these sits
# next to the language mention, the ad is still open to you.
_SOFTENER = re.compile(
    r"""
      meriterande | \bmerit\b | (?:ett|en|stor)\ fördel | \bgärna\b
    | plus\b | \bbonus\b | inte\ ett\ krav | inget\ krav | icke\ obligatorisk
    | nice\ to\ have | (?:an|is\ an?)\ advantage | desirable | preferab\w+
    | not\ (?:a\ )?require\w* | beneficial | \bwelcome\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Sentence and bullet boundaries. A softener only excuses a demand when it sits
# in the *same* item — "Kubernetes är meriterande. Du talar svenska." is two
# separate statements, and only the second one is about you being ruled out.
_SEGMENT = re.compile(r"[.;!?\n\r•·]+")

# Swedish ads often put the softener in a list heading instead of the item:
#     Meriterande:
#     • Erfarenhet av Azure
#     • Svenska
# So we also walk back over short list items looking for a heading.
_MAX_LOOKBACK = 5
_LIST_ITEM_CHARS = 80


def _segments(text: str) -> list[tuple[int, int, str]]:
    """Split `text` into (start, end, segment) triples on sentence/bullet ends."""
    spans: list[tuple[int, int, str]] = []
    cursor = 0
    for sep in _SEGMENT.finditer(text):
        spans.append((cursor, sep.start(), text[cursor : sep.start()]))
        cursor = sep.end()
    spans.append((cursor, len(text), text[cursor:]))
    return spans


def _context(spans: list[tuple[int, int, str]], index: int) -> str:
    """The matched segment plus any list heading it belongs under."""
    parts = [spans[index][2]]
    for previous in range(index - 1, max(-1, index - 1 - _MAX_LOOKBACK), -1):
        candidate = spans[previous][2].strip()
        if not candidate:
            continue
        if candidate.endswith(":"):
            parts.append(candidate)  # found the heading this item sits under
            break
        if len(candidate) > _LIST_ITEM_CHARS:
            break  # prose, not a list — stop looking
    return " ".join(parts)


def requires_swedish(text: str) -> bool:
    """True if `text` states Swedish as a requirement (not merely a plus)."""
    spans = _segments(text)
    for match in _SWEDISH_SKILL.finditer(text):
        index = next(
            (i for i, (start, end, _) in enumerate(spans) if start <= match.start() < end),
            None,
        )
        if index is None:
            continue
        if not _SOFTENER.search(_context(spans, index)):
            return True  # demanded, with nothing nearby softening it
    return False
