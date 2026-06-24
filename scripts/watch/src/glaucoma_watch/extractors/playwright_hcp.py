"""HCP / Akamai click-through extractor.

Some pharma publication portals sit behind one of two gates:

1. **Akamai bot mitigation**. The first response is an empty shell; JavaScript
   embedded in that shell runs a fingerprinting challenge and sets ``_abck`` /
   ``bm_sz`` cookies. Subsequent navigations from the same browser context
   pass. Solution: load the page in headless Chromium, wait
   ``bot_clear_seconds`` (default 5) for the JS challenge to complete, then
   navigate again or extract.

2. **HCP attestation modal**. A "I am a healthcare professional" overlay must
   be dismissed before the page reveals its content. Solution: a configured
   ``hcp_action`` string of the form ``click:<selector>``, ``wait:<ms>``, or
   ``eval:<js>``.

This driver combines the two. It writes one ``fetch_events`` row with
``method='GET_HCP'`` so operators can filter HCP-gated fetches from plain
static or JS fetches.

The extractor returned by this module is a thin wrapper over the static
``html_pdf_links`` extractor: it takes the rendered HTML and applies the same
selectors. The interesting work happens in ``hcp_render`` which the matching
driver calls.

Configurable via ``extractor_config``:

* ``bot_clear_seconds`` (int, default 5): seconds to wait after the initial
  navigation for Akamai cookies to settle.
* ``hcp_action`` (str, optional): one of
  ``click:<css>``, ``wait:<ms>``, ``eval:<js>``. Executed after the bot-clear
  wait but before extraction.
* ``wait_until`` (str, default ``load``): Playwright's wait_until value for
  the initial navigation.
* ``timeout_ms`` (int, default 30000): per-navigation timeout.
* ``post_action_wait_ms`` (int, default 2000): pause after the hcp_action
  fires so the page can re-render before we read it.
* ``link_selector``, ``url_must_match``, ``url_must_not_match``: forwarded to
  the static extractor (so callers can override the default ``\\.pdf$`` rule).
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass

from .. import db
from ..logging_setup import get_logger
from .base import ExtractedLink, register
from .html_pdf_links import extract as _static_extract


_DEFAULT_BOT_CLEAR_SECONDS = 5
_DEFAULT_TIMEOUT_MS = 30000
_DEFAULT_POST_ACTION_WAIT_MS = 2000

# Akamai and Cloudflare fingerprint the User-Agent against the browser's
# JS fingerprint. The custom archive watcher UA fails the match and triggers a
# 403 on Bayer's portal. A real Chrome UA passes. This default can still be
# overridden per-source via ``extractor_config.user_agent``.
_REAL_CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


@dataclass
class _HCPFetch:
    body: bytes
    http_status: int | None
    bytes: int
    sha256_head: str
    latency_ms: int
    cookies: list[dict]


def _run_hcp_action(page, action: str, timeout_ms: int) -> None:
    """Dispatch a single ``hcp_action`` directive against a Playwright page."""
    log = get_logger().bind(hcp_action=action)
    if ":" not in action:
        raise ValueError(f"hcp_action must be of the form <kind>:<argument>; got {action!r}")
    kind, _, argument = action.partition(":")
    kind = kind.strip().lower()
    argument = argument.strip()

    if kind == "click":
        log.info("hcp_action_click", selector=argument)
        page.locator(argument).first.click(timeout=timeout_ms)
    elif kind == "wait":
        try:
            ms = int(argument)
        except ValueError as exc:
            raise ValueError(f"hcp_action 'wait' needs an integer ms; got {argument!r}") from exc
        log.info("hcp_action_wait", ms=ms)
        page.wait_for_timeout(ms)
    elif kind == "eval":
        log.info("hcp_action_eval", js_len=len(argument))
        page.evaluate(argument)
    else:
        raise ValueError(f"unknown hcp_action kind {kind!r}; supported: click, wait, eval")


def _do_hcp_fetch(url: str, config: dict, extra_headers: dict | None = None) -> _HCPFetch:
    from playwright.sync_api import sync_playwright

    wait_until = config.get("wait_until", "load")
    timeout_ms = int(config.get("timeout_ms", _DEFAULT_TIMEOUT_MS))
    bot_clear_seconds = float(config.get("bot_clear_seconds", _DEFAULT_BOT_CLEAR_SECONDS))
    hcp_action = config.get("hcp_action")
    post_action_wait_ms = int(config.get("post_action_wait_ms", _DEFAULT_POST_ACTION_WAIT_MS))

    user_agent = config.get("user_agent") or _REAL_CHROME_UA
    started = time.monotonic()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            merged_headers = {"Accept-Language": "en-US,en;q=0.9"}
            if extra_headers:
                merged_headers.update(extra_headers)
            context = browser.new_context(
                user_agent=user_agent,
                extra_http_headers=merged_headers,
            )
            page = context.new_page()
            response = page.goto(url, wait_until=wait_until, timeout=timeout_ms)
            status = response.status if response is not None else None

            # Bot clear: give Akamai's JS challenge time to set _abck / bm_sz.
            if bot_clear_seconds > 0:
                page.wait_for_timeout(int(bot_clear_seconds * 1000))

            # HCP attestation gate.
            if hcp_action:
                try:
                    _run_hcp_action(page, hcp_action, timeout_ms)
                    page.wait_for_timeout(post_action_wait_ms)
                    page.wait_for_load_state("networkidle", timeout=timeout_ms)
                except Exception as exc:
                    # Action failure is recoverable: the page may already be in
                    # the cleared state from a prior session, or the selector
                    # may not be present today. Log and proceed with whatever
                    # HTML we have.
                    get_logger().warning(
                        "hcp_action_failed_continuing",
                        error=f"{type(exc).__name__}: {exc}",
                        action=hcp_action,
                    )

            html = page.content().encode("utf-8")
            cookies = context.cookies()
        finally:
            browser.close()

    latency_ms = int((time.monotonic() - started) * 1000)
    sha = hashlib.sha256(html[: 64 * 1024]).hexdigest()
    return _HCPFetch(
        body=html,
        http_status=status,
        bytes=len(html),
        sha256_head=sha,
        latency_ms=latency_ms,
        cookies=cookies,
    )


def hcp_render(
    *,
    url: str,
    run_id: str,
    source_id: str,
    config: dict,
    extra_headers: dict | None = None,
) -> tuple[bytes | None, list[dict]]:
    """Render ``url`` through an HCP gate and record a fetch_events row.

    Returns ``(html_bytes, cookies)`` so a downstream PDF downloader can replay
    the cleared session. Cookies are recorded but not persisted to the DB
    (they typically expire within minutes and contain Akamai-specific tokens).
    """
    log = get_logger().bind(source_id=source_id, url=url, method="GET_HCP")
    error: str | None = None
    fetched: _HCPFetch | None = None
    started = time.monotonic()
    try:
        fetched = _do_hcp_fetch(url, config, extra_headers=extra_headers)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        log.exception("hcp_fetch_failed", error=error)
    latency_ms = int((time.monotonic() - started) * 1000)

    s = db.session()
    try:
        s.add(
            db.FetchEvent(
                run_id=run_id,
                source_id=source_id,
                url=url,
                method="GET_HCP",
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
        return None, []
    log.info(
        "hcp_fetch_done",
        http_status=fetched.http_status,
        bytes=fetched.bytes,
        latency_ms=fetched.latency_ms,
        cookies=len(fetched.cookies),
    )
    return fetched.body, fetched.cookies


@register("playwright_hcp")
def extract(*, body: bytes, source_url: str, config: dict) -> list[ExtractedLink]:
    """Apply the static html_pdf_links rules to HCP-rendered HTML."""
    return _static_extract(body=body, source_url=source_url, config=config)
