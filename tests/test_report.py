"""Writing the JSON files the static site reads."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from conftest import make_job
from job_hunter.report import write_jobs, write_seen

GENERATED_AT = datetime(2026, 8, 11, 5, 50, tzinfo=UTC)


def test_writes_the_shape_the_viewer_expects(tmp_path: Path) -> None:
    path = tmp_path / "data" / "jobs.json"
    write_jobs([make_job()], GENERATED_AT, path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["count"] == 1
    assert payload["generated_at"] == "2026-08-11T05:50:00+00:00"
    assert payload["jobs"][0]["job_key"] == "data scientist|acme ab"


def test_creates_the_directory(tmp_path: Path) -> None:
    path = tmp_path / "deep" / "nested" / "jobs.json"
    write_jobs([], GENERATED_AT, path)
    assert path.exists()


def test_dates_are_json_safe(tmp_path: Path) -> None:
    """model_dump(mode='json') is what keeps datetimes from blowing up
    json.dumps — this test fails the moment someone drops that argument."""
    path = tmp_path / "jobs.json"
    job = make_job(posted_at=datetime(2026, 8, 1, tzinfo=UTC))
    job.first_seen = GENERATED_AT.date()
    write_jobs([job], GENERATED_AT, path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["jobs"][0]["posted_at"].startswith("2026-08-01")
    assert payload["jobs"][0]["first_seen"] == "2026-08-11"


def test_non_ascii_survives(tmp_path: Path) -> None:
    """Swedish company names must not come back as \\u00e5 escapes."""
    path = tmp_path / "jobs.json"
    write_jobs([make_job(company="Företaget Åkerström")], GENERATED_AT, path)
    assert "Företaget Åkerström" in path.read_text(encoding="utf-8")


def test_seen_roundtrips(tmp_path: Path) -> None:
    path = tmp_path / "seen.json"
    write_seen({"a|b": "2026-08-01"}, path)
    assert json.loads(path.read_text(encoding="utf-8")) == {"a|b": "2026-08-01"}
