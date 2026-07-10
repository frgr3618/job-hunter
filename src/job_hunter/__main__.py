"""Enables `python -m job_hunter ...` as an alias for the `job-hunter` command."""

from __future__ import annotations

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
