#!/usr/bin/env python3
"""Run the publication sweep with a fail-closed audit ledger.

This wrapper is intentionally thin: `scripts.sweep` still owns discovery and
download behavior, while this script writes the expected-source ledger,
source terminal statuses, validation logs, and run metadata consumed by
`/automation-audit/`.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
AUTOMATION_RUNS_DIR = ROOT / "artifacts" / "automation_runs"

TERMINAL_ERROR = {"fetch_error", "download_error", "validation_error"}
OK_RE = re.compile(r"ok \((\d+) candidates\)")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def run_id(prefix: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_prefix = re.sub(r"[^a-zA-Z0-9_.-]+", "-", prefix).strip("-") or "run"
    return f"{safe_prefix}-{stamp}"


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


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


def command_text(args: list[str]) -> str:
    return " ".join(args)


def run_command(args: list[str], run_dir: Path, label: str) -> dict[str, Any]:
    log_path = run_dir / "logs" / f"{label}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    started = utc_now()
    proc = subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    ended = utc_now()
    log_path.write_text(proc.stdout or "", encoding="utf-8")
    return {
        "command": command_text(args),
        "status": "passed" if proc.returncode == 0 else "failed",
        "exit_code": proc.returncode,
        "started_at": started,
        "ended_at": ended,
        "log_path": rel(log_path),
    }


def expected_sources() -> list[dict[str, Any]]:
    sys.path.insert(0, str(ROOT))
    from scripts import build_automation_audit  # noqa: PLC0415

    if hasattr(build_automation_audit, "expected_publication_sources"):
        return build_automation_audit.expected_publication_sources()
    return [
        row for row in build_automation_audit.expected_sources()
        if row.get("source_family", "publication") == "publication"
    ]


def git_sha() -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    return proc.stdout.strip() if proc.returncode == 0 else ""


def parse_candidate_count(status: str) -> int | None:
    match = OK_RE.search(status or "")
    if not match:
        return None
    return int(match.group(1))


def source_label(source: dict[str, Any]) -> str:
    if source.get("source_url"):
        return str(source["source_url"])
    terms = source.get("pubmed_terms") or []
    if terms:
        return f"pubmed:{','.join(terms[:2])}"
    return "(skip)"


def terminal_status(source: dict[str, Any], visited: dict[str, Any] | None) -> str:
    if source.get("status") == "skipped_by_config":
        return "skipped_by_config"
    if not visited:
        return "fetch_error"
    raw = str(visited.get("status") or "")
    if raw.startswith("error:"):
        return "fetch_error"
    count = parse_candidate_count(raw)
    if count == 0:
        return "checked_no_candidates"
    if source.get("discovery_only"):
        return "manual_retrieval_required"
    return "checked_ok"


def reconcile_sources(
    expected: list[dict[str, Any]],
    sweep_report: dict[str, Any],
    run_dir: Path,
    sweep_report_path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    companies = {c.get("company_id"): c for c in sweep_report.get("companies", [])}
    expected_by_company: dict[str, list[dict[str, Any]]] = {}
    for source in expected:
        expected_by_company.setdefault(str(source.get("company_id")), []).append(source)

    statuses: list[dict[str, Any]] = []
    for company_id, sources in expected_by_company.items():
        company = companies.get(company_id, {})
        visited_rows = list(company.get("sources_visited", []))
        for source in sources:
            index = int(source.get("source_index") or 0) - 1
            visited = visited_rows[index] if 0 <= index < len(visited_rows) else None
            raw_status = str((visited or {}).get("status") or "")
            status = terminal_status(source, visited)
            candidate_count = parse_candidate_count(raw_status)
            error = ""
            if status == "fetch_error":
                error = raw_status.removeprefix("error:").strip()
                if not error:
                    error = "expected source missing from sweep report"
            statuses.append({
                "source_key": source.get("source_key", ""),
                "company_id": company_id,
                "company_name": source.get("company_name", ""),
                "tier": source.get("tier"),
                "source_index": source.get("source_index"),
                "source_kind": source.get("source_kind", ""),
                "source_url": source.get("source_url", ""),
                "pubmed_terms": source.get("pubmed_terms", []),
                "fetcher": source.get("fetcher", ""),
                "expected_dest": source.get("expected_dest", ""),
                "dest_worklist": source.get("dest_worklist", ""),
                "status": status,
                "checked_at": utc_now(),
                "candidate_count": candidate_count,
                "new_candidate_count": None,
                "downloaded_count": 0,
                "worklist_count": 0,
                "error": error,
                "sweep_report_path": rel(sweep_report_path),
                "raw_status": raw_status,
                "raw_source_label": (visited or {}).get("url", source_label(source)),
            })

    status_by_key = {s["source_key"]: s for s in statuses}
    downloads: list[dict[str, Any]] = []
    worklist_items: list[dict[str, Any]] = []
    for company in sweep_report.get("companies", []):
        company_id = company.get("company_id", "")
        company_sources = expected_by_company.get(str(company_id), [])
        for item in company.get("downloads", []):
            if item.get("status") == "downloaded":
                downloads.append({"company_id": company_id, **item})
        for item in company.get("worklist_items", []):
            worklist_items.append({"company_id": company_id, "company": company.get("name", ""), **item})

        visited_rows = list(company.get("sources_visited", []))
        for index, source in enumerate(company_sources):
            status = status_by_key.get(source.get("source_key"))
            if not status or index >= len(visited_rows):
                continue
            if source.get("discovery_only") and int(status.get("candidate_count") or 0) > 0:
                status["worklist_count"] = int(status.get("candidate_count") or 0)

    return statuses, [{"company_id": w.get("company_id", ""), **w} for w in worklist_items], downloads


def newest_sweep_json(sweep_dir: Path) -> Path | None:
    reports = sorted(sweep_dir.glob("sweep-*.json"), reverse=True)
    return reports[0] if reports else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Discover only; do not download PDFs.")
    parser.add_argument("--strict", action="store_true", help="Pass --strict to scripts.sweep.")
    parser.add_argument("--trigger", default="on_demand_test")
    parser.add_argument("--run-prefix", default="publication-automation-test")
    args = parser.parse_args()

    rid = run_id(args.run_prefix)
    run_dir = AUTOMATION_RUNS_DIR / rid
    sweep_dir = run_dir / "sweep"
    run_dir.mkdir(parents=True, exist_ok=True)

    expected = expected_sources()
    active_expected = [s for s in expected if s.get("status") != "skipped_by_config"]
    write_json(run_dir / "expected_sources.json", expected)

    run_json: dict[str, Any] = {
        "run_id": rid,
        "run_type": "publication",
        "trigger": args.trigger,
        "status": "running",
        "started_at": utc_now(),
        "ended_at": "",
        "git_sha": git_sha(),
        "dry_run": args.dry_run,
        "expected_sources_count": len(active_expected),
        "sweep_report_path": "",
        "downloaded_documents": [],
        "worklist_items": [],
        "validations": [],
    }
    write_json(run_dir / "run.json", run_json)

    validations = []
    validations.append(run_command(
        [sys.executable, "-m", "scripts.sweep.smoke"],
        run_dir,
        "01-smoke",
    ))

    sweep_cmd = [
        sys.executable,
        "-m",
        "scripts.sweep",
        "--runs-dir",
        str(sweep_dir),
    ]
    if args.dry_run:
        sweep_cmd.append("--dry-run")
    if args.strict:
        sweep_cmd.append("--strict")
    company_ids = sorted({str(s["company_id"]) for s in active_expected})
    sweep_cmd.extend(["--companies", ",".join(company_ids)])
    validations.append(run_command(sweep_cmd, run_dir, "02-sweep"))

    sweep_path = newest_sweep_json(sweep_dir)
    if sweep_path:
        sweep_report = json.loads(sweep_path.read_text(encoding="utf-8"))
        statuses, worklist_items, downloads = reconcile_sources(expected, sweep_report, run_dir, sweep_path)
    else:
        statuses = []
        worklist_items = []
        downloads = []

    summary = {"sources": statuses}
    write_json(run_dir / "source_status_summary.json", summary)
    with (run_dir / "source_status.jsonl").open("w", encoding="utf-8") as f:
        for row in statuses:
            f.write(json.dumps(row, sort_keys=True) + "\n")

    checked = [s for s in statuses if s.get("status") not in {"skipped_by_config"}]
    errors = [s for s in checked if s.get("status") in TERMINAL_ERROR]
    missing_count = len(active_expected) - len(checked)

    if missing_count or errors or any(v["exit_code"] != 0 for v in validations):
        final_status = "partial"
    else:
        final_status = "success"

    run_json.update({
        "status": final_status,
        "ended_at": utc_now(),
        "sweep_report_path": rel(sweep_path) if sweep_path else "",
        "downloaded_documents": downloads,
        "worklist_items": worklist_items,
        "validations": validations,
    })
    write_json(run_dir / "run.json", run_json)

    audit_validation = run_command(
        [sys.executable, "scripts/build_automation_audit.py"],
        run_dir,
        "03-build-automation-audit",
    )
    validations.append(audit_validation)
    run_json["validations"] = validations
    if audit_validation["exit_code"] != 0 and run_json["status"] == "success":
        run_json["status"] = "partial"
    write_json(run_dir / "run.json", run_json)

    print(f"Run ID: {rid}")
    print(f"Run dir: {rel(run_dir)}")
    print(f"Status: {run_json['status']}")
    print(f"Sources checked: {len(checked)} / {len(active_expected)}")
    print(f"Error sources: {len(errors)}")
    print(f"Sweep report: {run_json['sweep_report_path']}")
    return 0 if run_json["status"] == "success" else 2


if __name__ == "__main__":
    raise SystemExit(main())
