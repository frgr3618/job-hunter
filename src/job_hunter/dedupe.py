"""Collapse duplicate postings and track which jobs are new since last run.

Two responsibilities:
1. `dedupe()` — merge jobs that share a `job_key` (same title+company) into one
   richest record, even if they came from different sources or paged twice.
2. `seen.json` handling — a small persisted file mapping job_key -> the date we
   first saw it. This is how we can show a "NEW" badge for postings that weren't
   in any previous run.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

from .models import Job

# Forget jobs we haven't seen in this many days, to keep seen.json small.
SEEN_RETENTION_DAYS = 60


def dedupe(jobs: list[Job]) -> list[Job]:
    """Merge jobs sharing a job_key; keep the richest, earliest, most-remote copy."""
    best: dict[str, Job] = {}
    for job in jobs:
        key = job.job_key
        existing = best.get(key)
        if existing is None:
            best[key] = job
            continue
        # Keep whichever has the longer description (usually the fuller listing)...
        winner = job if len(job.description) > len(existing.description) else existing
        loser = existing if winner is job else job
        # ...but carry over the better signals from the other copy.
        winner.remote = winner.remote or loser.remote
        winner.posted_at = _earliest(winner.posted_at, loser.posted_at)
        if not winner.salary and loser.salary:
            winner.salary = loser.salary
        best[key] = winner
    return list(best.values())


def _earliest(a: datetime | None, b: datetime | None) -> datetime | None:
    """Return the earlier of two datetimes, ignoring any that are None."""
    dates = [d for d in (a, b) if d is not None]
    return min(dates) if dates else None


def load_seen(path: Path) -> dict[str, str]:
    """Load the {job_key: first_seen_date} map, or empty if the file is absent."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def mark_new(jobs: list[Job], seen: dict[str, str], today: date) -> dict[str, str]:
    """Fill each job's `first_seen`/`is_new`, and return the updated seen map.

    A job is NEW if its key isn't already in `seen`. We record today's date for
    first-time keys and prune entries older than SEEN_RETENTION_DAYS.
    """
    today_str = today.isoformat()
    for job in jobs:
        key = job.job_key
        if key in seen:
            job.first_seen = _parse_iso_date(seen[key]) or today
            job.is_new = False
        else:
            seen[key] = today_str
            job.first_seen = today
            job.is_new = True
    return _prune_seen(seen, today)


def _prune_seen(seen: dict[str, str], today: date) -> dict[str, str]:
    """Drop entries first seen more than SEEN_RETENTION_DAYS ago."""
    cutoff = today - timedelta(days=SEEN_RETENTION_DAYS)
    return {
        key: value
        for key, value in seen.items()
        if (_parse_iso_date(value) or today) >= cutoff
    }


def _parse_iso_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        return None
