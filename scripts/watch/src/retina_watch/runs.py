"""Run lifecycle: open a Run row, attach it to log context, close it cleanly."""

from __future__ import annotations

import datetime as dt
import os
import subprocess
import traceback
from contextlib import contextmanager
from typing import Iterator

import structlog

from . import db
from .logging_setup import get_logger


def _git_sha() -> str | None:
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                stderr=subprocess.DEVNULL,
                text=True,
            )
            .strip()
            or None
        )
    except Exception:
        return None


@contextmanager
def start_run(trigger: str, stats_init: dict | None = None) -> Iterator[str]:
    """Open a new Run row and bind ``run_id`` into the structured-log context.

    The caller receives the run_id and can attach further events to it via the
    db helpers. On normal exit, status is set to ``ok``; on exception, status is
    set to ``failed`` with the traceback recorded in ``error_summary``.
    """
    s = db.session()
    run = db.Run(trigger=trigger, git_sha=_git_sha(), stats=stats_init or {})
    s.add(run)
    s.commit()
    run_id = run.run_id

    structlog.contextvars.bind_contextvars(run_id=run_id)
    log = get_logger()
    log.info("run_started", trigger=trigger, git_sha=run.git_sha)

    try:
        import sentry_sdk

        sentry_sdk.set_tag("run_id", run_id)
    except ImportError:
        pass

    try:
        yield run_id
    except Exception:
        run.status = "failed"
        run.ended_at = dt.datetime.now(dt.timezone.utc)
        run.error_summary = traceback.format_exc()
        s.add(run)
        s.commit()
        log.error("run_failed", run_id=run_id)
        raise
    else:
        run.status = "ok"
        run.ended_at = dt.datetime.now(dt.timezone.utc)
        s.add(run)
        s.commit()
        log.info("run_completed", run_id=run_id)
    finally:
        s.close()
        structlog.contextvars.unbind_contextvars("run_id")


def update_stats(run_id: str, **delta: int) -> None:
    s = db.session()
    try:
        run = s.get(db.Run, run_id)
        if run is None:
            return
        stats = dict(run.stats or {})
        for k, v in delta.items():
            stats[k] = stats.get(k, 0) + int(v)
        run.stats = stats
        s.add(run)
        s.commit()
    finally:
        s.close()
