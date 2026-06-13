"""Export the audit trail to ``_data/watch_audit.json`` for Jekyll consumption.

The Jekyll site is the public surface; SQLite is internal state. The export
job snapshots the rows the dashboard needs into a flat JSON file the site can
read on its next build. This keeps the dashboard generation step
deterministic, side-effect free, and version-controllable.

The export deliberately denormalizes joins (runs -> snapshots, snapshots ->
candidates) so the Liquid templates can iterate cleanly without computing
relations at render time.
"""

from __future__ import annotations

import datetime as dt
import json
from collections import defaultdict
from dataclasses import asdict

from sqlalchemy import desc, select

from . import db, health
from .paths import data_dir
from .watchlist import load_watchlist


def _iso(d: dt.datetime | None) -> str | None:
    return d.isoformat() if d else None


def _as_aware(d: dt.datetime | None) -> dt.datetime | None:
    """Coerce naive datetimes (SQLite default) to UTC-aware for arithmetic."""
    if d is None:
        return None
    return d if d.tzinfo is not None else d.replace(tzinfo=dt.timezone.utc)


def _round_or_none(v, places: int = 1):
    return round(v, places) if isinstance(v, (int, float)) else None


def export_audit() -> dict:
    wl = load_watchlist()
    entry_by_id = {e.source_id: e for e in wl.sources}

    s = db.session()
    try:
        run_rows = (
            s.execute(select(db.Run).order_by(desc(db.Run.started_at)).limit(50))
            .scalars()
            .all()
        )
        runs_payload = []
        for r in run_rows:
            duration_ms = None
            start = _as_aware(r.started_at)
            end = _as_aware(r.ended_at)
            if start and end:
                duration_ms = int((end - start).total_seconds() * 1000)
            runs_payload.append(
                {
                    "run_id": r.run_id,
                    "trigger": r.trigger,
                    "status": r.status,
                    "started_at": _iso(r.started_at),
                    "ended_at": _iso(r.ended_at),
                    "duration_ms": duration_ms,
                    "stats": r.stats or {},
                    "git_sha": r.git_sha,
                }
            )

        # Per-source snapshot: latest snapshot per source, plus rolling stats.
        snap_rows = (
            s.execute(select(db.Snapshot).order_by(desc(db.Snapshot.captured_at)))
            .scalars()
            .all()
        )
        latest_snap: dict[str, db.Snapshot] = {}
        link_history: dict[str, list[int]] = defaultdict(list)
        for snap in snap_rows:
            if snap.source_id not in latest_snap:
                latest_snap[snap.source_id] = snap
            link_history[snap.source_id].append(snap.link_count)

        fetch_rows = (
            s.execute(select(db.FetchEvent).order_by(desc(db.FetchEvent.fetched_at)))
            .scalars()
            .all()
        )
        latest_fetch: dict[str, db.FetchEvent] = {}
        latency_history: dict[str, list[int]] = defaultdict(list)
        for f in fetch_rows:
            if f.source_id not in latest_fetch:
                latest_fetch[f.source_id] = f
            if f.latency_ms is not None:
                latency_history[f.source_id].append(f.latency_ms)

        sources_payload = []
        all_source_ids = set(latest_snap) | set(latest_fetch) | set(entry_by_id)
        for sid in sorted(all_source_ids):
            entry = entry_by_id.get(sid)
            snap = latest_snap.get(sid)
            fetch = latest_fetch.get(sid)
            sources_payload.append(
                {
                    "source_id": sid,
                    "company_slug": entry.company_slug if entry else None,
                    "program_slug": entry.program_slug if entry else None,
                    "source_type": entry.source_type if entry else None,
                    "url": entry.url if entry else None,
                    "enabled": entry.enabled if entry else False,
                    "manual_review": entry.manual_review if entry else False,
                    "latest_link_count": snap.link_count if snap else None,
                    "latest_snapshot_at": _iso(snap.captured_at) if snap else None,
                    "latest_diff": snap.diff_vs_prior if snap else None,
                    "latest_fetch_status": fetch.http_status if fetch else None,
                    "latest_fetch_error": fetch.error if fetch else None,
                    "latest_fetch_method": fetch.method if fetch else None,
                    "latest_fetch_latency_ms": fetch.latency_ms if fetch else None,
                    "latency_history_ms": latency_history[sid][:10],
                    "link_history": link_history[sid][:10],
                }
            )

        # Latest candidate batch grouped by run_id, decision counts.
        cand_rows = (
            s.execute(select(db.Candidate).order_by(desc(db.Candidate.created_at)).limit(200))
            .scalars()
            .all()
        )
        candidates_payload = [
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
                "created_at": _iso(c.created_at),
            }
            for c in cand_rows
        ]
    finally:
        s.close()

    findings = [asdict(f) for f in health.evaluate()]

    payload = {
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "runs": runs_payload,
        "sources": sources_payload,
        "candidates": candidates_payload,
        "health_findings": findings,
        "summary": {
            "total_sources": len(sources_payload),
            "enabled_sources": sum(1 for s in sources_payload if s["enabled"]),
            "sources_with_recent_data": sum(
                1 for s in sources_payload if s["latest_snapshot_at"]
            ),
            "recent_runs": len(runs_payload),
            "candidates_total": len(candidates_payload),
            "candidates_new": sum(1 for c in candidates_payload if c["decision"] == "new"),
            "open_health_findings": len(findings),
        },
    }

    out_path = data_dir() / "watch_audit.json"
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=False, default=str)
    return {"path": str(out_path), "summary": payload["summary"]}
