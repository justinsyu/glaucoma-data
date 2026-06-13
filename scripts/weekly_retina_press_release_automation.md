# Weekly Retina Press Release Automation

Use these instructions for a weekly Codex automation that checks official company and investor press-release pages for new retinal disease releases, filters them by sponsor-specific program terms, and prepares updates to `_data/company_press_releases.yml` so the public Press Releases page can update after an authorized push.

## Automation settings

Name: `Retina Data weekly press release sweep`

CWD: `C:\Users\Justin\Desktop\retina-data`

Cadence: weekly, preferably Monday morning in the user's local time zone.

Model: `gpt-5.5`

Reasoning effort: `high`

Execution environment: local

## Scope

Monitor the same 15 companies used by `scripts/weekly_retina_publication_automation.md`:

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

## Inclusion rule

Keep only official press releases from company, investor-relations, or authorized wire pages that are directly about in-scope retinal disease assets, studies, regulatory decisions, commercial launches, or publication and congress announcements. Exclude generic earnings releases unless the release itself contains a retina product approval, sales, study, or milestone item that is not otherwise available as a product-specific release.

Use neutral generated display titles and summaries in `_data/company_press_releases.yml`. Do not copy marketing language from the original title when a neutral title can describe the same release. Do not add em dashes anywhere.

## Source roster and existing output

Use `scripts/press_release_sources.yml` as the structured source roster for automation and audit coverage. The table below documents the same sources for human review. Any source added to the table must also be added to the YAML file.

The current manually curated dataset is `_data/company_press_releases.yml`, rendered by `press-releases.md` through `_includes/press_release_list.html`.

Required fields for each row:

- `title`
- `date`
- `company`
- `company_slug`
- `program`
- `indication`
- `category`
- `summary`
- `source_url`

## Company source roster

| Company | Press source | Filter terms | Notes |
| --- | --- | --- | --- |
| 4DMT | `https://4dmt.gcs-web.com/news-releases` | `4D-150`, `PRISM`, `4FRONT`, `wet AMD`, `nAMD`, `DME`, `retina`, `neovascular retinopathy` | Include 4D-150 retinal releases. Exclude 4D-710 cystic fibrosis and 4D-310 Fabry releases unless they are part of a broader retina-focused corporate update already kept for 4D-150 context. |
| Adverum | `https://adverum.com/press-archive/` and `https://investors.adverum.com/press_releases/` | `ixo-vec`, `ixoberogene`, `ADVM-022`, `ARTEMIS`, `LUNA`, `OPTIC`, `wet AMD`, `nAMD`, `retinal`, `ophthalmology` | Adverum has both WordPress archive pages and the investor archive. Prefer the HTML company page when both contain the same release. |
| Clearside Biomedical | `https://ir.clearsidebio.com/news-releases` | `CLS-AX`, `axitinib`, `ODYSSEY`, `OASIS`, `suprachoroidal`, `wet AMD`, `nAMD`, `retina`, `macular` | Include CLS-AX wet AMD and suprachoroidal platform releases when they support retinal delivery context. Exclude uveitis-only CLS-TA releases unless tied to platform evidence relevant to retina. |
| EyePoint | `https://eyepoint.bio/press-releases/?from=eyepointpharma` and `https://investors.eyepoint.bio/news-events/press-releases` | `DURAVYU`, `EYP-1901`, `vorolanib`, `DAVIO`, `LUGANO`, `LUCIA`, `VERONA`, `wet AMD`, `DME`, `retinal` | The company changed investor-host domains from `eyepointpharma.com` to `eyepoint.bio`; keep old detail URLs if they are canonical for older releases. |
| Ocular Therapeutix | `https://investors.ocutx.com/news-releases` and `https://www.globenewswire.com/en/search/organization/Ocular%2520Therapeutix%252C%2520Inc.` | `AXPAXLI`, `OTX-TKI`, `axitinib`, `SOL-1`, `SOL-R`, `HELIOS`, `wet AMD`, `NPDR`, `diabetic retinopathy`, `retina` | Some investor pages expose a PDF node as the most stable source URL. Accept official node PDFs or authorized GlobeNewswire copies when the HTML detail page is not exposed. |
| REGENXBIO / AbbVie | `https://ir.regenxbio.com/news-releases` and `https://regenxbio.gcs-web.com/news-releases` | `RGX-314`, `ABBV-RGX-314`, `sura-vec`, `AAVIATE`, `ATMOSPHERE`, `ASCENT`, `ALTITUDE`, `wet AMD`, `diabetic retinopathy`, `retinal` | Prefer REGENXBIO official investor pages. Include AbbVie co-development releases when hosted by REGENXBIO. |
| Roche / Genentech | `https://www.gene.com/media/press-releases`, `https://www.roche.com/media/releases`, and `https://www.roche.com/investors/updates` | `Vabysmo`, `faricimab`, `Susvimo`, `ranibizumab`, `Lucentis`, `wet AMD`, `DME`, `RVO`, `retinal`, `ophthalmology`, `AVONELLE`, `TENAYA`, `LUCERNE`, `SALWEEN`, `VOYAGER` | For U.S.-specific product releases, prefer Genentech. For global congress, investor-update, and Roche-wide ophthalmology releases, use Roche. |
| Regeneron | `https://newsroom.regeneron.com/news-releases` and `https://investor.regeneron.com/news-releases` | `EYLEA`, `EYLEA HD`, `aflibercept`, `PULSAR`, `PHOTON`, `CANDELA`, `QUASAR`, `wet AMD`, `DME`, `DR`, `RVO`, `retinal` | Regeneron uses both newsroom and investor-detail paths. Keep either official URL. |
| Bayer | `https://www.bayer.com/media/en-us/` | `Eylea 8 mg`, `aflibercept 8 mg`, `PULSAR`, `PHOTON`, `wet AMD`, `nAMD`, `DME`, `retinal`, `EURETINA`, `ARVO`, `Angiogenesis` | Bayer releases may be marked not intended for U.S. or UK media. Keep the page because it is the official Bayer release. |
| Novartis | `https://www.novartis.com/news/media-releases` and `https://www.novartis.com/us-en/news/media-releases` | `Beovu`, `brolucizumab`, `HAWK`, `HARRIER`, `MERLIN`, `wet AMD`, `DME`, `retinal`, `macular` | Include Beovu wet AMD and retinal safety or label updates. Exclude non-retina Novartis ophthalmology unless tied to current archive programs. |
| Amgen | `https://www.amgen.com/newsroom/press-releases` | `PAVBLU`, `aflibercept-ayyh`, `ABP 938`, `EYLEA biosimilar`, `wet AMD`, `RVO`, `DME`, `diabetic retinopathy`, `retinal` | Amgen may mention Pavblu only inside quarterly results. Keep earnings releases only when they contain a retinal product approval or sales item. |
| Biogen / Samsung Bioepis | `https://investors.biogen.com/news-releases` | `BYOOVIZ`, `ranibizumab`, `SB11`, `wet AMD`, `RVO`, `myopic CNV`, `ophthalmology biosimilar` | Use Biogen investor releases for Byooviz because Biogen was the commercialization partner. |
| Samsung Bioepis / Biogen | `https://investors.biogen.com/news-releases` and `https://www.samsungbioepis.com/en/newsroom/` | `OPUVIZ`, `aflibercept`, `SB15`, `Eylea biosimilar`, `wet AMD`, `RVO`, `DME`, `myopic CNV` | Samsung Bioepis pages can be harder to index. Use Biogen partner releases when they are official joint releases. |
| Formycon / Klinge Biopharma | `https://www.formycon.com/en/blog/press-release/` | `FYB203`, `Ahzantive`, `Baiama`, `aflibercept`, `Eylea biosimilar`, `MAGELLAN-AMD`, `wet AMD`, `retinal` | Prefer English Formycon pages. Klinge is often mentioned in Formycon releases as the licensing partner. |
| Sandoz | `https://www.sandoz.com/news/media-releases`, `https://www.globenewswire.com/en/search/organization/Sandoz`, and legacy `https://www.novartis.com/news/media-releases` | `Enzeevu`, `Enzeevum`, `Afqlir`, `aflibercept`, `Cimerli`, `ranibizumab`, `MYLIGHT`, `wet AMD`, `RVO`, `DME`, `diabetic retinopathy`, `myopic CNV` | Older Sandoz releases may live on Novartis because Sandoz was still part of Novartis. Newer Sandoz releases can appear on Sandoz or GlobeNewswire. |

## Suggested weekly workflow

1. Inspect the worktree:

   ```powershell
   git status --short
   ```

   Do not revert user changes. If a file you need to edit has unrelated local edits, work around them and report the overlap.

2. Load `_data/company_press_releases.yml` and build a de-duplication set from normalized `source_url`, lowercased `title`, `company_slug`, and `date`.

3. Create an expected-source coverage ledger before fetching:

   - Read `scripts/press_release_sources.yml`.
   - Write the list of every source to `artifacts/automation_runs/<run-id>/expected_sources.json`.
   - Each expected source row must include `source_family: "press_release"`, `run_type: "press_release"`, `source_key`, `source_id`, `company_id`, `company_slug`, `company_name`, `tier`, `source_index`, `source_kind: "press_release_index"`, `source_url`, `fetcher`, `title_filter`, and `status: "pending"`.
   - Also write `artifacts/automation_runs/<run-id>/source_status.jsonl`. Append one JSON line per source as it reaches a terminal state.
   - Valid terminal statuses are `checked_ok`, `checked_with_new_items`, `checked_no_candidates`, `fetch_error`, `parse_error`, `validation_error`, and `build_error`.
   - The run must fail closed. If any expected source remains `pending`, missing, or without a terminal status after the sweep, mark the run `partial` or `failed`.

4. For each company source in `scripts/press_release_sources.yml`, fetch the press index with plain HTTP first. Use Playwright only when the index is JavaScript-rendered or blocks normal requests. Do not bypass paywalls, logins, HCP attestations, or bot challenges.

5. Extract candidate release links and dates from the index. If the index exposes only a recent page and pagination, follow pagination until the run reaches the newest existing kept release for that company or an automation cap of 5 pages.

6. Filter candidates by the company-specific terms above. For ambiguous candidates, open the detail page and search the body for in-scope product, study, or indication terms before keeping the release.

7. For each kept new release, write a neutral data row:

   - Use the official release date.
   - Use canonical sponsor names from `_data/company_profiles.json`.
   - Use generated neutral `title` and `summary` text.
   - Keep `source_url` as the official company, investor, or authorized wire URL.
   - Do not include em dashes or marketing intensifiers.

8. Sort `_data/company_press_releases.yml` by descending `date`, then by `company`, then by `program`. Keep YAML valid and stable.

9. Write `artifacts/automation_runs/<run-id>/run.json` with `run_type: "press_release"`, `trigger`, `status`, `started_at`, `ended_at`, `git_sha`, `new_press_releases`, and `validations`.

10. Refresh the shared automation audit data:

    ```powershell
    python scripts/build_automation_audit.py
    ```

    The audit builder reads `scripts/press_release_sources.yml` and `artifacts/automation_runs/<run-id>/` so `/automation-audit/` shows press release coverage alongside congress and publication coverage.

11. Build the site:

   ```powershell
   bundle exec jekyll build
   ```

12. Check the rendered `/press-releases/` page locally. Confirm sorting works by date, company, program, category, and indication.

13. Check for forbidden em dashes in files touched by the run:

    ```powershell
    $emdash = [char]0x2014
    $entity = '&' + 'mdash;'
    rg -n "$emdash|$entity" _data/company_press_releases.yml press-releases.md _includes/press_release_list.html scripts/weekly_retina_press_release_automation.md scripts/press_release_sources.yml _data/automation_audit.json automation-audit.md
    ```

14. Final report should state:

    - Number of company press pages checked.
    - Number of new candidate releases found.
    - Number of new rows added.
    - Any source that could not be checked and the reason.
    - Whether `_data/automation_audit.json` and `/automation-audit/` were refreshed.
    - Site build result.
    - Reminder that GitHub Pages updates only after commit and authorized push.

## Manual curation notes from initial setup

Initial rows were selected by searching each official press archive or investor-release archive for the company-specific terms above, then opening representative detail pages or official PDF nodes to verify that the release was directly tied to an in-scope retinal product, study, regulatory event, congress presentation, publication, launch, or sales update.

Where a company used more than one official release host, both hosts were recorded in the source roster. Examples include Genentech plus Roche, Regeneron newsroom plus investor pages, and EyePoint legacy plus current investor domains.
