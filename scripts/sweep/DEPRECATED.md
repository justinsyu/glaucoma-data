# scripts/sweep is retired

This tree has been retired in favor of [`scripts/watch/`](../watch/), which now
incorporates every operationally proven pattern that sweep introduced:

| Sweep pattern | Where it lives in watch |
|---|---|
| `playwright_hcp` Akamai + HCP click flow | `scripts/watch/src/glaucoma_watch/extractors/playwright_hcp.py` |
| `playwright_loadmore` Load-More clicker | `scripts/watch/src/glaucoma_watch/extractors/playwright_loadmore.py` |
| Per-source `title_filter` regex | `SourceEntry.title_filter` + `scripts/watch/src/glaucoma_watch/routing.py` |
| `dest_router` / `title_router` rules | `SourceEntry.dest_router` / `title_router` + `routing.py` |
| Tier 1-5 classification | `SourceEntry.tier` (see `scripts/watch/RUNBOOK.md` section 4) |
| `discovery_only` + worklist files | `SourceEntry.discovery_only` + `SourceEntry.dest_worklist` + `worklist.py` |
| `_worklist_pending_*.md` convention | `worklist.py` emits the same format |
| `RUNBOOK.md` | `scripts/watch/RUNBOOK.md` |
| Bayer / 4DMT / Clearside / Adverum / EyePoint / Ocular / REGENXBIO / Regeneron / Roche recipes | `scripts/watch/src/glaucoma_watch/recipes.py` |
| 4DMT `/pipeline/` URL (replaces broken `/publications/`) | applied via `recipes.py` -> watchlist |
| Bayer Akamai 403 finding (May 2026 WAF hardening) | Bayer recipe is now Tier 3 / `discovery_only` with the Akamai click flow kept for the day the WAF relaxes |

What watch adds on top of what sweep provided:

* **SQLite audit DB** (`runs`, `fetch_events`, `snapshots`, `candidates`, `triage_decisions`) for SQL-queryable history.
* **Dagster orchestration** with per-source dynamic partitions, weekly schedule, asset checks.
* **robots.txt compliance** + per-host token-bucket rate limit.
* **ClinicalTrials.gov v2 + PubMed E-utilities** structured-API drivers.
* **Five-tier dedupe cascade** against the existing manifest (URL exact, canonical, DOI, NCT, PMID, title fingerprint).
* **Tests + GitHub Actions CI** (28 unit tests as of the merge).
* **Health monitoring** (silent source detection, latency drift, fetch error rates).

What is intentionally not yet built (carried over from sweep's open backlog):

* PDF byte download for Tier 2 sources (sweep had `playwright_download`; watch's pipeline only discovers links today). This is the next layer: once a candidate is triaged as accepted, a downloader pulls the PDF using the cookies the `playwright_hcp` driver already captures.
* AI triage layer that consumes `candidates` and emits `triage_decisions`.

This tree is kept in the repo as archival reference. Do not run it; it has no
access to the new audit DB, schedule, or recipes. Future operational changes
go in `scripts/watch/`.

For day-to-day operation, see `scripts/watch/RUNBOOK.md`.
