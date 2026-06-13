"""Sweep entrypoint: `python -m scripts.sweep [--companies ...] [--tier ...] [--dry-run]`.

Exit codes:
  0  success (zero unhandled errors, even if individual companies failed)
  1  config error
  2  one or more source-level errors with --strict
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import requests

from .config import ConfigError, Source, load_config
from .dedup import Candidate, deduplicate
from .downloader import download_pdf
from .fetchers import FetchError, fetch_candidates, playwright_download
from .inventory import scan
from .report import CompanyRun, SweepReport, append_worklist


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m scripts.sweep")
    parser.add_argument("--config", default="scripts/sweep/sources.yaml",
                        help="Path to sources.yaml")
    parser.add_argument("--repo-root", default=".",
                        help="Repository root (parent of companies/)")
    parser.add_argument("--companies", default="",
                        help="Comma-separated list of company ids to sweep (default: all)")
    parser.add_argument("--tier", type=int, action="append", default=[],
                        help="Restrict to this tier; can be repeated (e.g. --tier 1 --tier 2)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Discover candidates but do not download")
    parser.add_argument("--strict", action="store_true",
                        help="Exit nonzero if any source raises an error")
    parser.add_argument("--runs-dir", default="scripts/sweep/runs",
                        help="Where to write sweep-<ts>.{json,md}")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    _setup_logging(args.verbose)
    log = logging.getLogger("sweep")

    repo_root = Path(args.repo_root).resolve()
    try:
        config = load_config(args.config)
    except ConfigError as exc:
        log.error("Config error: %s", exc)
        return 1

    target_ids: set[str] | None = None
    if args.companies:
        target_ids = {s.strip() for s in args.companies.split(",") if s.strip()}
    target_tiers: set[int] = set(args.tier) if args.tier else set()

    report = SweepReport.new(config_path=args.config, repo_root=str(repo_root))
    session = requests.Session()
    had_errors = False

    for company in config.companies:
        if target_ids is not None and company.id not in target_ids:
            continue
        if target_tiers and company.tier not in target_tiers:
            continue

        run = CompanyRun(company_id=company.id, name=company.name, tier=company.tier)
        report.companies.append(run)

        if company.tier == 5:
            run.errors.append("tier=5 (skipped by config); no sweep performed")
            run.sources_visited.append({"url": "(skip)", "status": "skipped"})
            continue

        inventory = scan(repo_root / company.folder, company.id, hash_bytes=False)
        log.info("[%s] inventory: %d existing PDFs, %d existing markdown records",
                 company.id, len(inventory.pdf_slugs), len(inventory.md_slugs))

        all_candidates: list[tuple[Source, Candidate]] = []
        for src in company.sources:
            if src.kind == "skip":
                run.sources_visited.append({"url": "(skip)", "status": f"skipped: {src.reason.splitlines()[0]}"})
                continue
            try:
                candidates = fetch_candidates(src, config.defaults, session)
                run.sources_visited.append({"url": src.url or f"pubmed:{','.join(src.terms[:2])}",
                                            "status": f"ok ({len(candidates)} candidates)"})
                for c in candidates:
                    all_candidates.append((src, c))
            except FetchError as exc:
                run.errors.append(f"{src.url or src.kind}: {exc}")
                run.sources_visited.append({"url": src.url or src.kind, "status": f"error: {exc}"})
                log.warning("[%s] fetch error: %s", company.id, exc)
                had_errors = True
            except Exception as exc:  # noqa: BLE001
                run.errors.append(f"{src.url or src.kind}: unexpected {type(exc).__name__}: {exc}")
                run.sources_visited.append({"url": src.url or src.kind, "status": f"error: {exc}"})
                log.exception("[%s] unexpected error in fetch", company.id)
                had_errors = True

        # Rehash on-disk PDFs once, so the downloader can detect identical bytes
        # across cross-listed sponsors.
        inventory_with_hashes = scan(repo_root / company.folder, company.id, hash_bytes=True) if all_candidates else inventory

        run.candidates_found = len(all_candidates)
        flat_candidates = [c for _, c in all_candidates]
        _, new_candidates = deduplicate(flat_candidates, inventory_with_hashes)
        run.candidates_new = len(new_candidates)
        run.candidates_already_archived = len(flat_candidates) - len(new_candidates)
        new_set = {c.url for c in new_candidates}

        if args.dry_run:
            for src, c in all_candidates:
                if c.url in new_set:
                    run.add_worklist_item(c, "dry-run: would download")
            continue

        for src, c in all_candidates:
            if c.url not in new_set:
                continue
            dest_dir = repo_root / (c.suggested_dest or src.dest)

            if src.discovery_only:
                run.add_worklist_item(c, "discovery_only source: manual HCP retrieval")
                continue

            try:
                if src.fetcher == "playwright_hcp":
                    # Use Playwright for the download too, to inherit cookies.
                    data = playwright_download(
                        c, dest_dir, config.defaults,
                        referer=src.referer or src.url,
                        extra_headers=src.extra_headers,
                    )
                    if data[:4] != b"%PDF":
                        run.add_worklist_item(c, f"invalid_pdf (gated PDF): first bytes {data[:16]!r}")
                        continue
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    safe = c.basename.replace(" ", "_") if c.basename.endswith(".pdf") else f"{c.slug}.pdf"
                    final_path = dest_dir / safe
                    if final_path.exists():
                        run.downloads.append({
                            "status": "duplicate_slug", "url": c.url, "title": c.title,
                            "dest_path": str(final_path), "bytes": 0, "sha1": "", "error": "exists",
                        })
                        continue
                    final_path.write_bytes(data)
                    run.downloads.append({
                        "status": "downloaded", "url": c.url, "title": c.title,
                        "dest_path": str(final_path), "bytes": len(data),
                        "sha1": "", "error": "",
                    })
                else:
                    result = download_pdf(
                        c, dest_dir, config.defaults, inventory_with_hashes, session,
                        extra_headers=src.extra_headers,
                    )
                    run.add_download(result)
                    if result.status == "invalid_pdf":
                        run.add_worklist_item(c, f"invalid_pdf: {result.error}")
            except Exception as exc:  # noqa: BLE001
                log.exception("[%s] download error %s", company.id, c.url)
                run.downloads.append({
                    "status": "exception", "url": c.url, "title": c.title,
                    "dest_path": None, "bytes": 0, "sha1": "", "error": str(exc),
                })
                had_errors = True

        # Flush worklist entries to the company's running worklist file.
        worklist_paths: dict[str, list[dict]] = {}
        for src in company.sources:
            if src.dest_worklist:
                worklist_paths[src.dest_worklist] = []
        for w in run.worklist_items:
            # Heuristic: write to the first source that has a dest_worklist.
            for src in company.sources:
                if src.dest_worklist:
                    worklist_paths.setdefault(src.dest_worklist, []).append(w)
                    break
        for p, items in worklist_paths.items():
            append_worklist(repo_root / p, items)

    report.finalize()
    json_path, md_path = report.write(Path(args.runs_dir))
    log.info("Wrote run report: %s and %s", json_path, md_path)

    if args.strict and had_errors:
        return 2
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
