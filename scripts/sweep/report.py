"""Per-run reporting: structured JSON + human-readable Markdown."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .dedup import Candidate
from .downloader import DownloadResult


@dataclass
class CompanyRun:
    company_id: str
    name: str
    tier: int
    sources_visited: list[dict] = field(default_factory=list)
    candidates_found: int = 0
    candidates_new: int = 0
    candidates_already_archived: int = 0
    downloads: list[dict] = field(default_factory=list)
    worklist_items: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def add_download(self, result: DownloadResult) -> None:
        self.downloads.append({
            "status": result.status,
            "url": result.candidate.url,
            "title": result.candidate.title,
            "dest_path": str(result.dest_path) if result.dest_path else None,
            "bytes": result.bytes_written,
            "sha1": result.sha1,
            "error": result.error,
        })

    def add_worklist_item(self, candidate: Candidate, reason: str) -> None:
        self.worklist_items.append({
            "url": candidate.url,
            "title": candidate.title,
            "source_url": candidate.source_url,
            "suggested_dest": candidate.suggested_dest,
            "reason": reason,
        })


@dataclass
class SweepReport:
    started_at: str
    ended_at: str = ""
    config_path: str = ""
    repo_root: str = ""
    companies: list[CompanyRun] = field(default_factory=list)

    @classmethod
    def new(cls, config_path: str, repo_root: str) -> "SweepReport":
        return cls(
            started_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            config_path=config_path,
            repo_root=repo_root,
        )

    def finalize(self) -> None:
        self.ended_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    def write(self, runs_dir: Path) -> tuple[Path, Path]:
        runs_dir.mkdir(parents=True, exist_ok=True)
        ts = self.started_at.replace(":", "-")
        json_path = runs_dir / f"sweep-{ts}.json"
        md_path = runs_dir / f"sweep-{ts}.md"

        json_path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        md_path.write_text(self._render_markdown(), encoding="utf-8")
        return json_path, md_path

    def _render_markdown(self) -> str:
        lines = [
            f"# Sweep Report: {self.started_at}",
            "",
            f"- Started: `{self.started_at}`",
            f"- Ended:   `{self.ended_at}`",
            f"- Config:  `{self.config_path}`",
            "",
            "## Summary",
            "",
            "| Company | Tier | Found | New | Downloaded | Worklist | Errors |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
        for c in self.companies:
            downloaded = sum(1 for d in c.downloads if d["status"] == "downloaded")
            errors = sum(1 for d in c.downloads if d["status"] in {"http_error", "timeout", "invalid_pdf"})
            errors += len(c.errors)
            lines.append(
                f"| {c.name} | {c.tier} | {c.candidates_found} | {c.candidates_new} | "
                f"{downloaded} | {len(c.worklist_items)} | {errors} |"
            )
        lines.append("")

        for c in self.companies:
            downloaded = [d for d in c.downloads if d["status"] == "downloaded"]
            errors_dl = [d for d in c.downloads if d["status"] not in {"downloaded", "duplicate_hash", "duplicate_slug"}]
            if not (downloaded or errors_dl or c.worklist_items or c.errors):
                continue
            lines.append(f"### {c.name} (tier {c.tier})")
            for s in c.sources_visited:
                lines.append(f"- Source: `{s['url']}`: {s['status']}")
            if downloaded:
                lines.append("")
                lines.append("**Downloaded:**")
                for d in downloaded:
                    lines.append(f"- `{d['dest_path']}` ({d['bytes']} bytes): {d['title']}")
            if errors_dl:
                lines.append("")
                lines.append("**Failed downloads:**")
                for d in errors_dl:
                    lines.append(f"- {d['status']}: {d['url']}: {d['error']}")
            if c.worklist_items:
                lines.append("")
                lines.append("**Worklist (manual retrieval required):**")
                for w in c.worklist_items:
                    lines.append(f"- {w['title']} ({w['reason']}): {w['url']}")
            if c.errors:
                lines.append("")
                lines.append("**Source errors:**")
                for e in c.errors:
                    lines.append(f"- {e}")
            lines.append("")
        return "\n".join(lines)


def append_worklist(path: Path, items: list[dict]) -> None:
    """Append worklist entries to a per-sponsor running worklist file."""
    if not items:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(
            "# Worklist: items requiring manual retrieval\n\n"
            "Each line below was discovered by the sweep but could not be\n"
            "downloaded automatically (HCP gating, publisher paywall, or\n"
            "non-PDF landing page). Retrieve manually and drop the PDF into\n"
            "the suggested_dest folder.\n\n",
            encoding="utf-8",
        )
    with path.open("a", encoding="utf-8") as f:
        for item in items:
            f.write(
                f"- [{datetime.now(timezone.utc).date()}] **{item['title']}**\n"
                f"    - reason: {item['reason']}\n"
                f"    - url: {item['url']}\n"
                f"    - source_page: {item['source_url']}\n"
                f"    - suggested_dest: `{item['suggested_dest']}`\n"
            )
