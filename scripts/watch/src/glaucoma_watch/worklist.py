"""Worklist file writer for discovery-only sources.

Tier 3 sources (Regeneron HCP portal, Roche /restricted/ paths, etc.) cannot
be downloaded by an automated pipeline because each PDF sits behind a
per-document attestation form whose state cannot be reused by a headless
crawler. The watcher still extracts the link list so operators see *what*
exists, but emits each discovered item to a per-sponsor markdown worklist
file instead of treating it as an auto-downloadable candidate.

The worklist file lives at ``<repo_root>/<entry.dest_worklist>`` and is an
append-only markdown document. A run that finds nothing new does not touch
the file. A run that finds N new items appends N rows with the run_id so
the operator can trace the item back through ``runs`` -> ``fetch_events`` ->
``snapshots`` -> the source page on the day it was discovered.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from .extractors.base import ExtractedLink
from .logging_setup import get_logger
from .paths import repo_root
from .watchlist import SourceEntry


def _worklist_path(rel: str) -> Path:
    """Resolve a worklist path relative to the repo root, creating parents."""
    p = repo_root() / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _header_if_missing() -> str:
    return (
        "# Worklist - items requiring manual retrieval\n\n"
        "Each row below was discovered by the deterministic source watcher\n"
        "but could not be downloaded automatically (HCP gating, publisher\n"
        "paywall, or a non-PDF landing page). Retrieve the item manually and\n"
        "drop the PDF into the suggested destination folder.\n\n"
    )


def _format_entry(
    *, run_id: str, link: ExtractedLink, source: SourceEntry, today: str
) -> str:
    title = link.title or "(no title)"
    suggested_dest = (link.extras or {}).get("suggested_dest") or source.dest or "(see watchlist entry)"
    return (
        f"- [{today}] **{title}**\n"
        f"    - reason: discovery_only source: manual HCP retrieval\n"
        f"    - url: {link.url}\n"
        f"    - source_page: {source.url}\n"
        f"    - source_id: `{source.source_id}`\n"
        f"    - run_id: `{run_id}`\n"
        f"    - suggested_dest: `{suggested_dest}`\n"
    )


def maybe_emit_worklist(
    *, entry: SourceEntry, run_id: str, links: list[ExtractedLink]
) -> int:
    """Append ``links`` to ``entry.dest_worklist`` if the entry is discovery_only.

    Returns the number of rows appended. Returns 0 if the entry is not
    discovery_only, if no links were supplied, or if ``dest_worklist`` is
    unset.
    """
    if not entry.discovery_only:
        return 0
    if not links:
        return 0
    if not entry.dest_worklist:
        get_logger().warning(
            "discovery_only_without_dest_worklist", source_id=entry.source_id
        )
        return 0

    path = _worklist_path(entry.dest_worklist)
    is_new_file = not path.exists()
    today = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")

    rows = [_format_entry(run_id=run_id, link=link, source=entry, today=today) for link in links]
    with path.open("a", encoding="utf-8") as fh:
        if is_new_file:
            fh.write(_header_if_missing())
        fh.write("\n".join(rows))
        fh.write("\n")

    get_logger().info(
        "worklist_appended",
        source_id=entry.source_id,
        path=str(path),
        rows=len(rows),
    )
    return len(rows)
