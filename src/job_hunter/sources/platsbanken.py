"""Platsbanken adapter via Sweden's official JobTech JobSearch API.

Docs: https://jobsearch.api.jobtechdev.se/ — free, no authentication. We send
one search request per configured query and normalize each hit into a `Job`.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from dateutil import parser as date_parser

from ..config import ApiKeys, Config
from ..models import Job
from .base import POLITE_DELAY, Source, build_client, get_json

log = logging.getLogger(__name__)

API_URL = "https://jobsearch.api.jobtechdev.se/search"
MAX_PER_REQUEST = 100  # JobTech caps a single request at 100 results

# Words that signal a remote role when the API doesn't flag it explicitly.
_REMOTE_HINTS = ("distans", "remote", "på distans", "hemifrån", "work from home")


class Platsbanken(Source):
    name = "platsbanken"

    def fetch(self, config: Config, keys: ApiKeys) -> list[Job]:
        limit = min(config.sources.platsbanken.limit, MAX_PER_REQUEST)
        jobs: list[Job] = []
        with build_client() as client:
            for i, query in enumerate(config.queries):
                if i:
                    time.sleep(POLITE_DELAY)  # be gentle between queries
                try:
                    data = get_json(client, API_URL, {"q": query, "limit": limit, "offset": 0})
                except Exception as exc:  # noqa: BLE001 - one bad query shouldn't kill the run
                    log.warning("platsbanken query %r failed: %s", query, exc)
                    continue
                hits = data.get("hits") or []
                log.info("platsbanken %r -> %d hits", query, len(hits))
                jobs.extend(self._to_job(h) for h in hits)
        return jobs

    def _to_job(self, hit: dict[str, Any]) -> Job:
        """Map one JobTech hit onto our normalized `Job`."""
        employer = hit.get("employer") or {}
        address = hit.get("workplace_address") or {}
        description = (hit.get("description") or {}).get("text") or ""

        location = ", ".join(
            part for part in (address.get("municipality"), address.get("region")) if part
        )
        url = hit.get("webpage_url") or (hit.get("application_details") or {}).get("url") or ""

        return Job(
            source=self.name,
            source_id=str(hit.get("id", "")),
            title=hit.get("headline") or "",
            company=employer.get("name") or "",
            location=location,
            remote=self._is_remote(hit, description),
            url=url,
            description=description,
            posted_at=_parse_date(hit.get("publication_date")),
            salary=hit.get("salary_description"),
        )

    @staticmethod
    def _is_remote(hit: dict[str, Any], description: str) -> bool:
        """Use an explicit remote flag if present, else scan the text for hints."""
        for key in ("remote_work", "remote"):
            value = hit.get(key)
            if isinstance(value, bool):
                return value
        text = f"{hit.get('headline', '')} {description}".lower()
        return any(hint in text for hint in _REMOTE_HINTS)


def _parse_date(value: str | None) -> Any:
    """Parse an ISO date string; return None if missing/unparseable."""
    if not value:
        return None
    try:
        return date_parser.isoparse(value)
    except (ValueError, TypeError):
        return None
