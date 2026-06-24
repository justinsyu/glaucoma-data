"""Source health monitoring.

A source is "healthy" when it consistently returns a link count in line with
its recent history and its fetch_events show successful HTTP responses with
stable latency. The most common failure modes for source watchers are silent:
the page still loads, but a selector change or a layout migration causes the
extractor to return zero links. Health checks surface those silent failures
explicitly.

Three checks per source:

* ``silent``: returned 0 links for ``N`` consecutive runs after previously
  returning > 0. Indicates a broken extractor or upstream redesign.
* ``link_count_drift``: the latest snapshot's link count is < ``drift_floor``
  fraction of the running median. Indicates partial regression.
* ``latency_anomaly``: latency_ms more than ``latency_multiplier`` x median
  over the trailing window. Indicates upstream slowdown or our crawler being
  throttled.

Configuration via ``RETINA_WATCH_HEALTH_*`` env vars or function kwargs.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass

from sqlalchemy import desc, select

from . import db


DEFAULT_SILENT_RUNS = 2
DEFAULT_DRIFT_FLOOR = 0.5
DEFAULT_LATENCY_MULTIPLIER = 5.0
DEFAULT_WINDOW = 6


@dataclass
class HealthFinding:
    source_id: str
    check: str
    severity: str  # "warning" | "critical"
    detail: dict


def _source_ids(session: db.Session) -> list[str]:
    rows = (
        session.execute(select(db.Snapshot.source_id).distinct()).scalars().all()
    )
    return sorted(set(rows))


def _snapshot_history(session: db.Session, source_id: str, limit: int) -> list[db.Snapshot]:
    stmt = (
        select(db.Snapshot)
        .where(db.Snapshot.source_id == source_id)
        .order_by(desc(db.Snapshot.captured_at))
        .limit(limit)
    )
    return list(session.execute(stmt).scalars().all())


def _fetch_history(session: db.Session, source_id: str, limit: int) -> list[db.FetchEvent]:
    stmt = (
        select(db.FetchEvent)
        .where(db.FetchEvent.source_id == source_id)
        .order_by(desc(db.FetchEvent.fetched_at))
        .limit(limit)
    )
    return list(session.execute(stmt).scalars().all())


def evaluate(
    *,
    silent_runs: int = DEFAULT_SILENT_RUNS,
    drift_floor: float = DEFAULT_DRIFT_FLOOR,
    latency_multiplier: float = DEFAULT_LATENCY_MULTIPLIER,
    window: int = DEFAULT_WINDOW,
) -> list[HealthFinding]:
    findings: list[HealthFinding] = []
    s = db.session()
    try:
        for source_id in _source_ids(s):
            snaps = _snapshot_history(s, source_id, window + silent_runs)
            if not snaps:
                continue

            recent = snaps[: silent_runs + 1]
            if len(recent) >= silent_runs + 1:
                # Most-recent snaps are at index 0. We want: the last N runs all
                # have link_count == 0, AND at least one earlier run was > 0.
                last_n = recent[:silent_runs]
                earlier = snaps[silent_runs:]
                if (
                    all(r.link_count == 0 for r in last_n)
                    and any(e.link_count > 0 for e in earlier)
                ):
                    findings.append(
                        HealthFinding(
                            source_id=source_id,
                            check="silent",
                            severity="critical",
                            detail={
                                "last_n_link_counts": [r.link_count for r in last_n],
                                "prior_max_link_count": max(e.link_count for e in earlier),
                                "consecutive_zero_runs": silent_runs,
                            },
                        )
                    )

            link_counts = [s_.link_count for s_ in snaps if s_.link_count is not None]
            if len(link_counts) >= 3:
                median = statistics.median(link_counts[1:])  # exclude latest
                latest = link_counts[0]
                if median > 0 and latest < median * drift_floor and latest > 0:
                    findings.append(
                        HealthFinding(
                            source_id=source_id,
                            check="link_count_drift",
                            severity="warning",
                            detail={
                                "latest_link_count": latest,
                                "median_prior": median,
                                "drift_floor": drift_floor,
                            },
                        )
                    )

            fetches = _fetch_history(s, source_id, window)
            latencies = [f.latency_ms for f in fetches if f.latency_ms]
            if len(latencies) >= 3:
                median_lat = statistics.median(latencies[1:])
                latest_lat = latencies[0]
                if median_lat > 0 and latest_lat > median_lat * latency_multiplier:
                    findings.append(
                        HealthFinding(
                            source_id=source_id,
                            check="latency_anomaly",
                            severity="warning",
                            detail={
                                "latest_latency_ms": latest_lat,
                                "median_prior_latency_ms": median_lat,
                                "latency_multiplier": latency_multiplier,
                            },
                        )
                    )

            errors = [f for f in fetches if f.error]
            if errors and len(errors) >= max(1, window // 2):
                findings.append(
                    HealthFinding(
                        source_id=source_id,
                        check="fetch_errors",
                        severity="critical",
                        detail={
                            "error_count_in_window": len(errors),
                            "window": window,
                            "latest_error": errors[0].error,
                        },
                    )
                )

    finally:
        s.close()
    return findings
