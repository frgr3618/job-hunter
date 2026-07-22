"""The end-to-end daily pipeline: fetch -> dedupe -> mark new -> rank -> write.

This is the one function the CLI (and the GitHub Action) calls. Keeping the
orchestration here, separate from the CLI plumbing, makes it easy to test and to
reuse from other entry points later.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from .config import ApiKeys, Config
from .dedupe import dedupe, load_seen, mark_new
from .rank import rank
from .recommender import add_semantic_scores, load_cv
from .report import SEEN_PATH, write_jobs, write_seen
from .sources import SOURCES
from .models import Job

log = logging.getLogger(__name__)


@dataclass
class RunResult:
    """Summary of a pipeline run, returned to the CLI for printing."""

    jobs: list[Job]
    fetched: int
    per_source: dict[str, int]


def run(
    config: Config,
    keys: ApiKeys,
    source_names: list[str] | None = None,
    dry_run: bool = False,
) -> RunResult:
    """Run the full pipeline and (unless dry_run) write jobs.json + seen.json."""
    sources = _select_sources(source_names)

    raw: list[Job] = []
    per_source: dict[str, int] = {}
    for source in sources:
        fetched = source.fetch(config, keys)
        per_source[source.name] = len(fetched)
        log.info("%s -> %d jobs", source.name, len(fetched))
        raw.extend(fetched)

    deduped = dedupe(raw)
    log.info("deduped %d -> %d", len(raw), len(deduped))

    today = datetime.now(timezone.utc).date()
    seen = load_seen(SEEN_PATH)
    updated_seen = mark_new(deduped, seen, today)

    # Semantic layer: score each job by how similar its text is to the CV.
    add_semantic_scores(deduped, load_cv())

    ranked = rank(deduped, config)
    log.info("ranked %d jobs (after filters)", len(ranked))

    if not dry_run:
        write_jobs(ranked, generated_at=datetime.now(timezone.utc))
        write_seen(updated_seen)
        log.info("wrote docs/data/jobs.json and seen.json")

    return RunResult(jobs=ranked, fetched=len(raw), per_source=per_source)


def _select_sources(source_names: list[str] | None):
    """Pick sources by name (or all of them if none specified)."""
    if not source_names:
        return list(SOURCES.values())
    chosen = []
    for name in source_names:
        source = SOURCES.get(name)
        if source is None:
            raise SystemExit(
                f"unknown source {name!r}; available: {', '.join(SOURCES)}"
            )
        chosen.append(source)
    return chosen
