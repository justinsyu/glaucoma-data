"""Watchlist loader and validator.

The watchlist is a YAML file at ``_data/source_watchlist.yml``. Each entry
describes one source (one URL or one structured API query) that the watcher
checks on every run.

Schema:

    - source_id: str        # stable identifier, used as join key in observability DB
      company_slug: str
      program_slug: str | None
      source_type: str      # one of EXTRACTOR_REGISTRY keys
      url: str
      enabled: bool         # default True
      render: 'static' | 'js'  # default 'static'
      extractor_config: dict   # extractor-specific selectors / params
      notes: str | None
      manual_review: bool   # default False; set when source_page in manifest was a free-text note

      # Optional refinements ported from scripts/sweep:
      tier: int             # 1..5 operator-expectation class (see RUNBOOK.md)
      title_filter: str     # case-insensitive regex; links whose "url + title" does not match are dropped
      dest_router: list     # [{pattern: regex, dest: folder}] route discovered links to per-program folders
      title_router: list    # same shape as dest_router; applied before dest_router (manuscripts vs posters)
      discovery_only: bool  # True = emit to dest_worklist instead of treating as auto-downloadable
      dest_worklist: str    # relative path to the worklist markdown file
      extra_headers: dict   # additional headers to send on the fetch (e.g., Accept, Referer)
      referer: str          # convenience for the single most-common extra header

The optional fields are all backwards-compatible. A bootstrap watchlist that
predates this schema continues to load unchanged: every new field has a default
that preserves prior behavior.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator

from .paths import watchlist_path


class RouterRule(BaseModel):
    """One row of a dest_router / title_router rule list."""

    pattern: str
    dest: str


class SourceEntry(BaseModel):
    source_id: str
    company_slug: str
    program_slug: str | None = None
    source_type: str
    url: str
    enabled: bool = True
    render: Literal["static", "js"] = "static"
    extractor_config: dict = Field(default_factory=dict)
    notes: str | None = None
    manual_review: bool = False

    tier: int | None = None
    title_filter: str | None = None
    dest: str | None = None
    dest_router: list[RouterRule] = Field(default_factory=list)
    title_router: list[RouterRule] = Field(default_factory=list)
    discovery_only: bool = False
    dest_worklist: str | None = None
    extra_headers: dict = Field(default_factory=dict)
    referer: str | None = None

    @field_validator("source_id")
    @classmethod
    def _id_pattern(cls, v: str) -> str:
        if not v or any(c.isspace() for c in v):
            raise ValueError("source_id must be non-empty and contain no whitespace")
        return v

    @field_validator("tier")
    @classmethod
    def _tier_range(cls, v: int | None) -> int | None:
        if v is not None and not 1 <= v <= 5:
            raise ValueError("tier must be in [1, 5] if set")
        return v


class Watchlist(BaseModel):
    sources: list[SourceEntry]

    def enabled_sources(self, source_type: str | None = None) -> list[SourceEntry]:
        out = [s for s in self.sources if s.enabled and not s.manual_review]
        if source_type:
            out = [s for s in out if s.source_type == source_type]
        return out


def load_watchlist(path: Path | None = None) -> Watchlist:
    p = path or watchlist_path()
    if not p.is_file():
        return Watchlist(sources=[])
    with p.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    return Watchlist.model_validate(raw)


def write_watchlist(wl: Watchlist, path: Path | None = None) -> None:
    p = path or watchlist_path()
    payload = wl.model_dump(mode="json", exclude_none=True, exclude_defaults=True)
    # exclude_defaults drops the new optional fields when unset; re-add the
    # required ones we always want to write explicitly.
    for src_in, src_out in zip(wl.sources, payload.get("sources", [])):
        src_out.setdefault("source_id", src_in.source_id)
        src_out.setdefault("company_slug", src_in.company_slug)
        src_out.setdefault("source_type", src_in.source_type)
        src_out.setdefault("url", src_in.url)
    with p.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(payload, fh, sort_keys=False, allow_unicode=True, width=120)
