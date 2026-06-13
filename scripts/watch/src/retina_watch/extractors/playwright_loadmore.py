"""Load-more clicker extractor.

For paginated publication lists that expose a "Load More" button, the static
extractor only sees the first page of items. This driver loads the page in
Chromium, clicks the configured selector up to ``loadmore_max_clicks`` times
(waiting for ``networkidle`` between clicks), then runs the static extractor
over the fully expanded DOM.

Config:

* ``loadmore_selector`` (CSS, required): selector for the Load More button.
* ``loadmore_max_clicks`` (int, default 30): safety cap on click count.
* ``wait_until`` (default ``load``), ``timeout_ms`` (default 30000): forwarded
  to the initial page navigation.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass

from .. import db
from ..logging_setup import get_logger
from .base import ExtractedLink, register
from .html_pdf_links import extract as _static_extract


@dataclass
class _LMFetch:
    body: bytes
    http_status: int | None
    bytes: int
    sha256_head: str
    latency_ms: int
    clicks: int


def _do_loadmore_fetch(url: str, config: dict) -> _LMFetch:
    from playwright.sync_api import sync_playwright

    selector = config.get("loadmore_selector")
    if not selector:
        raise ValueError("loadmore_selector is required for playwright_loadmore")
    max_clicks = int(config.get("loadmore_max_clicks", 30))
    wait_until = config.get("wait_until", "load")
    timeout_ms = int(config.get("timeout_ms", 30000))

    started = time.monotonic()
    clicks = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            context = browser.new_context(
                user_agent=(
                    "glaucoma-watch/0.1 (+https://github.com/justinsyu/glaucoma-data; "
                    "observability-and-audit-trail) Chromium-headless"
                ),
            )
            page = context.new_page()
            response = page.goto(url, wait_until=wait_until, timeout=timeout_ms)
            status = response.status if response is not None else None

            while clicks < max_clicks:
                button = page.locator(selector).first
                try:
                    is_visible = button.is_visible(timeout=2000)
                except Exception:
                    is_visible = False
                if not is_visible:
                    break
                try:
                    button.click(timeout=timeout_ms)
                except Exception:
                    break
                clicks += 1
                try:
                    page.wait_for_load_state("networkidle", timeout=timeout_ms)
                except Exception:
                    page.wait_for_timeout(1500)

            html = page.content().encode("utf-8")
        finally:
            browser.close()

    latency_ms = int((time.monotonic() - started) * 1000)
    sha = hashlib.sha256(html[: 64 * 1024]).hexdigest()
    return _LMFetch(
        body=html,
        http_status=status,
        bytes=len(html),
        sha256_head=sha,
        latency_ms=latency_ms,
        clicks=clicks,
    )


def loadmore_render(*, url: str, run_id: str, source_id: str, config: dict) -> bytes | None:
    log = get_logger().bind(source_id=source_id, url=url, method="GET_LOADMORE")
    error: str | None = None
    fetched: _LMFetch | None = None
    started = time.monotonic()
    try:
        fetched = _do_loadmore_fetch(url, config)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        log.exception("loadmore_fetch_failed", error=error)
    latency_ms = int((time.monotonic() - started) * 1000)

    s = db.session()
    try:
        s.add(
            db.FetchEvent(
                run_id=run_id,
                source_id=source_id,
                url=url,
                method="GET_LOADMORE",
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
        "loadmore_fetch_done",
        http_status=fetched.http_status,
        bytes=fetched.bytes,
        latency_ms=fetched.latency_ms,
        clicks=fetched.clicks,
    )
    return fetched.body


@register("playwright_loadmore")
def extract(*, body: bytes, source_url: str, config: dict) -> list[ExtractedLink]:
    return _static_extract(body=body, source_url=source_url, config=config)
