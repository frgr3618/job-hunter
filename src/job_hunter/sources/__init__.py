"""Job sources: each adapter fetches from one API and returns `Job` objects.

`SOURCES` is a simple registry mapping a name -> Source instance, so the
pipeline (and the `--source` CLI flag) can look them up by name.

(Adzuna gets added here once we write its adapter.)
"""

from __future__ import annotations

from .base import Source
from .platsbanken import Platsbanken

SOURCES: dict[str, Source] = {
    Platsbanken.name: Platsbanken(),
}

__all__ = ["SOURCES", "Source"]
