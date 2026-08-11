"""Score and order jobs by how well they match what you want.

Today this computes the *keyword* score from your `config.yaml` rules. The final
`Job.score` is set to that keyword score for now; later we'll blend in the
semantic (CV similarity) and relevance (trained classifier) signals. Keeping the
scoring here in one place makes that extension a small change.

Every job also gets `score_reasons` — short strings like "title: python +30" —
so the report can explain *why* a job ranked where it did.
"""

from __future__ import annotations

import bisect
import re
from datetime import UTC, datetime
from functools import lru_cache

from .config import Blend, Config
from .experience import required_years, seniority_gap
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
        if _too_old(job, ranking.max_age_days):
            continue
        if ranking.english_only and not is_english(f"{job.title} {job.description}"):
            continue
        if ranking.location_filter and _wrong_location(job, config):
            continue
        job.years_required = required_years(f"{job.title} {job.description}")
        if _experience_gap(job, config) and ranking.drop_over_experience:
            continue
        job.keyword_score = _keyword_score(job, config)  # also fills score_reasons
        kept.append(job)

    # Rescale each raw signal to a 0-100 percentile within this batch, so the
    # blend weights control real influence regardless of the signals' raw scales.
    _assign_norms(kept)
    for job in kept:
        job.score = _blend(job, config.blend)
    kept.sort(key=lambda j: j.score, reverse=True)
    return kept


def _assign_norms(jobs: list[Job]) -> None:
    """Set keyword_norm / semantic_norm as within-batch percentiles (0-100)."""
    if not jobs:
        return
    keyword_pct = _percentiles([j.keyword_score or 0.0 for j in jobs])
    has_semantic = any(j.semantic_score is not None for j in jobs)
    semantic_pct = _percentiles([j.semantic_score or 0.0 for j in jobs]) if has_semantic else None
    for i, job in enumerate(jobs):
        job.keyword_norm = keyword_pct[i]
        job.semantic_norm = semantic_pct[i] if semantic_pct is not None else None
        if job.semantic_norm is not None:
            job.score_reasons.append(f"cv match {job.semantic_norm:.0f}th pct")


def _percentiles(values: list[float]) -> list[float]:
    """Map each value to its percentile rank (0-100) among all values.

    Ties share the average rank; the min maps to 0 and the max to 100. This
    makes the semantic signal (tiny cosine numbers) comparable to the keyword
    signal (tens of points) before they're blended.
    """
    n = len(values)
    if n == 1:
        return [100.0]
    ordered = sorted(values)
    out: list[float] = []
    for value in values:
        low = bisect.bisect_left(ordered, value)   # count strictly less
        high = bisect.bisect_right(ordered, value)  # count <= value
        midrank = (low + high - 1) / 2               # average 0-based rank for ties
        out.append(midrank / (n - 1) * 100)
    return out


def _blend(job: Job, blend: Blend) -> float:
    """Combine the available normalized (0-100) signals using config weights.

    Keyword is always present. Semantic (CV similarity) and relevance join only
    when available. Weights are renormalized over whatever's present, so dropping
    a signal shifts its share to the others rather than shrinking the score.
    """
    parts: list[tuple[float, float]] = [(blend.keyword, job.keyword_norm or 0.0)]
    if job.semantic_norm is not None:
        parts.append((blend.semantic, job.semantic_norm))
    if job.relevance_prob is not None:
        parts.append((blend.relevance, job.relevance_prob * 100))

    total_weight = sum(weight for weight, _ in parts)
    if total_weight <= 0:
        return job.keyword_norm or 0.0
    return sum(weight * value for weight, value in parts) / total_weight


def _experience_gap(job: Job, config: Config) -> int:
    """Years demanded beyond what you have (0 when within reach or disabled).

    `max_years_experience: 0` turns the whole thing off, matching how
    `max_age_days: 0` disables the age cutoff.
    """
    max_years = config.ranking.max_years_experience
    if max_years <= 0:
        return 0
    return seniority_gap(job.years_required, max_years)


def _wrong_location(job: Job, config: Config) -> bool:
    """True if taking this job would mean showing up at an office you can't reach.

    The rule: a wanted city (on-site or hybrid, doesn't matter), or fully remote
    with no office anywhere. Everything else goes — a hybrid role in Göteborg is
    a Göteborg job however few days a week it asks for.

    When the location field is blank we read the ad text instead of guessing;
    an unnamed city is not an excuse to show a job you can't take.
    """
    if job.remote:  # remote.py already rejects hybrid/on-site wording
        return False
    if job.location.strip():
        return not _matches_location(job, config)
    return not _mentions_wanted_location(job, config)


def _mentions_wanted_location(job: Job, config: Config) -> bool:
    """True if the ad's text names one of your cities (used when there's no
    location field — plenty of ads say 'based in Stockholm' in the body)."""
    text = f"{job.title} {job.description}".lower()
    return any(
        _contains(wanted.lower(), text)
        for wanted in config.locations
        if wanted.lower() != "remote"
    )


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
    # Drop when required terms are configured but none is present.
    # bool(...) keeps the return type a plain bool (an empty list is falsy but not False).
    return bool(ranking.required) and not any(
        _contains(term, haystack) for term in ranking.required
    )


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

    # Over-experienced ads sink rather than disappear: you'd still apply to a
    # great role asking for one more year than you have.
    gap = _experience_gap(job, config)
    if gap:
        penalty = gap * ranking.experience_penalty
        score -= penalty
        reasons.append(f"wants {job.years_required}y exp -{penalty:g}")

    job.score_reasons = reasons
    return _clamp(score, 0.0, 100.0)


def _too_old(job: Job, max_age_days: int) -> bool:
    """True if the posting is older than `max_age_days` (0 disables the filter).

    Jobs with no posting date are kept — we don't drop what we can't measure.
    """
    if max_age_days <= 0 or job.posted_at is None:
        return False
    posted = job.posted_at
    if posted.tzinfo is None:  # treat naive timestamps as UTC
        posted = posted.replace(tzinfo=UTC)
    age_days = (datetime.now(UTC) - posted).total_seconds() / 86400
    return age_days > max_age_days


def _recency_boost(job: Job, recency_days: int) -> float:
    """Full RECENCY_MAX for a brand-new post, fading to 0 at `recency_days`."""
    if job.posted_at is None or recency_days <= 0:
        return 0.0
    now = datetime.now(UTC)
    posted = job.posted_at
    if posted.tzinfo is None:  # treat naive timestamps as UTC
        posted = posted.replace(tzinfo=UTC)
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
