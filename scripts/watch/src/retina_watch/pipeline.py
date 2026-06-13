"""Top-level orchestration: drive each source, persist snapshot, compute diff.

The pipeline is intentionally library-shaped: ``run_once`` can be called from
the CLI, from a Dagster asset graph, or from a test. Each call opens exactly
one Run row and dispatches each watchlist source to its registered driver.
"""

from __future__ import annotations

from typing import Iterable

from . import runs
from .candidates import materialize_candidates
from .drivers import DRIVERS, _ensure_api_drivers_loaded
from .logging_setup import get_logger
from .routing import apply_routing
from .snapshots import write_snapshot
from .watchlist import SourceEntry, load_watchlist
from .worklist import maybe_emit_worklist


def _process_source(run_id: str, entry: SourceEntry) -> dict:
    log = get_logger().bind(source_id=entry.source_id, source_type=entry.source_type)
    driver = DRIVERS.get(entry.source_type)
    if driver is None:
        log.error("driver_not_registered", source_type=entry.source_type)
        return {"source_id": entry.source_id, "status": "skipped", "reason": "no_driver"}

    result = driver(entry, run_id)
    if result.status == "skipped":
        return {"source_id": entry.source_id, "status": "skipped", "reason": result.reason}
    if result.status != "ok" or result.links is None:
        return {
            "source_id": entry.source_id,
            "status": result.status,
            "error": result.error,
        }

    routed_links = apply_routing(entry, result.links)
    worklist_emitted = maybe_emit_worklist(entry=entry, run_id=run_id, links=routed_links)

    diff = write_snapshot(
        run_id=run_id,
        source_id=entry.source_id,
        source_url=entry.url,
        extractor=entry.source_type,
        links=routed_links,
    )
    return {
        "source_id": entry.source_id,
        "status": "ok",
        "link_count": len(routed_links),
        "added": len(diff["added"]),
        "removed": len(diff["removed"]),
        "is_baseline": diff["is_baseline"],
        "filtered_out": len(result.links) - len(routed_links),
        "worklist_entries_appended": worklist_emitted,
    }


def run_once(
    *,
    trigger: str = "manual",
    source_types: Iterable[str] | None = None,
    source_ids: Iterable[str] | None = None,
) -> dict:
    _ensure_api_drivers_loaded()
    wl = load_watchlist()
    candidates = wl.enabled_sources()
    if source_types:
        st = set(source_types)
        candidates = [s for s in candidates if s.source_type in st]
    if source_ids:
        ids = set(source_ids)
        candidates = [s for s in candidates if s.source_id in ids]

    results: list[dict] = []
    with runs.start_run(trigger=trigger, stats_init={"planned_sources": len(candidates)}) as run_id:
        for entry in candidates:
            result = _process_source(run_id, entry)
            results.append(result)

        ok = sum(1 for r in results if r["status"] == "ok")
        baseline = sum(1 for r in results if r.get("is_baseline"))
        added = sum(r.get("added", 0) for r in results)
        skipped = sum(1 for r in results if r["status"] == "skipped")
        failed = sum(1 for r in results if r["status"] in {"fetch_failed", "extract_failed"})

        candidates_summary = materialize_candidates(run_id=run_id)
        runs.update_stats(
            run_id,
            sources_attempted=len(candidates),
            sources_ok=ok,
            sources_skipped=skipped,
            sources_failed=failed,
            sources_baseline=baseline,
            new_links_total=added,
            candidates_total=candidates_summary["candidates_total"],
            candidates_new=candidates_summary["by_decision"].get("new", 0),
        )
        return {"run_id": run_id, "results": results, "candidates": candidates_summary}
