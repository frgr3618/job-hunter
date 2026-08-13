"""Swedish-requirement detection used by the `drop_if_swedish_required` filter.

The distinction that matters: an ad *written* in Swedish is still a job you can
apply to, but an ad that *demands* Swedish is not. And "svenska är meriterande"
means a plus, not a demand — Swedish ads say it constantly, so getting that
wrong would hide most of the market.
"""

from __future__ import annotations

import pytest

from job_hunter.language import requires_swedish

# --- ads that genuinely rule you out -----------------------------------------

DEMANDS = [
    "Du behärskar svenska i tal och skrift.",
    "Vi söker dig som talar flytande svenska och engelska.",
    "Krav: goda kunskaper i svenska.",
    "Svenska språket är ett krav för tjänsten.",
    "You must be fluent in Swedish and English.",
    "Fluency in Swedish is required for this role.",
    "Professional proficiency in Swedish.",
    "Swedish is a must — you will work with local customers.",
    "We are looking for a native Swedish speaker.",
]

# --- ads that are still open to you ------------------------------------------

OPEN = [
    # Swedish-written, but never asks for the language.
    "Vi söker en dataanalytiker som vill arbeta med maskininlärning hos oss i "
    "Stockholm. Du kommer att arbeta med hela kedjan och det är en stor fördel "
    "om du har erfarenhet av Python.",
    # Explicitly a plus, not a requirement.
    "Svenska är meriterande men inget krav.",
    "Kunskaper i svenska är meriterande.",
    "Swedish is a plus but not required.",
    "Knowledge of Swedish is an advantage.",
    "Det är en fördel om du talar svenska.",
    # "svenska" as a nationality/market word, not a language skill.
    "Vi levererar lösningar till svenska kunder över hela landet.",
    "We are a Swedish company headquartered in Uppsala.",
    "You will analyse data from the Swedish market.",
    # Plain English ad with no mention at all.
    "We are looking for a data scientist to join our team in Stockholm.",
]


@pytest.mark.parametrize("text", DEMANDS)
def test_detects_a_stated_requirement(text: str) -> None:
    assert requires_swedish(text) is True


@pytest.mark.parametrize("text", OPEN)
def test_keeps_ads_that_do_not_demand_swedish(text: str) -> None:
    assert requires_swedish(text) is False


def test_requirement_elsewhere_still_counts() -> None:
    """A softener attached to some *other* perk must not excuse a real demand
    further down the ad."""
    text = (
        "Erfarenhet av Kubernetes är meriterande. "
        "Vi erbjuder flexibla arbetstider och friskvårdsbidrag. "
        "Du talar och skriver obehindrat på svenska."
    )
    assert requires_swedish(text) is True


def test_empty_text_is_not_a_requirement() -> None:
    assert requires_swedish("") is False


def test_softener_in_a_list_heading_still_counts() -> None:
    """Swedish ads often soften a whole bullet list from its heading."""
    text = "Meriterande:\n• Erfarenhet av Azure\n• Svenska i tal och skrift"
    assert requires_swedish(text) is False


# Phrasings found in real Platsbanken ads that earlier versions of the pattern
# missed — each one genuinely rules you out.
@pytest.mark.parametrize(
    "text",
    [
        "Kommunicerar väl på svenska och engelska",
        "Då våra kunder pratar svenska behöver du behärska båda språken i tal och skrift",
        "Ability to communicate confidently in Swedish",
    ],
)
def test_real_ad_phrasings_are_caught(text: str) -> None:
    assert requires_swedish(text) is True
