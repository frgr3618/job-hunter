"""Shared, 'safe by construction' HTTP layer for all sources.

Even though we only call well-behaved public APIs, we still want to be a polite
network citizen: identify ourselves, use sane timeouts, back off and retry on
transient errors, and honor the server's `Retry-After` when rate-limited. Doing
this once here keeps every adapter simple and consistent.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any

import httpx

from ..config import ApiKeys, Config
from ..models import Job

log = logging.getLogger(__name__)

# Identify ourselves honestly so API operators can see who's calling.
USER_AGENT = "job-hunter/0.1 (+https://github.com/; personal job search)"
DEFAULT_TIMEOUT = 20.0  # seconds before we give up on a single request
MAX_RETRIES = 3  # attempts for transient failures (timeouts, 429, 5xx)
POLITE_DELAY = 0.5  # seconds to pause between paged requests

# Status codes worth retrying: rate-limit + server-side errors.
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def build_client() -> httpx.Client:
    """Create a reusable HTTP client with our headers and timeout."""
    return httpx.Client(
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        timeout=DEFAULT_TIMEOUT,
    )


def get_json(
    client: httpx.Client,
    url: str,
    params: dict[str, Any],
    *,
    max_retries: int = MAX_RETRIES,
) -> dict[str, Any]:
    """GET `url` and parse JSON, retrying transient failures with backoff.

    Raises the last error if every attempt fails, so the caller can decide
    whether to skip that source or abort.
    """
    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            response = client.get(url, params=params)
            if response.status_code in _RETRYABLE_STATUS:
                wait = _retry_after_seconds(response, attempt)
                log.warning(
                    "%s -> %s, retrying in %.1fs (attempt %d/%d)",
                    url, response.status_code, wait, attempt, max_retries,
                )
                time.sleep(wait)
                continue
            response.raise_for_status()  # raise on other 4xx (e.g. bad request)
            return response.json()
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            last_error = exc
            if attempt == max_retries:
                break
            wait = POLITE_DELAY * attempt
            log.warning("request error %s, retrying in %.1fs", exc, wait)
            time.sleep(wait)
    assert last_error is not None
    raise last_error


def _retry_after_seconds(response: httpx.Response, attempt: int) -> float:
    """Respect a numeric `Retry-After` header; else exponential-ish backoff."""
    header = response.headers.get("Retry-After")
    if header and header.isdigit():
        return float(header)
    return POLITE_DELAY * (2**attempt)


class Source(ABC):
    """Base class every job source implements.

    Subclasses set a `name` and implement `fetch`, which turns config +
    keys into a list of normalized `Job` objects.
    """

    name: str

    @abstractmethod
    def fetch(self, config: Config, keys: ApiKeys) -> list[Job]:
        """Return jobs for all configured queries. Must not raise on empty results."""
        raise NotImplementedError
