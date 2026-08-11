"""Telling a genuinely remote job from a merely flexible one.

Every case here is real wording from Swedish ads that were wrongly flagged
remote and shown on a Stockholm-only list.
"""

from __future__ import annotations

import pytest

from job_hunter.remote import looks_remote


@pytest.mark.parametrize(
    "text",
    [
        "This is a fully remote position.",
        "We are a remote-first company.",
        "Work from anywhere in Sweden.",
        "100% remote, with optional meetups twice a year.",
        "Tjänsten utförs helt på distans.",
        "Vi erbjuder distansarbete.",
    ],
)
def test_genuinely_remote(text: str) -> None:
    assert looks_remote(text) is True


@pytest.mark.parametrize(
    "text",
    [
        # The Power Electronics Engineer in Göteborg.
        "Be it remote work, or flexible work hours, you will get a good environment.",
        # The ML Engineer in Göteborg.
        "Flexible working hours and the possibility to work from home some days a week.",
        # The Junior Data Scientist in Svedala.
        "The site in Svedala offers a hybrid working model, allowing you to work remotely.",
        "You will work on-site in our Göteborg office.",
        "Hybrid role: three days per week in the office.",
        "Du arbetar på plats i Malmö.",
    ],
)
def test_flexible_is_not_remote(text: str) -> None:
    """These are the false positives that started this. None are remote."""
    assert looks_remote(text) is False


def test_office_wording_beats_remote_wording() -> None:
    """An ad promising both is an office job with a perk."""
    assert looks_remote("A fully remote role, though we expect 2 days a week onsite.") is False


def test_silence_is_not_remote() -> None:
    assert looks_remote("Data Scientist in Stockholm. Python and SQL required.") is False
    assert looks_remote("") is False


def test_substrings_do_not_match() -> None:
    """The old bug in miniature: 'remote' must be a word, not a fragment."""
    assert looks_remote("Experience with remotely-triggered sensors is a plus.") is False
