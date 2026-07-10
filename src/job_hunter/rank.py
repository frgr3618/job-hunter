"""Score and order jobs by how well they match what you want.

Today this computes the *keyword* score from your `config.yaml` rules. The final
`Job.score` is set to that keyword score for now; later we'll blend in the
semantic (CV similarity) and relevance (trained classifier) signals. Keeping the
scoring here in one place makes that extension a small change.

Every job also gets `score_reasons` — short strings like "title: python +30" —
so the report can explain *why* a job ranked where it did.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from functools import lru_cache

from .config import Config
from .language import is_english
from .models import Job

# How many points a fresh-vs-old posting and a location match are worth.
RECENCY_MAX = 10.0
LOCATION_BOOST = 8.0


@lru_cache(maxsize=512)
def _term_pattern(term: str) -> re.Pattern[str]:
    """Compile a whole-word matcher for `term` (cached; terms repeat every run).

    We treat letters/digits as 'word' characters, so `ai` matches the word "AI"
    but not the "ai" inside "available" or "training". Multi-word terms like
    "machine learning" and punctuated ones like ".net" work too.
    """
    return re.compile(rf"(?<![a-z0-9]){re.escape(term.lower())}(?![a-z0-9])")


def _contains(term: str, text: str) -> bool:
    """True if `term` appears as a whole word in the already-lowercased `text`."""
    return _term_pattern(term).search(text) is not None


def rank(jobs: list[Job], config: Config) -> list[Job]:
    """Filter out unwanted jobs, score the rest, and return them best-first."""
    ranking = config.ranking
    kept: list[Job] = []
    for job in jobs:
        if _is_excluded(job, config):
            continue
        if ranking.english_only and not is_english(f"{job.title} {job.description}"):
            continue
        job.keyword_score = _keyword_score(job, config)
        job.score = job.keyword_score  # keyword-only blend for now
        kept.append(job)
    kept.sort(key=lambda j: j.score, reverse=True)
    return kept


def _searchable_text(job: Job) -> tuple[str, str]:
    """Return (title_text, body_text), both lowercased, for term matching."""
    title = job.title.lower()
    body = f"{job.description} {job.location}".lower()
    return title, body


def _is_excluded(job: Job, config: Config) -> bool:
    """Drop rules: excluded term anywhere, excluded term in the title, or no
    required term present."""
    ranking = config.ranking
    title, body = _searchable_text(job)
    # Company name is included here so excluding "consulting" also drops
    # consultancy firms, not just ads that use the word in their description.
    haystack = f"{title} {body} {job.company.lower()}"
    # Title-only exclusion — the right tool for seniority filtering.
    if any(_contains(term, title) for term in ranking.excluded_titles):
        return True
    if any(_contains(term, haystack) for term in ranking.excluded):
        return True
    if ranking.required and not any(_contains(term, haystack) for term in ranking.required):
        return True
    return False


def _keyword_score(job: Job, config: Config) -> float:
    """Compute a 0-100 keyword score and populate `job.score_reasons`."""
    ranking = config.ranking
    title, body = _searchable_text(job)
    reasons: list[str] = []
    score = 0.0

    # Positive terms: a match in the title counts double (it's a stronger signal).
    for term, weight in ranking.positive.items():
        if _contains(term, title):
            score += weight * 2
            reasons.append(f"title: {term} +{weight * 2:g}")
        elif _contains(term, body):
            score += weight
            reasons.append(f"{term} +{weight:g}")

    # Negative terms: subtract wherever they appear.
    haystack = f"{title} {body}"
    for term, weight in ranking.negative.items():
        if _contains(term, haystack):
            score -= weight
            reasons.append(f"{term} -{weight:g}")

    # Recency: linearly more points the fresher the posting is.
    recency = _recency_boost(job, ranking.recency_days)
    if recency:
        score += recency
        reasons.append(f"recent +{recency:.0f}")

    # Remote and preferred-location boosts.
    if job.remote and ranking.remote_boost:
        score += ranking.remote_boost
        reasons.append(f"remote +{ranking.remote_boost:g}")
    if _matches_location(job, config):
        score += LOCATION_BOOST
        reasons.append(f"location +{LOCATION_BOOST:g}")

    job.score_reasons = reasons
    return _clamp(score, 0.0, 100.0)


def _recency_boost(job: Job, recency_days: int) -> float:
    """Full RECENCY_MAX for a brand-new post, fading to 0 at `recency_days`."""
    if job.posted_at is None or recency_days <= 0:
        return 0.0
    now = datetime.now(timezone.utc)
    posted = job.posted_at
    if posted.tzinfo is None:  # treat naive timestamps as UTC
        posted = posted.replace(tzinfo=timezone.utc)
    age_days = (now - posted).total_seconds() / 86400
    if age_days < 0 or age_days > recency_days:
        return 0.0
    return RECENCY_MAX * (1 - age_days / recency_days)


def _matches_location(job: Job, config: Config) -> bool:
    """True if any configured non-remote location appears in the job's location."""
    location = job.location.lower()
    for wanted in config.locations:
        w = wanted.lower()
        if w == "remote":
            continue
        if w in location:
            return True
    return False


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
