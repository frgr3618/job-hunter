"""Work out how many years of experience an ad is asking for.

Job ads bury this in prose ("At least 3 years of experience in a similar role"),
so we pull it out with a small set of patterns rather than a model — it's a
narrow, well-defined extraction and a regex is honest about what it does.

Two deliberate choices, both aimed at *not* over-reacting:

1. When an ad names several figures we keep the **smallest**. A "nice to have:
   5 years of Kubernetes" shouldn't outweigh a "required: 2 years of Python".
   The lowest number is the most generous reading of the door being open.
2. Company self-description ("we have 10 years of experience in the industry")
   is skipped — that's a boast about them, not a requirement on you.
"""

from __future__ import annotations

import re

# A figure followed by a years unit: "3 years", "3+ years", "2-4 years", "3 år".
_YEARS = re.compile(
    # "års" is the Swedish genitive ("3 års erfarenhet"), hence the optional s.
    r"(\d{1,2})\s*(?:\+|\s*[-–]\s*\d{1,2})?\s*\+?\s*(?:years?|yrs?|års?)\b",
    re.IGNORECASE,
)

# The figure only counts if experience is being discussed nearby.
_EXPERIENCE_CUE = re.compile(r"experien|erfarenhet|worked|working|background", re.IGNORECASE)

# ...but not when the company is describing itself.
_ABOUT_THE_COMPANY = re.compile(
    r"\b(?:we|our|us|company|team)\b[^.]{0,30}$|\b(?:founded|established|since|in business)\b",
    re.IGNORECASE,
)

# How much text either side of the figure we read for those cues.
_WINDOW = 60

# Anything outside this range is a date, a headcount, or a typo — not a
# requirement. ("100 years of combined experience", "20 years" for a junior role.)
_MIN_PLAUSIBLE = 1
_MAX_PLAUSIBLE = 15


def required_years(text: str) -> int | None:
    """Smallest years-of-experience figure the ad asks for, or None if unstated."""
    if not text:
        return None
    found: list[int] = []
    for match in _YEARS.finditer(text):
        years = int(match.group(1))
        if not _MIN_PLAUSIBLE <= years <= _MAX_PLAUSIBLE:
            continue
        before = text[max(0, match.start() - _WINDOW) : match.start()]
        after = text[match.end() : match.end() + _WINDOW]
        if not _EXPERIENCE_CUE.search(before + after):
            continue
        if _ABOUT_THE_COMPANY.search(before):
            continue
        found.append(years)
    return min(found) if found else None


def seniority_gap(years_required: int | None, max_years: int) -> int:
    """How many years beyond `max_years` the ad demands (0 if it's within reach).

    `max_years` is what you can credibly claim. A gap of 0 means the ad is fair
    game; a gap of 3 means it's asking for meaningfully more than you have.
    """
    if years_required is None or max_years < 0:
        return 0
    return max(0, years_required - max_years)
