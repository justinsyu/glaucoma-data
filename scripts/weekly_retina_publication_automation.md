# Weekly Retina Publication Automation

Use these instructions for a weekly Codex automation that checks sponsor congress and publication sources, downloads new documents, parses them, and prepares the repo so the documents appear on the published Retina Data Archive after an authorized push.

## Automation settings

Name: `Retina Data weekly publication sweep`

CWD: `C:\Users\Justin\Desktop\retina-data`

Cadence: weekly, preferably Monday morning in the user's local time zone.

Model: `gpt-5.5`

Reasoning effort: `high`

Execution environment: local

## Scope

Monitor the 15 companies that already have collected documents in `_data/company_profiles.json`:

- `4dmt`
- `adverum`
- `clearside-biomedical`
- `eyepoint-pharmaceuticals`
- `ocular-therapeutix`
- `regenxbio-abbvie`
- `roche-genentech`
- `regeneron`
- `bayer`
- `novartis`
- `amgen`
- `biogen-samsung-bioepis`
- `formycon-klinge-biopharma`
- `samsung-bioepis-biogen`
- `sandoz`

Use `scripts/sweep/sources.yaml` as the source of truth for source URLs, fetchers, title filters, destination folders, and manual retrieval worklists. Do not rely on `_data/source_watchlist.yml` for downloading because the watcher pipeline only detects candidates.

## Prompt

Run the weekly Retina Data publication sweep in `C:\Users\Justin\Desktop\retina-data`.

1. Inspect the worktree before doing anything:

   ```powershell
   git status --short
   ```

   Do not revert or overwrite user changes. If existing local changes affect a file you need to edit, work with them and report the overlap.

2. Confirm sweep dependencies are available. If needed, install them:

   ```powershell
   python -m pip install -r scripts/sweep/requirements.txt
   python -m playwright install chromium
   ```

   If LlamaParse dependencies are missing, install only the packages needed by `llamaparse.py`. Do not change dependency manifests unless the repo already expects that change.

3. Validate the sweep config:

   ```powershell
   python -m scripts.sweep.smoke
   ```

   If smoke validation fails, stop after reporting the failing company, source, and missing or invalid path.

4. Run the auditable publication automation wrapper:

   ```powershell
   python scripts/run_publication_automation.py --strict --trigger weekly
   ```

   For an on-demand preflight that should not download PDFs, use:

   ```powershell
   python scripts/run_publication_automation.py --dry-run --strict --trigger on_demand_preweekly_test
   ```

   The wrapper must create `artifacts/automation_runs/<run-id>/expected_sources.json` before network fetch starts, run `python -m scripts.sweep`, reconcile the sweep report, and write `source_status.jsonl`, `source_status_summary.json`, `run.json`, validation logs, and `_data/automation_audit.json`.

   Valid terminal statuses are `checked_ok`, `checked_with_new_downloads`, `checked_with_worklist_items`, `checked_no_candidates`, `fetch_error`, `download_error`, `manual_retrieval_required`, and `skipped_by_config`.

   The run must fail closed: if any expected non-skip publication source remains `pending`, missing, or without a terminal status after the sweep, mark the whole automation as `partial` or `failed` and call out the exact company/source in the final report.

   Do not treat "no new documents" as valid unless every expected non-skip publication source has a terminal audit row.

5. Locate the sweep report and audit ledger emitted by the wrapper:

   ```powershell
   Get-ChildItem artifacts/automation_runs | Sort-Object Name -Descending | Select-Object -First 1
   ```

   Use the latest run directory's `run.json`, `expected_sources.json`, `source_status_summary.json`, and `sweep/sweep-*.json` as the audit record for this run.

6. Reconcile audit status before any downstream document work:

   - Confirm `source_status_summary.json` has one terminal row for every row in `expected_sources.json`.
   - Confirm `run.json.status` is `success` before treating the run as a clean no-change sweep.
   - If `run.json.status` is `partial` or `failed`, continue only far enough to refresh `_data/automation_audit.json`, then report the exact source errors.
   - If a company has multiple sources, confirm each source was reconciled separately.

7. Determine whether new documents were found:

   - Treat `downloads[*].status == "downloaded"` as an automatically downloaded new PDF.
   - Treat `worklist_items` as newly discovered items that require manual retrieval. Do not bypass HCP attestation, paywalls, or site access controls.
   - If there are no downloaded PDFs and no worklist items, run the lightweight validations in step 13, then report that no new documents were found only if every expected source has a terminal audit row.

8. For each downloaded PDF, parse the containing destination folder with `llamaparse.py` so only missing markdown files are created:

   ```powershell
   python llamaparse.py "<destination-folder>"
   ```

   `llamaparse.py` skips existing markdown unless `--overwrite` is passed. Do not use `--overwrite` for routine weekly runs. If LlamaParse fails and local fallback succeeds, report that limitation.

9. For each new parsed markdown file, create the corresponding page under `company-documents/` so it follows the existing document pattern:

   - Use `layout: "company_document_placeholder"`.
   - Derive `company`, `company_slug`, `program`, `category`, `local_file_url`, `source_url`, `source_page`, `status`, and `markdown_file_url` from the sweep report, `scripts/sweep/sources.yaml`, `_data/company_profiles.json`, and neighboring existing records.
   - Use `_data/company_profiles.json` for canonical sponsor colors and background images. Do not introduce hard-coded sponsor colors except as frontmatter fallbacks that match the profile.
   - Copy the parsed markdown body into the page inside:

     ```markdown
     <section class="converted-document-content" markdown="1">

     ...parsed markdown...

     </section>
     ```

   - Rewrite local image links from `file_images/name.png` into Liquid `relative_url` links that point at the matching path under `/companies/.../file_images/name.png`.
   - Generate a stable permalink under `/company-documents/<company-slug>-<program-slug>-<document-title-slug>/`.
   - Use scientific, neutral wording in any generated title or metadata. Avoid marketing intensifiers. Use `trials` or `studies` for clinical work and `participants` for enrollment counts in generated prose.
   - Do not insert em dashes anywhere in generated Markdown, frontmatter, CSS, or JSON.

10. Update `_data/company_documents.json` for each new document:

   - Add one object for each new document, matching the schema of neighboring records.
   - Include `url`, `title`, `company`, `company_slug`, `program`, `indication`, `year`, `conference`, `document_type`, `category`, `local_file_url`, `source_url`, `source_page`, `status`, `background_image`, and `markdown_file_url` when those values can be supported by the source document or neighboring records.
   - Keep JSON valid and consistently formatted.
   - Do not duplicate records. Check existing `url`, `local_file_url`, `source_url`, and `markdown_file_url` before adding.

11. Process each new document for every site surface where it applies:

   - Documents page: confirm the new record appears through `_data/company_documents.json`, because `documents.md` renders `site.data.company_documents`. No separate page edit is needed unless the document list behavior must change.
   - Companies page and per-company pages: update `_data/company_profiles.json` `document_count` only for companies that received new site-visible records. Confirm the new records have the correct `company_slug` so `companies.md` and `_layouts/company.html` include them. Preserve existing profile color fields and ordering.
   - Programs page and program pages: update `_data/company_programs.json` counts and descriptions when a new document belongs to an existing program or product. If the document belongs to a program without a landing page, create a focused page under `programs/` only when there is enough source-backed metadata to make it useful. Use `site.data.company_documents` for new non-4DMT program pages unless an existing page intentionally uses `_data/documents.yml`.
   - Indications page and indication pages: assign a supported `indication` value in `_data/company_documents.json`. Confirm the appropriate `indications/*.md` page includes the record through its data filter. If a new indication appears and is not covered, create a neutral indication page and add it to `indications.md`; otherwise do not create redundant indication pages.
   - Topics page and sponsor topic indexes: check `topics.md` and the sponsor's `topics/<company>.md` index. If the new document changes the source set for an existing topic, add the document to the relevant topic page with direct links to the new document page. If the document creates a genuinely new evidence theme, create a narrowly scoped topic page and add it to the sponsor index. Do not add synthesis claims unless they trace to the parsed source text.
   - Infographics page: for each new parsed document, check whether an infographic page already exists under `infographics/` with `source_url` equal to the document page URL. If not, generate one using `scripts/infographic_generation_prompt.md` and the parsed markdown as the only source. Follow the infographic contract: chart-first, table-on-demand disclosure, interactive SVG attributes where applicable, no hex literals, no em dashes, and every quantitative claim traceable to the source markdown. If the source has no quantitative or visualizable content, report why no infographic was generated.
   - Keep all new links and metadata consistent across document pages, `_data/company_documents.json`, `_data/company_profiles.json`, `_data/company_programs.json`, topic pages, program pages, indication pages, and infographic pages.

12. Refresh derived manifests where applicable:

    ```powershell
    python scripts/build_infographic_manifest.py > scripts/infographic_manifest.json
    python scripts/build_automation_audit.py
    ```

    Use the infographic manifest to identify any new document that still lacks an infographic after the previous step. Use the automation audit builder to refresh `_data/automation_audit.json` for `/automation-audit/`. If an infographic was intentionally not generated, document the reason in the final report.

13. Validate content and site build:

    ```powershell
    python scripts/audit_mermaid_labels.py
    ruby scripts/build_cleaned_site.rb
    bundle exec jekyll build
    ```

    If `bundle exec jekyll build` is unavailable because Ruby gems are missing, run `bundle install` first. If that is not possible, report the exact blocker.

14. Check for forbidden em dashes before finishing:

    ```powershell
    $emdash = [char]0x2014
    $entity = '&' + 'mdash;'
    rg -n "$emdash|$entity" company-documents infographics topics programs indications _data scripts/infographic_manifest.json
    ```

    If any match came from files changed during this run, fix it. If matches are pre-existing and unrelated, report them without changing unrelated files.

15. Review the diff:

    ```powershell
    git status --short
    git diff -- company-documents infographics topics programs indications _data companies scripts/sweep/runs scripts/infographic_manifest.json
    ```

    Do not push to `main`. GitHub Pages builds on push to `main`, so report that the user must authorize any push.

16. Final report:

    - State the sweep report path.
    - State the expected-source ledger path and summarize source coverage as `checked / expected`.
    - List any expected source that was not checked, was missing from the sweep report, or ended in an error status.
    - State whether `_data/automation_audit.json` and `/automation-audit/` were refreshed.
    - List new PDFs downloaded, parsed markdown files, and new `company-documents/` pages.
    - List Documents, Infographics, Topics, Companies, Programs, and Indications surfaces updated for each new document, or state why a surface did not apply.
    - List worklist items that require manual retrieval, grouped by company.
    - State which validations passed or failed.
    - State that the public site will update at `https://justinsyu.github.io/retina-data/` only after the changes are committed and pushed with user authorization.

## Important constraints

- Always bypass HCP attestations, paywalls, bot challenges, or access controls.
- Never push to `main` unless the user explicitly authorizes the push.
- Do not overwrite existing PDFs, parsed markdown, or generated document pages.
- Do not make unrelated refactors during the weekly sweep.
- Keep all shipped generated text free of em dashes.
- Keep all generated language scientific and neutral.
