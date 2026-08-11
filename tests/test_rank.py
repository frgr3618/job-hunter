"""Filtering, keyword scoring, percentile normalization, and the blend.

This is the heart of the project — the part that decides what you actually see
each morning — so it gets the most coverage.
"""

from __future__ import annotations

from typing import Any

import pytest

from conftest import days_ago, make_job
from job_hunter.config import Blend, Config, Ranking
from job_hunter.rank import _blend, _percentiles, rank


def cfg(locations: list[str] | None = None, **ranking: Any) -> Config:
    """A Config with only the ranking rules a given test cares about."""
    return Config(locations=locations or [], ranking=Ranking(**ranking))


# --- filters -----------------------------------------------------------------


def test_excluded_title_drops_the_job() -> None:
    jobs = [make_job(title="Senior Data Scientist")]
    assert rank(jobs, cfg(excluded_titles=["senior"])) == []


def test_excluded_title_ignores_the_description() -> None:
    """A junior role that merely mentions a senior colleague must survive — this
    is exactly why excluded_titles is separate from excluded."""
    jobs = [make_job(title="Data Scientist", description="You report to a senior lead.")]
    assert len(rank(jobs, cfg(excluded_titles=["senior", "lead"]))) == 1


def test_excluded_term_matches_the_company_name() -> None:
    """Excluding 'consulting' should drop consultancy firms, not just ads that
    happen to use the word."""
    jobs = [make_job(company="Nordic Consulting AB")]
    assert rank(jobs, cfg(excluded=["consulting"])) == []


def test_required_term_missing_drops_the_job() -> None:
    jobs = [make_job(description="We use Java and Spring.")]
    assert rank(jobs, cfg(required=["python"])) == []


def test_required_term_present_keeps_the_job() -> None:
    jobs = [make_job(description="We use Python daily.")]
    assert len(rank(jobs, cfg(required=["python"]))) == 1


def test_empty_required_list_keeps_everything() -> None:
    assert len(rank([make_job()], cfg(required=[]))) == 1


def test_english_only_drops_swedish_ads() -> None:
    swedish = make_job(
        description=(
            "Vi söker en analytiker som vill arbeta med maskininlärning hos oss. "
            "Du kommer att arbeta med hela kedjan och det är en fördel om du har "
            "erfarenhet av Python. Vi erbjuder dig en trygg anställning."
        )
    )
    assert rank([swedish], cfg(english_only=True)) == []


def test_old_postings_are_dropped() -> None:
    jobs = [make_job(posted_at=days_ago(45))]
    assert rank(jobs, cfg(max_age_days=30)) == []


def test_max_age_zero_disables_the_filter() -> None:
    jobs = [make_job(posted_at=days_ago(400))]
    assert len(rank(jobs, cfg(max_age_days=0))) == 1


def test_undated_postings_are_kept() -> None:
    """We don't drop what we can't measure."""
    jobs = [make_job(posted_at=None)]
    assert len(rank(jobs, cfg(max_age_days=30))) == 1


# --- keyword scoring ---------------------------------------------------------


def test_short_terms_match_whole_words_only() -> None:
    """The bug this guards: 'ai' scoring inside 'available' or 'training'."""
    job = make_job(title="Data Scientist", description="Several positions available.")
    ranked = rank([job], cfg(positive={"ai": 20}))
    assert ranked[0].keyword_score == 0


def test_short_terms_still_match_when_standalone() -> None:
    job = make_job(title="Data Scientist", description="Work on AI systems.")
    ranked = rank([job], cfg(positive={"ai": 20}))
    assert ranked[0].keyword_score == 20


def test_multi_word_terms_match() -> None:
    job = make_job(description="Applied machine learning work.")
    ranked = rank([job], cfg(positive={"machine learning": 12}))
    assert ranked[0].keyword_score == 12


def test_title_matches_count_double() -> None:
    in_title = rank([make_job(title="Python Developer")], cfg(positive={"python": 15}))
    in_body = rank([make_job(description="We use python")], cfg(positive={"python": 15}))
    assert in_title[0].keyword_score == 30
    assert in_body[0].keyword_score == 15


def test_title_match_does_not_double_count_the_body() -> None:
    """A term in both title and body scores the title value once, not both."""
    job = make_job(title="Python Developer", description="python python python")
    ranked = rank([job], cfg(positive={"python": 15}))
    assert ranked[0].keyword_score == 30


def test_negative_terms_subtract() -> None:
    job = make_job(description="Requires a security clearance.")
    ranked = rank([job], cfg(positive={"security": 30}, negative={"clearance": 10}))
    assert ranked[0].keyword_score == 20


def test_score_never_goes_negative() -> None:
    job = make_job(description="internship unpaid")
    ranked = rank([job], cfg(negative={"unpaid": 500}))
    assert ranked[0].keyword_score == 0


def test_score_is_capped_at_100() -> None:
    job = make_job(title="Python Python", description="python")
    ranked = rank([job], cfg(positive={"python": 90}))
    assert ranked[0].keyword_score == 100


def test_remote_boost_applies() -> None:
    ranked = rank([make_job(remote=True)], cfg(remote_boost=10))
    assert ranked[0].keyword_score == 10


def test_location_boost_applies() -> None:
    job = make_job(location="Stockholm, Stockholms län")
    ranked = rank([job], cfg(locations=["Stockholm", "Remote"]))
    assert ranked[0].keyword_score == 8  # LOCATION_BOOST


def test_remote_pseudo_location_is_not_matched_as_text() -> None:
    """'Remote' in locations is a preference, not a city — it must not award the
    location boost to an on-site job whose address contains the word."""
    job = make_job(location="Stockholm")
    ranked = rank([job], cfg(locations=["Remote"]))
    assert ranked[0].keyword_score == 0


def test_fresher_postings_score_higher() -> None:
    fresh = rank([make_job(posted_at=days_ago(0))], cfg(recency_days=30))
    stale = rank([make_job(posted_at=days_ago(25))], cfg(recency_days=30))
    assert fresh[0].keyword_score > stale[0].keyword_score


def test_recency_boost_expires() -> None:
    ranked = rank([make_job(posted_at=days_ago(60))], cfg(recency_days=30))
    assert ranked[0].keyword_score == 0


def test_score_reasons_explain_the_score() -> None:
    """The tooltip in the viewer reads these, so an unexplained score is a bug."""
    job = make_job(title="Python Developer", remote=True)
    ranked = rank([job], cfg(positive={"python": 15}, remote_boost=10))
    assert "title: python +30" in ranked[0].score_reasons
    assert "remote +10" in ranked[0].score_reasons


# --- percentile normalization ------------------------------------------------


def test_percentiles_span_the_full_range() -> None:
    assert _percentiles([5.0, 1.0, 9.0]) == [50.0, 0.0, 100.0]


def test_percentiles_of_a_single_value() -> None:
    assert _percentiles([7.0]) == [100.0]


def test_tied_values_share_a_percentile() -> None:
    low, mid_a, mid_b, high = _percentiles([0.0, 5.0, 5.0, 9.0])
    assert mid_a == mid_b
    assert low == 0.0
    assert high == 100.0


def test_ranking_is_best_first() -> None:
    weak = make_job(title="Office Manager", source_id="1")
    strong = make_job(title="Python Developer", source_id="2")
    ranked = rank([weak, strong], cfg(positive={"python": 15}))
    assert [j.title for j in ranked] == ["Python Developer", "Office Manager"]


# --- the blend ---------------------------------------------------------------


def test_blend_averages_all_three_signals() -> None:
    job = make_job(relevance_prob=0.5)
    job.keyword_norm = 100.0
    job.semantic_norm = 0.0
    blended = _blend(job, Blend(keyword=0.5, semantic=0.25, relevance=0.25))
    assert blended == pytest.approx(100 * 0.5 + 0 * 0.25 + 50 * 0.25)


def test_missing_signal_redistributes_its_weight() -> None:
    """The documented behaviour — and a trap worth stating out loud.

    Setting relevance: 0.4 does NOT reserve 40% of the score for the classifier
    when no classifier exists. The weight silently vanishes and the remaining
    signals absorb it. With keyword 0.2 / semantic 0.4 and no relevance_prob,
    semantic ends up driving two thirds of the score, not the 0.4 you wrote.
    """
    job = make_job()  # relevance_prob is None
    job.keyword_norm = 0.0
    job.semantic_norm = 100.0
    blended = _blend(job, Blend(keyword=0.2, semantic=0.4, relevance=0.4))
    assert blended == pytest.approx(100 * 0.4 / 0.6)  # ~66.7, not 40


def test_keyword_only_when_nothing_else_is_available() -> None:
    job = make_job()
    job.keyword_norm = 73.0
    assert _blend(job, Blend()) == pytest.approx(73.0)


def test_all_zero_weights_fall_back_to_keyword() -> None:
    """A config of all zeros would divide by zero; we return the keyword score."""
    job = make_job()
    job.keyword_norm = 42.0
    assert _blend(job, Blend(keyword=0, semantic=0, relevance=0)) == pytest.approx(42.0)


def test_semantic_signal_changes_the_order() -> None:
    """Two jobs with identical keyword scores should be separated by CV fit."""
    poor, good = make_job(source_id="1"), make_job(title="ML Engineer", source_id="2")
    poor.semantic_score, good.semantic_score = 0.01, 0.20
    ranked = rank([poor, good], cfg())
    assert ranked[0].source_id == "2"


def test_rank_of_an_empty_list() -> None:
    assert rank([], cfg()) == []
