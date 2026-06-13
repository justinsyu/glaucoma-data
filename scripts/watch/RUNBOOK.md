# retina-watch operator runbook

Deterministic source watcher with an append-only SQLite audit trail, a
Dagster orchestration layer, and a Jekyll-rendered audit page. This runbook
covers daily operation, the tier system, common failure recipes, and the
post-sweep manual steps a worklist requires.

The watcher does not write to the published manifest. Every discovered
document arrives as a row in the `candidates` table tagged `decision=new`;
a separate triage step (AI or human) decides whether each candidate is
added to `_data/company_documents.json`.

## 1. First-time setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e "scripts/watch[test,js,dagster,sentry]"
python -m playwright install chromium

retina-watch init-db
retina-watch bootstrap-watchlist
```

The `init-db` step creates `artifacts/watch/observability.sqlite` with WAL
mode and the five append-only tables (`runs`, `fetch_events`, `snapshots`,
`candidates`, `triage_decisions`).

The `bootstrap-watchlist` step generates `_data/source_watchlist.yml` in two
passes: a conservative auto-classification from the existing manifest, then
a hand-tuned recipe layer that applies the operationally-proven patterns
(Bayer Akamai, 4DMT pipeline, Clearside title filter, etc.). Pass
`--skip-recipes` if you want only the auto-classified output.

## 2. Day-to-day commands

```powershell
# Run the full pipeline against every enabled source.
retina-watch run --trigger=weekly

# Run a subset.
retina-watch run --source-type=clinicaltrials_v2_api
retina-watch run --source-id=bayer-congresspublications-hcp

# Operator queries.
retina-watch show-runs --limit 10
retina-watch show-source <source_id>
retina-watch show-candidates --decision=new

# Health check (silent sources, latency drift, fetch errors).
retina-watch health

# Refresh the Jekyll dashboard JSON.
retina-watch export-audit
```

## 3. Dagster UI

The CLI is sufficient for operators who think in shells. Dagster is the
visual surface on top: a graph of the four assets, per-source partition
history, schedules, asset checks, and a structured run log.

```powershell
$env:DAGSTER_HOME = "$pwd\.dagster_home"
.\.venv\Scripts\dagster.exe dev -m retina_watch.dagster_defs --port 3333
# then open http://localhost:3333
```

The `watcher_weekly_monday_09utc` schedule fires the full pipeline every
Monday at 09:00 UTC. The schedule is off by default; flip the toggle in the
Automation tab to start it.

## 4. The tier system

Every watchlist entry carries a `tier` field that sets operator expectation.
Behavior is not branched on tier; the tier is documentation.

| Tier | Meaning | Expected runtime | Example |
|---|---|---|---|
| 1 | Plain HTTP, server-rendered HTML PDF list. Near-100% success. | seconds | 4DMT, Clearside, REGENXBIO |
| 2 | Browser-required (Akamai or one-shot HCP modal). Cookies cleared once and persisted. | tens of seconds | Bayer, Ocular Therapeutix |
| 3 | Discovery-only. Per-PDF attestation forms make automated download impossible; the watcher emits rows to a worklist instead. | seconds | Regeneron HCP portal, Roche `/restricted/` |
| 4 | PubMed / PMC fallback. No corporate publication library. Query by drug name + sponsor affiliation. | seconds | Amgen biosimilar, Novartis Beovu (legacy) |
| 5 | Skipped by config. Recorded for visibility; no fetch performed. | n/a | Bausch + Lomb |

## 5. Failure recipes

### HTTP 403 from a Tier 1 source

Some sponsors flip on bot mitigation between runs. If a source that used to
return 200 starts returning 403, escalate it to Tier 2 by changing the
`source_type` to `playwright_hcp` and adding a recipe in `recipes.py`.

```yaml
source_type: playwright_hcp
extractor_config:
  bot_clear_seconds: 5
  wait_until: load
  timeout_ms: 30000
  # If an HCP modal also appears, add:
  hcp_action: "click:text=Continue"
```

### A source returns zero links and `health` reports `silent`

The page DOM probably changed. Three checks in order:

1. Open the URL in a real browser. Has the page restructured?
2. Look at the latest snapshot file under `artifacts/watch/snapshots/<source_id>/`. Compare to the prior snapshot.
3. Run a one-source diagnosis: `retina-watch run --source-id=<id> --log-level=DEBUG`.

Most fixes are a new `link_selector` or `url_must_match` in
`extractor_config`. Persistent fixes belong in `recipes.py`, not the YAML,
so they survive future `bootstrap-watchlist` regenerations.

### `playwright_hcp` returns `js_render_returned_none`

The HCP click selector did not match. The watcher logs the failure and
continues with whatever HTML it has, so the page is often partially
extracted. Three common causes:

1. Selector changed: open the page, copy the new selector, update the recipe.
2. Bot challenge took longer than `bot_clear_seconds`: raise to 10 or 15.
3. Cookies persisted from a prior run: clear `.dagster_home` and Playwright cache.

### PubMed returns zero hits

The MeSH-filtered query is too narrow. Two adjustments:

1. Add an intervention alias in `bootstrap.py`'s `PROGRAM_INTERVENTION_TERMS`.
2. Widen the MeSH clause, or drop the MeSH restriction entirely for drugs
   that are not yet indexed under any retinal heading.

Set `NCBI_API_KEY` in the environment for higher rate limits.

### Worklist file is growing unbounded

Each Tier 3 source can append the same items to the worklist on every run,
because there is no dedupe at write time. Two mitigations:

1. The triage layer is supposed to consume the worklist; review and remove
   resolved rows during the manual retrieval step (see section 7).
2. The worklist file is plain markdown, edit it freely.

A future iteration will key worklist rows by canonical URL and skip duplicates.

### Dagster shows the schedule as off

Open Automation, find `watcher_weekly_monday_09utc`, flip the toggle. The
schedule state is persisted in the Dagster instance database under
`.dagster_home`.

## 6. Adding a new sponsor

1. Add the company to `_data/company_profiles.json` and (if new programs)
   `_data/company_programs.json`. The manifest is the truth, the watchlist
   reads from it.
2. Run `retina-watch bootstrap-watchlist`. Conservative entries appear in
   the YAML; CT.gov and PubMed sources are seeded per program.
3. Discover the publication URL by hand. Open the company's IR / MedInfo
   site, find the page that lists posters/manuscripts, copy the URL.
4. If the page is JavaScript-rendered or behind an HCP modal, add a recipe
   in `scripts/watch/src/retina_watch/recipes.py` (a few lines of Python).
   If it is plain HTML, just edit the YAML to set the right URL and
   `source_type: html_pdf_links`.
5. Run a one-source dry-run: `retina-watch run --source-id=<id>`. Inspect
   the snapshot. Iterate on `extractor_config` / `title_filter` until the
   link count looks right.
6. Re-run `bootstrap-watchlist` so the recipe layer applies your changes
   atomically. The YAML is now reproducible from code.

## 7. Manual retrieval from a worklist

```markdown
# Worklist - items requiring manual retrieval
- [2026-05-27] **Faricimab in nAMD: PULSAR 2-Year Results**
    - reason: discovery_only source: manual HCP retrieval
    - url: https://www.regeneronmedical.com/.../faricimab-pulsar-2yr.pdf
    - source_page: https://www.regeneronmedical.com/search-results?type=Congresses&q=PULSAR
    - source_id: `regeneron-eylea-hd-www-regeneronmedical-com`
    - run_id: `5dbe9b37-cd68-46df-8382-c25354fd9986`
    - suggested_dest: `companies/regeneron/eylea_hd/presentations_posters/`
```

To resolve a row:

1. Open the URL in a logged-in HCP browser session.
2. Download the PDF.
3. Move it to `suggested_dest` with a slugified filename.
4. Delete the row from the worklist file (or leave it as historical record).
5. Eventually the AI triage layer will consume the worklist directly and
   open a PR for each item; for now this is the manual loop.

## 8. Audit trail

Every audit query joins on `run_id`. The interesting joins:

* "Which fetch produced this published document?"
  `candidates -> snapshots -> fetch_events` (all by run_id and source_id).
* "Which sources have been silent N runs in a row?"
  `retina-watch health` or query `snapshots` directly.
* "What did we attempt last Monday morning?"
  `SELECT * FROM runs WHERE started_at > date('now','-7 days')` plus the
  Dagster Runs tab for the same window.

The SQLite file lives at `artifacts/watch/observability.sqlite`. It is
gitignored. Snapshot JSON files under `artifacts/watch/snapshots/` are
committable history if you want git as a second time machine.

## 9. Non-goals

The watcher does not parse PDF content, generate markdown extracts, or
write to the manifest. Those steps live in `llamaparse.py` and in the
triage layer (not yet shipped). The watcher only answers "what document
URLs exist today that did not exist on the last cycle, and which company /
program / indication do they belong to."
