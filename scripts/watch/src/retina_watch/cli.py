"""Command-line interface.

Three sub-commands:

* ``init-db``: create the SQLite tables.
* ``bootstrap-watchlist``: derive ``_data/source_watchlist.yml`` from the manifest.
* ``run``: execute one pipeline pass for the enabled sources.
"""

from __future__ import annotations

import json

import click

from . import db
from .bootstrap import bootstrap
from .candidates import materialize_candidates
from .logging_setup import init_logging, init_sentry
from .pipeline import run_once
from .watchlist import load_watchlist


@click.group()
@click.option("--log-level", default="INFO", show_default=True)
def main(log_level: str) -> None:
    init_logging(level=log_level)
    init_sentry()


@main.command("init-db")
def init_db_cmd() -> None:
    """Create the observability tables in the SQLite database."""
    db.init_db()
    click.echo(f"initialized {db.engine().url}")


@main.command("bootstrap-watchlist")
@click.option("--dry-run", is_flag=True, help="Print the coverage report without writing the YAML.")
@click.option(
    "--skip-recipes",
    is_flag=True,
    help="Do not apply hand-tuned recipes after bootstrap (auto-classified output only).",
)
def bootstrap_cmd(dry_run: bool, skip_recipes: bool) -> None:
    """Generate or refresh _data/source_watchlist.yml from the manifest."""
    from .recipes import apply_recipes
    from .watchlist import write_watchlist

    wl, coverage = bootstrap(write=False)
    if not skip_recipes:
        wl, recipe_report = apply_recipes(wl)
        coverage["recipes"] = recipe_report
    if not dry_run:
        write_watchlist(wl)
    click.echo(json.dumps(coverage, indent=2))


@main.command("show-watchlist")
def show_watchlist_cmd() -> None:
    """Print the current watchlist as JSON for quick inspection."""
    wl = load_watchlist()
    click.echo(json.dumps(wl.model_dump(mode="json", exclude_none=True), indent=2))


@main.command("run")
@click.option("--trigger", default="manual", show_default=True)
@click.option(
    "--source-type",
    "source_types",
    multiple=True,
    help="Restrict to one or more source_type values (repeatable).",
)
@click.option(
    "--source-id",
    "source_ids",
    multiple=True,
    help="Restrict to one or more source_id values (repeatable).",
)
def run_cmd(trigger: str, source_types: tuple[str, ...], source_ids: tuple[str, ...]) -> None:
    """Execute a single pipeline pass."""
    db.init_db()
    summary = run_once(
        trigger=trigger,
        source_types=list(source_types) or None,
        source_ids=list(source_ids) or None,
    )
    click.echo(json.dumps(summary, indent=2))


@main.command("show-runs")
@click.option("--limit", default=10, show_default=True)
def show_runs_cmd(limit: int) -> None:
    """Print the most recent run rows with their stats."""
    from sqlalchemy import select

    s = db.session()
    try:
        rows = (
            s.execute(select(db.Run).order_by(db.Run.started_at.desc()).limit(limit))
            .scalars()
            .all()
        )
        payload = [
            {
                "run_id": r.run_id,
                "trigger": r.trigger,
                "git_sha": r.git_sha,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "ended_at": r.ended_at.isoformat() if r.ended_at else None,
                "status": r.status,
                "stats": r.stats,
                "error_summary": (r.error_summary or "")[:200] or None,
            }
            for r in rows
        ]
        click.echo(json.dumps(payload, indent=2))
    finally:
        s.close()


@main.command("show-source")
@click.argument("source_id")
@click.option("--limit", default=5, show_default=True)
def show_source_cmd(source_id: str, limit: int) -> None:
    """Print recent fetch_events and snapshots for one source."""
    from sqlalchemy import select

    s = db.session()
    try:
        fetches = (
            s.execute(
                select(db.FetchEvent)
                .where(db.FetchEvent.source_id == source_id)
                .order_by(db.FetchEvent.id.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )
        snaps = (
            s.execute(
                select(db.Snapshot)
                .where(db.Snapshot.source_id == source_id)
                .order_by(db.Snapshot.id.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )
        payload = {
            "source_id": source_id,
            "recent_fetches": [
                {
                    "run_id": f.run_id,
                    "http_status": f.http_status,
                    "bytes": f.bytes,
                    "latency_ms": f.latency_ms,
                    "retries": f.retries,
                    "error": f.error,
                    "fetched_at": f.fetched_at.isoformat() if f.fetched_at else None,
                }
                for f in fetches
            ],
            "recent_snapshots": [
                {
                    "run_id": sn.run_id,
                    "link_count": sn.link_count,
                    "diff": sn.diff_vs_prior,
                    "captured_at": sn.captured_at.isoformat() if sn.captured_at else None,
                }
                for sn in snaps
            ],
        }
        click.echo(json.dumps(payload, indent=2))
    finally:
        s.close()


@main.command("export-audit")
def export_audit_cmd() -> None:
    """Export the observability tables to _data/watch_audit.json for Jekyll."""
    from .export import export_audit

    result = export_audit()
    click.echo(json.dumps(result, indent=2))


@main.command("export-clinicaltrials-updates")
def export_clinicaltrials_updates_cmd() -> None:
    """Export CT.gov snapshot changes to _data/clinicaltrials_updates.json."""
    from .clinicaltrials_updates import export

    result = export()
    click.echo(json.dumps(result, indent=2))


@main.command("health")
@click.option("--silent-runs", default=None, type=int)
@click.option("--drift-floor", default=None, type=float)
@click.option("--latency-multiplier", default=None, type=float)
@click.option("--window", default=None, type=int)
def health_cmd(
    silent_runs: int | None,
    drift_floor: float | None,
    latency_multiplier: float | None,
    window: int | None,
) -> None:
    """Evaluate per-source health and print findings."""
    from dataclasses import asdict

    from . import health

    kwargs = {}
    if silent_runs is not None:
        kwargs["silent_runs"] = silent_runs
    if drift_floor is not None:
        kwargs["drift_floor"] = drift_floor
    if latency_multiplier is not None:
        kwargs["latency_multiplier"] = latency_multiplier
    if window is not None:
        kwargs["window"] = window
    findings = health.evaluate(**kwargs)
    payload = [asdict(f) for f in findings]
    click.echo(json.dumps(payload, indent=2))


@main.command("diff-run")
@click.argument("run_id")
def diff_run_cmd(run_id: str) -> None:
    """Re-materialize candidates for a specific run_id (idempotent if already done)."""
    summary = materialize_candidates(run_id=run_id)
    click.echo(json.dumps(summary, indent=2))


@main.command("show-candidates")
@click.option("--run-id", default=None, help="Filter to a single run.")
@click.option("--decision", default=None, help="Filter to a dedupe decision (e.g. 'new').")
@click.option("--limit", default=20, show_default=True)
def show_candidates_cmd(run_id: str | None, decision: str | None, limit: int) -> None:
    """Print recent candidate rows with their dedupe decision."""
    from sqlalchemy import select

    s = db.session()
    try:
        stmt = select(db.Candidate).order_by(db.Candidate.created_at.desc()).limit(limit)
        if run_id:
            stmt = stmt.where(db.Candidate.run_id == run_id)
        if decision:
            stmt = stmt.where(db.Candidate.dedupe_decision == decision)
        rows = s.execute(stmt).scalars().all()
        payload = [
            {
                "candidate_id": c.candidate_id,
                "run_id": c.run_id,
                "source_id": c.source_id,
                "url": c.url,
                "decision": c.dedupe_decision,
                "normalized_title": c.normalized_title,
                "title": (c.confidence_features or {}).get("title"),
                "doi": (c.confidence_features or {}).get("doi"),
                "nct": (c.confidence_features or {}).get("nct"),
                "pmid": (c.confidence_features or {}).get("pmid"),
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in rows
        ]
        click.echo(json.dumps(payload, indent=2))
    finally:
        s.close()


if __name__ == "__main__":
    main()
