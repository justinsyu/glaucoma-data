#!/usr/bin/env python3
"""Run the Glaucoma Data press-release source sweep and write audit artifacts."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
import yaml

from build_automation_audit import expected_press_release_sources, rel


ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "_data" / "company_press_releases.yml"
RUNS_DIR = ROOT / "artifacts" / "automation_runs"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0 Safari/537.36 RetinaDataPressReleaseSweep/1.0"
)


@dataclass
class Candidate:
    title: str
    url: str
    date: str = ""


@dataclass
class FetchResult:
    html: str
    content_type: str = ""
    method: str = "requests"
    status_code: int | None = None
    url: str = ""


class FetchError(RuntimeError):
    def __init__(self, message: str, *, kind: str = "fetch_error") -> None:
        super().__init__(message)
        self.kind = kind


class PressLinkParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.links: list[dict[str, str]] = []
        self._stack: list[dict[str, Any]] = []
        self.page_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key.lower(): value or "" for key, value in attrs}
        if tag.lower() == "a" and attr_map.get("href"):
            self._stack.append({
                "href": urljoin(self.base_url, attr_map["href"]),
                "text": [],
            })

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or not self._stack:
            return
        current = self._stack.pop()
        text = normalize_space(" ".join(current["text"]))
        if text:
            self.links.append({"href": current["href"], "text": text})

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.page_text.append(text)
            for item in self._stack:
                item["text"].append(text)


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def run_id() -> str:
    return "press-release-sweep-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def read_existing_rows() -> list[dict[str, Any]]:
    if not DATA_PATH.exists():
        return []
    data = yaml.safe_load(DATA_PATH.read_text(encoding="utf-8")) or []
    return data if isinstance(data, list) else []


def existing_keys(rows: list[dict[str, Any]]) -> set[str]:
    keys: set[str] = set()
    for row in rows:
        source_url = str(row.get("source_url") or "").strip().lower()
        title = str(row.get("title") or "").strip().lower()
        date = str(row.get("date") or "").strip()
        company_slug = str(row.get("company_slug") or "").strip().lower()
        if source_url:
            keys.add(f"url:{source_url}")
        if title and company_slug and date:
            keys.add(f"row:{company_slug}:{date}:{title}")
    return keys


def looks_like_browser_challenge(html: str) -> bool:
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


def looks_like_soft_not_found(url: str, html: str) -> bool:
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


def retry_delay(attempt: int, backoff_seconds: list[int]) -> int:
    if not backoff_seconds:
        return 0
    return backoff_seconds[min(attempt, len(backoff_seconds) - 1)]


def should_try_browser_fallback(status_code: int | None, error: Exception | None = None) -> bool:
    if status_code in {403, 408, 409, 425, 429, 500, 502, 503, 504}:
        return True
    if status_code == 404:
        return False
    if isinstance(error, (requests.Timeout, requests.ConnectionError)):
        return True
    return False


def classify_error(message: str) -> str:
    lower = message.lower()
    if "getaddrinfo failed" in lower or "nameresolutionerror" in lower:
        return "dns_error"
    if "http 404" in lower:
        return "not_found"
    if "http 403" in lower or "blocked by browser challenge" in lower:
        return "blocked"
    if "read timed out" in lower or "timeout" in lower:
        return "timeout"
    if "err_http2_protocol_error" in lower:
        return "http2_protocol_error"
    if "ssl" in lower or "certificate" in lower:
        return "tls_error"
    return "fetch_error"


def fetch_with_browser(
    url: str,
    timeout: int,
    headless: bool,
    *,
    disable_http2: bool = False,
) -> FetchResult:
    try:
        from playwright.sync_api import sync_playwright  # noqa: PLC0415
    except Exception as exc:  # noqa: BLE001
        raise FetchError(f"Browser fallback unavailable: {type(exc).__name__}: {exc}") from exc

    with sync_playwright() as p:
        launch_args = ["--disable-http2"] if disable_http2 else []
        browser = p.chromium.launch(headless=headless, args=launch_args)
        context = browser.new_context(
            user_agent=USER_AGENT,
            ignore_https_errors=True,
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        page = context.new_page()
        response = page.goto(url, timeout=timeout * 1000, wait_until="domcontentloaded")
        try:
            page.wait_for_load_state("networkidle", timeout=min(timeout, 15) * 1000)
        except Exception:
            pass
        html = page.content()
        status_code = response.status if response else None
        content_type = response.headers.get("content-type", "") if response else ""
        browser.close()

    if looks_like_browser_challenge(html):
        raise FetchError("Blocked by browser challenge")
    if looks_like_soft_not_found(url, html):
        raise FetchError("Soft 404 page returned", kind="not_found")
    if status_code and status_code >= 400:
        raise FetchError(f"Browser fallback returned HTTP {status_code}")
    return FetchResult(
        html=html,
        content_type=content_type,
        method="playwright_no_http2" if disable_http2 else "playwright",
        status_code=status_code,
        url=url,
    )


def fetch_url(
    session: requests.Session,
    url: str,
    *,
    timeout: int,
    retry_attempts: int,
    retry_backoff_seconds: list[int],
    browser_fallback: bool,
    browser_headless: bool,
) -> FetchResult:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    attempts = max(1, retry_attempts)
    last_error: Exception | None = None
    last_status_code: int | None = None

    for attempt in range(attempts):
        try:
            response = session.get(url, headers=headers, timeout=timeout)
            last_status_code = response.status_code
            if response.status_code == 200:
                if looks_like_browser_challenge(response.text):
                    raise FetchError("Blocked by browser challenge")
                if looks_like_soft_not_found(response.url, response.text):
                    raise FetchError("Soft 404 page returned", kind="not_found")
                return FetchResult(
                    html=response.text,
                    content_type=response.headers.get("content-type", ""),
                    method="requests",
                    status_code=response.status_code,
                    url=url,
                )
            last_error = FetchError(f"HTTP {response.status_code}")
            if response.status_code == 404:
                break
        except (requests.Timeout, requests.ConnectionError, requests.RequestException) as exc:
            last_error = exc

        if attempt < attempts - 1:
            time.sleep(retry_delay(attempt, retry_backoff_seconds))

    if browser_fallback and should_try_browser_fallback(last_status_code, last_error):
        try:
            return fetch_with_browser(url, timeout=timeout, headless=browser_headless)
        except Exception as fallback_exc:
            fallback_text = str(fallback_exc)
            if "ERR_HTTP2_PROTOCOL_ERROR" in fallback_text:
                try:
                    return fetch_with_browser(
                        url,
                        timeout=timeout,
                        headless=browser_headless,
                        disable_http2=True,
                    )
                except Exception as second_fallback_exc:
                    fallback_exc = second_fallback_exc
            error_text = str(last_error) if last_error else f"HTTP {last_status_code}"
            message = f"{error_text}; browser fallback failed: {fallback_exc}"
            raise FetchError(message, kind=classify_error(message)) from fallback_exc

    if isinstance(last_error, FetchError):
        raise last_error
    if last_error:
        message = str(last_error)
        raise FetchError(message, kind=classify_error(message)) from last_error
    message = f"HTTP {last_status_code}"
    raise FetchError(message, kind=classify_error(message))


def source_urls(source: dict[str, Any]) -> list[str]:
    urls = [str(source.get("source_url") or "").strip()]
    urls.extend(str(url).strip() for url in source.get("fallback_urls", []) if str(url).strip())
    seen: set[str] = set()
    out: list[str] = []
    for url in urls:
        if url and url not in seen:
            seen.add(url)
            out.append(url)
    return out


def fetch_source(
    session: requests.Session,
    source: dict[str, Any],
    *,
    timeout: int,
    retry_attempts: int,
    retry_backoff_seconds: list[int],
    browser_fallback: bool,
    browser_headless: bool,
) -> tuple[FetchResult, list[dict[str, Any]]]:
    attempts: list[dict[str, Any]] = []
    last_error: FetchError | None = None
    for index, url in enumerate(source_urls(source), start=1):
        try:
            result = fetch_url(
                session,
                url,
                timeout=timeout,
                retry_attempts=retry_attempts,
                retry_backoff_seconds=retry_backoff_seconds,
                browser_fallback=browser_fallback,
                browser_headless=browser_headless,
            )
            attempts.append({
                "url": url,
                "status": "success",
                "attempt_index": index,
                "fetch_method": result.method,
                "http_status": result.status_code,
            })
            return result, attempts
        except FetchError as exc:
            last_error = exc
            attempts.append({
                "url": url,
                "status": "error",
                "attempt_index": index,
                "error_kind": exc.kind,
                "error": str(exc)[:300],
            })
    if last_error:
        message = f"All configured source URLs failed. Last error: {last_error}"
        final_error = FetchError(message, kind=last_error.kind)
        final_error.attempts = attempts
        raise final_error
    final_error = FetchError("No configured source URLs", kind="configuration_error")
    final_error.attempts = attempts
    raise final_error


def host(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def keep_same_host_or_wire(source_url: str, candidate_url: str) -> bool:
    source_host = host(source_url)
    candidate_host = host(candidate_url)
    if not candidate_host or candidate_url.startswith(("mailto:", "tel:")):
        return False
    if source_host == candidate_host:
        return True
    return "globenewswire.com" in source_host and "globenewswire.com" in candidate_host


def extract_date(text: str, href: str) -> str:
    patterns = [
        r"\b(20\d{2})[-/](0?[1-9]|1[0-2])[-/](0?[1-9]|[12]\d|3[01])\b",
        r"\b(0?[1-9]|1[0-2])[-/](0?[1-9]|[12]\d|3[01])[-/](20\d{2})\b",
    ]
    haystack = f"{text} {href}"
    for pattern in patterns:
        match = re.search(pattern, haystack)
        if not match:
            continue
        groups = match.groups()
        if len(groups[0]) == 4:
            year, month, day = groups
        else:
            month, day, year = groups
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    months = (
        "January|February|March|April|May|June|July|August|September|"
        "October|November|December|Jan\\.?|Feb\\.?|Mar\\.?|Apr\\.?|Jun\\.?|"
        "Jul\\.?|Aug\\.?|Sep\\.?|Sept\\.?|Oct\\.?|Nov\\.?|Dec\\.?"
    )
    match = re.search(rf"\b({months})\s+([0-9]{{1,2}}),\s+(20\d{{2}})\b", haystack, re.I)
    if not match:
        return ""
    month_lookup = {
        "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
        "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7,
        "july": 7, "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
        "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
    }
    month_text = match.group(1).lower().rstrip(".")
    return f"{int(match.group(3)):04d}-{month_lookup[month_text]:02d}-{int(match.group(2)):02d}"


def candidates_from_html(source: dict[str, Any], html: str, base_url: str) -> list[Candidate]:
    parser = PressLinkParser(base_url)
    parser.feed(html)
    regex = re.compile(source.get("title_filter") or ".", re.I)
    seen: set[str] = set()
    candidates: list[Candidate] = []
    for link in parser.links:
        href = link["href"].split("#", 1)[0]
        text = normalize_space(link["text"])
        if not href or href in seen:
            continue
        if not keep_same_host_or_wire(base_url, href):
            continue
        search_text = f"{text} {href}"
        if not regex.search(search_text):
            continue
        if len(text) < 4:
            continue
        seen.add(href)
        candidates.append(Candidate(title=text[:220], url=href, date=extract_date(text, href)))
    return candidates


def status_row(source: dict[str, Any], status: str, **extra: Any) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return {
        **source,
        "status": status,
        "checked_at": now,
        **extra,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trigger", default="manual")
    parser.add_argument("--run-id", default=run_id())
    parser.add_argument("--timeout", type=int, default=12)
    parser.add_argument("--retry-attempts", type=int, default=1)
    parser.add_argument("--retry-backoff-seconds", default="2,5,15")
    parser.add_argument("--no-browser-fallback", action="store_true")
    parser.add_argument("--browser-headed", action="store_true")
    parser.add_argument(
        "--source-id",
        action="append",
        default=[],
        help="Limit the run to one or more source IDs for targeted checks.",
    )
    args = parser.parse_args(argv)
    retry_backoff_seconds = [
        int(part.strip()) for part in args.retry_backoff_seconds.split(",")
        if part.strip()
    ]

    started = datetime.now(timezone.utc)
    run_dir = RUNS_DIR / args.run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "logs").mkdir(parents=True, exist_ok=True)

    expected = expected_press_release_sources()
    if args.source_id:
        selected = set(args.source_id)
        expected = [source for source in expected if source.get("source_id") in selected]
    (run_dir / "expected_sources.json").write_text(
        json.dumps(expected, indent=2),
        encoding="utf-8",
    )

    existing = existing_keys(read_existing_rows())
    source_status_path = run_dir / "source_status.jsonl"
    worklist_items: list[dict[str, Any]] = []
    new_press_releases: list[dict[str, Any]] = []
    checked_sources = 0
    error_sources = 0
    candidate_total = 0
    new_candidate_total = 0

    session = requests.Session()
    with source_status_path.open("w", encoding="utf-8") as status_file:
        for source in expected:
            try:
                result, attempts = fetch_source(
                    session,
                    source,
                    timeout=args.timeout,
                    retry_attempts=args.retry_attempts,
                    retry_backoff_seconds=retry_backoff_seconds,
                    browser_fallback=not args.no_browser_fallback,
                    browser_headless=not args.browser_headed,
                )
                candidates = candidates_from_html(source, result.html, result.url or source["source_url"])
                checked_sources += 1
                candidate_total += len(candidates)
                new_candidates = [
                    c for c in candidates
                    if f"url:{c.url.lower()}" not in existing
                ]
                new_candidate_total += len(new_candidates)
                for candidate in new_candidates:
                    worklist_items.append({
                        "company": source.get("company_name", ""),
                        "company_id": source.get("company_id", ""),
                        "title": candidate.title,
                        "reason": "candidate press release requires review before adding",
                        "url": candidate.url,
                        "source_url": result.url or source.get("source_url", ""),
                        "date": candidate.date,
                    })
                status = (
                    "checked_with_new_items"
                    if new_candidates else
                    "checked_ok"
                    if candidates else
                    "checked_no_candidates"
                )
                row = status_row(
                    source,
                    status,
                    candidate_count=len(candidates),
                    new_candidate_count=len(new_candidates),
                    downloaded_count=0,
                    worklist_count=len(new_candidates),
                    content_type=result.content_type,
                    fetch_method=result.method,
                    http_status=result.status_code,
                    resolved_source_url=result.url,
                    source_attempts=attempts,
                )
            except (FetchError, TimeoutError, OSError) as exc:
                attempts = getattr(exc, "attempts", [])
                error_sources += 1
                error_kind = exc.kind if isinstance(exc, FetchError) else classify_error(str(exc))
                row = status_row(
                    source,
                    "fetch_error",
                    candidate_count=0,
                    new_candidate_count=0,
                    downloaded_count=0,
                    worklist_count=0,
                    error_kind=error_kind,
                    source_attempts=attempts,
                    error=str(exc)[:300],
                )
            except Exception as exc:
                error_sources += 1
                row = status_row(
                    source,
                    "parse_error",
                    candidate_count=0,
                    new_candidate_count=0,
                    downloaded_count=0,
                    worklist_count=0,
                    error=f"{type(exc).__name__}: {exc}"[:300],
                )
            status_file.write(json.dumps(row, sort_keys=True) + "\n")

    status = "partial" if error_sources else "success"
    run = {
        "run_id": args.run_id,
        "run_type": "press_release",
        "trigger": args.trigger,
        "status": status,
        "dry_run": False,
        "started_at": started.isoformat(timespec="seconds"),
        "ended_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_sha": "",
        "expected_sources_count": len(expected),
        "checked_sources_count": checked_sources,
        "error_sources_count": error_sources,
        "candidate_count": candidate_total,
        "new_candidate_count": new_candidate_total,
        "new_press_releases": new_press_releases,
        "worklist_items": worklist_items,
        "validations": [],
    }
    (run_dir / "run.json").write_text(json.dumps(run, indent=2), encoding="utf-8")

    print(json.dumps({
        "run_id": args.run_id,
        "status": status,
        "expected_sources": len(expected),
        "checked_sources": checked_sources,
        "error_sources": error_sources,
        "candidates": candidate_total,
        "new_candidates": new_candidate_total,
        "new_press_releases": len(new_press_releases),
        "worklist_items": len(worklist_items),
        "run_dir": rel(run_dir),
    }, indent=2))
    return 1 if error_sources else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
