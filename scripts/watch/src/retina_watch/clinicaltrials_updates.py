"""Build ClinicalTrials.gov update history for the public site.

Daily monitor runs write full CT.gov source snapshots under
``artifacts/watch/snapshots``. This exporter compares consecutive snapshots for
each CT.gov source and writes a durable JSON ledger to
``_data/clinicaltrials_updates.json``.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from .paths import data_dir, repo_root, snapshots_dir
from .watchlist import SourceEntry, load_watchlist


OUTPUT_PATH = data_dir() / "clinicaltrials_updates.json"

TRACKED_FIELDS = [
    ("title", "Title"),
    ("overall_status", "Status"),
    ("phase", "Phase"),
    ("has_results", "Results Posted"),
    ("last_update_submit_date", "Last Update Submitted"),
    ("last_update_post_date", "Last Update Posted"),
    ("study_first_post_date", "Study First Posted"),
    ("results_first_post_date", "Results First Posted"),
    ("primary_completion_date", "Primary Completion"),
    ("completion_date", "Completion"),
    ("status_verified_date", "Status Verified"),
    ("enrollment_count", "Enrollment"),
    ("conditions", "Conditions"),
    ("interventions", "Interventions"),
    ("lead_sponsor", "Lead Sponsor"),
    ("collaborators", "Collaborators"),
    ("location_countries", "Countries"),
]


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _rel(path: Path | str | None) -> str:
    if not path:
        return ""
    p = Path(path)
    if p.is_absolute():
        try:
            return p.relative_to(repo_root()).as_posix()
        except ValueError:
            return p.as_posix()
    return p.as_posix().replace("\\", "/")


def _iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _date_part(value: str | None) -> str:
    if not value:
        return ""
    return value[:10]


def _record_status_module(extras: dict[str, Any]) -> dict[str, Any]:
    record = extras.get("ctgov_record") or {}
    return (
        record.get("protocolSection", {})
        .get("statusModule", {})
        or {}
    )


def _date_struct_type(status_mod: dict[str, Any], key: str) -> str:
    value = status_mod.get(key)
    if isinstance(value, dict):
        return str(value.get("type") or "")
    return ""


def _display_value(value: Any) -> str:
    if value is None or value == "":
        return "None"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, list):
        return ", ".join(_display_value(item) for item in value) or "None"
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    return str(value).replace("_", " ")


def _field_change_sentence(change: dict[str, Any]) -> str:
    label = change.get("label") or change.get("field") or "Field"
    before = _display_value(change.get("before"))
    after = _display_value(change.get("after"))
    return f"{label}: {before} to {after}"


def _week_start(date_text: str) -> str:
    date_value = dt.date.fromisoformat(date_text)
    return (date_value - dt.timedelta(days=date_value.weekday())).isoformat()


def _week_end(week_start: str) -> str:
    return (dt.date.fromisoformat(week_start) + dt.timedelta(days=6)).isoformat()


def _profile_lookup() -> dict[str, dict[str, Any]]:
    profiles = _read_json(data_dir() / "company_profiles.json", [])
    return {str(p.get("slug")): p for p in profiles if p.get("slug")}


def _program_lookup() -> dict[tuple[str, str], dict[str, Any]]:
    programs = _read_json(data_dir() / "company_programs.json", [])
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for program in programs:
        company_slug = str(program.get("company_slug") or "")
        program_slug = str(program.get("program_slug") or "")
        if company_slug and program_slug:
            out[(company_slug, program_slug)] = program
    return out


def _query_display(config: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "sponsor",
        "sponsor_aliases",
        "intervention",
        "intervention_aliases",
        "condition",
        "condition_aliases",
        "query_terms",
        "term_aliases",
    ]
    out = {}
    for key in keys:
        value = config.get(key)
        if isinstance(value, list):
            out[key] = [str(item) for item in value if str(item).strip()]
        elif value:
            out[key] = [str(value)]
    return out


def _source_label(
    entry: SourceEntry,
    profiles: dict[str, dict[str, Any]],
    programs: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    profile = profiles.get(entry.company_slug, {})
    program = programs.get((entry.company_slug, entry.program_slug or ""), {})
    return {
        "source_id": entry.source_id,
        "company_slug": entry.company_slug,
        "company": profile.get("short_name") or profile.get("name") or entry.company_slug,
        "program_slug": entry.program_slug,
        "program": program.get("program") or entry.program_slug or "",
        "url": entry.url,
        "enabled": entry.enabled,
        "manual_review": entry.manual_review,
        "query": _query_display(entry.extractor_config),
    }


def _snapshot_files(source_id: str) -> list[Path]:
    source_dir = snapshots_dir() / source_id
    if not source_dir.exists():
        return []
    return sorted(source_dir.glob("*.json"))


def _load_snapshots(source_id: str) -> list[dict[str, Any]]:
    rows = []
    for path in _snapshot_files(source_id):
        payload = _read_json(path, {})
        if not isinstance(payload, dict):
            continue
        captured = payload.get("captured_at_utc") or ""
        rows.append(
            {
                "path": path,
                "captured_at_utc": captured,
                "captured_date": _date_part(captured),
                "run_id": payload.get("run_id", ""),
                "links": payload.get("links") or [],
            }
        )
    rows.sort(key=lambda row: (row["captured_at_utc"], str(row["path"])))
    return rows


def _nct_id(link: dict[str, Any]) -> str:
    extras = link.get("extras") or {}
    return str(extras.get("nct_id") or "").upper()


def _tracked_record(link: dict[str, Any]) -> dict[str, Any]:
    extras = link.get("extras") or {}
    return {
        "title": link.get("title") or extras.get("brief_title") or extras.get("official_title"),
        **{field: extras.get(field) for field, _label in TRACKED_FIELDS if field != "title"},
    }


def _record_hash(link: dict[str, Any]) -> str:
    extras = link.get("extras") or {}
    if extras.get("ctgov_record_hash"):
        return str(extras["ctgov_record_hash"])
    raw = json.dumps(_tracked_record(link), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _value_changed(before: Any, after: Any) -> bool:
    return before != after


def _field_changes(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    changes = []
    for field, label in TRACKED_FIELDS:
        before_value = before.get(field)
        after_value = after.get(field)
        if _value_changed(before_value, after_value):
            changes.append(
                {
                    "field": field,
                    "label": label,
                    "before": before_value,
                    "after": after_value,
                }
            )
    return changes


def _event_id(source_id: str, captured: str, nct_id: str, event_type: str) -> str:
    material = f"{source_id}|{captured}|{nct_id}|{event_type}"
    return hashlib.sha1(material.encode("utf-8")).hexdigest()[:16]


def _event(
    *,
    source: dict[str, Any],
    snapshot: dict[str, Any],
    link: dict[str, Any],
    event_type: str,
    changes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    extras = link.get("extras") or {}
    nct_id = _nct_id(link)
    detected_at = snapshot.get("captured_at_utc") or ""
    labels = {
        "new_trial": "New Trial",
        "removed_trial": "Removed Trial",
        "trial_updated": "Trial Updated",
    }
    return {
        "id": _event_id(source["source_id"], detected_at, nct_id, event_type),
        "event_type": event_type,
        "event_type_label": labels.get(event_type, event_type),
        "detected_at_utc": detected_at,
        "detected_date": snapshot.get("captured_date") or _date_part(detected_at),
        "source_id": source["source_id"],
        "company_slug": source["company_slug"],
        "company": source["company"],
        "program_slug": source.get("program_slug"),
        "program": source.get("program", ""),
        "nct_id": nct_id,
        "trial_title": link.get("title") or extras.get("brief_title") or "",
        "trial_url": link.get("url") or "",
        "overall_status": extras.get("overall_status"),
        "last_update_post_date": extras.get("last_update_post_date"),
        "has_results": extras.get("has_results"),
        "changed_fields": changes or [],
        "snapshot_path": _rel(snapshot.get("path")),
        "run_id": snapshot.get("run_id", ""),
    }


def _link_map(links: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out = {}
    for link in links:
        nct = _nct_id(link)
        if nct:
            out[nct] = link
    return out


def _source_events(source: dict[str, Any], snapshots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events = []
    prior: dict[str, dict[str, Any]] | None = None
    for snapshot in snapshots:
        current = _link_map(snapshot["links"])
        if prior is None:
            prior = current
            continue

        for nct, link in current.items():
            previous = prior.get(nct)
            if previous is None:
                events.append(
                    _event(source=source, snapshot=snapshot, link=link, event_type="new_trial")
                )
                continue
            if _record_hash(previous) == _record_hash(link):
                continue
            changes = _field_changes(_tracked_record(previous), _tracked_record(link))
            if not changes:
                changes = [
                    {
                        "field": "ctgov_record_hash",
                        "label": "Registry Record",
                        "before": _record_hash(previous),
                        "after": _record_hash(link),
                    }
                ]
            events.append(
                _event(
                    source=source,
                    snapshot=snapshot,
                    link=link,
                    event_type="trial_updated",
                    changes=changes,
                )
            )

        for nct, link in prior.items():
            if nct not in current:
                events.append(
                    _event(
                        source=source,
                        snapshot=snapshot,
                        link=link,
                        event_type="removed_trial",
                    )
                )
        prior = current
    return events


def _latest_trials(source: dict[str, Any], snapshot: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not snapshot:
        return []
    rows = []
    for link in snapshot.get("links") or []:
        extras = link.get("extras") or {}
        status_mod = _record_status_module(extras)
        enrollment_count = extras.get("enrollment_count")
        enrollment_type = extras.get("enrollment_type")
        rows.append(
            {
                "source_id": source["source_id"],
                "company": source["company"],
                "company_slug": source["company_slug"],
                "program": source.get("program", ""),
                "program_slug": source.get("program_slug"),
                "nct_id": _nct_id(link),
                "trial_title": link.get("title") or extras.get("brief_title") or "",
                "trial_url": link.get("url") or "",
                "overall_status": extras.get("overall_status"),
                "phase": extras.get("phase"),
                "has_results": extras.get("has_results"),
                "last_update_submit_date": extras.get("last_update_submit_date")
                or status_mod.get("lastUpdateSubmitDate"),
                "last_update_post_date": extras.get("last_update_post_date"),
                "last_update_post_type": _date_struct_type(status_mod, "lastUpdatePostDateStruct"),
                "status_verified_date": extras.get("status_verified_date")
                or status_mod.get("statusVerifiedDate"),
                "primary_completion_date": extras.get("primary_completion_date"),
                "primary_completion_type": _date_struct_type(
                    status_mod, "primaryCompletionDateStruct"
                ),
                "completion_date": extras.get("completion_date"),
                "completion_type": _date_struct_type(status_mod, "completionDateStruct"),
                "enrollment_count": enrollment_count,
                "enrollment_type": enrollment_type,
                "conditions": extras.get("conditions") or [],
                "interventions": extras.get("interventions") or [],
                "lead_sponsor": extras.get("lead_sponsor"),
            }
        )
    rows.sort(key=lambda row: (row.get("company") or "", row.get("program") or "", row["nct_id"]))
    return rows


def _merge_label(existing: str, value: str) -> str:
    labels = [item.strip() for item in existing.split(",") if item.strip()] if existing else []
    if value and value not in labels:
        labels.append(value)
    return ", ".join(labels)


def _dedupe_trials(trials: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_nct: dict[str, dict[str, Any]] = {}
    for trial in trials:
        nct_id = trial.get("nct_id")
        if not nct_id:
            continue
        existing = by_nct.get(nct_id)
        if existing is None:
            by_nct[nct_id] = dict(trial)
            continue
        existing["company"] = _merge_label(existing.get("company", ""), trial.get("company", ""))
        existing["program"] = _merge_label(existing.get("program", ""), trial.get("program", ""))
        existing["source_id"] = _merge_label(existing.get("source_id", ""), trial.get("source_id", ""))
        if (trial.get("last_update_post_date") or "") > (
            existing.get("last_update_post_date") or ""
        ):
            for key in (
                "trial_title",
                "trial_url",
                "overall_status",
                "phase",
                "has_results",
                "last_update_submit_date",
                "last_update_post_date",
                "last_update_post_type",
                "status_verified_date",
                "primary_completion_date",
                "primary_completion_type",
                "completion_date",
                "completion_type",
                "enrollment_count",
                "enrollment_type",
                "conditions",
                "interventions",
                "lead_sponsor",
            ):
                existing[key] = trial.get(key)
    rows = list(by_nct.values())
    rows.sort(
        key=lambda row: (
            row.get("company") or "",
            row.get("program") or "",
            row.get("nct_id") or "",
        )
    )
    return rows


def _event_map(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_nct: dict[str, dict[str, Any]] = {}
    for event in sorted(
        events,
        key=lambda row: (row.get("detected_at_utc") or "", row.get("id") or ""),
        reverse=True,
    ):
        nct_id = event.get("nct_id")
        if nct_id and nct_id not in by_nct:
            by_nct[nct_id] = event
    return by_nct


def _typed_date(date_text: str | None, date_type: str | None) -> str:
    if not date_text:
        return ""
    if date_type:
        return f"{date_text} ({date_type.lower()})"
    return date_text


def _trial_update_details(trial: dict[str, Any], event: dict[str, Any] | None) -> list[dict[str, str]]:
    posted = _typed_date(trial.get("last_update_post_date"), trial.get("last_update_post_type"))
    submitted = trial.get("last_update_submit_date")
    details: list[dict[str, str]] = []
    if posted:
        value = f"Posted {posted}"
        if submitted:
            value += f"; submitted {submitted}"
        details.append({"label": "CT.gov update", "value": value})
    if trial.get("status_verified_date"):
        details.append(
            {
                "label": "Status",
                "value": (
                    f"{_display_value(trial.get('overall_status'))}; "
                    f"verified {trial.get('status_verified_date')}"
                ),
            }
        )
    completion_parts = [
        _typed_date(trial.get("primary_completion_date"), trial.get("primary_completion_type")),
        _typed_date(trial.get("completion_date"), trial.get("completion_type")),
    ]
    completion_parts = [part for part in completion_parts if part]
    if completion_parts:
        details.append(
            {
                "label": "Completion dates",
                "value": f"Primary {completion_parts[0]}"
                + (f"; final {completion_parts[1]}" if len(completion_parts) > 1 else ""),
            }
        )
    if trial.get("enrollment_count") is not None:
        enrollment = str(trial.get("enrollment_count"))
        if trial.get("enrollment_type"):
            enrollment += f" ({str(trial.get('enrollment_type')).lower()})"
        details.append({"label": "Enrollment", "value": enrollment})
    if event and event.get("changed_fields"):
        details.append(
            {
                "label": "Snapshot comparison",
                "value": "; ".join(
                    _field_change_sentence(change)
                    for change in event.get("changed_fields", [])[:4]
                ),
            }
        )
    else:
        details.append(
            {
                "label": "Snapshot comparison",
                "value": (
                    "No prior retained CT.gov snapshot is available for field-level "
                    "delta review yet."
                ),
            }
        )
    return details


def _most_recent_registry_updates(
    trials: list[dict[str, Any]], events: list[dict[str, Any]]
) -> dict[str, Any]:
    dates = [trial.get("last_update_post_date") for trial in trials if trial.get("last_update_post_date")]
    if not dates:
        return {"date": "", "trials": []}
    latest_date = max(dates)
    events_by_nct = _event_map(events)
    rows = []
    for trial in trials:
        if trial.get("last_update_post_date") != latest_date:
            continue
        row = dict(trial)
        row["update_details"] = _trial_update_details(
            row, events_by_nct.get(row.get("nct_id", ""))
        )
        rows.append(row)
    rows.sort(key=lambda row: (row.get("company") or "", row.get("program") or "", row["nct_id"]))
    return {"date": latest_date, "trials": rows}


def _weekly_buckets(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        date_text = event.get("detected_date")
        if date_text:
            buckets[_week_start(date_text)].append(event)
    rows = []
    for week_start, items in buckets.items():
        counts: dict[str, int] = defaultdict(int)
        for item in items:
            counts[item["event_type"]] += 1
        rows.append(
            {
                "week_start": week_start,
                "week_end": _week_end(week_start),
                "update_count": len(items),
                "new_trials": counts.get("new_trial", 0),
                "updated_trials": counts.get("trial_updated", 0),
                "removed_trials": counts.get("removed_trial", 0),
            }
        )
    rows.sort(key=lambda row: row["week_start"], reverse=True)
    return rows


def build() -> dict[str, Any]:
    wl = load_watchlist()
    profiles = _profile_lookup()
    programs = _program_lookup()
    ctgov_entries = [
        entry
        for entry in wl.sources
        if entry.source_type == "clinicaltrials_v2_api" and entry.enabled and not entry.manual_review
    ]

    sources = []
    events = []
    trials = []
    latest_capture_at = ""
    for entry in ctgov_entries:
        source = _source_label(entry, profiles, programs)
        snapshots = _load_snapshots(entry.source_id)
        latest = snapshots[-1] if snapshots else None
        if latest and latest.get("captured_at_utc", "") > latest_capture_at:
            latest_capture_at = latest.get("captured_at_utc", "")
        source["snapshot_count"] = len(snapshots)
        source["latest_snapshot_at"] = latest.get("captured_at_utc") if latest else ""
        source["latest_link_count"] = len(latest.get("links") or []) if latest else 0
        source["latest_snapshot_path"] = _rel(latest.get("path")) if latest else ""
        sources.append(source)
        events.extend(_source_events(source, snapshots))
        trials.extend(_latest_trials(source, latest))

    events.sort(key=lambda row: (row.get("detected_at_utc") or "", row["id"]), reverse=True)
    trials = _dedupe_trials(trials)
    most_recent = _most_recent_registry_updates(trials, events)
    weeks = _weekly_buckets(events)
    recent_cutoff = dt.date.today() - dt.timedelta(days=7)
    recent_events = [
        event
        for event in events
        if event.get("detected_date")
        and dt.date.fromisoformat(event["detected_date"]) >= recent_cutoff
    ]

    return {
        "generated_at_utc": _iso_now(),
        "summary": {
            "monitored_sources": len(sources),
            "sources_with_snapshots": sum(1 for source in sources if source["snapshot_count"] > 0),
            "tracked_trials": len(trials),
            "updates_total": len(events),
            "updates_last_7_days": len(recent_events),
            "weekly_buckets": len(weeks),
            "latest_capture_at": latest_capture_at,
            "most_recent_registry_update_date": most_recent["date"],
        },
        "sources": sources,
        "updates": events,
        "weekly_buckets": weeks,
        "most_recent_registry_updates": most_recent,
        "latest_trials": trials,
    }


def export() -> dict[str, Any]:
    payload = build()
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=False), encoding="utf-8")
    return {"path": _rel(OUTPUT_PATH), "summary": payload["summary"]}
