# Job Hunter

Automated, ToS-compliant job aggregator with ML relevance ranking for the Swedish job market.

Every morning a GitHub Action fetches fresh postings from public job APIs, deduplicates them, scores each one against my CV, and publishes a ranked, filterable list to a static web page — no manual searching required.

## What it does

- **Aggregates** jobs from official APIs only (no scraping, no terms-of-service violations). The active source is Platsbanken (Arbetsförmedlingen); the pipeline is multi-source by design.
- **Ranks** each posting 0–100 by blending three signals:
  - a hand-tuned **keyword** score (skills, seniority, location),
  - a **semantic** score — TF-IDF cosine similarity between the job text and my CV,
  - a trained **relevance** classifier probability (grows as I label jobs).
- **Filters** out noise: internships, consultancies, senior/lead titles, ads that require Swedish, and postings older than a cutoff.
- **Flags new** postings since the last run and tracks what's already been seen.
- **Publishes** results to `docs/data/jobs.json`, served as a searchable page via GitHub Pages.

## How it works

```
sources (APIs) ─► dedupe ─► mark new ─► semantic score (vs cv.md) ─► rank ─► jobs.json ─► web page
```

| Stage | Module | Notes |
|-------|--------|-------|
| Fetch | `sources/platsbanken.py` | Platsbanken (JobTech), no key needed |
| Dedupe | `dedupe.py` | Merges the same posting appearing across sources |
| Semantic | `recommender.py` | TF-IDF vectors + cosine similarity to `cv.md` |
| Rank | `rank.py` | Blends the signals, applies filters and recency/remote boosts |
| Report | `report.py` | Writes `jobs.json` / `seen.json` |
| Orchestration | `pipeline.py` | The single function the CLI and the Action call |

**Why TF-IDF instead of neural embeddings?** Zero recurring cost and no gigabyte model download — a deliberate constraint. The interface is model-agnostic, so a neural embedder can be swapped in later without touching the rest of the pipeline.

## Sources

| Source | API | Key required | Status |
|--------|-----|--------------|--------|
| Platsbanken | [JobTech Dev](https://jobtechdev.se/) (Arbetsförmedlingen) | No | **Active** |
| Adzuna | [Adzuna API](https://developer.adzuna.com/) (free tier) | Yes | Inactive — no Sweden coverage |

Platsbanken is the sole live source: as Sweden's official public job board it covers the market well. An Adzuna adapter exists (`sources/adzuna.py`) to demonstrate the pluggable multi-source design, but Adzuna has no Swedish listings, so it's left disabled.

## Getting started

Requires Python 3.13+.

```bash
# Install (editable, with dev tools)
pip install -e ".[dev]"

# Run the full pipeline (Platsbanken needs no API key)
job-hunter run

# Preview without writing any files
job-hunter -v run --dry-run

# Only one source
job-hunter run --source platsbanken
```

Open `docs/index.html` in a browser to view the ranked results locally.

## Configuration

Everything is tunable in [`config.yaml`](config.yaml) — no code changes needed:

- **`queries`** / **`locations`** — what and where to search.
- **`blend`** — how the keyword / semantic / relevance signals are weighted (auto-renormalized if a signal is unavailable).
- **`ranking`** — positive/negative keyword weights, excluded titles and terms, `drop_if_swedish_required`, `recency_days`, `max_age_days`, `remote_boost`.

The semantic layer reads your CV from `cv.md` (git-ignored — kept out of the public repo).

## Automation

- **`.github/workflows/scrape.yml`** — runs daily at 05:00 UTC (`workflow_dispatch` also allows a manual run). It restores `cv.md` from the `CV_MD` repo secret, runs the pipeline, and commits the updated data back. GitHub Pages then serves the new results.
- **`.github/workflows/ci.yml`** — lint (Ruff) + type-check (mypy, strict) on every push and PR.

## Tech stack

Python 3.13 · httpx · pydantic · scikit-learn · PyYAML · Ruff · mypy · GitHub Actions · GitHub Pages

## License

MIT
