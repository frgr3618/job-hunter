"""Load and validate the user's settings.

Two kinds of settings live outside the code so you can tweak them without
touching Python:

1. `config.yaml` — *what* to search for and *how* to rank (queries, locations,
   ranking weights). Loaded into a validated `Config` object here.
2. `.env` — *secret* API keys (Adzuna, optional Anthropic). Kept out of git.
   Loaded into an `ApiKeys` object.

Validating with pydantic means a typo (e.g. `postive:` instead of `positive:`)
fails immediately with a clear message, instead of silently doing the wrong
thing later.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

# Default locations, relative to wherever job-hunter is run from (repo root).
DEFAULT_CONFIG_PATH = Path("config.yaml")
DEFAULT_ENV_PATH = Path(".env")


class Blend(BaseModel):
    """How the three ranking signals combine into the final score.

    Weights don't have to sum to 1 — rank.py renormalizes them, and drops any
    signal that isn't available yet (no CV → no semantic; no model → no
    relevance).
    """

    model_config = {"extra": "forbid"}

    keyword: float = 0.4
    semantic: float = 0.4
    relevance: float = 0.2


class Ranking(BaseModel):
    """Hand-tuned keyword rules and filters for the keyword score."""

    model_config = {"extra": "forbid"}

    # term -> weight. Presence of the term adds/subtracts that many points.
    positive: dict[str, float] = Field(default_factory=dict)
    negative: dict[str, float] = Field(default_factory=dict)
    # If non-empty, a job must contain at least one of these to survive.
    required: list[str] = Field(default_factory=list)
    # A job is dropped if it contains any of these (matched anywhere in the text).
    excluded: list[str] = Field(default_factory=list)
    # A job is dropped if any of these appear in its TITLE only. Use this for
    # seniority ("senior", "lead") so a junior role that merely mentions a senior
    # colleague in its description isn't wrongly removed.
    excluded_titles: list[str] = Field(default_factory=list)
    # If true, drop ads that look like they're written in Swedish (keep English).
    english_only: bool = False
    # If true, keep only jobs that are remote or in one of `locations`. Jobs with
    # no location at all are kept — we don't drop what we can't measure.
    location_filter: bool = False
    # Years of experience you can credibly claim. Ads asking for more are pushed
    # down by `experience_penalty` points per extra year. 0 disables the whole
    # thing. This is a penalty, not a filter, because ads overstate what they
    # need and the good ones are worth stretching for.
    max_years_experience: int = 0
    # Points subtracted per year of experience demanded beyond max_years_experience.
    experience_penalty: float = 8.0
    # Set true to drop over-experienced ads outright instead of demoting them.
    # Off by default: it hides roles you'd probably still apply for.
    drop_over_experience: bool = False
    # Linear recency boost applied within this many days of posting.
    recency_days: int = 30
    # Hard cutoff: drop postings older than this many days (0 = keep all ages).
    # Jobs with no posting date are always kept.
    max_age_days: int = 0
    # Extra points for remote roles.
    remote_boost: float = 10.0


class PlatsbankenSource(BaseModel):
    model_config = {"extra": "forbid"}
    limit: int = 100  # results per query (JobTech caps a single request at 100)


class AdzunaSource(BaseModel):
    model_config = {"extra": "forbid"}
    max_pages: int = 3  # 50 results per page


class Sources(BaseModel):
    model_config = {"extra": "forbid"}
    platsbanken: PlatsbankenSource = Field(default_factory=PlatsbankenSource)
    adzuna: AdzunaSource = Field(default_factory=AdzunaSource)


class Config(BaseModel):
    """The whole `config.yaml`, validated."""

    model_config = {"extra": "forbid"}

    queries: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    blend: Blend = Field(default_factory=Blend)
    ranking: Ranking = Field(default_factory=Ranking)
    sources: Sources = Field(default_factory=Sources)

    @classmethod
    def load(cls, path: Path = DEFAULT_CONFIG_PATH) -> Config:
        """Read and validate config.yaml (or use all-defaults if it's missing)."""
        if not path.exists():
            return cls()
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return cls.model_validate(raw)


class ApiKeys(BaseModel):
    """Secret keys read from the environment (never from config.yaml/git)."""

    adzuna_app_id: str | None = None
    adzuna_app_key: str | None = None
    anthropic_api_key: str | None = None

    @property
    def has_adzuna(self) -> bool:
        """True only if BOTH Adzuna keys are present; else that source is skipped."""
        return bool(self.adzuna_app_id and self.adzuna_app_key)

    @classmethod
    def load(cls, env_path: Path = DEFAULT_ENV_PATH) -> ApiKeys:
        """Load keys from a local .env file (if present) plus real env vars.

        Real environment variables win over the .env file, which is what we
        want in CI where secrets are injected as env vars.
        """
        _load_dotenv(env_path)
        return cls(
            adzuna_app_id=os.environ.get("ADZUNA_APP_ID") or None,
            adzuna_app_key=os.environ.get("ADZUNA_APP_KEY") or None,
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY") or None,
        )


def _load_dotenv(path: Path) -> None:
    """Minimal .env reader: set KEY=VALUE lines into os.environ if not already set.

    We parse it by hand (a few lines) rather than add a dependency. Existing
    environment variables are never overwritten.
    """
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value
