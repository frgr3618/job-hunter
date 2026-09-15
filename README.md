# Job Hunter

Automated job aggregator with ML relevance ranking for the Swedish job market.

Every morning a GitHub Action fetches fresh postings, deduplicates them, scores each one against my CV, and publishes a ranked, filterable list to a static web page — no manual searching required.

## What it does

- **Aggregates** jobs from multiple sources: Platsbanken (Sweden's official public job API) plus LinkedIn and Indeed via [JobSpy](https://github.com/speedyapply/JobSpy). The JobSpy-backed sources scrape rather than use an official API — see [Sources](#sources) below for what that means in practice.
- **Ranks** each posting 0–100 by blending three signals:
  - a hand-tuned **keyword** score (skills, seniority, location),
  - a **semantic** score — TF-IDF cosine similarity between the job text and my CV,
  - a trained **relevance** classifier probability (grows as I label jobs).
- **Filters** out noise: internships, consultancies, senior/lead titles, ads that require Swedish, and postings older than a cutoff.
- **Flags new** postings since the last run and tracks what's already been seen.
- **Publishes** results to `docs/data/jobs.json`, served as a searchable page via GitHub Pages.

## How it works

```
sources ─► dedupe ─► mark new ─► semantic score (vs cv.md) ─► rank ─► jobs.json ─► web page
```

| Stage | Module | Notes |
|-------|--------|-------|
| Fetch | `sources/platsbanken.py`, `sources/jobspy_source.py` | Platsbanken (official API); LinkedIn + Indeed (scraped via JobSpy) |
| Dedupe | `dedupe.py` | Merges the same posting appearing across sources |
| Semantic | `recommender.py` | TF-IDF vectors + cosine similarity to `cv.md` |
| Rank | `rank.py` | Blends the signals, applies filters and recency/remote boosts |
| Report | `report.py` | Writes `jobs.json` / `seen.json` |
| Orchestration | `pipeline.py` | The single function the CLI and the Action call |

**Why TF-IDF instead of neural embeddings?** Zero recurring cost and no gigabyte model download — a deliberate constraint. The interface is model-agnostic, so a neural embedder can be swapped in later without touching the rest of the pipeline.

## Sources

| Source | How | Key required | Status |
|--------|-----|--------------|--------|
| Platsbanken | Official API ([JobTech Dev](https://jobtechdev.se/), Arbetsförmedlingen) | No | **Active** — reliable |
| LinkedIn | Scraped via [JobSpy](https://github.com/speedyapply/JobSpy) | No | **Active** — best-effort, may occasionally fail |
| Indeed | Scraped via [JobSpy](https://github.com/speedyapply/JobSpy) | No | **Active** — best-effort |

Platsbanken, as Sweden's official public job board, is the reliable backbone.
LinkedIn and Indeed add real coverage JobTech doesn't have, but JobSpy works by
scraping each site's search pages rather than calling an official API — that's
against those sites' terms of service, done here at low, personal-use volume
(a handful of searches, once a day). LinkedIn in particular may occasionally
return nothing on a given run if it rate-limits the request; the pipeline
tolerates that the same way it tolerates any other source having a bad day.
Google Jobs and Glassdoor are supported by JobSpy in principle but aren't used
here: Google's scraper is currently broken upstream (jobspy issue
[#302](https://github.com/speedyapply/JobSpy/issues/302)), and Glassdoor has no
Sweden coverage in JobSpy. ZipRecruiter, Bayt, and Naukri aren't used either —
none cover the Swedish market.

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
job-hunter run --source jobspy
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

Python 3.13 · httpx · pydantic · scikit-learn · PyYAML · JobSpy · Ruff · mypy · GitHub Actions · GitHub Pages

## License

MIT
