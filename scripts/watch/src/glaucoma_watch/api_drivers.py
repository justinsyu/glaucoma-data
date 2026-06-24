"""Structured-API drivers.

Two APIs are wired here:

* ``clinicaltrials_v2_api``: ClinicalTrials.gov v2 REST. Each source is a query
  (sponsor + intervention + condition). Records emitted with the NCT id as the
  stable URL key.
* ``pubmed_eutils``: NCBI E-utilities. Each source is an ESearch term. Records
  emitted with the PMID as the stable URL key.

These drivers do not retrieve PDFs; they retrieve *signals* that a publication
exists, which then drive downstream PDF discovery (e.g., querying the company
medinfo portal for a matching title, or pulling from PMC for open access).

Both APIs are public, rate-limited, and require no authentication. PubMed
recommends an ``api_key`` query parameter for higher rate limits; we accept it
via the ``NCBI_API_KEY`` environment variable. CT.gov has no key requirement.
"""

from __future__ import annotations

import json
import hashlib
import time
from urllib.parse import urlencode

from . import db
from .drivers import DriverResult, register_driver
from .extractors import ExtractedLink
from .fetcher import fetch
from .logging_setup import get_logger
from .watchlist import SourceEntry


CT_GOV_BASE = "https://clinicaltrials.gov/api/v2/studies"
PUBMED_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
PUBMED_ARTICLE_URL_TEMPLATE = "https://pubmed.ncbi.nlm.nih.gov/{pmid}/"


def _record_api_fetch(
    *,
    run_id: str,
    source_id: str,
    url: str,
    http_status: int | None,
    bytes_count: int,
    latency_ms: int,
    error: str | None,
    method: str,
) -> None:
    s = db.session()
    try:
        s.add(
            db.FetchEvent(
                run_id=run_id,
                source_id=source_id,
                url=url,
                method=method,
                http_status=http_status,
                bytes=bytes_count,
                sha256_head=None,
                latency_ms=latency_ms,
                retries=0,
                error=error,
            )
        )
        s.commit()
    finally:
        s.close()


# ---------------------------- ClinicalTrials.gov ----------------------------


def _as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    text = str(value).strip()
    return [text] if text else []


def _area_clause(area: str, terms: list[str]) -> str | None:
    clauses = [f"AREA[{area}]{term}" for term in terms if term]
    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return "(" + " OR ".join(clauses) + ")"


def _raw_clause(terms: list[str]) -> str | None:
    clauses = [term for term in terms if term]
    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return "(" + " OR ".join(clauses) + ")"


def _date_value(module: dict, key: str) -> str | None:
    value = module.get(key)
    if isinstance(value, dict):
        return value.get("date")
    return None


def _intervention_names(study: dict) -> list[str]:
    arms = (
        study.get("protocolSection", {})
        .get("armsInterventionsModule", {})
        .get("interventions", [])
    )
    return [
        str(item.get("name")).strip()
        for item in arms
        if isinstance(item, dict) and item.get("name")
    ]


def _sponsor_summary(study: dict) -> dict:
    sponsors = (
        study.get("protocolSection", {})
        .get("sponsorCollaboratorsModule", {})
        or {}
    )
    lead = sponsors.get("leadSponsor") or {}
    collaborators = sponsors.get("collaborators") or []
    return {
        "lead_sponsor": lead.get("name"),
        "collaborators": [
            item.get("name")
            for item in collaborators
            if isinstance(item, dict) and item.get("name")
        ],
    }


def _location_countries(study: dict) -> list[str]:
    locations = (
        study.get("protocolSection", {})
        .get("contactsLocationsModule", {})
        .get("locations", [])
    )
    countries = {
        item.get("country")
        for item in locations
        if isinstance(item, dict) and item.get("country")
    }
    return sorted(countries)


def _study_extras(study: dict) -> dict:
    protocol = study.get("protocolSection", {}) or {}
    ident = protocol.get("identificationModule", {}) or {}
    status_mod = protocol.get("statusModule", {}) or {}
    design = protocol.get("designModule", {}) or {}
    conditions = protocol.get("conditionsModule", {}) or {}
    sponsor = _sponsor_summary(study)
    enrollment = design.get("enrollmentInfo") or {}
    record_json = json.dumps(study, sort_keys=True, separators=(",", ":"))

    return {
        "nct_id": ident.get("nctId"),
        "brief_title": ident.get("briefTitle"),
        "official_title": ident.get("officialTitle"),
        "acronym": ident.get("acronym"),
        "overall_status": status_mod.get("overallStatus"),
        "phase": design.get("phases"),
        "study_type": design.get("studyType"),
        "enrollment_count": enrollment.get("count"),
        "enrollment_type": enrollment.get("type"),
        "conditions": conditions.get("conditions") or [],
        "interventions": _intervention_names(study),
        "lead_sponsor": sponsor["lead_sponsor"],
        "collaborators": sponsor["collaborators"],
        "location_countries": _location_countries(study),
        "has_results": study.get("hasResults"),
        "last_update_submit_date": status_mod.get("lastUpdateSubmitDate"),
        "last_update_post_date": _date_value(status_mod, "lastUpdatePostDateStruct"),
        "study_first_post_date": _date_value(status_mod, "studyFirstPostDateStruct"),
        "results_first_post_date": _date_value(status_mod, "resultsFirstPostDateStruct"),
        "primary_completion_date": _date_value(status_mod, "primaryCompletionDateStruct"),
        "completion_date": _date_value(status_mod, "completionDateStruct"),
        "status_verified_date": status_mod.get("statusVerifiedDate"),
        "ctgov_record_hash": hashlib.sha256(record_json.encode("utf-8")).hexdigest(),
        "ctgov_record": study,
    }


@register_driver("clinicaltrials_v2_api")
def _ctgov_driver(entry: SourceEntry, run_id: str) -> DriverResult:
    """Query ClinicalTrials.gov v2.

    Expected ``extractor_config``:
        sponsor: str or list[str] (optional)
        sponsor_aliases: list[str] (optional)
        intervention: str or list[str] (optional)
        intervention_aliases: list[str] (optional)
        condition: str or list[str] (optional)
        condition_aliases: list[str] (optional)
        query_terms: str or list[str] (optional, raw CT.gov search terms)
        term_aliases: list[str] (optional)
        recruitment_status: list[str] (optional)
        fields: list[str] (optional, omit by default to retain full records)
        page_size: int (optional, default 50; max 1000)
        last_update_after: str (optional ISO date)
    """
    log = get_logger().bind(source_id=entry.source_id, driver="clinicaltrials_v2_api")
    cfg = entry.extractor_config
    sponsor_terms = _as_list(cfg.get("sponsor")) + _as_list(cfg.get("sponsor_aliases"))
    intervention_terms = _as_list(cfg.get("intervention")) + _as_list(
        cfg.get("intervention_aliases")
    )
    condition_terms = _as_list(cfg.get("condition")) + _as_list(cfg.get("condition_aliases"))
    raw_terms = _as_list(cfg.get("query_terms")) + _as_list(cfg.get("term_aliases"))

    query_terms = [
        clause
        for clause in (
            _area_clause("LeadSponsorName", sponsor_terms),
            _area_clause("InterventionName", intervention_terms),
            _area_clause("Condition", condition_terms),
            _raw_clause(raw_terms),
        )
        if clause
    ]
    if not query_terms:
        return DriverResult(
            links=None,
            status="skipped",
            reason="missing_ctgov_query_terms_in_extractor_config",
        )

    params: dict[str, str] = {
        "query.term": " AND ".join(query_terms),
        "pageSize": str(min(max(int(cfg.get("page_size", 50)), 1), 1000)),
        "format": "json",
    }
    if cfg.get("fields"):
        params["fields"] = ",".join(_as_list(cfg.get("fields")))
    if cfg.get("recruitment_status"):
        params["filter.overallStatus"] = "|".join(cfg["recruitment_status"])
    if cfg.get("last_update_after"):
        params["filter.advanced"] = (
            f"AREA[LastUpdatePostDate]RANGE[{cfg['last_update_after']},MAX]"
        )

    studies: list[dict] = []
    next_page_token = None
    pages = 0
    max_pages = int(cfg.get("max_pages", 100))
    while True:
        page_params = dict(params)
        if next_page_token:
            page_params["pageToken"] = next_page_token
        url = f"{CT_GOV_BASE}?{urlencode(page_params)}"
        result = fetch(url, run_id=run_id, source_id=entry.source_id)
        if result.skipped_reason:
            return DriverResult(links=None, status="skipped", reason=result.skipped_reason)
        if not result.ok:
            return DriverResult(links=None, status="fetch_failed", error=result.error)

        try:
            payload = json.loads(result.body.decode("utf-8"))
        except Exception as exc:
            log.exception("ctgov_json_parse_failed")
            return DriverResult(links=None, status="extract_failed", error=str(exc))

        studies.extend(payload.get("studies") or [])
        next_page_token = payload.get("nextPageToken")
        pages += 1
        if not next_page_token or pages >= max_pages:
            break

    links: list[ExtractedLink] = []
    for study in studies:
        ident = (
            study.get("protocolSection", {}).get("identificationModule", {}) or {}
        )
        nct = ident.get("nctId")
        if not nct:
            continue
        title = ident.get("briefTitle") or ident.get("officialTitle")
        canonical_url = f"https://clinicaltrials.gov/study/{nct}"
        links.append(
            ExtractedLink(
                url=canonical_url,
                title=title,
                extras=_study_extras(study),
            )
        )
    log.info("ctgov_query_ok", studies=len(studies), links=len(links), pages=pages)
    return DriverResult(links=sorted(links, key=lambda x: x.url), status="ok")


# --------------------------------- PubMed ---------------------------------


@register_driver("pubmed_eutils")
def _pubmed_driver(entry: SourceEntry, run_id: str) -> DriverResult:
    """Run a PubMed ESearch + ESummary query.

    Expected ``extractor_config``:
        term: str (required, PubMed search syntax)
        retmax: int (optional, default 100; PubMed allows up to 10000 per page)
        last_n_days: int (optional, restrict to recently published)
        api_key: str (optional, otherwise read from NCBI_API_KEY env var)
    """
    import os

    log = get_logger().bind(source_id=entry.source_id, driver="pubmed_eutils")
    cfg = entry.extractor_config
    term = cfg.get("term")
    if not term:
        return DriverResult(
            links=None, status="skipped", reason="missing_term_in_extractor_config"
        )
    api_key = cfg.get("api_key") or os.environ.get("NCBI_API_KEY")
    retmax = int(cfg.get("retmax", 100))

    esearch_params: dict[str, str] = {
        "db": "pubmed",
        "term": term,
        "retmax": str(retmax),
        "retmode": "json",
    }
    if cfg.get("last_n_days"):
        esearch_params["reldate"] = str(int(cfg["last_n_days"]))
        esearch_params["datetype"] = "pdat"
    if api_key:
        esearch_params["api_key"] = api_key

    esearch_url = f"{PUBMED_ESEARCH}?{urlencode(esearch_params)}"
    es_result = fetch(esearch_url, run_id=run_id, source_id=entry.source_id)
    if es_result.skipped_reason:
        return DriverResult(links=None, status="skipped", reason=es_result.skipped_reason)
    if not es_result.ok:
        return DriverResult(links=None, status="fetch_failed", error=es_result.error)

    try:
        es_payload = json.loads(es_result.body.decode("utf-8"))
    except Exception as exc:
        log.exception("pubmed_esearch_parse_failed")
        return DriverResult(links=None, status="extract_failed", error=str(exc))

    pmids: list[str] = (
        es_payload.get("esearchresult", {}).get("idlist") or []
    )
    if not pmids:
        log.info("pubmed_no_hits")
        return DriverResult(links=[], status="ok")

    esummary_params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "json",
    }
    if api_key:
        esummary_params["api_key"] = api_key
    esummary_url = f"{PUBMED_ESUMMARY}?{urlencode(esummary_params)}"

    # PubMed asks for at most 3 requests per second without an API key. The
    # politeness layer's default 2.0s host interval is well under that.
    time.sleep(0.0)
    sum_result = fetch(esummary_url, run_id=run_id, source_id=entry.source_id)
    if sum_result.skipped_reason:
        return DriverResult(links=None, status="skipped", reason=sum_result.skipped_reason)
    if not sum_result.ok:
        return DriverResult(links=None, status="fetch_failed", error=sum_result.error)

    try:
        sum_payload = json.loads(sum_result.body.decode("utf-8"))
    except Exception as exc:
        log.exception("pubmed_esummary_parse_failed")
        return DriverResult(links=None, status="extract_failed", error=str(exc))

    docs = (sum_payload.get("result") or {})
    links: list[ExtractedLink] = []
    for pmid in pmids:
        rec = docs.get(pmid) or {}
        if not rec:
            continue
        article_ids = {a["idtype"]: a["value"] for a in rec.get("articleids", [])}
        links.append(
            ExtractedLink(
                url=PUBMED_ARTICLE_URL_TEMPLATE.format(pmid=pmid),
                title=rec.get("title"),
                extras={
                    "pmid": pmid,
                    "pmc": article_ids.get("pmc"),
                    "doi": article_ids.get("doi"),
                    "journal": rec.get("fulljournalname") or rec.get("source"),
                    "pubdate": rec.get("pubdate"),
                    "epubdate": rec.get("epubdate"),
                    "authors": [a.get("name") for a in rec.get("authors", []) if a.get("name")][:5],
                },
            )
        )
    log.info("pubmed_query_ok", pmids=len(pmids), links=len(links))
    return DriverResult(links=sorted(links, key=lambda x: x.url), status="ok")


# Both drivers also need a placeholder extractor entry so the source_type passes
# watchlist validation. The driver does the actual work, so the extractor body
# is never called; we register no-op extractors so the registry is complete.
from .extractors.base import register as _register_extractor  # noqa: E402


@_register_extractor("clinicaltrials_v2_api")
def _ctgov_extractor(*, body: bytes, source_url: str, config: dict) -> list[ExtractedLink]:
    return []


@_register_extractor("pubmed_eutils")
def _pubmed_extractor(*, body: bytes, source_url: str, config: dict) -> list[ExtractedLink]:
    return []
