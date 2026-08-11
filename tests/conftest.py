"""Shared builders for the test suite.

`make_job` exists so each test can state only the fields it actually cares
about. A test about seniority filtering shouldn't have to invent a URL.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from job_hunter.models import Job


def make_job(
    title: str = "Data Scientist",
    company: str = "Acme AB",
    *,
    description: str = "",
    location: str = "",
    remote: bool = False,
    posted_at: datetime | None = None,
    source: str = "platsbanken",
    source_id: str = "1",
    **extra: Any,
) -> Job:
    """Build a Job with sensible defaults for everything the test ignores."""
    return Job(
        source=source,
        source_id=source_id,
        title=title,
        company=company,
        location=location,
        remote=remote,
        url=f"https://example.com/{source_id}",
        description=description,
        posted_at=posted_at,
        **extra,
    )


def days_ago(days: float) -> datetime:
    """A timezone-aware timestamp `days` in the past."""
    return datetime.now(UTC) - timedelta(days=days)
