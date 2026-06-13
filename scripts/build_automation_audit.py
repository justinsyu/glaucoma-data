#!/usr/bin/env python3
"""Build the weekly automation audit dashboard data."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent.parent
SOURCES_PATH = ROOT / "scripts" / "sweep" / "sources.yaml"
PRESS_RELEASE_SOURCES_PATH = ROOT / "scripts" / "press_release_sources.yml"
PROFILES_PATH = ROOT / "_data" / "company_profiles.json"
OUTPUT_PATH = ROOT / "_data" / "automation_audit.json"
AUTOMATION_RUNS_DIR = ROOT / "artifacts" / "automation_runs"
SWEEP_RUNS_DIR = ROOT / "scripts" / "sweep" / "runs"


TERMINAL_OK = {
    "checked_ok",
    "checked_with_new_downloads",
    "checked_with_worklist_items",
    "checked_with_new_items",
    "checked_no_candidates",
    "manual_retrieval_required",
    "skipped_by_config",
}
TERMINAL_ERROR = {
    "fetch_error",
    "download_error",
    "parse_error",
    "validation_error",
    "build_error",
}
TERMINAL_STATUSES = TERMINAL_OK | TERMINAL_ERROR

DISPLAY_LABELS = {
    "publication": "Publication",
    "press_release": "Press release",
    "press_release_index": "Press release index",
    "html": "HTML",
    "pubmed": "PubMed",
    "requests": "Requests",
    "playwright_loadmore": "Playwright Load More",
    "playwright_hcp": "Playwright HCP",
    "checked_ok": "Checked OK",
    "checked_with_new_downloads": "Checked With New Downloads",
    "checked_with_worklist_items": "Checked With Worklist Items",
    "checked_with_new_items": "Checked With New Items",
    "checked_no_candidates": "Checked No Candidates",
    "manual_retrieval_required": "Manual Retrieval Required",
    "skipped_by_config": "Skipped By Config",
    "fetch_error": "Fetch Error",
    "download_error": "Download Error",
    "parse_error": "Parse Error",
    "validation_error": "Validation Error",
    "build_error": "Build Error",
    "missing": "Missing",
    "success": "Success",
    "partial": "Partial",
    "failed": "Failed",
    "running": "Running",
    "not_run": "Not Run",
    "high": "High",
    "medium": "Medium",
    "low": "Low",
    "missing_source": "Missing Source",
    "source_error": "Source Error",
    "dns_error": "DNS Error",
    "not_found": "Not Found",
    "blocked": "Blocked",
    "timeout": "Timeout",
    "http2_protocol_error": "HTTP/2 Protocol Error",
    "tls_error": "TLS Error",
    "configuration_error": "Configuration Error",
}


def display_label(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text in DISPLAY_LABELS:
        return DISPLAY_LABELS[text]
    return " ".join(part.capitalize() for part in text.replace("_", " ").split())


def rel(path: Path | str | None) -> str:
    if not path:
        return ""
    p = Path(path)
    if p.is_absolute():
        try:
            return p.relative_to(ROOT).as_posix()
        except ValueError:
            return p.as_posix()
    return p.as_posix().replace("\\", "/")


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def source_identity(
    company: dict[str, Any],
    source: dict[str, Any],
    index: int,
    family: str = "publication",
) -> str:
    key_material = {
        "family": family,
        "company_id": company.get("id", ""),
        "index": index,
        "kind": source.get(
            "kind",
            "press_release_index" if family == "press_release" else "html",
        ),
        "url": source.get("url", ""),
        "fallback_urls": source.get("fallback_urls", []),
        "terms": source.get("terms", []),
    }
    digest = hashlib.sha1(
        json.dumps(key_material, sort_keys=True).encode("utf-8")
    ).hexdigest()[:12]
    return f"{family}:{company.get('id', 'unknown')}:{index}:{digest}"


def profile_lookup() -> tuple[dict[str, dict[str, Any]], set[str]]:
    profiles = read_json(PROFILES_PATH, [])
    folder_to_profile: dict[str, dict[str, Any]] = {}
    in_scope_folders: set[str] = set()
    for profile in profiles:
        folder = str(profile.get("folder") or "")
        if folder:
            folder_to_profile[folder] = profile
        if int(profile.get("document_count") or 0) > 0 and folder:
            in_scope_folders.add(folder)
    return folder_to_profile, in_scope_folders


def expected_publication_sources() -> list[dict[str, Any]]:
    raw = yaml.safe_load(SOURCES_PATH.read_text(encoding="utf-8"))
    folder_to_profile, in_scope_folders = profile_lookup()
    rows: list[dict[str, Any]] = []
    for company in raw.get("companies", []):
        folder = str(company.get("folder") or "")
        folder_key = folder.removeprefix("companies/").strip("/")
        if folder_key not in in_scope_folders:
            continue
        profile = folder_to_profile.get(folder_key, {})
        for index, source in enumerate(company.get("sources") or [], start=1):
            kind = source.get("kind", "html")
            status = "skipped_by_config" if kind == "skip" else "pending"
            row = {
                "source_key": source_identity(company, source, index, "publication"),
                "source_family": "publication",
                "source_family_label": display_label("publication"),
                "run_type": "publication",
                "company_id": company.get("id", ""),
                "company_slug": profile.get("slug", ""),
                "company_name": company.get("name", ""),
                "tier": company.get("tier"),
                "source_index": index,
                "source_kind": kind,
                "source_kind_label": display_label(kind),
                "source_url": source.get("url", ""),
                "fallback_urls": source.get("fallback_urls", []),
                "pubmed_terms": source.get("terms", []),
                "fetcher": source.get("fetcher", "pubmed" if kind == "pubmed" else "requests"),
                "fetcher_label": display_label(source.get("fetcher", "pubmed" if kind == "pubmed" else "requests")),
                "expected_dest": source.get("dest", ""),
                "dest_worklist": source.get("dest_worklist", ""),
                "discovery_only": bool(source.get("discovery_only", False)),
                "status": status,
                "status_label": display_label(status),
                "skip_reason": source.get("reason", "") if kind == "skip" else "",
            }
            rows.append(row)
    return rows


def expected_press_release_sources() -> list[dict[str, Any]]:
    if not PRESS_RELEASE_SOURCES_PATH.exists():
        return []
    raw = yaml.safe_load(PRESS_RELEASE_SOURCES_PATH.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for company in raw.get("companies", []):
        for index, source in enumerate(company.get("sources") or [], start=1):
            row = {
                "source_key": source_identity(company, source, index, "press_release"),
                "source_family": "press_release",
                "source_family_label": display_label("press_release"),
                "run_type": "press_release",
                "source_id": source.get("source_id", ""),
                "company_id": company.get("id", ""),
                "company_slug": company.get("company_slug", ""),
                "company_name": company.get("name", ""),
                "tier": company.get("tier"),
                "source_index": index,
                "source_kind": source.get("kind", "press_release_index"),
                "source_kind_label": display_label(source.get("kind", "press_release_index")),
                "source_url": source.get("url", ""),
                "fallback_urls": source.get("fallback_urls", []),
                "pubmed_terms": [],
                "fetcher": source.get("fetcher", "requests"),
                "fetcher_label": display_label(source.get("fetcher", "requests")),
                "title_filter": source.get("title_filter", ""),
                "expected_dest": "_data/company_press_releases.yml",
                "dest_worklist": "",
                "discovery_only": False,
                "status": "pending",
                "status_label": display_label("pending"),
                "skip_reason": "",
            }
            rows.append(row)
    return rows


def expected_sources() -> list[dict[str, Any]]:
    return expected_publication_sources() + expected_press_release_sources()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            rows.append({"status": "parse_error", "error": "invalid JSONL row", "raw": line})
    return rows


def normalize_statuses(run_dir: Path) -> list[dict[str, Any]]:
    summary = read_json(run_dir / "source_status_summary.json", None)
    if isinstance(summary, dict):
        statuses = summary.get("sources") or summary.get("source_statuses") or []
        if isinstance(statuses, dict):
            statuses = list(statuses.values())
        if isinstance(statuses, list):
            return [s for s in statuses if isinstance(s, dict)]
    if isinstance(summary, list):
        return [s for s in summary if isinstance(s, dict)]
    return read_jsonl(run_dir / "source_status.jsonl")


def latest_by_source(statuses: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for status in statuses:
        key = (
            status.get("source_key")
            or status.get("source_id")
            or status.get("source_url")
            or status.get("company_id")
            or ""
        )
        if not key:
            continue
        latest[str(key)] = status
    return latest


def count_downloads(run: dict[str, Any]) -> int:
    if "downloaded_documents" in run:
        return len(run.get("downloaded_documents") or [])
    return sum(
        1
        for company in run.get("companies", [])
        for item in company.get("downloads", [])
        if item.get("status") == "downloaded"
    )


def count_worklist(run: dict[str, Any]) -> int:
    if "worklist_items" in run:
        return len(run.get("worklist_items") or [])
    return sum(
        len(company.get("worklist_items", []))
        for company in run.get("companies", [])
    )


def summarize_run(run_dir: Path) -> dict[str, Any]:
    run_json = read_json(run_dir / "run.json", {})
    expected = read_json(run_dir / "expected_sources.json", [])
    statuses = normalize_statuses(run_dir)
    latest = latest_by_source(statuses)

    expected_rows = expected if isinstance(expected, list) else []
    source_rows = []
    missing = []
    for source in expected_rows:
        key = (
            source.get("source_key")
            or source.get("source_id")
            or source.get("source_url")
            or source.get("company_id")
            or ""
        )
        status = latest.get(str(key), {})
        terminal = status.get("status") in TERMINAL_STATUSES
        row = {
            **source,
            "source_family_label": display_label(source.get("source_family", "")),
            "source_kind_label": display_label(source.get("source_kind", "")),
            "fetcher_label": display_label(source.get("fetcher", "")),
            "terminal_status": status.get("status", "missing"),
            "terminal_status_label": display_label(status.get("status", "missing")),
            "checked_at": status.get("checked_at", ""),
            "candidate_count": status.get("candidate_count"),
            "new_candidate_count": status.get("new_candidate_count"),
            "downloaded_count": status.get("downloaded_count"),
            "worklist_count": status.get("worklist_count"),
            "error": status.get("error", ""),
            "error_kind": status.get("error_kind", ""),
            "error_kind_label": display_label(status.get("error_kind", "")),
            "resolved_source_url": status.get("resolved_source_url", ""),
            "source_attempts": status.get("source_attempts", []),
            "terminal": terminal,
        }
        source_rows.append(row)
        if source.get("status") != "skipped_by_config" and not terminal:
            missing.append(row)

    error_rows = [
        row for row in source_rows if row.get("terminal_status") in TERMINAL_ERROR
    ]
    checked = [
        row for row in source_rows
        if row.get("terminal_status") in TERMINAL_STATUSES
    ]
    status_value = run_json.get("status") or (
        "failed" if missing else "partial" if error_rows else "success"
    )

    return {
        "run_id": run_json.get("run_id") or run_dir.name,
        "run_type": run_json.get("run_type") or run_json.get("source_family") or "publication",
        "run_type_label": display_label(run_json.get("run_type") or run_json.get("source_family") or "publication"),
        "trigger": run_json.get("trigger", ""),
        "status": status_value,
        "status_label": display_label(status_value),
        "dry_run": bool(run_json.get("dry_run", False)),
        "started_at": run_json.get("started_at", ""),
        "ended_at": run_json.get("ended_at", ""),
        "git_sha": run_json.get("git_sha", ""),
        "run_dir": rel(run_dir),
        "expected_sources_count": len([r for r in expected_rows if r.get("status") != "skipped_by_config"]),
        "checked_sources_count": len([r for r in checked if r.get("status") != "skipped_by_config"]),
        "missing_sources_count": len(missing),
        "error_sources_count": len(error_rows),
        "downloaded_documents_count": count_downloads(run_json),
        "worklist_items_count": count_worklist(run_json),
        "new_press_releases_count": len(run_json.get("new_press_releases", []) or []),
        "sweep_report": rel(run_json.get("sweep_report_path", "")),
        "source_statuses": source_rows,
        "missing_sources": missing,
        "error_sources": error_rows,
        "downloaded_documents": run_json.get("downloaded_documents", []),
        "worklist_items": run_json.get("worklist_items", []),
        "new_press_releases": run_json.get("new_press_releases", []),
        "validations": run_json.get("validations", []),
    }


def automation_runs() -> list[dict[str, Any]]:
    if not AUTOMATION_RUNS_DIR.exists():
        return []
    run_dirs = [p for p in AUTOMATION_RUNS_DIR.iterdir() if p.is_dir()]
    runs = [summarize_run(p) for p in run_dirs]
    runs.sort(
        key=lambda run: (
            run.get("started_at") or "",
            run.get("run_id") or "",
        ),
        reverse=True,
    )
    return runs


def recent_sweep_runs(limit: int = 20) -> list[dict[str, Any]]:
    if not SWEEP_RUNS_DIR.exists():
        return []
    rows = []
    for path in sorted(SWEEP_RUNS_DIR.glob("sweep-*.json"), reverse=True)[:limit]:
        data = read_json(path, {})
        companies = data.get("companies", [])
        rows.append({
            "path": rel(path),
            "started_at": data.get("started_at", ""),
            "ended_at": data.get("ended_at", ""),
            "companies_count": len(companies),
            "sources_visited": sum(len(c.get("sources_visited", [])) for c in companies),
            "new_candidates": sum(int(c.get("candidates_new") or 0) for c in companies),
            "downloaded": sum(
                1
                for c in companies
                for d in c.get("downloads", [])
                if d.get("status") == "downloaded"
            ),
            "worklist_items": sum(len(c.get("worklist_items", [])) for c in companies),
            "errors": sum(len(c.get("errors", [])) for c in companies),
        })
    return rows


def source_label(row: dict[str, Any]) -> str:
    source = row.get("resolved_source_url") or row.get("source_url")
    if source:
        return str(source)
    terms = row.get("pubmed_terms", [])
    return ", ".join(terms) if terms else ""


def finding_severity(row: dict[str, Any]) -> str:
    kind = row.get("error_kind", "")
    if kind in {"dns_error", "not_found", "configuration_error"}:
        return "high"
    return "medium"


def grouped_error_findings(error_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in error_rows:
        source = source_label(row)
        error_kind = row.get("error_kind") or "fetch_error"
        key = (
            str(row.get("run_type") or row.get("source_family") or ""),
            source,
            str(error_kind),
        )
        group = groups.setdefault(
            key,
            {
                "rows": [],
                "companies": [],
                "source": source,
                "error_kind": error_kind,
                "detail": row.get("error", ""),
                "severity": finding_severity(row),
            },
        )
        group["rows"].append(row)
        company = row.get("company_name", "")
        if company and company not in group["companies"]:
            group["companies"].append(company)
        if group["severity"] != "high" and finding_severity(row) == "high":
            group["severity"] = "high"

    findings = []
    for group in groups.values():
        companies = "; ".join(group["companies"])
        detail = str(group["detail"] or "")
        if len(group["rows"]) > 1:
            detail = f"{detail} ({len(group['rows'])} source rows affected)"
        findings.append({
            "severity": group["severity"],
            "severity_label": display_label(group["severity"]),
            "kind": "source_error",
            "kind_label": display_label("source_error"),
            "error_kind": group["error_kind"],
            "error_kind_label": display_label(group["error_kind"]),
            "company": companies,
            "source": group["source"],
            "detail": detail,
            "affected_source_rows": len(group["rows"]),
        })
    findings.sort(
        key=lambda finding: (
            {"high": 0, "medium": 1, "low": 2}.get(finding["severity"], 9),
            finding["company"],
            finding["source"],
        )
    )
    return findings


def build() -> dict[str, Any]:
    expected = expected_sources()
    runs = automation_runs()
    latest = runs[0] if runs else {}
    active_expected = [r for r in expected if r.get("status") != "skipped_by_config"]
    findings = []
    if latest:
        for row in latest.get("missing_sources", []):
            findings.append({
                "severity": "high",
                "severity_label": display_label("high"),
                "kind": "missing_source",
                "kind_label": display_label("missing_source"),
                "company": row.get("company_name", ""),
                "source": row.get("source_url") or ", ".join(row.get("pubmed_terms", [])),
                "detail": "Expected source has no terminal audit status.",
            })
        findings.extend(grouped_error_findings(latest.get("error_sources", [])))

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "summary": {
            "in_scope_companies": len({r["company_id"] for r in expected}),
            "publication_expected_sources": len([
                r for r in active_expected if r.get("source_family") == "publication"
            ]),
            "press_release_expected_sources": len([
                r for r in active_expected if r.get("source_family") == "press_release"
            ]),
            "expected_sources": len(active_expected),
            "configured_skips": len(expected) - len(active_expected),
            "automation_runs": len(runs),
            "latest_run_id": latest.get("run_id", ""),
            "latest_run_status": latest.get("status", "not_run"),
            "latest_run_status_label": display_label(latest.get("status", "not_run")),
            "latest_run_started_at": latest.get("started_at", ""),
            "latest_checked_sources": latest.get("checked_sources_count", 0),
            "latest_expected_sources": latest.get("expected_sources_count", len(active_expected)),
            "latest_downloaded_documents": latest.get("downloaded_documents_count", 0),
            "latest_worklist_items": latest.get("worklist_items_count", 0),
            "latest_error_sources": latest.get("error_sources_count", 0),
            "open_findings": len(findings),
        },
        "expected_sources": expected,
        "runs": runs,
        "recent_sweep_runs": recent_sweep_runs(),
        "findings": findings,
    }


def main() -> int:
    data = build()
    OUTPUT_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"Wrote {rel(OUTPUT_PATH)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
