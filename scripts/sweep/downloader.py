"""Atomic PDF download with %PDF header verification and SHA-1 dedup."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path

import requests

from .config import Defaults
from .dedup import Candidate, Inventory, sha1_bytes, slugify_basename, verify_pdf_bytes

log = logging.getLogger(__name__)


@dataclass
class DownloadResult:
    candidate: Candidate
    status: str            # "downloaded" | "duplicate_hash" | "duplicate_slug" | "invalid_pdf" | "http_error" | "timeout"
    dest_path: Path | None
    bytes_written: int = 0
    sha1: str = ""
    error: str = ""


def _safe_filename(candidate: Candidate) -> str:
    """Construct a filesystem-safe filename from a candidate URL/title.

    Prefers the URL-decoded source basename. Falls back to the slug if the URL
    has no file extension (e.g. UUID-style static-file endpoints).
    """
    base = candidate.basename
    if base and base.lower().endswith(".pdf"):
        # URL-decoded base; replace any whitespace/control chars with underscore.
        safe = base.replace("%20", "_").replace(" ", "_")
        safe = "".join(ch if (ch.isalnum() or ch in "._-") else "_" for ch in safe)
        return safe
    # Synthesize from the title or URL slug.
    slug = candidate.slug or slugify_basename(candidate.url)
    return f"{slug}.pdf"


def download_pdf(
    candidate: Candidate,
    dest_dir: Path,
    defaults: Defaults,
    inventory: Inventory,
    session: requests.Session | None = None,
    extra_headers: dict[str, str] | None = None,
) -> DownloadResult:
    """Download a single candidate PDF.

    Workflow:
      1. Issue GET with retries/backoff and the configured user agent.
      2. Verify the response body starts with `%PDF`. If not, mark invalid.
      3. SHA-1 the bytes. If the hash already exists anywhere in the company
         inventory, mark duplicate_hash and do NOT write.
      4. Atomic write: bytes -> dest_dir/<safe-name>.part -> rename to .pdf.
    """
    session = session or requests.Session()
    headers = {
        "User-Agent": defaults.user_agent,
        "Accept": "application/pdf,*/*;q=0.8",
    }
    if extra_headers:
        headers.update(extra_headers)

    last_err = ""
    for attempt in range(defaults.retry_attempts):
        try:
            r = session.get(
                candidate.url,
                headers=headers,
                timeout=defaults.download_timeout_seconds,
                allow_redirects=True,
            )
            if r.status_code != 200:
                last_err = f"HTTP {r.status_code}"
                if r.status_code in (429, 500, 502, 503, 504) and attempt + 1 < defaults.retry_attempts:
                    time.sleep(defaults.retry_backoff_seconds[min(attempt, len(defaults.retry_backoff_seconds) - 1)])
                    continue
                return DownloadResult(candidate=candidate, status="http_error", dest_path=None, error=last_err)
            data = r.content
            break
        except requests.exceptions.Timeout:
            last_err = "timeout"
            if attempt + 1 < defaults.retry_attempts:
                time.sleep(defaults.retry_backoff_seconds[min(attempt, len(defaults.retry_backoff_seconds) - 1)])
                continue
            return DownloadResult(candidate=candidate, status="timeout", dest_path=None, error=last_err)
        except requests.exceptions.RequestException as exc:
            last_err = str(exc)
            if attempt + 1 < defaults.retry_attempts:
                time.sleep(defaults.retry_backoff_seconds[min(attempt, len(defaults.retry_backoff_seconds) - 1)])
                continue
            return DownloadResult(candidate=candidate, status="http_error", dest_path=None, error=last_err)
    else:  # pragma: no cover - loop always exits via break/return
        return DownloadResult(candidate=candidate, status="http_error", dest_path=None, error=last_err)

    if not verify_pdf_bytes(data):
        return DownloadResult(
            candidate=candidate,
            status="invalid_pdf",
            dest_path=None,
            error=f"Response did not start with %PDF (first bytes: {data[:16]!r})",
        )

    digest = sha1_bytes(data)
    if inventory.has_hash(digest):
        existing = inventory.pdf_hashes.get(digest)
        return DownloadResult(
            candidate=candidate,
            status="duplicate_hash",
            dest_path=existing,
            sha1=digest,
            error=f"Identical content already at {existing}" if existing else "",
        )

    dest_dir.mkdir(parents=True, exist_ok=True)
    filename = _safe_filename(candidate)
    final_path = dest_dir / filename
    if final_path.exists():
        # Same filename already on disk; if its slug already matches inventory the
        # caller should have filtered upstream, but be safe and skip.
        return DownloadResult(
            candidate=candidate,
            status="duplicate_slug",
            dest_path=final_path,
            sha1=digest,
            error="Destination filename already exists",
        )

    tmp_path = final_path.with_suffix(final_path.suffix + ".part")
    tmp_path.write_bytes(data)
    tmp_path.replace(final_path)

    # Register the new hash so subsequent candidates in the same run can dedupe.
    inventory.pdf_hashes[digest] = final_path
    inventory.pdf_slugs.add(slugify_basename(final_path.stem))
    inventory.pdf_paths.append(final_path)

    return DownloadResult(
        candidate=candidate,
        status="downloaded",
        dest_path=final_path,
        bytes_written=len(data),
        sha1=digest,
    )
