"""Dedupe cascade unit tests."""

from __future__ import annotations

from retina_watch.candidates import (
    _ManifestIndex,
    _canonical_url,
    _classify_link,
    _title_fingerprint,
)


def _index(**kwargs) -> _ManifestIndex:
    defaults = {
        "urls_exact": set(),
        "urls_canonical": set(),
        "dois": set(),
        "ncts": set(),
        "pmids": set(),
        "titles": set(),
    }
    defaults.update(kwargs)
    return _ManifestIndex(**defaults)


def test_canonical_url_strips_tracking_params():
    raw = "https://Example.com/Foo/?utm_source=x&id=42"
    assert _canonical_url(raw) == "https://example.com/Foo?id=42"


def test_canonical_url_sorts_query_pairs():
    a = _canonical_url("https://example.com/?b=2&a=1")
    b = _canonical_url("https://example.com/?a=1&b=2")
    assert a == b


def test_title_fingerprint_strips_years_and_punctuation():
    fp = _title_fingerprint("Faricimab in nAMD: TENAYA/LUCERNE 2-Year Results (2024)")
    assert fp == "faricimab in namd tenaya lucerne 2 year results"


def test_url_exact_match():
    manifest = _index(urls_exact={"https://x.com/a.pdf"})
    verdict = _classify_link("https://x.com/a.pdf", "Title", None, manifest)
    assert verdict.decision == "dup_url_exact"


def test_url_canonical_match_when_only_tracking_differs():
    manifest = _index(urls_canonical={"https://x.com/a.pdf"})
    verdict = _classify_link("https://X.com/a.pdf?utm_source=mail", "Title", None, manifest)
    assert verdict.decision == "dup_url_canonical"


def test_doi_match_takes_precedence_over_title():
    manifest = _index(dois={"10.1056/NEJMoa2032187"}, titles={"different title"})
    verdict = _classify_link(
        "https://x.com/something.pdf",
        "TENAYA LUCERNE phase 3 doi:10.1056/NEJMoa2032187",
        None,
        manifest,
    )
    assert verdict.decision == "dup_doi"


def test_nct_match_via_extras():
    manifest = _index(ncts={"NCT04428541"})
    verdict = _classify_link(
        "https://clinicaltrials.gov/study/NCT04428541",
        "Phase 3 Faricimab",
        {"nct_id": "NCT04428541"},
        manifest,
    )
    assert verdict.decision == "dup_nct"


def test_pmid_match_via_extras():
    manifest = _index(pmids={"38000000"})
    verdict = _classify_link(
        "https://pubmed.ncbi.nlm.nih.gov/38000000/",
        "Article",
        {"pmid": "38000000"},
        manifest,
    )
    assert verdict.decision == "dup_pmid"


def test_title_fingerprint_match_last_resort():
    fp = _title_fingerprint("TENAYA LUCERNE 2-Year Faricimab Results (2024)")
    manifest = _index(titles={fp})
    verdict = _classify_link(
        "https://medinfo.example.com/never-seen.pdf",
        "TENAYA LUCERNE 2-Year Faricimab Results (2024)",
        None,
        manifest,
    )
    assert verdict.decision == "dup_title"


def test_new_when_no_matcher_fires():
    manifest = _index()
    verdict = _classify_link(
        "https://medinfo.example.com/genuinely-new.pdf",
        "A novel topic not in the archive",
        None,
        manifest,
    )
    assert verdict.decision == "new"
    assert verdict.features["canonical_url"].startswith("https://medinfo.example.com/")
