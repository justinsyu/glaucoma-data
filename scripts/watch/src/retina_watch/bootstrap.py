"""Derive an initial watchlist from existing manifest data.

The seed comes from two places:

1. ``_data/company_documents.json``: every distinct ``source_page`` that is a
   real URL becomes a watchlist entry. Free-text source notes (e.g.,
   "Direct journal article") are emitted with ``manual_review: true`` so an
   operator can replace them with a proper URL before they are crawled.
2. ``_data/company_profiles.json``: every company that has no ``source_page``
   in the manifest gets a placeholder entry pointing at its ``brand_site`` with
   ``manual_review: true`` and ``enabled: false``.

The bootstrap also classifies each URL into a source_type by host so the right
extractor is selected during a run. Classification is conservative: anything
unfamiliar lands in ``html_pdf_links`` (the safest generic extractor) and is
flagged for manual review of the extractor config.
"""

from __future__ import annotations

import json
import re
from collections import OrderedDict
from urllib.parse import urlparse

from .paths import data_dir, manifest_path, profiles_path
from .watchlist import SourceEntry, Watchlist, write_watchlist


# Canonical sponsor names for ClinicalTrials.gov LeadSponsorName queries. The
# manifest's display names contain partner slashes ("Roche / Genentech") that
# CT.gov does not understand. Mapping kept compact; missing entries fall back
# to the manifest's company display name and rely on the operator to refine.
SPONSOR_CANONICAL: dict[str, str] = {
    "4dmt": "4D Molecular Therapeutics",
    "adverum": "Adverum Biotechnologies",
    "amgen": "Amgen",
    "bausch-and-lomb": "Bausch & Lomb",
    "bayer": "Bayer",
    "biocon-biologics": "Biocon Biologics",
    "biogen-samsung-bioepis": "Biogen",
    "celltrion": "Celltrion",
    "clearside-biomedical": "Clearside Biomedical",
    "eyepoint-pharmaceuticals": "EyePoint Pharmaceuticals",
    "formycon-klinge-biopharma": "Formycon",
    "intas-sun-pharma": "Sun Pharma",
    "lupin": "Lupin",
    "novartis": "Novartis",
    "ocular-therapeutix": "Ocular Therapeutix",
    "outlook-therapeutics": "Outlook Therapeutics",
    "regeneron": "Regeneron Pharmaceuticals",
    "regenxbio-abbvie": "REGENXBIO",
    "roche-genentech": "Hoffmann-La Roche",
    "samsung-bioepis-biogen": "Samsung Bioepis",
    "sandoz": "Sandoz",
}


# Common drug aliases keyed by ``program_slug``. PubMed and CT.gov index drugs
# by generic name far more often than by brand or development code. The
# operator can extend this with additional aliases via the watchlist YAML.
PROGRAM_INTERVENTION_TERMS: dict[str, list[str]] = {
    "vabysmo": ["faricimab"],
    "lucentis": ["ranibizumab"],
    "susvimo": ["ranibizumab", "Port Delivery System"],
    "eylea": ["aflibercept"],
    "eylea_hd": ["aflibercept", "aflibercept 8 mg"],
    "beovu": ["brolucizumab"],
    "byooviz": ["ranibizumab biosimilar"],
    "cimerli": ["ranibizumab biosimilar"],
    "ahzantive": ["aflibercept biosimilar", "FYB203"],
    "enzeevu_enzeevum": ["aflibercept biosimilar"],
    "pavblu": ["aflibercept biosimilar", "ABP 938"],
    "duravyu_eyp_1901": ["vorolanib", "EYP-1901"],
    "axpaxli_otx_tki": ["axitinib", "OTX-TKI"],
    "cls_ax": ["axitinib", "CLS-AX"],
    "ixo_vec": ["ixoberogene soroparvovec", "ADVM-022"],
    "4d_150": ["4D-150"],
    "4d_310": ["4D-310"],
    "4d_710": ["4D-710"],
    "rgx_314": ["RGX-314", "ABBV-RGX-314"],
}


HOST_TO_SOURCE_TYPE: dict[str, str] = {
    "www.genentech-medinfo.com": "html_pdf_links",
    "medically.gene.com": "html_pdf_links",
    "www.regeneronmedical.com": "html_pdf_links",
    "www.regeneron.com": "html_pdf_links",
    "congresspublications.bayer.com": "html_pdf_links",
    "www.4dmoleculartherapeutics.com": "html_pdf_links",
    "4dmoleculartherapeutics.com": "html_pdf_links",
    "investor.regeneron.com": "press_release_index",
    "www.novartis.com": "press_release_index",
    "www.amgen.com": "press_release_index",
    "www.formycon.com": "publications_hub",
}


def _slugify(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value or "source"


def _source_id(company: str, program: str | None, url: str) -> str:
    host = urlparse(url).netloc or "no-host"
    return _slugify(f"{company}-{program or 'all'}-{host}")


def _looks_like_url(value: str) -> bool:
    return value.startswith(("http://", "https://"))


def _seed_structured_api_sources(seen: "OrderedDict[str, SourceEntry]") -> None:
    """Append one CT.gov and one PubMed entry per program in the archive.

    CT.gov entries are enabled by default (deterministic JSON API). PubMed
    entries are seeded as ``enabled: false`` so the operator opts in after
    sanity-checking the query terms for each drug; PubMed search syntax is
    drug-specific and a too-broad term floods the candidates table.
    """
    with (data_dir() / "company_programs.json").open("r", encoding="utf-8") as fh:
        programs = json.load(fh)

    for prog in programs:
        company_slug = prog["company_slug"]
        program_slug = prog["program_slug"]
        sponsor = SPONSOR_CANONICAL.get(company_slug) or prog.get("company") or ""
        if not sponsor:
            continue
        interventions = PROGRAM_INTERVENTION_TERMS.get(program_slug) or [prog["program"]]
        primary_intervention = interventions[0]

        # ClinicalTrials.gov entry per program.
        ct_sid = _slugify(f"{company_slug}-{program_slug}-ctgov")
        if ct_sid not in seen:
            seen[ct_sid] = SourceEntry(
                source_id=ct_sid,
                company_slug=company_slug,
                program_slug=program_slug,
                source_type="clinicaltrials_v2_api",
                url=(
                    "https://clinicaltrials.gov/search?"
                    f"sponsor={sponsor}&intervention={primary_intervention}"
                ),
                enabled=True,
                manual_review=False,
                extractor_config={
                    "sponsor": sponsor,
                    "intervention": primary_intervention,
                    "page_size": 50,
                },
                notes=(
                    "ClinicalTrials.gov v2 API. Sponsor and intervention are auto-seeded; "
                    "refine in this YAML if the API returns too many or too few studies."
                ),
            )

        # PubMed entry per program, off by default.
        pm_sid = _slugify(f"{company_slug}-{program_slug}-pubmed")
        if pm_sid not in seen:
            # Build a search term: any intervention alias, restricted to retina-relevant MeSH headings.
            alias_clause = " OR ".join(f'"{a}"' for a in interventions)
            term = (
                f"({alias_clause}) AND ("
                "\"Macular Degeneration\"[MeSH] OR "
                "\"Wet Macular Degeneration\"[MeSH] OR "
                "\"Diabetic Retinopathy\"[MeSH] OR "
                "\"Retinal Vein Occlusion\"[MeSH] OR "
                "retina[Title/Abstract]"
                ")"
            )
            seen[pm_sid] = SourceEntry(
                source_id=pm_sid,
                company_slug=company_slug,
                program_slug=program_slug,
                source_type="pubmed_eutils",
                url=f"https://pubmed.ncbi.nlm.nih.gov/?term={primary_intervention}",
                enabled=False,
                manual_review=True,
                extractor_config={
                    "term": term,
                    "retmax": 100,
                    "last_n_days": 365,
                },
                notes=(
                    "PubMed E-utilities. Disabled by default; enable after verifying that "
                    "the search term has the right precision for this drug. Set NCBI_API_KEY "
                    "for higher rate limits."
                ),
            )


def bootstrap(write: bool = True) -> tuple[Watchlist, dict]:
    """Build the watchlist; return (watchlist, coverage_report)."""
    with manifest_path().open("r", encoding="utf-8") as fh:
        docs = json.load(fh)
    with profiles_path().open("r", encoding="utf-8") as fh:
        profiles = json.load(fh)

    seen: "OrderedDict[str, SourceEntry]" = OrderedDict()
    companies_with_real_source: set[str] = set()
    free_text_notes: list[tuple[str, str]] = []

    for doc in docs:
        sp = (doc.get("source_page") or "").strip()
        if not sp:
            continue
        company = doc["company_slug"]
        program = doc.get("program_slug") or None

        if not _looks_like_url(sp):
            free_text_notes.append((company, sp))
            sid = _source_id(company, program, f"manual-{_slugify(sp)}")
            if sid in seen:
                continue
            seen[sid] = SourceEntry(
                source_id=sid,
                company_slug=company,
                program_slug=program,
                source_type="manual",
                url="",
                enabled=False,
                manual_review=True,
                notes=f"Free-text source note in manifest: {sp!r}. Replace with a real URL before enabling.",
            )
            continue

        companies_with_real_source.add(company)
        host = urlparse(sp).netloc
        source_type = HOST_TO_SOURCE_TYPE.get(host, "html_pdf_links")
        sid = _source_id(company, program, sp)
        if sid in seen:
            continue
        seen[sid] = SourceEntry(
            source_id=sid,
            company_slug=company,
            program_slug=program,
            source_type=source_type,
            url=sp,
            enabled=source_type == "html_pdf_links",
            manual_review=source_type != "html_pdf_links",
            notes=(
                None
                if source_type == "html_pdf_links"
                else f"Auto-classified as {source_type!r}; review extractor before enabling."
            ),
        )

    # Companies without any URL-shaped source_page in the manifest get a
    # placeholder pinned to their brand_site so they remain visible in the
    # watchlist coverage report.
    missing: list[str] = []
    for p in profiles:
        slug = p["slug"]
        if slug in companies_with_real_source:
            continue
        missing.append(slug)
        brand = (p.get("brand_site") or "").strip()
        if not brand:
            continue
        sid = _source_id(slug, None, brand)
        if sid in seen:
            continue
        seen[sid] = SourceEntry(
            source_id=sid,
            company_slug=slug,
            program_slug=None,
            source_type="publications_hub",
            url=brand,
            enabled=False,
            manual_review=True,
            notes=(
                "Seeded from company_profiles.brand_site. Replace with the real "
                "publications/press-release index URL before enabling."
            ),
        )

    _seed_structured_api_sources(seen)

    wl = Watchlist(sources=list(seen.values()))
    if write:
        write_watchlist(wl)

    coverage = {
        "total_sources": len(wl.sources),
        "structured_api_sources": sum(
            1
            for s in wl.sources
            if s.source_type in {"clinicaltrials_v2_api", "pubmed_eutils"}
        ),
        "enabled_sources": sum(1 for s in wl.sources if s.enabled),
        "manual_review_sources": sum(1 for s in wl.sources if s.manual_review),
        "companies_with_real_source": sorted(companies_with_real_source),
        "companies_missing_real_source": sorted(missing),
        "free_text_source_notes": len(free_text_notes),
        "by_source_type": {
            t: sum(1 for s in wl.sources if s.source_type == t)
            for t in sorted({s.source_type for s in wl.sources})
        },
    }
    return wl, coverage
