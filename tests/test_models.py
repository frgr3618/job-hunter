"""The Job model, and the identity key everything else depends on."""

from __future__ import annotations

from conftest import make_job
from job_hunter.models import normalize_key_part


def test_normalize_collapses_case_and_whitespace() -> None:
    assert normalize_key_part("  Data   Scientist\n") == "data scientist"


def test_same_role_and_company_share_a_key_despite_formatting() -> None:
    """Dedupe leans entirely on this: cosmetic differences must not split a job."""
    a = make_job(title="Data Scientist", company="Acme AB")
    b = make_job(title="  DATA   scientist ", company="acme ab")
    assert a.job_key == b.job_key


def test_different_companies_do_not_collide() -> None:
    a = make_job(title="Data Scientist", company="Acme AB")
    b = make_job(title="Data Scientist", company="Globex")
    assert a.job_key != b.job_key


def test_job_key_is_serialized() -> None:
    """The web viewer keys thumbs-up/down feedback off job_key, so it must be
    present in jobs.json — not just on the Python object."""
    assert "job_key" in make_job().model_dump(mode="json")


def test_ml_signals_default_to_none() -> None:
    """None means 'not computed', which is what lets rank.py drop a signal
    instead of blending a misleading zero."""
    job = make_job()
    assert job.keyword_score is None
    assert job.semantic_score is None
    assert job.relevance_prob is None
