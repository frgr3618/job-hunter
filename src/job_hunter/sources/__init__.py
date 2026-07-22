"""Job sources: each adapter fetches from one API and returns `Job` objects.

`SOURCES` is a simple registry mapping a name -> Source instance, so the
pipeline (and the `--source` CLI flag) can look them up by name.

NOTE: Adzuna is intentionally NOT registered — its API does not cover Sweden
(every /se/ request 404s). The adapter file is kept for reference / reuse, but
it's disabled until/unless we point it at a supported country.
"""

from __future__ import annotations

from .base import Source
from .platsbanken import Platsbanken

SOURCES: dict[str, Source] = {
    Platsbanken.name: Platsbanken(),
}

__all__ = ["SOURCES", "Source"]
