"""Hand-tuned source recipes ported from scripts/sweep.

The bootstrap step produces a conservative watchlist that classifies sources
by host. The recipes step layers in the operationally-proven configuration
worked out over weeks of manual crawling: the Bayer Akamai click-through, the
4DMT pipeline page with per-program routing, the Clearside / Adverum /
EyePoint title filters that confine each source to its in-scope program, and
the Tier 3 (discovery_only) treatment of Regeneron's HCP portal and Roche's
restricted MedInfo paths.

Each recipe is keyed by a stable label and emits either a replacement entry
(the full SourceEntry) or a patch that merges into an existing entry matched
by ``(company_slug, predicate)``. Replacements delete any other watchlist
entries for that company that overlap the recipe's coverage (e.g., 4DMT's
single pipeline page replaces the three same-URL entries that bootstrap
produced from three program slugs).

The recipes are intentionally small and self-documenting; an operator adding
a new sponsor should be able to read this file and follow the same shape.
"""

from __future__ import annotations

import re
from typing import Callable

from .watchlist import RouterRule, SourceEntry, Watchlist


# A handful of recipes need long regex patterns. Each pattern is from the
# manual-crawl audit in scripts/sweep/sources.yaml and has been confirmed to
# match the in-scope program while excluding off-target programs the
# publication portal shares with the in-scope one.
ADVERUM_IXOVEC_FILTER = (
    r"(?i)ixo-vec|advm-022|optic|luna|aav2\.7m8|7m8|namd|wet[- ]?amd|nAMD"
)
CLEARSIDE_CLSAX_FILTER = (
    r"(?i)CLS-?(AX|TA|301|AX)|suprachoroidal|axitinib|integrin|odyssey|oasis|"
    r"peachtree|magnolia|sapphire|topaz|tanzanite|tybee|hulk|biopharma|"
    r"wet[- ]?amd|namd"
)
EYEPOINT_DURAVYU_FILTER = (
    r"(?i)duravyu|eyp-?1901|vorolanib|davio|lugano|lucia|verona|wet[- ]?amd|namd|dme"
)
REGENXBIO_RGX314_FILTER = (
    r"(?i)rgx-?314|abbv-?rgx-?314|sura-?vec|aaviate|atmosphere|ascent|altitude|"
    r"aav8|wet[- ]?amd|namd|diabetic[- ]retinopathy"
)
BAYER_EYLEA_NAMD_FILTER = (
    r"(?i)pulsar|spectrum.*namd|aflibercept.*8.?mg|xtend|aries|altair|view|"
    r"namd|iris.*vestrum.*namd|wet[- ]?amd"
)
OCULAR_TKI_FILTER = (
    r"(?i)axpaxli|otx-?tki|axitinib|hydrogel|sol-?1|sol-?r|helios|wet[- ]?amd|"
    r"namd|npdr|diabetic[- ]retinopathy"
)
REGENERON_EYLEA_FILTER = r"(?i)pulsar|candela|quasar|aflibercept|eylea|namd"
ROCHE_RETINA_FILTER = (
    r"(?i)faricimab|vabysmo|ranibizumab|susvimo|lucentis|pds|tenaya|lucerne|"
    r"avonelle|voyager|truckee|portal|archway"
)


def _se(**kw) -> SourceEntry:
    """Concise constructor for an explicit replacement entry."""
    return SourceEntry(**kw)


def _rr(pattern: str, dest: str) -> RouterRule:
    return RouterRule(pattern=pattern, dest=dest)


# --------------------------------------------------------------------------
# REPLACEMENTS: every entry returned by these factories *replaces* all
# bootstrap-generated entries that share the same (company_slug, predicate).
# --------------------------------------------------------------------------


def _replacements_for_4dmt() -> tuple[Callable[[SourceEntry], bool], list[SourceEntry]]:
    """4DMT: single pipeline page, dest_router by program."""

    def predicate(e: SourceEntry) -> bool:
        return (
            e.company_slug == "4dmt"
            and e.source_type == "html_pdf_links"
            and "4dmoleculartherapeutics.com" in e.url
        )

    entry = _se(
        source_id="4dmt-pipeline-posters",
        company_slug="4dmt",
        program_slug=None,
        source_type="html_pdf_links",
        url="https://4dmoleculartherapeutics.com/pipeline/",
        enabled=True,
        manual_review=False,
        tier=1,
        notes=(
            "Pipeline page lists posters/publications across 4D-150, 4D-310, and 4D-710. "
            "dest_router fans out per program."
        ),
        dest_router=[
            _rr(r"(?i)4d-150|prism|spectra|4front|namd|wamd|175",
                "companies/4d_molecular_therapeutics/4d_150/presentations_posters/"),
            _rr(r"(?i)4d-310|fabry",
                "companies/4d_molecular_therapeutics/4d_310/presentations_posters/"),
            _rr(r"(?i)4d-710|cftr|cf|cystic",
                "companies/4d_molecular_therapeutics/4d_710/presentations_posters/"),
            _rr(r".*",
                "companies/4d_molecular_therapeutics/uncategorized/presentations_posters/"),
        ],
    )
    return predicate, [entry]


def _replacements_for_bayer() -> tuple[Callable[[SourceEntry], bool], list[SourceEntry]]:
    """Bayer: congresspublications.bayer.com is behind a hardened Akamai WAF.

    The 2025 sweep ran successfully against this host because the WAF was in
    challenge mode (cookies-clear-once). As of May 2026 the WAF returns an
    explicit IP block ("Your bot have been rated as a harmful activity")
    with HTTP 403 regardless of User-Agent or click flow. The host now
    requires either an IP allowlist or a residential proxy, neither of which
    the watcher is configured for.

    Decision: keep the source in the watchlist as ``discovery_only`` so the
    audit trail captures attempts, and route operators to a worklist where
    they handle retrieval through an authenticated HCP browser. The
    extractor_config is kept (playwright_hcp + click:text=Continue) so the
    moment Bayer relaxes the block, restoring auto-fetch is a one-line edit.
    """

    def predicate(e: SourceEntry) -> bool:
        return e.company_slug == "bayer" and "bayer.com" in e.url

    entry = _se(
        source_id="bayer-congresspublications-hcp",
        company_slug="bayer",
        program_slug="eylea_hd",
        source_type="playwright_hcp",
        url="https://congresspublications.bayer.com/",
        enabled=True,
        manual_review=False,
        tier=3,
        discovery_only=True,
        dest_worklist="companies/bayer/_worklist_pending_hcp.md",
        notes=(
            "Bayer WAF returns 403 'bot rated as harmful activity' with an IP "
            "block since May 2026. Tier-2 auto-fetch is not possible without "
            "a residential proxy or IP allowlist. Until the block is lifted, "
            "the source runs as Tier 3 (discovery_only) and emits worklist "
            "rows to companies/bayer/_worklist_pending_hcp.md. Restore "
            "tier=2 + discovery_only=false when the WAF posture relaxes."
        ),
        title_filter=BAYER_EYLEA_NAMD_FILTER,
        extractor_config={
            "wait_until": "load",
            "timeout_ms": 30000,
            "bot_clear_seconds": 5,
            "hcp_action": "click:text=Continue",
            "post_action_wait_ms": 2000,
        },
        dest="companies/bayer/eylea_hd/presentations_posters/",
    )
    return predicate, [entry]


def _replacements_for_4dmt_disable_other() -> tuple[Callable[[SourceEntry], bool], list[SourceEntry]]:
    return (lambda e: False, [])  # no-op slot


# --------------------------------------------------------------------------
# PATCHES: dictionaries merged into a matching bootstrap entry. Only the
# fields named in the patch are overridden; everything else stays as bootstrap
# produced it.
# --------------------------------------------------------------------------


PATCHES: list[tuple[Callable[[SourceEntry], bool], dict]] = [
    # Clearside Biomedical: confine to CLS-AX program; route manuscripts vs posters.
    (
        lambda e: e.company_slug == "clearside-biomedical",
        {
            "tier": 1,
            "title_filter": CLEARSIDE_CLSAX_FILTER,
            "dest": "companies/clearside_biomedical/cls_ax/presentations_posters/",
            "title_router": [
                _rr(
                    r"(?i)journal|publication|retina[- ]specialist|retinal[- ]physician|"
                    r"review|ophthalmology[- ]times|expert[- ]panel",
                    "companies/clearside_biomedical/cls_ax/published_manuscripts/",
                ),
            ],
        },
    ),
    # Adverum: confine to ixo-vec / ADVM-022 (excluding ADVM-062 BCM, A1AT, etc.).
    (
        lambda e: e.company_slug == "adverum",
        {
            "tier": 1,
            "title_filter": ADVERUM_IXOVEC_FILTER,
            "dest": "companies/adverum/ixo_vec/presentations_posters/",
        },
    ),
    # EyePoint: confine to Duravyu / EYP-1901.
    (
        lambda e: e.company_slug == "eyepoint-pharmaceuticals",
        {
            "tier": 1,
            "title_filter": EYEPOINT_DURAVYU_FILTER,
            "dest": "companies/eyepoint_pharmaceuticals/duravyu_eyp_1901/presentations_posters/",
        },
    ),
    # REGENXBIO / AbbVie: confine to RGX-314, route manuscripts.
    (
        lambda e: e.company_slug == "regenxbio-abbvie",
        {
            "tier": 1,
            "title_filter": REGENXBIO_RGX314_FILTER,
            "dest": "companies/regenxbio_abbvie/rgx_314/presentations_posters/",
            "title_router": [
                _rr(
                    r"(?i)molecular[- ]therapy|aaojournal|sciencedirect|publication|journal|published",
                    "companies/regenxbio_abbvie/rgx_314/published_manuscripts/",
                ),
            ],
        },
    ),
    # Ocular Therapeutix: confine to AXPAXLI / OTX-TKI.
    (
        lambda e: e.company_slug == "ocular-therapeutix",
        {
            "tier": 2,
            "title_filter": OCULAR_TKI_FILTER,
            "dest": "companies/ocular_therapeutix/axpaxli_otx_tki/presentations_posters/",
        },
    ),
    # Regeneron MedInfo / search-results pages: Tier 3, discovery_only.
    (
        lambda e: e.company_slug == "regeneron" and "regeneronmedical" in e.url,
        {
            "tier": 3,
            "source_type": "playwright_hcp",
            "title_filter": REGENERON_EYLEA_FILTER,
            "discovery_only": True,
            "dest_worklist": "companies/regeneron/_worklist_pending_hcp.md",
            "extractor_config": {
                "wait_until": "load",
                "timeout_ms": 30000,
                "bot_clear_seconds": 3,
                "post_action_wait_ms": 1500,
            },
            "notes": (
                "Each PDF on regeneronmedical.com is bound to a per-document "
                "HCP attestation form. The watcher discovers titles and URLs "
                "but cannot download; rows are emitted to the worklist for "
                "manual retrieval by an authenticated operator."
            ),
        },
    ),
    # Roche/Genentech medinfo product pages: tier 1 for the unrestricted ones,
    # title_filter to keep retinal scope only.
    (
        lambda e: e.company_slug == "roche-genentech"
        and "genentech-medinfo.com" in e.url,
        {
            "tier": 1,
            "title_filter": ROCHE_RETINA_FILTER,
        },
    ),
    # The medically.gene.com single-document URL is a leaf, not a list page;
    # disable so it does not waste a fetch each run.
    (
        lambda e: e.company_slug == "roche-genentech" and "medically.gene.com" in e.url,
        {
            "enabled": False,
            "manual_review": True,
            "notes": (
                "Single-document page, not an index. Original entry left in "
                "the watchlist as documentation; disabled by recipe."
            ),
        },
    ),
]


# --------------------------------------------------------------------------
# Public entrypoint
# --------------------------------------------------------------------------


REPLACEMENT_FACTORIES = [
    _replacements_for_4dmt,
    _replacements_for_bayer,
]


def apply_recipes(wl: Watchlist) -> tuple[Watchlist, dict]:
    """Apply replacements and patches in-place. Returns (new watchlist, report)."""
    report = {"replaced": 0, "patched": 0, "unchanged": 0, "actions": []}

    sources = list(wl.sources)
    for factory in REPLACEMENT_FACTORIES:
        predicate, replacements = factory()
        kept = []
        removed = 0
        for s in sources:
            if predicate(s):
                removed += 1
            else:
                kept.append(s)
        if removed:
            sources = kept + replacements
            report["replaced"] += removed
            report["actions"].append(
                {
                    "kind": "replace",
                    "removed": removed,
                    "added": [r.source_id for r in replacements],
                }
            )

    # Apply patches
    out = []
    for s in sources:
        merged = s
        for predicate, patch in PATCHES:
            if predicate(s):
                data = merged.model_dump()
                for k, v in patch.items():
                    data[k] = v
                merged = SourceEntry.model_validate(data)
                report["patched"] += 1
                report["actions"].append({"kind": "patch", "source_id": s.source_id, "fields": list(patch.keys())})
        if merged is s:
            report["unchanged"] += 1
        out.append(merged)

    return Watchlist(sources=out), report
