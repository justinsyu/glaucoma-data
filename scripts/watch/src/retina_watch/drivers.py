"""Per-source-type driver registry.

Each driver knows how to obtain links for one ``source_type``. The pipeline
calls ``DRIVERS[source_type]`` with the watchlist entry and the active
``run_id``; the driver is responsible for performing whatever I/O is required
(HTTP, headless browser, structured API) and recording its own ``fetch_events``
rows. The pipeline persists the snapshot and computes the diff.

This indirection lets us add new source types (e.g., RSS, EDGAR, sitemaps)
without touching ``pipeline.py``: register a driver and a watchlist
``source_type`` value, and the engine picks it up.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .extractors import EXTRACTOR_REGISTRY, ExtractedLink
from .fetcher import fetch
from .logging_setup import get_logger
from .watchlist import SourceEntry


@dataclass
class DriverResult:
    links: list[ExtractedLink] | None
    status: str  # "ok", "fetch_failed", "extract_failed", "skipped"
    error: str | None = None
    reason: str | None = None
    cookies: list | None = None  # populated by playwright_hcp for downstream PDF download


Driver = Callable[[SourceEntry, str], DriverResult]
DRIVERS: dict[str, Driver] = {}


def register_driver(source_type: str) -> Callable[[Driver], Driver]:
    def _inner(fn: Driver) -> Driver:
        if source_type in DRIVERS:
            raise ValueError(f"driver {source_type!r} already registered")
        DRIVERS[source_type] = fn
        return fn

    return _inner


@register_driver("html_pdf_links")
def _static_html_driver(entry: SourceEntry, run_id: str) -> DriverResult:
    log = get_logger().bind(source_id=entry.source_id, driver="html_pdf_links")
    result = fetch(entry.url, run_id=run_id, source_id=entry.source_id)
    if result.skipped_reason:
        return DriverResult(links=None, status="skipped", reason=result.skipped_reason)
    if not result.ok:
        return DriverResult(links=None, status="fetch_failed", error=result.error)
    extractor = EXTRACTOR_REGISTRY["html_pdf_links"]
    try:
        links = extractor(body=result.body, source_url=entry.url, config=entry.extractor_config)
    except Exception as exc:
        log.exception("extractor_raised", error=str(exc))
        return DriverResult(links=None, status="extract_failed", error=str(exc))
    return DriverResult(links=links, status="ok")


@register_driver("html_pdf_links_js")
def _js_html_driver(entry: SourceEntry, run_id: str) -> DriverResult:
    log = get_logger().bind(source_id=entry.source_id, driver="html_pdf_links_js")
    try:
        from .extractors.html_pdf_links_js import js_render
    except ImportError as exc:
        log.error("playwright_not_installed", error=str(exc))
        return DriverResult(
            links=None,
            status="skipped",
            reason="playwright_not_installed",
        )

    try:
        body = js_render(
            url=entry.url,
            run_id=run_id,
            source_id=entry.source_id,
            config=entry.extractor_config,
        )
    except ImportError as exc:
        log.error("playwright_not_installed", error=str(exc))
        return DriverResult(
            links=None,
            status="skipped",
            reason="playwright_not_installed",
        )
    except Exception as exc:
        log.exception("js_render_failed", error=str(exc))
        return DriverResult(links=None, status="fetch_failed", error=str(exc))

    if body is None:
        return DriverResult(links=None, status="fetch_failed", error="js_render_returned_none")

    extractor = EXTRACTOR_REGISTRY["html_pdf_links_js"]
    try:
        links = extractor(body=body, source_url=entry.url, config=entry.extractor_config)
    except Exception as exc:
        log.exception("extractor_raised", error=str(exc))
        return DriverResult(links=None, status="extract_failed", error=str(exc))
    return DriverResult(links=links, status="ok")


# ----- Structured-API drivers -----
#
# These are registered lazily so a watchlist that does not reference them does
# not pay the import cost.


def _ensure_api_drivers_loaded() -> None:
    # Importing the modules triggers @register_driver below.
    from . import api_drivers  # noqa: F401


@register_driver("playwright_hcp")
def _hcp_driver(entry: SourceEntry, run_id: str) -> DriverResult:
    log = get_logger().bind(source_id=entry.source_id, driver="playwright_hcp")
    try:
        from .extractors.playwright_hcp import hcp_render
    except ImportError as exc:
        log.error("playwright_not_installed", error=str(exc))
        return DriverResult(links=None, status="skipped", reason="playwright_not_installed")

    extra_headers = dict(entry.extra_headers or {})
    if entry.referer:
        extra_headers.setdefault("Referer", entry.referer)

    try:
        body, cookies = hcp_render(
            url=entry.url,
            run_id=run_id,
            source_id=entry.source_id,
            config=entry.extractor_config,
            extra_headers=extra_headers or None,
        )
    except ImportError as exc:
        log.error("playwright_not_installed", error=str(exc))
        return DriverResult(links=None, status="skipped", reason="playwright_not_installed")
    except Exception as exc:
        log.exception("hcp_render_failed", error=str(exc))
        return DriverResult(links=None, status="fetch_failed", error=str(exc))

    if body is None:
        return DriverResult(links=None, status="fetch_failed", error="hcp_render_returned_none")

    extractor = EXTRACTOR_REGISTRY["playwright_hcp"]
    try:
        links = extractor(body=body, source_url=entry.url, config=entry.extractor_config)
    except Exception as exc:
        log.exception("extractor_raised", error=str(exc))
        return DriverResult(links=None, status="extract_failed", error=str(exc))
    return DriverResult(links=links, status="ok", cookies=cookies)


@register_driver("playwright_loadmore")
def _loadmore_driver(entry: SourceEntry, run_id: str) -> DriverResult:
    log = get_logger().bind(source_id=entry.source_id, driver="playwright_loadmore")
    try:
        from .extractors.playwright_loadmore import loadmore_render
    except ImportError as exc:
        log.error("playwright_not_installed", error=str(exc))
        return DriverResult(links=None, status="skipped", reason="playwright_not_installed")

    try:
        body = loadmore_render(
            url=entry.url,
            run_id=run_id,
            source_id=entry.source_id,
            config=entry.extractor_config,
        )
    except Exception as exc:
        log.exception("loadmore_render_failed", error=str(exc))
        return DriverResult(links=None, status="fetch_failed", error=str(exc))

    if body is None:
        return DriverResult(links=None, status="fetch_failed", error="loadmore_render_returned_none")

    extractor = EXTRACTOR_REGISTRY["playwright_loadmore"]
    try:
        links = extractor(body=body, source_url=entry.url, config=entry.extractor_config)
    except Exception as exc:
        log.exception("extractor_raised", error=str(exc))
        return DriverResult(links=None, status="extract_failed", error=str(exc))
    return DriverResult(links=links, status="ok")
