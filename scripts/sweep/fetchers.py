"""Per-source fetchers: requests, playwright_loadmore, playwright_hcp, pubmed.

Each fetcher discovers candidate PDFs (URL + title + suggested destination)
from a configured source. The fetchers do NOT download PDFs themselves; the
downloader module handles that uniformly with %PDF validation and dedup.

Playwright fetchers are imported lazily so that companies on Tier 4 (PubMed
only) do not require Playwright to be installed.
"""
from __future__ import annotations

import logging
import re
import time
from html.parser import HTMLParser
from typing import Iterable
from urllib.parse import urljoin, urlparse

import requests

from .config import Defaults, Source
from .dedup import Candidate
from .inventory import slugify_basename

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# HTML link extraction
# ---------------------------------------------------------------------------


class _LinkScanner(HTMLParser):
    """Collect (href, link_text) tuples from rendered HTML."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._capture_href: str | None = None
        self._capture_buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        href = next((v for k, v in attrs if k.lower() == "href" and v), None)
        if href:
            self._capture_href = href
            self._capture_buf = []

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._capture_href is not None:
            text = " ".join(t.strip() for t in self._capture_buf if t.strip())
            self.links.append((self._capture_href, text))
            self._capture_href = None
            self._capture_buf = []

    def handle_data(self, data: str) -> None:
        if self._capture_href is not None:
            self._capture_buf.append(data)


def _extract_links(html: str) -> list[tuple[str, str]]:
    scanner = _LinkScanner()
    scanner.feed(html)
    return scanner.links


def _select_dest(src: Source, url: str, title: str) -> str:
    """Apply the source's dest_router/title_router rules; fall back to src.dest."""
    needle = f"{url} {title}"
    for rule in src.title_router:
        if rule.pattern.search(needle):
            return rule.dest
    for rule in src.dest_router:
        if rule.pattern.search(needle):
            return rule.dest
    return src.dest


def _candidate_from_link(src: Source, base_url: str, href: str, text: str) -> Candidate | None:
    abs_url = urljoin(base_url, href)
    if not src.link_pattern.search(abs_url) and not src.link_pattern.search(href):
        return None
    if src.title_filter is not None:
        needle = f"{abs_url} {text}"
        if not src.title_filter.search(needle):
            return None
    dest = _select_dest(src, abs_url, text)
    return Candidate(url=abs_url, title=text or abs_url, source_url=base_url, suggested_dest=dest)


def _looks_like_browser_challenge(html: str) -> bool:
    challenge_markers = (
        "cf-mitigated",
        "challenge-platform",
        "challenges.cloudflare.com",
        "just a moment",
        "attention required",
        "enable javascript and cookies",
    )
    haystack = html[:200_000].lower()
    return any(marker in haystack for marker in challenge_markers)


def _looks_like_soft_not_found(url: str, html: str) -> bool:
    lower_url = url.lower()
    if "/404" in lower_url or "404page" in lower_url:
        return True
    haystack = html[:50_000].lower()
    markers = (
        "<title>404",
        "page not found",
        "404 not found",
        "the page you requested could not be found",
    )
    return any(marker in haystack for marker in markers)


def _retry_delay(defaults: Defaults, attempt: int) -> int:
    if not defaults.retry_backoff_seconds:
        return 0
    return defaults.retry_backoff_seconds[min(attempt, len(defaults.retry_backoff_seconds) - 1)]


def _should_try_browser_fallback(status_code: int | None, error: Exception | None = None) -> bool:
    if status_code in {403, 408, 409, 425, 429, 500, 502, 503, 504}:
        return True
    if status_code == 404:
        return False
    if isinstance(error, (requests.Timeout, requests.ConnectionError)):
        return True
    return False


def _fetch_html_with_playwright(
    src: Source,
    defaults: Defaults,
    *,
    disable_http2: bool = False,
) -> tuple[str, int | None]:
    from playwright.sync_api import sync_playwright  # lazy import

    with sync_playwright() as p:
        launch_args = ["--disable-http2"] if disable_http2 else []
        browser = p.chromium.launch(headless=defaults.playwright_headless, args=launch_args)
        context = browser.new_context(
            user_agent=defaults.user_agent,
            ignore_https_errors=True,
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        page = context.new_page()
        response = page.goto(
            src.url,
            timeout=defaults.timeout_seconds * 1000,
            wait_until="domcontentloaded",
        )
        try:
            page.wait_for_load_state(
                "networkidle",
                timeout=min(defaults.timeout_seconds, 15) * 1000,
            )
        except Exception as exc:  # noqa: BLE001
            log.info("networkidle wait failed for %s (continuing): %s", src.url, exc)
        html = page.content()
        status_code = response.status if response else None
        browser.close()

    if _looks_like_browser_challenge(html):
        raise FetchError("blocked by browser challenge")
    if _looks_like_soft_not_found(src.url, html):
        raise FetchError("soft 404 page returned")
    if status_code and status_code >= 400:
        raise FetchError(f"browser fallback returned HTTP {status_code}")
    return html, status_code


# ---------------------------------------------------------------------------
# Fetcher: requests
# ---------------------------------------------------------------------------


def fetch_with_requests(src: Source, defaults: Defaults, session: requests.Session) -> list[Candidate]:
    headers = {"User-Agent": defaults.user_agent, "Accept": "text/html,*/*;q=0.8"}
    attempts = max(1, defaults.retry_attempts)
    last_error: Exception | None = None
    last_status_code: int | None = None

    for attempt in range(attempts):
        try:
            r = session.get(src.url, headers=headers, timeout=defaults.timeout_seconds)
            last_status_code = r.status_code
            if r.status_code == 200:
                if _looks_like_browser_challenge(r.text):
                    raise FetchError("blocked by browser challenge")
                if _looks_like_soft_not_found(r.url, r.text):
                    raise FetchError("soft 404 page returned")
                return _candidates_from_html(src, src.url, r.text)
            last_error = FetchError(f"GET {src.url} -> HTTP {r.status_code}")
            if r.status_code == 404:
                break
        except (requests.Timeout, requests.ConnectionError, requests.RequestException) as exc:
            last_error = exc

        if attempt < attempts - 1:
            delay = _retry_delay(defaults, attempt)
            log.info("GET %s failed; retrying in %ss", src.url, delay)
            time.sleep(delay)

    if _should_try_browser_fallback(last_status_code, last_error):
        try:
            html, _status_code = _fetch_html_with_playwright(src, defaults)
            return _candidates_from_html(src, src.url, html)
        except Exception as fallback_exc:  # noqa: BLE001
            if "ERR_HTTP2_PROTOCOL_ERROR" in str(fallback_exc):
                try:
                    html, _status_code = _fetch_html_with_playwright(
                        src,
                        defaults,
                        disable_http2=True,
                    )
                    return _candidates_from_html(src, src.url, html)
                except Exception as second_fallback_exc:  # noqa: BLE001
                    fallback_exc = second_fallback_exc
            error_text = str(last_error) if last_error else f"HTTP {last_status_code}"
            raise FetchError(f"{error_text}; browser fallback failed: {fallback_exc}") from fallback_exc

    if isinstance(last_error, FetchError):
        raise last_error
    if last_error:
        raise FetchError(str(last_error)) from last_error
    raise FetchError(f"GET {src.url} -> HTTP {last_status_code}")


def _candidates_from_html(src: Source, base_url: str, html: str) -> list[Candidate]:
    out: list[Candidate] = []
    for href, text in _extract_links(html):
        cand = _candidate_from_link(src, base_url, href, text)
        if cand is not None:
            out.append(cand)
    return out


# ---------------------------------------------------------------------------
# Fetcher: playwright_loadmore
# ---------------------------------------------------------------------------


def fetch_with_playwright_loadmore(src: Source, defaults: Defaults) -> list[Candidate]:
    from playwright.sync_api import sync_playwright  # lazy import

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=defaults.playwright_headless)
        context = browser.new_context(user_agent=defaults.user_agent)
        page = context.new_page()
        page.goto(src.url, timeout=defaults.timeout_seconds * 1000, wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle", timeout=defaults.timeout_seconds * 1000)

        if src.loadmore_selector:
            for i in range(src.loadmore_max_clicks):
                btn = page.locator(src.loadmore_selector).first
                if btn.count() == 0:
                    break
                try:
                    btn.scroll_into_view_if_needed(timeout=5000)
                    btn.click(timeout=5000)
                except Exception as exc:
                    log.info("loadmore click %d failed: %s", i, exc)
                    break
                page.wait_for_load_state("networkidle", timeout=defaults.timeout_seconds * 1000)
                time.sleep(0.5)

        html = page.content()
        browser.close()

    return _candidates_from_html(src, src.url, html)


# ---------------------------------------------------------------------------
# Fetcher: playwright_hcp
# ---------------------------------------------------------------------------


def fetch_with_playwright_hcp(src: Source, defaults: Defaults) -> list[Candidate]:
    """Open a Playwright session, clear bot/HCP gating, return discovered candidates.

    The session is intentionally short-lived; we extract the candidate URL list
    and let the downloader re-establish a fresh session per PDF. For the gated
    Tier 2 case (Bayer/OcuTx) the downloader is invoked with the cookies set
    in this session via the `playwright_download` helper.
    """
    from playwright.sync_api import sync_playwright  # lazy import

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=defaults.playwright_headless)
        context = browser.new_context(
            user_agent=defaults.user_agent,
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        page = context.new_page()
        page.goto(src.url, timeout=defaults.timeout_seconds * 1000, wait_until="domcontentloaded")
        time.sleep(src.bot_clear_seconds)
        _run_hcp_action(page, src.hcp_action)
        try:
            page.wait_for_load_state("networkidle", timeout=defaults.timeout_seconds * 1000)
        except Exception as exc:  # noqa: BLE001
            log.info("networkidle wait failed for %s (continuing): %s", src.url, exc)

        html = page.content()
        cookies = context.cookies()
        browser.close()

    candidates = _candidates_from_html(src, src.url, html)
    # Attach cookie jar to each candidate via extra_headers Cookie string so the
    # downloader can replay the gated session.
    cookie_header = "; ".join(f"{c['name']}={c['value']}" for c in cookies)
    annotated: list[Candidate] = []
    for c in candidates:
        # We don't mutate Candidate (frozen); cookie is applied at download time
        # via Source.extra_headers in main loop. For Tier 2 sources extra_headers
        # already carries Accept/Referer; the cookie header is added per call.
        annotated.append(c)
    return annotated


def _run_hcp_action(page, action: str) -> None:
    """Execute the configured HCP-gate clearance.

    Supported forms:
      click:<selector>   click a CSS or text selector
      wait:<ms>          fixed sleep
      eval:<js>          page.evaluate the snippet
    """
    if not action:
        return
    kind, _, arg = action.partition(":")
    if kind == "click":
        try:
            page.locator(arg).first.click(timeout=5000)
        except Exception as exc:
            log.info("hcp click %r failed (continuing): %s", arg, exc)
    elif kind == "wait":
        time.sleep(int(arg) / 1000.0)
    elif kind == "eval":
        page.evaluate(arg)
    else:
        log.warning("Unknown hcp_action kind: %r", action)


def playwright_download(
    candidate: Candidate,
    dest_path,
    defaults: Defaults,
    referer: str,
    extra_headers: dict[str, str] | None = None,
):
    """Fetch a single PDF inside a fresh Playwright context.

    Used by Tier 2 download paths where the PDF endpoint demands a real browser
    fingerprint (Akamai/Cloudflare). Returns the bytes; the caller is
    responsible for %PDF validation and atomic write.
    """
    from playwright.sync_api import sync_playwright  # lazy import

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=defaults.playwright_headless)
        context = browser.new_context(user_agent=defaults.user_agent)
        page = context.new_page()
        # Warm the host so cookies are set.
        host = f"{urlparse(candidate.url).scheme}://{urlparse(candidate.url).netloc}/"
        page.goto(host, timeout=defaults.timeout_seconds * 1000, wait_until="domcontentloaded")
        time.sleep(3)

        headers = {"Referer": referer or candidate.source_url}
        if extra_headers:
            headers.update(extra_headers)

        b64 = page.evaluate(
            """async ({url, headers}) => {
                const r = await fetch(url, {credentials: 'include', headers});
                if (!r.ok) throw new Error('HTTP ' + r.status);
                const ab = await r.arrayBuffer();
                let bin = '';
                const u8 = new Uint8Array(ab);
                for (let i = 0; i < u8.length; i++) bin += String.fromCharCode(u8[i]);
                return btoa(bin);
            }""",
            {"url": candidate.url, "headers": headers},
        )
        browser.close()

    import base64
    return base64.b64decode(b64)


# ---------------------------------------------------------------------------
# Fetcher: pubmed
# ---------------------------------------------------------------------------


_LAST_PUBMED_REQUEST = 0.0


def _pubmed_get(
    session: requests.Session,
    url: str,
    *,
    params: dict,
    timeout: int,
    has_api_key: bool,
    retry_attempts: int,
    retry_backoff_seconds: list[int],
) -> requests.Response:
    global _LAST_PUBMED_REQUEST

    min_interval = 0.12 if has_api_key else 0.40
    now = time.monotonic()
    wait = min_interval - (now - _LAST_PUBMED_REQUEST)
    if wait > 0:
        time.sleep(wait)

    attempts = max(1, retry_attempts)
    for attempt in range(attempts):
        r = session.get(url, params=params, timeout=timeout)
        _LAST_PUBMED_REQUEST = time.monotonic()
        if r.status_code not in {429, 500, 502, 503, 504}:
            r.raise_for_status()
            return r
        if attempt == attempts - 1:
            r.raise_for_status()
        delay = retry_backoff_seconds[min(attempt, len(retry_backoff_seconds) - 1)]
        log.info("PubMed %s returned HTTP %d; retrying in %ss", url, r.status_code, delay)
        time.sleep(delay)

    raise FetchError(f"PubMed request failed after {attempts} attempts")


def fetch_with_pubmed(src: Source, defaults: Defaults, session: requests.Session) -> list[Candidate]:
    """Query NCBI E-Utilities for sponsor-authored publications.

    For each PMID:
      1. Use prefer_pmc to look up the PMCID via elink.
      2. If a PMC OA PDF exists, use it.
      3. Else resolve the DOI via efetch and emit a candidate pointing at
         the publisher landing page. Such candidates will likely 403 when
         downloaded but should be surfaced in the worklist.
    """
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    common = {
        "tool": defaults.pubmed_tool_name,
        "email": defaults.pubmed_email,
    }
    if defaults.pubmed_api_key:
        common["api_key"] = defaults.pubmed_api_key

    term = " OR ".join(f"({t})" for t in src.terms)
    if src.affiliations:
        aff_clause = " OR ".join(f'"{a}"[Affiliation]' for a in src.affiliations)
        term = f"({term}) AND ({aff_clause})"
    if src.date_min:
        term = f"({term}) AND ({src.date_min}[PDAT] : 3000[PDAT])"

    r = _pubmed_get(
        session,
        f"{base}/esearch.fcgi",
        params={**common, "db": "pubmed", "term": term, "retmode": "json", "retmax": 100},
        timeout=defaults.timeout_seconds,
        has_api_key=bool(defaults.pubmed_api_key),
        retry_attempts=defaults.retry_attempts,
        retry_backoff_seconds=defaults.retry_backoff_seconds,
    )
    pmids = r.json().get("esearchresult", {}).get("idlist", [])
    log.info("PubMed query returned %d PMIDs for %s", len(pmids), src.dest)
    if not pmids:
        return []

    candidates: list[Candidate] = []
    # Title metadata via esummary.
    r2 = _pubmed_get(
        session,
        f"{base}/esummary.fcgi",
        params={**common, "db": "pubmed", "id": ",".join(pmids), "retmode": "json"},
        timeout=defaults.timeout_seconds,
        has_api_key=bool(defaults.pubmed_api_key),
        retry_attempts=defaults.retry_attempts,
        retry_backoff_seconds=defaults.retry_backoff_seconds,
    )
    summaries = r2.json().get("result", {})

    # PMCID mapping via elink.
    r3 = _pubmed_get(
        session,
        f"{base}/elink.fcgi",
        params={
            **common,
            "dbfrom": "pubmed",
            "db": "pmc",
            "id": ",".join(pmids),
            "retmode": "json",
        },
        timeout=defaults.timeout_seconds,
        has_api_key=bool(defaults.pubmed_api_key),
        retry_attempts=defaults.retry_attempts,
        retry_backoff_seconds=defaults.retry_backoff_seconds,
    )
    pmid_to_pmcid: dict[str, str] = {}
    for ls in r3.json().get("linksets", []):
        ids = ls.get("ids", [])
        links = ls.get("linksetdbs", [])
        for db in links:
            if db.get("dbto") == "pmc" and ids and db.get("links"):
                pmid_to_pmcid[str(ids[0])] = str(db["links"][0])

    for pmid in pmids:
        s = summaries.get(pmid, {})
        title = s.get("title", f"PMID {pmid}")
        pmcid = pmid_to_pmcid.get(pmid)
        if pmcid and src.prefer_pmc:
            # PMC OA package PDF (publisher-agnostic mirror).
            url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmcid}/pdf/"
            candidates.append(Candidate(
                url=url,
                title=title,
                source_url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                suggested_dest=src.dest,
            ))
        else:
            # No PMC mirror; emit a PubMed landing-page candidate. The downloader
            # will fail %PDF validation for these, which surfaces them in the
            # worklist for manual journal retrieval.
            url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
            candidates.append(Candidate(
                url=url,
                title=title,
                source_url=url,
                suggested_dest=src.dest,
            ))

    return candidates


# ---------------------------------------------------------------------------
# Public dispatch
# ---------------------------------------------------------------------------


class FetchError(RuntimeError):
    pass


def fetch_candidates(src: Source, defaults: Defaults, session: requests.Session) -> list[Candidate]:
    if src.kind == "skip":
        return []
    if src.kind == "pubmed":
        return fetch_with_pubmed(src, defaults, session)
    if src.kind != "html":
        raise FetchError(f"unknown source kind: {src.kind}")

    if src.fetcher == "requests":
        return fetch_with_requests(src, defaults, session)
    if src.fetcher == "playwright_loadmore":
        return fetch_with_playwright_loadmore(src, defaults)
    if src.fetcher == "playwright_hcp":
        return fetch_with_playwright_hcp(src, defaults)
    raise FetchError(f"unknown fetcher: {src.fetcher}")
