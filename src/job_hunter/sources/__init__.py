"""Job sources: each adapter fetches jobs from one place and returns `Job`
objects.

`SOURCES` is a simple registry mapping a name -> Source instance, so the
pipeline (and the `--source` CLI flag) can look them up by name.
"""

from __future__ import annotations

from .base import Source
from .jobspy_source import Jobspy
from .platsbanken import Platsbanken

SOURCES: dict[str, Source] = {
    Platsbanken.name: Platsbanken(),
    Jobspy.name: Jobspy(),
}

__all__ = ["SOURCES", "Source"]
