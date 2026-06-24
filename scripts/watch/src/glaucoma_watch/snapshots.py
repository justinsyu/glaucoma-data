"""Snapshot writer and differ.

A snapshot is a JSON file on disk *and* a row in the ``snapshots`` table. The
file is the durable artifact that survives database resets; the row is the
queryable index. Snapshot files live at::

    artifacts/watch/snapshots/<source_id>/<YYYY-MM-DD>__<run_id>.json

The diff against the prior snapshot is computed at write time so the observer
sees the delta immediately (no recomputation needed at read time).
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import asdict
from pathlib import Path

from . import db
from .extractors.base import ExtractedLink
from .logging_setup import get_logger
from .paths import snapshots_dir


def _source_dir(source_id: str) -> Path:
    p = snapshots_dir() / source_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def _latest_prior(source_dir: Path, current: Path) -> Path | None:
    candidates = sorted(p for p in source_dir.glob("*.json") if p != current)
    return candidates[-1] if candidates else None


def _diff(prior: list[dict] | None, current: list[dict]) -> dict:
    if not prior:
        return {"added": [], "removed": [], "unchanged_count": 0, "is_baseline": True}
    prior_urls = {item["url"]: item for item in prior}
    current_urls = {item["url"]: item for item in current}
    added = [current_urls[u] for u in current_urls if u not in prior_urls]
    removed = [prior_urls[u] for u in prior_urls if u not in current_urls]
    unchanged = [u for u in current_urls if u in prior_urls]
    return {
        "added": sorted(added, key=lambda x: x["url"]),
        "removed": sorted(removed, key=lambda x: x["url"]),
        "unchanged_count": len(unchanged),
        "is_baseline": False,
    }


def write_snapshot(
    *,
    run_id: str,
    source_id: str,
    source_url: str,
    extractor: str,
    links: list[ExtractedLink],
) -> dict:
    log = get_logger().bind(source_id=source_id)
    source_dir = _source_dir(source_id)
    today = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    out_path = source_dir / f"{today}__{run_id}.json"

    payload = {
        "source_id": source_id,
        "source_url": source_url,
        "extractor": extractor,
        "captured_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "run_id": run_id,
        "links": [asdict(link) for link in links],
    }

    prior_path = _latest_prior(source_dir, out_path)
    prior_links = None
    if prior_path is not None:
        try:
            with prior_path.open("r", encoding="utf-8") as fh:
                prior_links = json.load(fh).get("links")
        except Exception as exc:
            log.warning("prior_snapshot_unreadable", prior=str(prior_path), error=str(exc))

    diff = _diff(prior_links, payload["links"])

    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=False)

    s = db.session()
    try:
        s.add(
            db.Snapshot(
                run_id=run_id,
                source_id=source_id,
                link_count=len(links),
                snapshot_path=str(out_path.relative_to(out_path.anchor)) if out_path.is_absolute() else str(out_path),
                diff_vs_prior=diff,
            )
        )
        s.commit()
    finally:
        s.close()

    log.info(
        "snapshot_written",
        link_count=len(links),
        added=len(diff["added"]),
        removed=len(diff["removed"]),
        is_baseline=diff["is_baseline"],
        path=str(out_path),
    )
    return diff
