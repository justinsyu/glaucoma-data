"""Smoke test: validate sources.yaml without doing any network I/O.

Usage:
  python -m scripts.sweep.smoke [--config scripts/sweep/sources.yaml]

Exits 0 if the config parses and every destination folder is reachable under
the repo root; exits 1 otherwise. Prints a per-company summary table so you
can sanity-check coverage before scheduling a real run.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import ConfigError, load_config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m scripts.sweep.smoke")
    parser.add_argument("--config", default="scripts/sweep/sources.yaml")
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()

    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(f"CONFIG ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"defaults.user_agent       : {config.defaults.user_agent}")
    print(f"defaults.timeout_seconds  : {config.defaults.timeout_seconds}")
    print(f"companies                 : {len(config.companies)}")
    print()
    print(f"{'id':<32} {'tier':>4} {'sources':>8} {'first_source':<50}")
    print("-" * 100)
    bad = 0
    for c in config.companies:
        first = c.sources[0]
        first_label = first.url or f"pubmed:{','.join(first.terms[:2])}" if first.kind != "skip" else "(skip)"
        print(f"{c.id:<32} {c.tier:>4} {len(c.sources):>8} {first_label[:50]:<50}")
        # Verify the company folder exists under repo_root.
        folder = repo_root / c.folder
        if not folder.exists():
            print(f"    ! folder missing: {folder}", file=sys.stderr)
            bad += 1
        for src in c.sources:
            if src.kind == "skip":
                continue
            dest_targets = [src.dest] if src.dest else []
            dest_targets += [r.dest for r in src.dest_router]
            dest_targets += [r.dest for r in src.title_router]
            for d in dest_targets:
                if d and not (repo_root / d).parent.exists():
                    print(f"    ! dest parent missing: {repo_root / d}", file=sys.stderr)
                    bad += 1

    if bad:
        print(f"\n{bad} smoke-test issue(s) detected.", file=sys.stderr)
        return 1
    print("\nAll companies parse and have reachable folders.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
