"""
Emit a JSON manifest of every document that still needs an infographic.

Each manifest record carries everything a subagent needs to write a single
infographic page: source markdown path, output path/permalink, doc URL,
title and full metadata. Records for documents whose infographic file
already exists are skipped.

Usage:
    python scripts/build_infographic_manifest.py > scripts/infographic_manifest.json
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = json.loads((ROOT / "_data" / "company_documents.json").read_text(encoding="utf-8"))
INFOGRAPHICS_DIR = ROOT / "infographics"

def url_slug(url: str) -> str:
    # /company-documents/<slug>/  ->  <slug>
    parts = [p for p in url.split("/") if p]
    if len(parts) >= 2:
        return parts[1]
    return parts[-1] if parts else ""

def source_md_path(rec: dict) -> str:
    return (
        rec.get("markdown_file_url")
        or rec.get("local_file_url")
        or ""
    ).lstrip("/")

def main():
    out = []
    skipped = 0
    no_md = 0
    for d in DOCS:
        slug = url_slug(d.get("url", ""))
        if not slug:
            continue
        ig_file = INFOGRAPHICS_DIR / f"{slug}.md"
        if ig_file.exists():
            skipped += 1
            continue
        smd = source_md_path(d)
        if not smd or not smd.endswith(".md"):
            no_md += 1
            continue
        smd_abs = (ROOT / smd)
        if not smd_abs.exists():
            no_md += 1
            continue
        out.append({
            "slug": slug,
            "source_md": smd,
            "output_file": f"infographics/{slug}.md",
            "permalink": f"/infographics/{slug}/",
            "doc_url": d.get("url", ""),
            "doc_title": d.get("title", "").replace('"', "'"),
            "company": d.get("company", ""),
            "company_slug": d.get("company_slug", ""),
            "program": d.get("program", ""),
            "indication": d.get("indication", ""),
            "year": d.get("year", ""),
            "conference": d.get("conference", ""),
            "document_type": d.get("document_type", ""),
            "pdf_url": d.get("source_url", "") if (d.get("source_url", "") or "").endswith(".pdf") else "",
        })
    print(json.dumps({
        "total_company_documents": len(DOCS),
        "already_done": skipped,
        "missing_markdown": no_md,
        "to_generate": len(out),
        "records": out,
    }, indent=2))


if __name__ == "__main__":
    main()
