"""Filesystem layout used by the watcher.

All paths resolve relative to the repository root. The repo root is detected by
walking up from this file until a directory containing both ``_data`` and
``_config.yml`` is found, which keeps the package portable when the working
directory changes (e.g., Dagster daemon, scheduled runs).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in (here, *here.parents):
        if (parent / "_config.yml").is_file() and (parent / "_data").is_dir():
            return parent
    raise RuntimeError("Could not locate glaucoma-data repo root from " + str(here))


def data_dir() -> Path:
    return repo_root() / "_data"


def artifacts_dir() -> Path:
    p = repo_root() / "artifacts" / "watch"
    p.mkdir(parents=True, exist_ok=True)
    return p


def snapshots_dir() -> Path:
    p = artifacts_dir() / "snapshots"
    p.mkdir(parents=True, exist_ok=True)
    return p


def runs_dir() -> Path:
    p = artifacts_dir() / "runs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def db_path() -> Path:
    return artifacts_dir() / "observability.sqlite"


def watchlist_path() -> Path:
    return data_dir() / "source_watchlist.yml"


def manifest_path() -> Path:
    return data_dir() / "company_documents.json"


def profiles_path() -> Path:
    return data_dir() / "company_profiles.json"
