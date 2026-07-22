"""Adzuna adapter — a free, ToS-compliant job-search aggregator covering Sweden.

Docs: https://developer.adzuna.com/ . Requires a free app_id + app_key (from
the environment). If either is missing we skip this source entirely and let
Platsbanken carry the run, so the tool always works out of the box.
"""

from __future__ import annotations

import html
import logging
import re
import time
from typing import Any

from dateutil import parser as date_parser

from ..config import ApiKeys, Config
from ..models import Job
from .base import POLITE_DELAY, Source, build_client, get_json

log = logging.getLogger(__name__)

# {page} is filled in per request; Sweden = the "se" country code.
API_URL = "https://api.adzuna.com/v1/api/jobs/se/search/{page}"
RESULTS_PER_PAGE = 50  # Adzuna's maximum per page

_TAG = re.compile(r"<[^>]+>")
_REMOTE_HINTS = ("distans", "remote", "på distans", "hemifrån", "work from home")


class Adzuna(Source):
    name = "adzuna"

    def fetch(self, config: Config, keys: ApiKeys) -> list[Job]:
        if not keys.has_adzuna:
            log.warning("adzuna skipped: ADZUNA_APP_ID / ADZUNA_APP_KEY not set")
            return []

        max_pages = config.sources.adzuna.max_pages
        jobs: list[Job] = []
        with build_client() as client:
            for query in config.queries:
                for page in range(1, max_pages + 1):
                    if page > 1:
                        time.sleep(POLITE_DELAY)  # be gentle between pages
                    params = {
                        "app_id": keys.adzuna_app_id,
                        "app_key": keys.adzuna_app_key,
                        "results_per_page": RESULTS_PER_PAGE,
                        "what": query,
                        "content-type": "application/json",
                    }
                    try:
                        data = get_json(client, API_URL.format(page=page), params)
                    except Exception as exc:  # noqa: BLE001 - one bad page shouldn't kill the run
                        log.warning("adzuna query %r page %d failed: %s", query, page, exc)
                        break
                    results = data.get("results") or []
                    log.info("adzuna %r page %d -> %d hits", query, page, len(results))
                    jobs.extend(self._to_job(r) for r in results)
                    if len(results) < RESULTS_PER_PAGE:
                        break  # last page for this query
        return jobs

    def _to_job(self, result: dict[str, Any]) -> Job:
        """Map one Adzuna result onto our normalized `Job`."""
        title = _clean(result.get("title"))
        description = _clean(result.get("description"))
        company = _clean((result.get("company") or {}).get("display_name"))
        location = _clean((result.get("location") or {}).get("display_name"))

        return Job(
            source=self.name,
            source_id=str(result.get("id", "")),
            title=title,
            company=company,
            location=location,
            remote=self._is_remote(f"{title} {description}"),
            url=result.get("redirect_url") or "",
            description=description,
            posted_at=_parse_date(result.get("created")),
            salary=_salary(result),
        )

    @staticmethod
    def _is_remote(text: str) -> bool:
        lowered = text.lower()
        return any(hint in lowered for hint in _REMOTE_HINTS)


def _clean(value: str | None) -> str:
    """Strip HTML tags and unescape entities (Adzuna text is HTML fragments)."""
    return _TAG.sub("", html.unescape(value or "")).strip()


def _salary(result: dict[str, Any]) -> str | None:
    """Build a human-readable salary string from Adzuna's min/max, if present."""
    low, high = result.get("salary_min"), result.get("salary_max")
    if low and high and low != high:
        return f"{int(low):,}–{int(high):,} SEK/yr"
    if low:
        return f"{int(low):,} SEK/yr"
    return None


def _parse_date(value: str | None) -> Any:
    if not value:
        return None
    try:
        return date_parser.isoparse(value)
    except (ValueError, TypeError):
        return None
