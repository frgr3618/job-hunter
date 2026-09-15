"""JobSpy adapter — scrapes LinkedIn and Indeed (see note below on other sites).

Unlike Platsbanken, this doesn't call an official API: JobSpy (`pip install
python-jobspy`) scrapes each site's own job-search pages. That's a real
departure from this project's original "official APIs only" design — see the
README for why that tradeoff was made and what it means in practice.

Site list, verified by testing against the real installed package (not just
docs) during development:
- linkedin, indeed: work, and cover Sweden.
- google: excluded. Its jobspy scraper is currently broken upstream — even
  the library's own documented example returns 0 results. Open issue:
  https://github.com/speedyapply/JobSpy/issues/302
- glassdoor: excluded. jobspy has no Sweden domain mapping for it; every call
  raises immediately (`Country.glassdoor_domain_value`).
- zip_recruiter, bayt, naukri: never wired in — no Sweden coverage.

`config.sources.jobspy.sites` controls which of these run; google/glassdoor
are still valid config values in case jobspy fixes/adds support later.
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, date, datetime
from typing import Any

import pandas as pd
from jobspy import scrape_jobs

from ..config import ApiKeys, Config
from ..models import Job
from ..remote import looks_remote
from .base import POLITE_DELAY, Source

log = logging.getLogger(__name__)


class Jobspy(Source):
    name = "jobspy"

    def fetch(self, config: Config, keys: ApiKeys) -> list[Job]:
        cfg = config.sources.jobspy
        jobs: list[Job] = []
        first = True
        for site in cfg.sites:
            for query in config.queries:
                if not first:
                    time.sleep(POLITE_DELAY)
                first = False
                try:
                    df = scrape_jobs(
                        site_name=[site],
                        search_term=query,
                        location=cfg.location,
                        country_indeed=cfg.country_indeed,
                        results_wanted=cfg.results_wanted,
                        hours_old=cfg.hours_old,
                    )
                except Exception as exc:  # noqa: BLE001 - one bad (site, query) shouldn't kill the run
                    log.warning("jobspy %s/%r failed: %s", site, query, exc)
                    continue
                if df is None or df.empty:
                    log.info("jobspy %s/%r -> 0 hits", site, query)
                    continue
                log.info("jobspy %s/%r -> %d hits", site, query, len(df))
                jobs.extend(self._to_job(row) for row in df.to_dict("records"))
        return jobs

    def _to_job(self, row: dict[str, Any]) -> Job:
        """Map one jobspy result row onto our normalized `Job`."""
        title = str(row.get("title") or "")
        description = str(row.get("description") or "")
        return Job(
            source=str(row.get("site") or self.name),
            source_id=str(row.get("id") or row.get("job_url") or ""),
            title=title,
            company=str(row.get("company") or ""),
            location=str(row.get("location") or ""),
            # jobspy's own is_remote is a naive "remote" substring check on every
            # site (same false-positive problem remote.py's looks_remote() exists
            # to avoid) — ignored in favor of our own detector, for consistency
            # with platsbanken.py.
            remote=looks_remote(f"{title} {description}"),
            url=str(row.get("job_url") or row.get("job_url_direct") or ""),
            description=description,
            posted_at=_parse_posted(row.get("date_posted")),
            salary=_salary(row),
        )


def _parse_posted(value: Any) -> datetime | None:
    """Normalize jobspy's date_posted, which can arrive as date/Timestamp/NaT."""
    try:
        if value is None or pd.isna(value):
            return None
    except TypeError:
        pass
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time(), tzinfo=UTC)
    return None


def _salary(row: dict[str, Any]) -> str | None:
    """Build a human-readable salary string from jobspy's min/max amount fields."""
    low = _clean_amount(row.get("min_amount"))
    high = _clean_amount(row.get("max_amount"))
    if low is None and high is None:
        return None
    currency = str(row.get("currency") or "").strip()
    interval = str(row.get("interval") or "").strip()
    suffix = " ".join(p for p in (currency, f"/{interval}" if interval else "") if p)
    if low is not None and high is not None and low != high:
        text = f"{low:,}–{high:,}"
    else:
        value = low if low is not None else high
        assert value is not None
        text = f"{value:,}"
    return f"{text} {suffix}".strip() if suffix else text


def _clean_amount(value: Any) -> int | None:
    """jobspy's min/max amounts arrive as a number or NaN; normalize to int|None."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    return int(value)
