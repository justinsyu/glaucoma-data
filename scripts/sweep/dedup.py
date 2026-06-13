"""Deduplication helpers shared across fetchers."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse

from .inventory import Inventory, slugify_basename


@dataclass(frozen=True)
class Candidate:
    """A document discovered by a fetcher and considered for download."""
    url: str
    title: str         # human-readable title (link text or inferred)
    source_url: str    # the page on which this link was discovered
    suggested_dest: str  # directory path under repo root

    @property
    def basename(self) -> str:
        path = urlparse(self.url).path
        return unquote(path.rsplit("/", 1)[-1])

    @property
    def slug(self) -> str:
        return slugify_basename(self.basename or self.title or self.url)


def deduplicate(candidates: list[Candidate], inventory: Inventory) -> tuple[list[Candidate], list[Candidate]]:
    """Split candidates into (already_archived, new_to_fetch).

    A candidate is "already archived" if its slug matches a slug already present
    in the inventory (PDF or markdown).
    """
    already: list[Candidate] = []
    new: list[Candidate] = []
    seen_slugs: set[str] = set()
    for c in candidates:
        s = c.slug
        if not s:
            continue
        if s in seen_slugs:
            continue  # duplicate within the same fetch batch
        seen_slugs.add(s)
        if inventory.has_slug(s):
            already.append(c)
        else:
            new.append(c)
    return already, new


def verify_pdf_bytes(data: bytes) -> bool:
    """Return True iff the byte string starts with the %PDF magic header."""
    return data[:4] == b"%PDF"


def sha1_bytes(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()
