"""Scan a company folder and return the set of currently-archived document keys.

A "document key" is a deduplication identifier built from:
  - the URL-decoded basename of the file (lowercased, hyphens/underscores normalized)
  - the SHA-1 of the file bytes (computed on demand only when needed)

The inventory is the input to the diff step. A document fetched from a source
counts as "already archived" iff its basename slug or content hash matches an
existing file in the same company folder.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote


_NORMALIZE_RE = re.compile(r"[^a-z0-9]+")


def slugify_basename(name: str) -> str:
    """Normalize a filename or URL basename to a deterministic comparison slug."""
    name = unquote(name)
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    name = name.lower()
    # strip common file suffixes
    for suf in (".pdf", ".html", ".htm"):
        if name.endswith(suf):
            name = name[: -len(suf)]
            break
    return _NORMALIZE_RE.sub("-", name).strip("-")


@dataclass
class Inventory:
    company_id: str
    company_folder: Path
    pdf_slugs: set[str] = field(default_factory=set)
    md_slugs: set[str] = field(default_factory=set)
    pdf_hashes: dict[str, Path] = field(default_factory=dict)
    pdf_paths: list[Path] = field(default_factory=list)

    def has_slug(self, slug: str) -> bool:
        return slug in self.pdf_slugs or slug in self.md_slugs

    def has_hash(self, sha1: str) -> bool:
        return sha1 in self.pdf_hashes


def scan(company_folder: Path, company_id: str, hash_bytes: bool = False) -> Inventory:
    """Walk a company folder and capture its current document inventory.

    By default we skip SHA-1 hashing (it is only needed when we want to
    second-check a downloaded byte stream against on-disk files). Pass
    hash_bytes=True to populate Inventory.pdf_hashes.
    """
    inv = Inventory(company_id=company_id, company_folder=company_folder)
    if not company_folder.exists():
        return inv

    for path in company_folder.rglob("*"):
        if not path.is_file():
            continue
        # Ignore parser-byproduct trees (we only care about canonical artifacts).
        if "plain_text" in path.parts or "original_markdown" in path.parts:
            continue
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            inv.pdf_paths.append(path)
            inv.pdf_slugs.add(slugify_basename(path.stem))
            if hash_bytes:
                h = hashlib.sha1(path.read_bytes()).hexdigest()
                inv.pdf_hashes[h] = path
        elif suffix == ".md" and path.stem not in ("brand", "README"):
            inv.md_slugs.add(slugify_basename(path.stem))

    return inv
