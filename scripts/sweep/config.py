"""Configuration loader and schema validation for sources.yaml."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


VALID_KINDS = {"html", "pubmed", "skip"}
VALID_FETCHERS = {"requests", "playwright_loadmore", "playwright_hcp"}
VALID_TIERS = {1, 2, 3, 4, 5}


class ConfigError(ValueError):
    """Raised when sources.yaml is malformed or contains an unknown value."""


@dataclass
class Defaults:
    user_agent: str
    timeout_seconds: int
    download_timeout_seconds: int
    retry_attempts: int
    retry_backoff_seconds: list[int]
    playwright_headless: bool
    pubmed_api_key: str
    pubmed_tool_name: str
    pubmed_email: str


@dataclass
class RouteRule:
    pattern: re.Pattern
    dest: str


@dataclass
class Source:
    kind: str = "html"
    url: str = ""
    fetcher: str = "requests"
    loadmore_selector: str = ""
    loadmore_max_clicks: int = 30
    hcp_action: str = ""
    bot_clear_seconds: int = 5
    link_pattern: re.Pattern = field(default_factory=lambda: re.compile(r"\.pdf(\?|$)", re.I))
    title_filter: re.Pattern | None = None
    dest: str = ""
    dest_router: list[RouteRule] = field(default_factory=list)
    title_router: list[RouteRule] = field(default_factory=list)
    referer: str = ""
    extra_headers: dict[str, str] = field(default_factory=dict)
    discovery_only: bool = False
    dest_worklist: str = ""
    # pubmed-only
    terms: list[str] = field(default_factory=list)
    affiliations: list[str] = field(default_factory=list)
    date_min: str = ""
    prefer_pmc: bool = True
    # skip-only
    reason: str = ""


@dataclass
class Company:
    id: str
    name: str
    folder: str
    tier: int
    sources: list[Source]


@dataclass
class Config:
    defaults: Defaults
    companies: list[Company]


def _compile(pattern: str | None) -> re.Pattern | None:
    if not pattern:
        return None
    try:
        return re.compile(pattern, re.IGNORECASE)
    except re.error as exc:
        raise ConfigError(f"Invalid regex {pattern!r}: {exc}") from exc


def _parse_router(rules: list[dict] | None) -> list[RouteRule]:
    if not rules:
        return []
    out = []
    for r in rules:
        if "pattern" not in r or "dest" not in r:
            raise ConfigError(f"Router rule missing pattern/dest: {r}")
        out.append(RouteRule(pattern=_compile(r["pattern"]), dest=r["dest"]))
    return out


def _parse_source(raw: dict, company_id: str) -> Source:
    kind = raw.get("kind", "html")
    if kind not in VALID_KINDS:
        raise ConfigError(f"[{company_id}] unknown source kind={kind!r}; "
                          f"valid: {sorted(VALID_KINDS)}")

    src = Source(kind=kind)

    if kind == "skip":
        src.reason = raw.get("reason", "(no reason provided)")
        return src

    if kind == "pubmed":
        src.terms = list(raw.get("terms") or [])
        src.affiliations = list(raw.get("affiliations") or [])
        src.date_min = raw.get("date_min", "")
        src.prefer_pmc = bool(raw.get("prefer_pmc", True))
        src.dest = raw.get("dest", "") or ""
        if not src.terms:
            raise ConfigError(f"[{company_id}] pubmed source missing terms")
        if not src.dest and not raw.get("discovery_only"):
            raise ConfigError(f"[{company_id}] pubmed source missing dest")
        return src

    # kind == "html"
    src.url = raw.get("url", "")
    if not src.url:
        raise ConfigError(f"[{company_id}] html source missing url")

    src.fetcher = raw.get("fetcher", "requests")
    if src.fetcher not in VALID_FETCHERS:
        raise ConfigError(f"[{company_id}] unknown fetcher={src.fetcher!r}; "
                          f"valid: {sorted(VALID_FETCHERS)}")

    src.loadmore_selector = raw.get("loadmore_selector", "")
    src.loadmore_max_clicks = int(raw.get("loadmore_max_clicks", 30))
    src.hcp_action = raw.get("hcp_action", "")
    src.bot_clear_seconds = int(raw.get("bot_clear_seconds", 5))

    link_pat = raw.get("link_pattern")
    if link_pat:
        src.link_pattern = _compile(link_pat)

    src.title_filter = _compile(raw.get("title_filter"))
    src.dest_router = _parse_router(raw.get("dest_router"))
    src.title_router = _parse_router(raw.get("title_router"))
    src.dest = raw.get("dest", "")
    src.referer = raw.get("referer", "")
    src.extra_headers = dict(raw.get("extra_headers") or {})

    src.discovery_only = bool(raw.get("discovery_only", False))
    src.dest_worklist = raw.get("dest_worklist", "")

    if not src.discovery_only and not src.dest and not src.dest_router:
        raise ConfigError(f"[{company_id}] html source needs dest or dest_router")
    if src.discovery_only and not src.dest_worklist:
        raise ConfigError(f"[{company_id}] discovery_only source needs dest_worklist")

    return src


def load_config(path: str | Path) -> Config:
    path = Path(path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))

    d = raw.get("defaults") or {}
    defaults = Defaults(
        user_agent=d.get("user_agent", "Mozilla/5.0"),
        timeout_seconds=int(d.get("timeout_seconds", 60)),
        download_timeout_seconds=int(d.get("download_timeout_seconds", 120)),
        retry_attempts=int(d.get("retry_attempts", 3)),
        retry_backoff_seconds=list(d.get("retry_backoff_seconds", [2, 5, 15])),
        playwright_headless=bool(d.get("playwright_headless", True)),
        pubmed_api_key=d.get("pubmed_api_key", "") or "",
        pubmed_tool_name=d.get("pubmed_tool_name", "glaucoma-data-archive-sweep"),
        pubmed_email=d.get("pubmed_email", ""),
    )

    companies: list[Company] = []
    for c in raw.get("companies") or []:
        cid = c.get("id")
        if not cid:
            raise ConfigError(f"Company missing id: {c}")
        tier = int(c.get("tier", 0))
        if tier not in VALID_TIERS:
            raise ConfigError(f"[{cid}] tier {tier} not in {sorted(VALID_TIERS)}")
        sources = [_parse_source(s, cid) for s in (c.get("sources") or [])]
        companies.append(Company(
            id=cid,
            name=c.get("name", cid),
            folder=c.get("folder", f"companies/{cid}"),
            tier=tier,
            sources=sources,
        ))

    seen = set()
    for c in companies:
        if c.id in seen:
            raise ConfigError(f"Duplicate company id: {c.id}")
        seen.add(c.id)

    return Config(defaults=defaults, companies=companies)
