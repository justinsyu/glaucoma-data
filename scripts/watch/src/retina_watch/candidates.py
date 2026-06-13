"""Candidate generation + deduplication cascade.

After ``run_once`` materializes a new snapshot, the candidates layer compares
the snapshot diff against the existing archive manifest and emits one
``candidates`` row per genuinely new document. The dedupe cascade runs each
``added`` link through a series of increasingly fuzzy matchers; the first
matcher to fire decides the dedupe verdict.

Matchers (in order of precedence):

1. ``url_exact``: byte-equal match against any ``source_url`` or
   ``local_file_url`` in the manifest.
2. ``url_canonical``: scheme/host lowercased, query string sorted, trailing slash
   trimmed, common tracking parameters dropped.
3. ``doi``: doi.org URL extracted from the link or its title, matched against
   manifest entries that carry a DOI.
4. ``pmid`` / ``nct``: structured-source identifier match against manifest
   ``source_url`` if it embeds the identifier.
5. ``title_fingerprint``: lowercased, year-stripped, punctuation-stripped title
   compared to the same transform of each manifest title.

A link that passes all matchers is classified ``new`` and persisted as a
candidate. Any other verdict produces a candidate row too, with the dedupe
decision recorded so the audit trail shows what was filtered and why.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from sqlalchemy import select

from . import db
from .logging_setup import get_logger
from .paths import manifest_path


_TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_content",
    "utm_term",
    "gclid",
    "fbclid",
    "ref",
}
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
_PUNCT_RE = re.compile(r"[^a-z0-9]+")
_DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+")
_NCT_RE = re.compile(r"NCT0?\d{7,8}", re.IGNORECASE)
_PMID_RE = re.compile(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)", re.IGNORECASE)


def _canonical_url(url: str) -> str:
    try:
        parsed = urlparse(url)
    except Exception:
        return url
    scheme = (parsed.scheme or "https").lower()
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/") or "/"
    query_pairs = sorted(
        (k.lower(), v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=False)
        if k.lower() not in _TRACKING_PARAMS
    )
    query = urlencode(query_pairs, doseq=True)
    return urlunparse((scheme, netloc, path, "", query, ""))


def _title_fingerprint(title: str | None) -> str | None:
    if not title:
        return None
    lowered = title.lower()
    stripped = _YEAR_RE.sub(" ", lowered)
    cleaned = _PUNCT_RE.sub(" ", stripped).strip()
    if not cleaned:
        return None
    return re.sub(r"\s+", " ", cleaned)


def _extract_doi(link_url: str, link_title: str | None) -> str | None:
    for haystack in (link_url, link_title or ""):
        m = _DOI_RE.search(haystack or "")
        if m:
            return m.group(0).rstrip(".,);")
    return None


def _extract_nct(link_url: str, link_title: str | None, extras: dict | None) -> str | None:
    if extras and extras.get("nct_id"):
        return str(extras["nct_id"]).upper()
    for haystack in (link_url, link_title or ""):
        m = _NCT_RE.search(haystack or "")
        if m:
            return m.group(0).upper()
    return None


def _extract_pmid(link_url: str, extras: dict | None) -> str | None:
    if extras and extras.get("pmid"):
        return str(extras["pmid"])
    m = _PMID_RE.search(link_url)
    if m:
        return m.group(1)
    return None


@dataclass
class _ManifestIndex:
    urls_exact: set[str]
    urls_canonical: set[str]
    dois: set[str]
    ncts: set[str]
    pmids: set[str]
    titles: set[str]

    @classmethod
    def load(cls) -> "_ManifestIndex":
        with manifest_path().open("r", encoding="utf-8") as fh:
            docs = json.load(fh)
        urls_exact: set[str] = set()
        urls_canonical: set[str] = set()
        dois: set[str] = set()
        ncts: set[str] = set()
        pmids: set[str] = set()
        titles: set[str] = set()
        for d in docs:
            for k in ("source_url", "local_file_url", "url"):
                v = (d.get(k) or "").strip()
                if v:
                    urls_exact.add(v)
                    if v.startswith("http"):
                        urls_canonical.add(_canonical_url(v))
            title = d.get("title")
            fp = _title_fingerprint(title)
            if fp:
                titles.add(fp)
            for v in (d.get("source_url") or "", d.get("source_page") or ""):
                m = _DOI_RE.search(v)
                if m:
                    dois.add(m.group(0).rstrip(".,);"))
                m = _NCT_RE.search(v)
                if m:
                    ncts.add(m.group(0).upper())
                m = _PMID_RE.search(v)
                if m:
                    pmids.add(m.group(1))
        return cls(
            urls_exact=urls_exact,
            urls_canonical=urls_canonical,
            dois=dois,
            ncts=ncts,
            pmids=pmids,
            titles=titles,
        )


@dataclass
class DedupeVerdict:
    decision: str  # one of: new, dup_url_exact, dup_url_canonical, dup_doi, dup_nct, dup_pmid, dup_title
    features: dict


def _classify_link(
    url: str, title: str | None, extras: dict | None, manifest: _ManifestIndex
) -> DedupeVerdict:
    canonical = _canonical_url(url)
    title_fp = _title_fingerprint(title)
    doi = _extract_doi(url, title)
    nct = _extract_nct(url, title, extras)
    pmid = _extract_pmid(url, extras)
    features = {
        "canonical_url": canonical,
        "title_fingerprint": title_fp,
        "doi": doi,
        "nct": nct,
        "pmid": pmid,
    }
    if url in manifest.urls_exact:
        return DedupeVerdict("dup_url_exact", features)
    if canonical in manifest.urls_canonical:
        return DedupeVerdict("dup_url_canonical", features)
    if doi and doi in manifest.dois:
        return DedupeVerdict("dup_doi", features)
    if nct and nct in manifest.ncts:
        return DedupeVerdict("dup_nct", features)
    if pmid and pmid in manifest.pmids:
        return DedupeVerdict("dup_pmid", features)
    if title_fp and title_fp in manifest.titles:
        return DedupeVerdict("dup_title", features)
    return DedupeVerdict("new", features)


def materialize_candidates(*, run_id: str) -> dict:
    """For every snapshot in ``run_id`` with added links, persist candidates.

    Returns a summary dict suitable for inclusion in the run stats.
    """
    log = get_logger().bind(run_id=run_id)
    manifest = _ManifestIndex.load()

    summary = {
        "added_total": 0,
        "candidates_total": 0,
        "by_decision": {},
    }
    s = db.session()
    try:
        snaps = (
            s.execute(select(db.Snapshot).where(db.Snapshot.run_id == run_id))
            .scalars()
            .all()
        )
        for snap in snaps:
            diff = snap.diff_vs_prior or {}
            added = diff.get("added") or []
            if not added:
                continue
            summary["added_total"] += len(added)
            for link in added:
                url = link["url"]
                title = link.get("title")
                extras = link.get("extras") or {}
                verdict = _classify_link(url, title, extras, manifest)
                summary["candidates_total"] += 1
                summary["by_decision"][verdict.decision] = (
                    summary["by_decision"].get(verdict.decision, 0) + 1
                )
                s.add(
                    db.Candidate(
                        run_id=run_id,
                        source_id=snap.source_id,
                        url=url,
                        normalized_title=verdict.features.get("title_fingerprint"),
                        dedupe_decision=verdict.decision,
                        confidence_features={
                            "title": title,
                            "extras": extras,
                            **verdict.features,
                        },
                    )
                )
        s.commit()
    finally:
        s.close()

    log.info("candidates_materialized", **summary)
    return summary
