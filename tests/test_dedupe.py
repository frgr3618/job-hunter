"""Merging duplicate postings and tracking what's new since the last run."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from conftest import make_job
from job_hunter.dedupe import (
    SEEN_RETENTION_DAYS,
    dedupe,
    load_seen,
    mark_new,
)

TODAY = date(2026, 8, 11)


def test_duplicates_collapse_to_one() -> None:
    jobs = [make_job(source_id="1"), make_job(title="DATA SCIENTIST", source_id="2")]
    assert len(dedupe(jobs)) == 1


def test_longer_description_wins() -> None:
    short = make_job(description="short", source_id="1")
    long = make_job(description="a much longer and fuller description", source_id="2")
    (winner,) = dedupe([short, long])
    assert winner.description == long.description


def test_merge_keeps_the_better_signals_from_the_loser() -> None:
    """The fuller listing wins, but we don't throw away what the other copy knew."""
    rich = make_job(
        description="a much longer and fuller description",
        source_id="1",
        posted_at=datetime(2026, 8, 10),
    )
    sparse = make_job(
        description="short",
        source_id="2",
        remote=True,
        posted_at=datetime(2026, 8, 1),
        salary="45000 SEK",
    )
    (winner,) = dedupe([rich, sparse])
    assert winner.remote is True
    assert winner.salary == "45000 SEK"
    assert winner.posted_at == datetime(2026, 8, 1)  # earliest known posting date


def test_distinct_jobs_survive() -> None:
    jobs = [make_job(title="Data Scientist"), make_job(title="ML Engineer")]
    assert len(dedupe(jobs)) == 2


def test_first_run_marks_everything_new() -> None:
    jobs = [make_job()]
    seen = mark_new(jobs, {}, TODAY)
    assert jobs[0].is_new is True
    assert jobs[0].first_seen == TODAY
    assert seen[jobs[0].job_key] == "2026-08-11"


def test_second_run_is_not_new() -> None:
    """The NEW badge is the whole point of seen.json — it must not re-fire."""
    first = [make_job()]
    seen = mark_new(first, {}, TODAY)
    second = [make_job()]
    mark_new(second, seen, TODAY + timedelta(days=1))
    assert second[0].is_new is False
    assert second[0].first_seen == TODAY  # keeps the original sighting date


def test_stale_entries_are_pruned() -> None:
    old = (TODAY - timedelta(days=SEEN_RETENTION_DAYS + 1)).isoformat()
    seen = mark_new([], {"ancient|corp": old}, TODAY)
    assert "ancient|corp" not in seen


def test_recent_entries_survive_pruning() -> None:
    recent = (TODAY - timedelta(days=SEEN_RETENTION_DAYS - 1)).isoformat()
    seen = mark_new([], {"recent|corp": recent}, TODAY)
    assert "recent|corp" in seen


def test_load_seen_missing_file(tmp_path) -> None:  # type: ignore[no-untyped-def]
    assert load_seen(tmp_path / "nope.json") == {}


def test_load_seen_corrupt_file_does_not_crash(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """A half-written seen.json should cost us NEW badges, not the whole run."""
    path = tmp_path / "seen.json"
    path.write_text("{not valid json", encoding="utf-8")
    assert load_seen(path) == {}


def test_load_seen_roundtrip(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "seen.json"
    path.write_text(json.dumps({"a|b": "2026-08-01"}), encoding="utf-8")
    assert load_seen(path) == {"a|b": "2026-08-01"}
