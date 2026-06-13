"""JS-rendering extractor.

Wraps the static ``html_pdf_links`` extractor with a Playwright headless
Chromium fetch so JavaScript-rendered link lists become visible. The watchlist
entry's ``extractor_config`` accepts everything the static extractor accepts
plus:

* ``wait_until`` (default ``networkidle``): one of Playwright's wait_until values.
* ``wait_for_selector`` (optional): block until this selector appears.
* ``scroll_to_bottom`` (default False): scroll the page to trigger lazy load.
* ``timeout_ms`` (default 30000): per-page navigation timeout.

The fetcher does not call this extractor directly. Instead, the pipeline
detects ``source_type == 'html_pdf_links_js'``, calls
``js_render_to_bytes(entry)`` to produce the rendered HTML, records a synthetic
``fetch_events`` row for that work, and then dispatches the bytes through the
shared static extractor.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .. import db
from ..logging_setup import get_logger
from .base import ExtractedLink, register
from .html_pdf_links import extract as _static_extract

if TYPE_CHECKING:  # avoid importing playwright at module import time
    pass


@dataclass
class _JSFetch:
    body: bytes
    http_status: int | None
    bytes: int
    sha256_head: str
    latency_ms: int


def _do_js_fetch(url: str, config: dict) -> _JSFetch:
    """Render ``url`` in headless Chromium and return the final HTML."""
    # Lazy import so installs without Playwright still load this module.
    from playwright.sync_api import sync_playwright

    wait_until = config.get("wait_until", "networkidle")
    wait_for_selector = config.get("wait_for_selector")
    scroll_to_bottom = bool(config.get("scroll_to_bottom", False))
    timeout_ms = int(config.get("timeout_ms", 30000))

    started = time.monotonic()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            context = browser.new_context(
                user_agent=(
                    "glaucoma-watch/0.1 (+https://github.com/justinsyu/glaucoma-data; "
                    "observability-and-audit-trail) Chromium-headless"
                )
            )
            page = context.new_page()
            response = page.goto(url, wait_until=wait_until, timeout=timeout_ms)
            status = response.status if response is not None else None
            if wait_for_selector:
                page.wait_for_selector(wait_for_selector, timeout=timeout_ms)
            if scroll_to_bottom:
                page.evaluate(
                    "() => new Promise(resolve => {"
                    " let total = 0;"
                    " const id = setInterval(() => {"
                    "   window.scrollBy(0, 800);"
                    "   total += 800;"
                    "   if (total >= document.body.scrollHeight + 1000) { clearInterval(id); resolve(); }"
                    " }, 250);"
                    "})"
                )
                page.wait_for_load_state("networkidle", timeout=timeout_ms)
            html = page.content().encode("utf-8")
        finally:
            browser.close()

    latency_ms = int((time.monotonic() - started) * 1000)
    sha = hashlib.sha256(html[: 64 * 1024]).hexdigest()
    return _JSFetch(
        body=html,
        http_status=status,
        bytes=len(html),
        sha256_head=sha,
        latency_ms=latency_ms,
    )


def js_render(
    *, url: str, run_id: str, source_id: str, config: dict
) -> bytes | None:
    """Render ``url`` and record a fetch_events row. Returns the HTML body or None.

    The recorded fetch_events row uses ``method='GET_JS'`` so operators can
    filter JS fetches from static fetches in the audit trail.
    """
    log = get_logger().bind(source_id=source_id, url=url, method="GET_JS")
    error: str | None = None
    fetched: _JSFetch | None = None
    started = time.monotonic()
    try:
        fetched = _do_js_fetch(url, config)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        log.exception("js_fetch_failed", error=error)
    latency_ms = int((time.monotonic() - started) * 1000)

    s = db.session()
    try:
        s.add(
            db.FetchEvent(
                run_id=run_id,
                source_id=source_id,
                url=url,
                method="GET_JS",
                http_status=fetched.http_status if fetched else None,
                bytes=fetched.bytes if fetched else None,
                sha256_head=fetched.sha256_head if fetched else None,
                latency_ms=fetched.latency_ms if fetched else latency_ms,
                retries=0,
                error=error,
            )
        )
        s.commit()
    finally:
        s.close()

    if fetched is None:
        return None
    log.info(
        "js_fetch_done",
        http_status=fetched.http_status,
        bytes=fetched.bytes,
        latency_ms=fetched.latency_ms,
    )
    return fetched.body


@register("html_pdf_links_js")
def extract(*, body: bytes, source_url: str, config: dict) -> list[ExtractedLink]:
    """Re-uses the static extractor on rendered HTML."""
    return _static_extract(body=body, source_url=source_url, config=config)
