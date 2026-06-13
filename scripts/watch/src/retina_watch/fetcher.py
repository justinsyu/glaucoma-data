"""HTTP fetcher with structured observability.

Every fetch attempt produces exactly one ``fetch_events`` row whether it
succeeded, failed, or was retried. ``sha256_head`` fingerprints the first 64KiB
of the response body, which is enough to detect PDF content changes without
downloading multi-megabyte files in full during the link-discovery pass.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass

import requests
from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from . import db
from .logging_setup import get_logger
from . import politeness


USER_AGENT = (
    "glaucoma-watch/0.1 (+https://github.com/justinsyu/glaucoma-data; "
    "observability-and-audit-trail)"
)
HEAD_PROBE_BYTES = 64 * 1024


@dataclass
class FetchResult:
    url: str
    http_status: int | None
    bytes: int | None
    sha256_head: str | None
    latency_ms: int
    retries: int
    body: bytes | None
    content_type: str | None
    error: str | None
    skipped_reason: str | None = None

    @property
    def ok(self) -> bool:
        return (
            self.error is None
            and self.skipped_reason is None
            and (self.http_status or 0) < 400
            and self.body is not None
        )


def fetch(
    url: str,
    *,
    run_id: str,
    source_id: str,
    method: str = "GET",
    timeout: float = 30.0,
    max_retries: int = 3,
    head_only: bool = False,
    min_interval_seconds: float | None = None,
) -> FetchResult:
    log = get_logger().bind(source_id=source_id, url=url, method=method)

    if not politeness.robots_allows(url, user_agent=USER_AGENT):
        s = db.session()
        try:
            s.add(
                db.FetchEvent(
                    run_id=run_id,
                    source_id=source_id,
                    url=url,
                    method=method,
                    http_status=None,
                    bytes=None,
                    sha256_head=None,
                    latency_ms=0,
                    retries=0,
                    error="robots_disallow",
                )
            )
            s.commit()
        finally:
            s.close()
        log.warning("robots_disallow", url=url)
        return FetchResult(
            url=url,
            http_status=None,
            bytes=None,
            sha256_head=None,
            latency_ms=0,
            retries=0,
            body=None,
            content_type=None,
            error=None,
            skipped_reason="robots_disallow",
        )

    waited = politeness.wait_for_host(url, interval=min_interval_seconds)
    if waited > 0:
        log.debug("politeness_wait", waited_seconds=round(waited, 3))

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "*/*"})

    started = time.monotonic()
    retries = 0
    last_error: str | None = None
    response: requests.Response | None = None

    retrying = Retrying(
        stop=stop_after_attempt(max_retries),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        retry=retry_if_exception_type(
            (requests.ConnectionError, requests.Timeout, requests.HTTPError)
        ),
        reraise=True,
    )

    try:
        for attempt in retrying:
            with attempt:
                if attempt.retry_state.attempt_number > 1:
                    retries = attempt.retry_state.attempt_number - 1
                    log.warning("fetch_retry", attempt=attempt.retry_state.attempt_number)
                if head_only:
                    response = session.head(url, timeout=timeout, allow_redirects=True)
                else:
                    response = session.get(url, timeout=timeout, allow_redirects=True, stream=True)
                if response.status_code >= 500:
                    response.raise_for_status()
    except Exception as exc:
        last_error = f"{type(exc).__name__}: {exc}"
        log.error("fetch_failed", error=last_error, retries=retries)

    latency_ms = int((time.monotonic() - started) * 1000)
    body: bytes | None = None
    sha: str | None = None
    nbytes: int | None = None
    status: int | None = None
    content_type: str | None = None

    if response is not None:
        status = response.status_code
        content_type = response.headers.get("Content-Type")
        if not head_only:
            chunks: list[bytes] = []
            collected = 0
            try:
                for chunk in response.iter_content(chunk_size=8192):
                    if not chunk:
                        continue
                    chunks.append(chunk)
                    collected += len(chunk)
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                log.error("fetch_body_read_failed", error=last_error)
            body = b"".join(chunks) if chunks else b""
            nbytes = len(body)
            sha = hashlib.sha256(body[:HEAD_PROBE_BYTES]).hexdigest() if body else None
        response.close()

    s = db.session()
    try:
        s.add(
            db.FetchEvent(
                run_id=run_id,
                source_id=source_id,
                url=url,
                method=method,
                http_status=status,
                bytes=nbytes,
                sha256_head=sha,
                latency_ms=latency_ms,
                retries=retries,
                error=last_error,
            )
        )
        s.commit()
    finally:
        s.close()

    log.info(
        "fetch_done",
        http_status=status,
        bytes=nbytes,
        latency_ms=latency_ms,
        retries=retries,
        ok=last_error is None and (status or 0) < 400,
    )

    return FetchResult(
        url=url,
        http_status=status,
        bytes=nbytes,
        sha256_head=sha,
        latency_ms=latency_ms,
        retries=retries,
        body=body,
        content_type=content_type,
        error=last_error,
    )
