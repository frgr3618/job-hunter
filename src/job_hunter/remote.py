"""Decide whether an ad is *actually* remote, not just remote-friendly.

Swedish job ads talk about flexibility constantly — "hybrid", "work from home
some days a week", "be it remote work or flexible hours". None of that helps if
you live in Uppsala and the desk is in Göteborg. Searching for the bare word
"remote" flags all of it, which is how a Power Electronics Engineer in Göteborg
ends up on a list filtered to Stockholm.

So we do the opposite of the usual keyword scan: a phrase must promise the whole
job is location-independent, and any wording that ties you to an office wins.
Measured on a 134-job sample of this exact market, one ad said "fully remote"
and thirty-four said "hybrid" — false positives are the failure mode that
matters here, not misses.
"""

from __future__ import annotations

import re

# Phrases that promise the role itself is location-independent.
_FULLY_REMOTE = (
    "fully remote", "100% remote", "100 % remote", "completely remote",
    "remote-first", "remote first", "fully distributed", "work from anywhere",
    "remote position", "remote role", "anywhere in sweden",
    "helt på distans", "helt distans", "distansarbete", "arbeta på distans",
)

# Wording that pins you to a place. These beat any remote phrasing: an ad
# offering "remote work" *and* three days on-site is an on-site job.
_TIED_TO_A_PLACE = (
    "hybrid", "on-site", "on site", "onsite", "in-office", "in the office",
    "days a week", "days per week", "some days", "few days", "twice a week",
    "på plats", "på kontoret", "kontoret i",
)

_PATTERNS = {
    phrase: re.compile(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])")
    for phrase in _FULLY_REMOTE + _TIED_TO_A_PLACE
}


def looks_remote(text: str) -> bool:
    """True only if the ad reads as fully remote and nothing ties it to an office."""
    lowered = text.lower()
    if any(_PATTERNS[p].search(lowered) for p in _TIED_TO_A_PLACE):
        return False
    return any(_PATTERNS[p].search(lowered) for p in _FULLY_REMOTE)
