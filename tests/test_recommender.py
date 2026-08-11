"""TF-IDF CV-to-job similarity, and its graceful-degradation paths."""

from __future__ import annotations

from pathlib import Path

from conftest import make_job
from job_hunter.recommender import add_semantic_scores, load_cv

CV = """
Data scientist with a background in Python, pandas and scikit-learn. Built
machine learning models, natural language processing pipelines and statistical
analyses. Experience with SQL, data visualization and experiment design.
"""


def test_relevant_job_scores_higher_than_an_unrelated_one() -> None:
    """The one property that actually matters: the ordering must be sensible."""
    match = make_job(
        title="Machine Learning Engineer",
        description="Python, scikit-learn and natural language processing pipelines.",
        source_id="1",
    )
    mismatch = make_job(
        title="Pastry Chef",
        description="Baking bread and cakes in a busy kitchen. Early mornings.",
        source_id="2",
    )
    assert add_semantic_scores([match, mismatch], CV) is True
    assert match.semantic_score is not None and mismatch.semantic_score is not None
    assert match.semantic_score > mismatch.semantic_score


def test_scores_are_valid_cosine_similarities() -> None:
    jobs = [make_job(description="Python machine learning")]
    add_semantic_scores(jobs, CV)
    assert jobs[0].semantic_score is not None
    assert 0.0 <= jobs[0].semantic_score <= 1.0


def test_no_cv_skips_scoring() -> None:
    """Before the user writes a CV the pipeline must still run, keyword-only."""
    jobs = [make_job(description="Python machine learning")]
    assert add_semantic_scores(jobs, "") is False
    assert jobs[0].semantic_score is None


def test_no_jobs_is_not_an_error() -> None:
    assert add_semantic_scores([], CV) is False


def test_empty_vocabulary_degrades_gracefully() -> None:
    """A CV of nothing but stop-words leaves TF-IDF with no vocabulary. That
    should cost us the semantic signal, not crash the nightly run."""
    jobs = [make_job(title="the and of", description="the and of")]
    assert add_semantic_scores(jobs, "the and of a in is") is False
    assert jobs[0].semantic_score is None


def test_every_job_gets_a_score() -> None:
    jobs = [make_job(source_id=str(i), description="python data") for i in range(5)]
    add_semantic_scores(jobs, CV)
    assert all(j.semantic_score is not None for j in jobs)


def test_load_cv_missing_file(tmp_path: Path) -> None:
    assert load_cv(tmp_path / "nope.md") == ""


def test_load_cv_strips_html_comments(tmp_path: Path) -> None:
    """The CV template ships with <!-- instructions -->; those words would
    otherwise pollute the similarity scores."""
    path = tmp_path / "cv.md"
    path.write_text("# CV\n<!-- replace this\nwith your own -->\nPython", encoding="utf-8")
    text = load_cv(path)
    assert "replace this" not in text
    assert "Python" in text
