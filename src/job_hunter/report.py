"""Write pipeline results to the files the static web site reads.

Everything the site needs lives under `docs/data/` as plain JSON, committed to
git. There's no server: GitHub Pages serves these files and the browser fetches
them. So "publishing" is just writing JSON here.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .models import Job

DATA_DIR = Path("docs/data")
JOBS_PATH = DATA_DIR / "jobs.json"
SEEN_PATH = DATA_DIR / "seen.json"


def write_jobs(jobs: list[Job], generated_at: datetime, path: Path = JOBS_PATH) -> None:
    """Write ranked jobs (plus a timestamp) as jobs.json."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": generated_at.isoformat(),
        "count": len(jobs),
        # mode="json" turns datetimes/dates into strings so json.dumps is happy.
        "jobs": [job.model_dump(mode="json") for job in jobs],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_seen(seen: dict[str, str], path: Path = SEEN_PATH) -> None:
    """Persist the {job_key: first_seen_date} map for the next run's NEW badges."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(seen, ensure_ascii=False, indent=2), encoding="utf-8")
