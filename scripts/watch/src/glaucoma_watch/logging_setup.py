"""Structured logging plus optional Sentry initialization.

Logs are emitted as JSON lines so the same stream feeds operator stdout, the
Dagster compute log capture, and a downstream log shipper (Loki, Datadog) when
deployed. Every log record carries ``run_id`` once a run is active so that
events can be joined to the observability database.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

import structlog


def init_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level)),
        cache_logger_on_first_use=True,
    )


def init_sentry() -> None:
    """Initialize Sentry if SENTRY_DSN is set.

    Kept optional so local runs without a DSN remain silent rather than failing.
    Sentry tags are populated with the active run_id once a run begins (see
    ``runs.start_run``).
    """
    dsn = os.environ.get("SENTRY_DSN")
    if not dsn:
        return
    try:
        import sentry_sdk
    except ImportError:
        get_logger().warning("sentry_sdk_not_installed", hint="pip install retina-watch[sentry]")
        return
    sentry_sdk.init(
        dsn=dsn,
        traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.0")),
        environment=os.environ.get("SENTRY_ENV", "local"),
    )


def get_logger(**initial: Any) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger().bind(**initial)
