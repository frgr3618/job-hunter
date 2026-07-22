"""Command-line interface: `job-hunter <command>`.

For now the only command is `run` (fetch + rank + write results). The `train`,
`enrich`, and `dashboard` commands will be added as we build those layers.
"""

from __future__ import annotations

import argparse
import logging

from .config import ApiKeys, Config
from .pipeline import RunResult
from .pipeline import run as run_pipeline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="job-hunter",
        description="Automated, ToS-compliant Swedish job aggregator + ML ranking.",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="show detailed progress logs"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="fetch, rank, and write jobs.json")
    run_parser.add_argument(
        "--source",
        action="append",
        dest="sources",
        metavar="NAME",
        help="only use this source (repeatable); default: all",
    )
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="run everything but don't write any files",
    )

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    if args.command == "run":
        return _cmd_run(args)
    parser.error(f"unknown command {args.command!r}")  # unreachable; keeps types happy
    return 2


def _cmd_run(args: argparse.Namespace) -> int:
    config = Config.load()
    keys = ApiKeys.load()
    result = run_pipeline(
        config, keys, source_names=args.sources, dry_run=args.dry_run
    )
    _print_summary(result, dry_run=args.dry_run)
    return 0


def _print_summary(result: RunResult, dry_run: bool) -> None:
    print(f"\nFetched {result.fetched} jobs "
          f"({', '.join(f'{k}={v}' for k, v in result.per_source.items()) or 'none'})")
    print(f"Ranked {len(result.jobs)} jobs after dedupe + filters")
    if dry_run:
        print("(dry run — no files written)")
    else:
        print("Wrote docs/data/jobs.json")

    print("\nTop 5:")
    for job in result.jobs[:5]:
        badge = "NEW " if job.is_new else "    "
        print(f"  {badge}{job.score:5.1f}  {job.title[:45]:45}  {job.company[:25]}")


if __name__ == "__main__":  # allows `python -m job_hunter.cli`
    raise SystemExit(main())
