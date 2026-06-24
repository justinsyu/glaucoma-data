"""Dagster definitions: assets, schedules, and asset checks.

Three assets form the watcher pipeline in Dagster's view of the world:

* ``watchlist`` (source asset) - reads ``_data/source_watchlist.yml``.
* ``source_snapshot`` (partitioned, one partition per enabled watchlist entry)
  - drives each source through its registered driver, persists a snapshot,
  computes the diff.
* ``candidates`` - materializes the candidates table for the latest run.
* ``audit_export`` - regenerates ``_data/watch_audit.json`` so the Jekyll
  dashboard sees fresh data.

A weekly schedule fires the pipeline. An asset check evaluates source health
after each materialization.

Start the Dagster UI locally with::

    dagster dev -m glaucoma_watch.dagster_defs
"""

from dataclasses import asdict
from typing import Optional

import dagster as dg
from dagster import AssetCheckExecutionContext, AssetExecutionContext

from . import db, health
from .candidates import materialize_candidates
from .drivers import DRIVERS, _ensure_api_drivers_loaded
from .export import export_audit
from .pipeline import _process_source, run_once
from .runs import start_run
from .watchlist import load_watchlist


# ---------------------------------------------------------------------------
# Partitions: one partition per enabled watchlist source_id.
# ---------------------------------------------------------------------------

sources_partition = dg.DynamicPartitionsDefinition(name="source_id")


def _sync_partitions(context: Optional[AssetExecutionContext] = None) -> list:
    """Ensure the dynamic partition set matches the watchlist's enabled entries."""
    wl = load_watchlist()
    desired = [s.source_id for s in wl.enabled_sources()]

    instance = context.instance if context is not None else dg.DagsterInstance.get()
    current = set(instance.get_dynamic_partitions("source_id"))
    to_add = [sid for sid in desired if sid not in current]
    to_remove = [sid for sid in current if sid not in desired]

    if to_add:
        instance.add_dynamic_partitions("source_id", to_add)
    for sid in to_remove:
        instance.delete_dynamic_partition("source_id", sid)
    return desired


# ---------------------------------------------------------------------------
# Assets
# ---------------------------------------------------------------------------


@dg.asset(
    group_name="watcher",
    description="Source watchlist loaded from _data/source_watchlist.yml. Refreshes the dynamic partition set on each materialization.",
)
def watchlist(context: AssetExecutionContext) -> dg.MaterializeResult:
    desired = _sync_partitions(context)
    return dg.MaterializeResult(
        metadata={
            "enabled_sources": len(desired),
            "source_ids": dg.MetadataValue.json(desired),
        }
    )


@dg.asset(
    group_name="watcher",
    partitions_def=sources_partition,
    deps=[watchlist],
    description="One snapshot per source. Each materialization runs the registered driver, persists the snapshot, and emits the diff vs prior.",
)
def source_snapshot(context: AssetExecutionContext) -> dg.MaterializeResult:
    _ensure_api_drivers_loaded()
    source_id = context.partition_key
    wl = load_watchlist()
    entry = next((s for s in wl.sources if s.source_id == source_id), None)
    if entry is None:
        raise dg.Failure(description=f"Watchlist entry {source_id!r} not found.")

    with start_run(trigger=f"dagster:source_snapshot:{source_id}") as run_id:
        result = _process_source(run_id, entry)
        context.add_output_metadata(
            {
                "run_id": run_id,
                "status": result["status"],
                "link_count": result.get("link_count"),
                "added": result.get("added"),
                "removed": result.get("removed"),
                "is_baseline": result.get("is_baseline"),
                "error": result.get("error"),
            }
        )
        if result["status"] not in {"ok", "skipped"}:
            raise dg.Failure(
                description=f"{source_id}: {result['status']}: {result.get('error')}"
            )
        return dg.MaterializeResult(
            metadata={
                "run_id": run_id,
                "status": result["status"],
                "link_count": result.get("link_count") or 0,
                "added": result.get("added") or 0,
            }
        )


@dg.asset(
    group_name="watcher",
    deps=[source_snapshot],
    description="Materialize candidate rows for all snapshots in the most recent run.",
)
def candidates(context: AssetExecutionContext) -> dg.MaterializeResult:
    from sqlalchemy import desc, select

    s = db.session()
    try:
        latest = (
            s.execute(select(db.Run).order_by(desc(db.Run.started_at)).limit(1))
            .scalars()
            .first()
        )
    finally:
        s.close()
    if latest is None:
        return dg.MaterializeResult(metadata={"summary": "no runs yet"})
    summary = materialize_candidates(run_id=latest.run_id)
    return dg.MaterializeResult(
        metadata={
            "run_id": latest.run_id,
            "added_total": summary["added_total"],
            "candidates_total": summary["candidates_total"],
            "by_decision": dg.MetadataValue.json(summary["by_decision"]),
        }
    )


@dg.asset(
    group_name="watcher",
    deps=[candidates],
    description="Regenerate _data/watch_audit.json so the Jekyll dashboard reflects the latest state.",
)
def audit_export(context: AssetExecutionContext) -> dg.MaterializeResult:
    out = export_audit()
    return dg.MaterializeResult(
        metadata={
            "path": out["path"],
            "summary": dg.MetadataValue.json(out["summary"]),
        }
    )


# ---------------------------------------------------------------------------
# Asset checks: per-source health
# ---------------------------------------------------------------------------


@dg.asset_check(asset=source_snapshot, blocking=False)
def source_health_check(context: AssetCheckExecutionContext) -> dg.AssetCheckResult:
    findings = health.evaluate()
    by_severity: dict[str, int] = {}
    for f in findings:
        by_severity[f.severity] = by_severity.get(f.severity, 0) + 1
    return dg.AssetCheckResult(
        passed=not any(f.severity == "critical" for f in findings),
        metadata={
            "findings_total": len(findings),
            "by_severity": dg.MetadataValue.json(by_severity),
            "findings": dg.MetadataValue.json([asdict(f) for f in findings]),
        },
    )


# ---------------------------------------------------------------------------
# Job + schedule
# ---------------------------------------------------------------------------


watcher_job = dg.define_asset_job(
    name="watcher_weekly",
    selection=dg.AssetSelection.assets(watchlist, source_snapshot, candidates, audit_export),
    description="Run the full watcher pipeline against every enabled source.",
    partitions_def=sources_partition,
)


weekly_schedule = dg.ScheduleDefinition(
    job=watcher_job,
    cron_schedule="0 9 * * MON",
    name="watcher_weekly_monday_09utc",
    description="Weekly Monday 09:00 UTC sweep of every enabled source.",
)


# ---------------------------------------------------------------------------
# Definitions object that ``dagster dev`` loads
# ---------------------------------------------------------------------------


defs = dg.Definitions(
    assets=[watchlist, source_snapshot, candidates, audit_export],
    asset_checks=[source_health_check],
    jobs=[watcher_job],
    schedules=[weekly_schedule],
)
