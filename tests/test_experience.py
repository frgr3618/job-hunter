"""Pulling a years-of-experience requirement out of ad prose."""

from __future__ import annotations

import pytest

from job_hunter.experience import required_years, seniority_gap


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("At least 3 years of experience in a similar role", 3),
        ("Minimum 5 years of experience in software engineering", 5),
        ("3+ years of hands-on experience with deep learning", 3),
        ("2-4 years of experience working with deep learning", 2),  # ranges: take the floor
        ("2–4 years of experience", 2),  # en dash
        ("You have 4 yrs experience building data pipelines", 4),
        ("Vi söker dig med 3 års erfarenhet av Python", 3),
        ("At least 2-3 years of work experience as a data scientist", 2),
    ],
)
def test_extracts_the_requirement(text: str, expected: int) -> None:
    assert required_years(text) == expected


def test_lowest_figure_wins() -> None:
    """A steep 'nice to have' shouldn't outrank a modest hard requirement."""
    ad = (
        "Required: 2 years of experience with Python. "
        "Nice to have: 8 years of Kubernetes experience."
    )
    assert required_years(ad) == 2


@pytest.mark.parametrize(
    "text",
    [
        "",
        "We are looking for a curious data scientist to join us.",
        "A degree in computer science or equivalent.",
    ],
)
def test_no_requirement_stated(text: str) -> None:
    assert required_years(text) is None


def test_company_boasting_is_not_a_requirement() -> None:
    """'We have 10 years of experience' says nothing about what they want."""
    assert required_years("We have 10 years of experience serving Nordic retailers.") is None


def test_years_without_an_experience_cue_are_ignored() -> None:
    """Otherwise 'a 3 year contract' or '5 years of growth' would count."""
    assert required_years("This is a 3 year fixed-term contract.") is None


def test_implausible_figures_are_ignored() -> None:
    assert required_years("Our team has 100 years of combined experience") is None
    assert required_years("0 years of experience needed") is None


# --- the gap -----------------------------------------------------------------


def test_gap_is_zero_when_within_reach() -> None:
    assert seniority_gap(2, 2) == 0
    assert seniority_gap(1, 2) == 0


def test_gap_counts_only_the_excess() -> None:
    assert seniority_gap(5, 2) == 3


def test_unstated_requirement_is_no_gap() -> None:
    """Silence isn't a barrier — plenty of junior-friendly ads never say."""
    assert seniority_gap(None, 2) == 0
