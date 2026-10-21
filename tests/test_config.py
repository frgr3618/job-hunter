"""Config loading and validation — the safety net against silent typos."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from job_hunter.config import ApiKeys, Config, _load_dotenv

VALID = """
queries: [data scientist]
locations: [Stockholm, Remote]
blend:
  keyword: 0.3
  semantic: 0.5
  relevance: 0.2
ranking:
  positive:
    python: 15
  excluded_titles: [senior]
  drop_if_swedish_required: true
"""


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_loads_a_valid_config(tmp_path: Path) -> None:
    config = Config.load(write(tmp_path, VALID))
    assert config.queries == ["data scientist"]
    assert config.blend.semantic == 0.5
    assert config.ranking.positive["python"] == 15
    assert config.ranking.drop_if_swedish_required is True


def test_missing_file_falls_back_to_defaults(tmp_path: Path) -> None:
    config = Config.load(tmp_path / "absent.yaml")
    assert config.queries == []
    assert config.blend.keyword == 0.4


def test_empty_file_falls_back_to_defaults(tmp_path: Path) -> None:
    assert Config.load(write(tmp_path, "")).queries == []


def test_typo_in_a_key_is_rejected(tmp_path: Path) -> None:
    """`postive:` instead of `positive:` must fail loudly, not rank on nothing.

    This is the entire reason for extra='forbid'.
    """
    with pytest.raises(ValidationError):
        Config.load(write(tmp_path, "ranking:\n  postive:\n    python: 15\n"))


def test_unknown_top_level_key_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        Config.load(write(tmp_path, "queries: [x]\nnonsense: true\n"))


def test_wrong_type_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        Config.load(write(tmp_path, "queries: not-a-list\n"))


def test_shipped_config_is_valid() -> None:
    """The real config.yaml in the repo must always load — if this fails, the
    nightly scrape is already broken."""
    config = Config.load(Path("config.yaml"))
    assert config.queries
    # google/glassdoor are broken/unsupported for Sweden in jobspy right now
    # (see sources/jobspy_source.py) — the shipped default must not include them.
    assert config.sources.jobspy.sites == ["linkedin", "indeed"]
    # Consultancies are fine (his rule since 2026-10-14): neither dropped nor
    # scored down. The viewer still tags them, for information only.
    assert "consultant" not in config.ranking.excluded
    assert "consulting" not in config.ranking.excluded
    assert "consultant" not in config.ranking.negative
    assert "consulting" not in config.ranking.negative
    assert config.ranking.max_age_days == 30
    assert config.ranking.max_years_experience == 3
    # Roles chosen 2026-10-21 from the master CV + live Platsbanken counts.
    # NLP engineer dropped: no openings in Sweden.
    assert config.queries == [
        "data scientist",
        "machine learning engineer",
        "AI engineer",
        "data engineer",
        "analytics engineer",
        "AI-specialist",
        "data analyst",
    ]
    # Evaluation shows up inside AI/ML ads rather than as a job title.
    assert config.ranking.positive["evaluation"] > 0
    assert config.ranking.positive["LLM"] > 0
    # Gothenburg added 2026-10-21, under both spellings the sources use.
    assert {"Stockholm", "Uppsala", "Remote", "Göteborg", "Gothenburg"} <= set(
        config.locations
    )


# --- .env handling -----------------------------------------------------------


def test_dotenv_does_not_override_real_env_vars(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CI injects secrets as real env vars; a stale .env must never win."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "from-ci")
    env = tmp_path / ".env"
    env.write_text("ANTHROPIC_API_KEY=from-file\n", encoding="utf-8")
    _load_dotenv(env)
    assert ApiKeys.load(env).anthropic_api_key == "from-ci"


def test_dotenv_strips_quotes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    env = tmp_path / ".env"
    env.write_text('# a comment\nANTHROPIC_API_KEY="quoted-value"\n', encoding="utf-8")
    _load_dotenv(env)
    assert ApiKeys.load(env).anthropic_api_key == "quoted-value"
