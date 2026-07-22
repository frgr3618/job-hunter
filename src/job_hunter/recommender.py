"""Semantic matching: how similar is each job's text to your CV?

This is the content-based recommender. It represents your CV and every job as
TF-IDF vectors (words weighted by how distinctive they are), then scores each
job by the cosine similarity between it and the CV — a number from 0 (nothing in
common) to 1 (very similar). That `semantic_score` gets blended into the final
ranking alongside the keyword score.

Why TF-IDF and not neural embeddings? Zero recurring cost and no gigabyte model
download (a project constraint). The interface here is model-agnostic, so a
neural embedder could be swapped in later without touching the rest of the code.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

from .models import Job

log = logging.getLogger(__name__)

CV_PATH = Path("cv.md")
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


def load_cv(path: Path = CV_PATH) -> str:
    """Read cv.md as plain text, stripping HTML comments (the template notes)."""
    if not path.exists():
        return ""
    return _HTML_COMMENT.sub(" ", path.read_text(encoding="utf-8")).strip()


def add_semantic_scores(jobs: list[Job], cv_text: str) -> bool:
    """Set each job's `semantic_score` from cosine similarity to the CV.

    Returns True if scores were computed, False if we skipped (no CV, no jobs,
    or the text had no usable vocabulary). On skip, `semantic_score` stays None
    and the ranker falls back to keyword-only — graceful degradation.
    """
    if not cv_text or not jobs:
        log.info("semantic scoring skipped (no CV text or no jobs)")
        return False

    # Corpus = the CV first, then one document per job (title + description).
    corpus = [cv_text] + [f"{job.title}\n{job.description}" for job in jobs]
    vectorizer = TfidfVectorizer(
        stop_words="english",
        ngram_range=(1, 2),  # capture phrases like "machine learning" too
        min_df=1,
    )
    try:
        matrix = vectorizer.fit_transform(corpus)
    except ValueError as exc:  # e.g. vocabulary is empty after stop-word removal
        log.warning("semantic scoring skipped: %s", exc)
        return False

    # TF-IDF rows are L2-normalized, so a linear (dot) product IS cosine similarity.
    cv_vector = matrix[0:1]
    job_matrix = matrix[1:]
    similarities = linear_kernel(cv_vector, job_matrix).ravel()

    for job, score in zip(jobs, similarities, strict=True):
        job.semantic_score = float(score)
    log.info("semantic scored %d jobs (max similarity %.3f)", len(jobs), similarities.max())
    return True
