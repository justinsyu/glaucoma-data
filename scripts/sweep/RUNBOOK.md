# Retina Data Archive Sweep: Operator Runbook

This runbook covers the scheduled publication/congress sweep that keeps `companies/` in sync with each sponsor's public publication library. It is the operational complement to `sources.yaml`, which is the single source of truth for what gets fetched.

---

## 1. What the sweep does

The sweep performs five steps for each company listed in `sources.yaml`:

1. **Scan inventory.** Walk `companies/<sponsor>/` to build the set of currently archived PDFs and parsed markdown records.
2. **Fetch source pages.** Hit every configured URL using the per-source fetcher (plain HTTP, Playwright with "Load More", or Playwright with HCP/Akamai clearance) or query PubMed E-Utilities.
3. **Extract candidates.** Parse the rendered HTML for `<a>` tags matching the source's `link_pattern` and `title_filter`. PubMed sources convert each PMID to either a PMC OA PDF URL or a PubMed landing-page URL.
4. **Deduplicate.** Discard candidates whose URL-decoded basename slug already matches an inventory item.
5. **Download.** Atomically fetch each new candidate, verify the `%PDF` magic header, dedupe by SHA-1, and write to the per-source `dest` (or `dest_router`-selected) folder. Failed downloads and discovery-only items are appended to per-sponsor worklist files for manual retrieval.

Every run produces two artifacts in `scripts/sweep/runs/`:

- `sweep-<ISO timestamp>.json`: machine-readable, full per-source detail.
- `sweep-<ISO timestamp>.md`: human-readable summary table plus per-company breakdown.

These files are append-only; the sweep never modifies past runs.

---

## 2. First-time setup

```powershell
# From the repo root.
python -m pip install -r scripts/sweep/requirements.txt
python -m playwright install chromium
```

Validate the config without doing any network work:

```powershell
python -m scripts.sweep.smoke
```

The smoke test parses `sources.yaml`, prints a per-company table, and warns if any destination folder is missing.

---

## 3. Running the sweep

### Full sweep (every company, all tiers)

```powershell
python -m scripts.sweep
```

### Subset

```powershell
# Only the Tier 1 (plain-HTTP) companies.
python -m scripts.sweep --tier 1

# Specific companies.
python -m scripts.sweep --companies adverum,clearside_biomedical

# Dry run (no downloads, just discovery and worklist generation).
python -m scripts.sweep --dry-run
```

### CLI flags

| Flag | Purpose |
|---|---|
| `--config PATH` | Use an alternate config file. |
| `--repo-root PATH` | Run against a different working tree (default `.`). |
| `--companies ID,ID` | Restrict to specific company ids. |
| `--tier N` | Restrict to a tier; repeatable. |
| `--dry-run` | Discover candidates but skip downloads; write a worklist as if every new item required manual retrieval. |
| `--strict` | Exit code 2 if any source raised an error. Default is exit 0 even on partial failures. |
| `--runs-dir PATH` | Write run reports to a different folder. |
| `-v / --verbose` | Debug logging. |

---

## 4. Scheduling

### Windows Task Scheduler

Create a weekly task with action:

```
Program/script: powershell.exe
Arguments:      -NoProfile -Command "cd C:\Users\Justin\Desktop\retina-data; python -m scripts.sweep --strict 2>&1 | Tee-Object -FilePath scripts\sweep\runs\last-stderr.log"
Start in:       C:\Users\Justin\Desktop\retina-data
```

### Cron (WSL or another Unix host)

```cron
# Mondays at 06:00 local time.
0 6 * * 1 cd /path/to/retina-data && python -m scripts.sweep --strict >> scripts/sweep/runs/last-stderr.log 2>&1
```

### GitHub Actions

A workflow that runs daily and opens a pull request when new PDFs land:

```yaml
name: weekly-sweep
on:
  schedule:
    - cron: "0 6 * * 1"   # Mondays 06:00 UTC
  workflow_dispatch:
jobs:
  sweep:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r scripts/sweep/requirements.txt
      - run: python -m playwright install --with-deps chromium
      - run: python -m scripts.sweep --tier 1 --tier 2
      - uses: peter-evans/create-pull-request@v6
        with:
          commit-message: "chore(sweep): add new sponsor publications"
          branch: sweep/auto
          title: "Weekly sweep results"
          body-path: scripts/sweep/runs/sweep-*.md
```

Note: Tier 4 PubMed sweeps can run in GitHub Actions; Tier 3 discovery-only sweeps for Regeneron and Roche/Genentech will only emit worklist entries, never downloads. Bayer Tier 2 requires Playwright and works in Actions.

---

## 5. Tier-by-tier expectations

Every company in `sources.yaml` carries a `tier:` number. Tier sets the operator expectation, not just the fetcher choice.

### Tier 1: Plain HTTP

Companies: 4D Molecular Therapeutics, Adverum, Clearside Biomedical, EyePoint Pharmaceuticals, REGENXBIO/AbbVie.

These publish PDFs at stable, server-rendered URLs. Expect near-100% download success per run. If a Tier 1 source starts failing, the first thing to check is whether the company restructured its site (see "Failure recipes" below).

### Tier 2: One-shot browser session

Companies: Bayer, Ocular Therapeutix.

The PDFs themselves are direct, but the index page sits behind Akamai/Cloudflare bot mitigation or a strict header policy. The fetcher uses Playwright to clear the gate once, then either replays the cookies via `playwright_download` (Bayer) or sends a per-PDF fetch with explicit `Accept` + `Referer` headers (Ocular Therapeutix). Expect near-100% download success but slower runs (5–10 minutes per company).

### Tier 3: Discovery only

Companies: Regeneron, Roche/Genentech.

The sweep can detect new posters but cannot bypass the per-document HCP attestation flow that gates the actual PDFs (regeneronmedical.com binds the download to a JS callback; medically.gene.com mixes `/unrestricted/` and `/restricted/` paths). New items are written to per-sponsor `_worklist_pending_hcp.md` files. Operator does the manual retrieval from an HCP-attested browser, drops PDFs into the suggested folder, and removes the worklist entry.

### Tier 4: PubMed/PMC fallback

Companies: Amgen, Novartis, Sandoz, Formycon/Klinge, Biogen/Samsung Bioepis, Samsung Bioepis/Biogen, Celltrion, Outlook Therapeutics, Intas/Sun Pharma, Biocon Biologics, Lupin.

These sponsors do not host a publication library on their corporate site. The sweep runs an NCBI E-Utilities query keyed on product/molecule names and sponsor affiliations. Each result is mapped through `elink` to a PMC ID; if a PMC OA mirror exists the PDF is fetched from there. Items with no PMC mirror are emitted to the worklist with a PubMed landing-page link for institutional retrieval.

### Tier 5: Deliberately skipped

Companies: Bausch + Lomb.

Documented in `sources.yaml` with a `reason:` field. The sweep records the skip in its run report and moves on. Move a company out of Tier 5 only when the operator confirms a new sponsor publishing presence.

---

## 6. Adding or modifying a company

1. Open `scripts/sweep/sources.yaml`.
2. Pick the right `tier:` based on how the sponsor exposes its content. Read the comments at the top of the file for the contract.
3. Set `folder:` to the path under `companies/`. Create the destination directory (`presentations_posters/`, `published_manuscripts/`, or both) before the first run; the sweep will not create parent companies/<sponsor> folders on its own.
4. For each `source:` set the `dest:` (or `dest_router`) to the right product subfolder. If multiple programs share the same source page, use `dest_router` with regex patterns that target the URL or link text.
5. Use `title_filter:` to keep the sweep focused on the in-scope program; the page may list out-of-scope items (e.g., Clearside CLS-TA uveitis posters when CLS-AX is in scope).
6. Run `python -m scripts.sweep.smoke` to validate.
7. Run `python -m scripts.sweep --companies <new_id> --dry-run` to confirm the candidate list is sensible.
8. Run for real.

---

## 7. Failure recipes

When a run completes with errors, open the latest `scripts/sweep/runs/sweep-<ts>.md`. The "Failed downloads" and "Source errors" sections list each problem. Common failure modes and how to handle them:

### `http_error: HTTP 403` on a Tier 1 source

The sponsor either added bot protection or restricted the path. Investigate by hand:

```powershell
curl.exe -I -A "<UA>" "<URL>"
```

If you see `server: AkamaiGHost` or Cloudflare cookies, the company has moved to Tier 2. Switch `fetcher: requests` to `fetcher: playwright_hcp` and set a sensible `bot_clear_seconds:` and (if relevant) `hcp_action:`.

### `http_error: HTTP 404` on a known-good URL

The sponsor restructured the site. Locate the new URL by hand (typically `/science/publications`, `/scientific-publications`, `/our-science`, `/news-and-resources`). Update `url:` in `sources.yaml` and rerun.

### `invalid_pdf` after Playwright fetch

The destination URL returned HTML, not a PDF. Usually one of:

- The Akamai/Cloudflare challenge was not cleared. Increase `bot_clear_seconds:` (typical fix: 5 → 10).
- The page now requires HCP attestation. Add `hcp_action: "click:text=Continue"` (or the new selector).
- The URL pattern has changed; the link the sweep picked up is no longer a PDF endpoint. Tighten `link_pattern:`.

### PubMed source returns zero candidates

- Verify the term syntax in PubMed's web UI first.
- Check that `defaults.pubmed_email:` is set (NCBI rate-limits anonymous traffic harshly).
- If you have many sponsors on Tier 4, register for an API key at https://www.ncbi.nlm.nih.gov/account/settings/ and set `defaults.pubmed_api_key:`. The per-second limit relaxes from 3 to 10 requests.

### Playwright fails to launch in a scheduled job

If you see `Executable doesn't exist at .../chromium-...`, rerun `python -m playwright install chromium`. On a Windows scheduled task make sure the task runs as the same user that installed Playwright; the browser binaries live in `%LOCALAPPDATA%\ms-playwright\` and are user-scoped.

### Discovery-only worklist keeps growing

This is expected behavior. Tier 3 cannot retrieve PDFs automatically. Triage the worklist roughly monthly:

1. Open `companies/<sponsor>/_worklist_pending_hcp.md`.
2. For each entry, log in to the HCP portal in a real browser, accept attestation, download the PDF.
3. Drop the file into `suggested_dest`.
4. Remove the line from the worklist.

---

## 8. What the sweep will NOT do

These are deliberate non-goals; do not extend the sweep to cover them without a design conversation:

- **Parse PDFs into markdown.** The sweep only fetches. PDF-to-markdown extraction is a separate `llamaparse.py` pipeline and runs after the sweep.
- **Update `companies/manifest.csv` or `companies/validation_index.csv`.** These manifests carry editorial fields (validation titles, notes) that the sweep cannot infer.
- **Generate infographics.** That contract is documented in `scripts/infographic_generation_prompt.md`.
- **Push to `main`.** GitHub Pages builds on every push. The CLAUDE.md gate requires explicit user authorization for any push.
- **Modify pre-existing PDFs.** SHA-1 dedup and atomic write ensure existing files are never overwritten.
- **Touch the parser byproduct trees** (`plain_text/`, `original_markdown/`). The inventory scanner explicitly skips these.

---

## 9. Post-sweep manual steps

After every sweep that downloaded new files:

1. Review the run report markdown (`scripts/sweep/runs/sweep-<ts>.md`).
2. For each new PDF, run the PDF-to-markdown extractor (`python llamaparse.py <pdf>`).
3. Add a row to `companies/manifest.csv` (marketed products) or `companies/development_stage_manifest.csv` (development-stage programs) with the validated title and source URL.
4. Run `python scripts/audit_mermaid_labels.py` if any new markdown made it into `companies/` or `company-documents/`.
5. Run `python scripts/build_infographic_manifest.py > scripts/infographic_manifest.json` if new manuscripts were added.
6. Commit the new PDFs, manifest rows, parsed markdown, and the run report together. Do not push to `main` until the user authorizes.

---

## 10. Audit trail

Every run is fully reproducible from its JSON report. If a downstream consumer asks "where did this file come from", look up its SHA-1 in the run reports under `scripts/sweep/runs/sweep-*.json`. The `downloads[*].url` and `downloads[*].sha1` fields give you the exact source and content fingerprint.

Worklist files (`companies/<sponsor>/_worklist_pending_*.md`) carry the same provenance metadata for items that required manual retrieval.

---

## 11. Quick reference

| Action | Command |
|---|---|
| Install | `pip install -r scripts/sweep/requirements.txt && python -m playwright install chromium` |
| Validate config | `python -m scripts.sweep.smoke` |
| Full sweep | `python -m scripts.sweep` |
| Tier 1 only | `python -m scripts.sweep --tier 1` |
| Dry run | `python -m scripts.sweep --dry-run` |
| One company | `python -m scripts.sweep --companies bayer` |
| Strict (CI) | `python -m scripts.sweep --strict` |
| Latest run report | `Get-ChildItem scripts/sweep/runs/sweep-*.md | Sort-Object LastWriteTime -Descending | Select-Object -First 1` |
