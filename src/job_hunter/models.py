"""The core data structures the whole pipeline passes around.

Everything in job-hunter revolves around one shape: `Job`. Each source adapter
(Platsbanken, Adzuna) converts its own API response into a list of `Job`
objects, so the rest of the code never has to care where a job came from.

We use pydantic's `BaseModel`: we declare the fields and their types, and
pydantic validates incoming data and gives us clean attribute access
(`job.title`) plus easy JSON conversion (`job.model_dump()`).
"""

from __future__ import annotations

import re
from datetime import date, datetime

from pydantic import BaseModel, Field

# Collapses any run of whitespace into a single space; used to normalize the
# title/company text before we build a job's identity key.
_WHITESPACE = re.compile(r"\s+")


def normalize_key_part(text: str) -> str:
    """Lowercase, strip, and collapse inner whitespace — for stable matching."""
    return _WHITESPACE.sub(" ", text).strip().lower()


class Job(BaseModel):
    """One normalized job posting, shared across all sources and the ML layer."""

    # --- where it came from ---
    source: str  # "platsbanken" | "adzuna"
    source_id: str  # the id this source assigned the posting

    # --- the posting itself ---
    title: str
    company: str
    location: str = ""  # human-readable "city, region" string
    remote: bool = False
    url: str
    description: str = ""
    posted_at: datetime | None = None
    salary: str | None = None  # free-text, only some sources provide it

    # --- tracking: filled in by the dedupe / "what's new" step ---
    first_seen: date | None = None
    is_new: bool = False

    # --- final ranking, filled in by rank.py ---
    score: float = 0.0
    score_reasons: list[str] = Field(default_factory=list)

    # --- individual ML signals that get blended into `score` ---
    # Each is optional so the system still works before the CV/model exist.
    keyword_score: float | None = None  # from hand-tuned keyword rules
    semantic_score: float | None = None  # TF-IDF cosine similarity to the CV
    relevance_prob: float | None = None  # trained classifier probability
    skills: list[str] = Field(default_factory=list)  # extracted skill tags
    fit_summary: str | None = None  # optional LLM fit/gap note

    @property
    def job_key(self) -> str:
        """Identity used for dedupe and 'new since last run' tracking.

        Two postings of the same role at the same company collapse to one key,
        even across sources or with minor whitespace/casing differences.
        """
        return f"{normalize_key_part(self.title)}|{normalize_key_part(self.company)}"
