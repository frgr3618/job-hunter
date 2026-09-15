"""Tests for the JobSpy adapter: DataFrame->Job mapping and fault tolerance.

There's no HTTP-mocking pattern to reuse here (jobspy owns its own HTTP
end-to-end), so these monkeypatch `scrape_jobs` itself — the one function
boundary our adapter calls through.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

import pandas as pd
import pytest

from job_hunter.config import ApiKeys, Config, JobspySite, JobspySource, Sources
from job_hunter.sources import jobspy_source
from job_hunter.sources.jobspy_source import Jobspy

ROW: dict[str, Any] = {
    "id": "li-123",
    "site": "linkedin",
    "job_url": "https://www.linkedin.com/jobs/view/123",
    "job_url_direct": None,
    "title": "Data Analyst",
    "company": "Acme AB",
    "location": "Stockholm, Stockholm County, Sweden",
    "date_posted": date(2026, 9, 10),
    "min_amount": 40000,
    "max_amount": 50000,
    "currency": "SEK",
    "interval": "monthly",
    "is_remote": True,  # deliberately misleading — see test below
    "description": "Join our on-site team in Stockholm, hybrid welcome.",
}


def _config(sites: list[JobspySite], queries: list[str]) -> Config:
    return Config(
        queries=queries,
        sources=Sources(jobspy=JobspySource(sites=sites)),
    )


def test_maps_dataframe_row_to_job(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        jobspy_source, "scrape_jobs", lambda **_kwargs: pd.DataFrame([ROW])
    )

    jobs = Jobspy().fetch(_config(["linkedin"], ["data analyst"]), ApiKeys())

    assert len(jobs) == 1
    job = jobs[0]
    assert job.source == "linkedin"
    assert job.source_id == "li-123"
    assert job.title == "Data Analyst"
    assert job.company == "Acme AB"
    assert job.location == "Stockholm, Stockholm County, Sweden"
    assert job.url == "https://www.linkedin.com/jobs/view/123"
    assert job.posted_at == datetime(2026, 9, 10, tzinfo=UTC)
    assert job.salary == "40,000–50,000 SEK /monthly"
    # jobspy's own is_remote=True is ignored: the text ties the role to an
    # office ("hybrid", "on-site"), so our own looks_remote() says False.
    assert job.remote is False


def test_failure_in_one_call_does_not_lose_others(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_scrape_jobs(**kwargs: Any) -> pd.DataFrame:
        if kwargs["search_term"] == "bad query":
            raise RuntimeError("blocked")
        return pd.DataFrame([ROW])

    monkeypatch.setattr(jobspy_source, "scrape_jobs", fake_scrape_jobs)

    jobs = Jobspy().fetch(
        _config(["linkedin"], ["bad query", "data analyst"]), ApiKeys()
    )

    assert len(jobs) == 1
    assert jobs[0].source_id == "li-123"


def test_empty_dataframe_is_skipped_cleanly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(jobspy_source, "scrape_jobs", lambda **_kwargs: pd.DataFrame())

    jobs = Jobspy().fetch(_config(["linkedin"], ["data analyst"]), ApiKeys())

    assert jobs == []
