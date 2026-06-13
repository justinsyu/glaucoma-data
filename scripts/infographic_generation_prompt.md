# Document Infographic Generation Prompt

This is the canonical prompt template for generating a single-document infographic page in the Retina Data Archive Jekyll site. One subagent per document, one source markdown per subagent. The agent reads ONLY the source markdown it is given and writes ONE output file.

---

## Inputs the dispatcher must fill in

| Placeholder | What it is | Example |
|---|---|---|
| `{{SOURCE_MARKDOWN_PATH}}` | Absolute path to the parsed source markdown | `companies/roche_genentech/vabysmo/presentations_posters/002_faricimab_in_neovascular_age_related_macular_degeneration_48_week_results.md` |
| `{{DOC_URL}}` | URL of the source document page (from the doc index / yml / json) | `/company-documents/roche-genentech-vabysmo-faricimab-in-neovascular-age-related-macular-degeneration-48-week-result/` |
| `{{DOC_SLUG}}` | The last URL segment of the source document URL | `roche-genentech-vabysmo-faricimab-in-neovascular-age-related-macular-degeneration-48-week-result` |
| `{{OUTPUT_PATH}}` | Absolute path to write the infographic markdown | `infographics/roche-genentech-vabysmo-faricimab-in-neovascular-age-related-macular-degeneration-48-week-result.md` |
| `{{OUTPUT_PERMALINK}}` | URL the infographic will live at | `/infographics/roche-genentech-vabysmo-faricimab-in-neovascular-age-related-macular-degeneration-48-week-result/` |
| `{{DOC_TITLE}}` | Document title | `Faricimab in nAMD: 48-Week Results by Dosing Cohort` |
| `{{COMPANY_NAME}}` | Sponsor display name | `Roche / Genentech` |
| `{{COMPANY_SLUG}}` | Sponsor slug | `roche-genentech` |
| `{{PROGRAM}}` | Program (optional) | `Vabysmo` |
| `{{INDICATION}}` | Indication (optional) | `Wet AMD` |
| `{{YEAR}}` | Year (optional) | `2022` |
| `{{CONFERENCE}}` | Conference (optional) | `WOC` |
| `{{DOCUMENT_TYPE}}` | Type (optional) | `Presentation/Poster` |
| `{{PDF_URL}}` | Direct PDF URL if present in the doc metadata (optional) | `https://...pdf` |

For 4DMT documents the source markdown lives under `companies/4d_molecular_therapeutics/<program>/presentations_posters/cleaned_markdown/`. Look up the matching entry in `_data/documents.yml`. The dispatcher prefixes `4dmt-` onto the DOC_SLUG so the infographic URL is `/infographics/4dmt-<slug>/`.

For all other sponsors the source markdown lives under `companies/<sponsor_folder>/<program_slug>/<category>/`. Look up the matching entry in `_data/company_documents.json`. The DOC_URL field has the `url` value from that record.

---

## The prompt the subagent receives

Paste the block below into the Agent prompt, substituting the placeholders.

```
You are generating ONE infographic page for the Retina Data Archive Jekyll site at C:\Users\Justin\Desktop\retina-data. Read ONLY the source markdown listed below. Do not read any other documents. Do not synthesize claims that are not in this file. Hallucination is the failure mode we are protecting against, so when in doubt: cite the source verbatim, or omit the claim.

## Source document
- Title: {{DOC_TITLE}}
- Sponsor: {{COMPANY_NAME}} ({{COMPANY_SLUG}})
- Program: {{PROGRAM}}
- Indication: {{INDICATION}}
- Year: {{YEAR}}
- Conference: {{CONFERENCE}}
- Document type: {{DOCUMENT_TYPE}}
- Source markdown path: {{SOURCE_MARKDOWN_PATH}}
- Source document page URL: {{DOC_URL}}
- PDF URL (may be empty): {{PDF_URL}}

## Output
Write the infographic to: {{OUTPUT_PATH}}

The output is a Jekyll page with this frontmatter (fill it in exactly):

---
layout: document_infographic
title: "{{DOC_TITLE}}"
permalink: {{OUTPUT_PERMALINK}}
company: "{{COMPANY_NAME}}"
company_slug: "{{COMPANY_SLUG}}"
source_url: "{{DOC_URL}}"
source_title: "{{DOC_TITLE}}"
program: "{{PROGRAM}}"
indication: "{{INDICATION}}"
year: "{{YEAR}}"
conference: "{{CONFERENCE}}"
document_type: "{{DOCUMENT_TYPE}}"
pdf_url: "{{PDF_URL}}"
description: "Infographic version of {{DOC_TITLE}}, generated from the parsed source markdown."
---

After the frontmatter, write the infographic body as HTML using the components below. Wrap each conceptual section in a `<section>...</section>`. Lead each section with a short `<h2>` (1.45rem) or `<h3>` (1.15rem) heading.

## Hard rules
1. **No hallucination.** Every number, study name, dose, cohort size, endpoint result, and safety claim must appear verbatim or be a direct transcription from the source markdown. If a value is "approximately X" or "N/A" in the source, preserve that. Never invent.
2. **No information loss.** Preserve every quantitative claim and every cohort/timepoint/result tuple. If a chart cannot represent everything in a table, ALSO include the table. Use the disclosure pattern below so the chart stays the primary visual.
3. **Chart first, table-on-demand.** Any data that is a series across timepoints OR a comparison across cohorts MUST be presented as a chart. The corresponding data table, if you include one, goes inside `<details class="data-table-toggle"><summary>Show data table</summary>...<table>...</table></details>` so it is collapsed by default and revealed when the reader clicks. Do not place a duplicate raw table directly after a chart; readers got confused by seeing the same numbers twice.
4. **Interactive line and bar charts.** Every chart's data points must carry `data-x`, `data-y`, and (when multi-series) `data-series` attributes on each `<circle class="point">` or `<rect class="bar">`. Add `data-interactive="line"` (or `data-interactive="bar"`) to the parent `<svg class="svg-chart">`. Line charts must include a vertical `<line class="hover-guide" x1="0" y1="20" x2="0" y2="270"/>` element (its x is set on hover by the script). The `assets/js/infographic-charts.js` script reads these attributes and shows a tooltip on hover. Use human-readable values, e.g. `data-x="Week 24" data-y="6.7 letters" data-series="Faricimab up to Q16W"`.
5. **No em dashes** (—). Use commas, periods, semicolons, parentheses, or rewrite. Replace any em dash from the source with a different separator in the rendered text (but keep the meaning).
6. **Scientific, neutral language.** No marketing words ("groundbreaking", "revolutionary", "powerful", "deep", "broad" as intensifiers). "Trials"/"studies" not "programs" for clinical work. "Participants" not "patients" for enrollment counts.
7. **Stay in the style guide.** Use only the component classes below or existing site classes you have observed in `topics/4d-150-retinal-gene-therapy-evidence.md`. Do not load external JS or CSS. Do not include `<script>` tags in the page body. Inline SVG only.
8. **Company colors.** All chart fills/strokes reference `var(--company-primary)`, `var(--company-secondary)`, `var(--company-accent)`. Do not hardcode hex colors except for `#fff`/`currentColor`/`none` if absolutely needed.
9. **Accessibility.** Each `<svg>` must have a `<title>` child describing the chart. Each table must have a `<thead><tr><th></th></tr></thead>` header row. Use `aria-label` on grouped widgets where appropriate. Leave a generous blank line above every `<table>` (the site CSS adds 2rem top-margin to tables and 1.1rem padding above table headers; do not override this).

## Component kit

Use any combination of these. None are mandatory; pick what fits the data.

### Stat grid (1 to 4 headline numbers up top)
```html
<div class="stat-grid" aria-label="Headline numbers">
  <div class="stat">
    <span class="stat-value">+6.6<span class="stat-unit">letters</span></span>
    <span class="stat-label">Mean BCVA change at Week 48 (pooled)</span>
  </div>
  <div class="stat">
    <span class="stat-value">77.8<span class="stat-unit">%</span></span>
    <span class="stat-label">Achieved Q12W or longer dosing at Week 48</span>
  </div>
</div>
```

### Bar list (CSS-only horizontal bar; great for comparisons across cohorts)
```html
<div class="bar-list" aria-label="Annualized injection rate by cohort">
  <div><span>3E10 vg/eye</span><strong style="--bar:84%">-84%</strong></div>
  <div><span>1E10 vg/eye</span><strong style="--bar:68%">-68%</strong></div>
  <div><span>6E9 vg/eye</span><strong style="--bar:80%">-80%</strong></div>
</div>
```
Set `--bar` to the magnitude (0-100). The leading text in `<strong>` is shown.

### Flow diagram (study schema, dosing arms, eligibility pipeline)
```html
<div class="flow-diagram" aria-label="Study schema">
  <div>Screen</div>
  <div>Randomize 1:1</div>
  <div>Faricimab 6 mg / aflibercept 2 mg</div>
  <div>Week 48 primary endpoint</div>
</div>
```

### Evidence cards (paired or 3-up text blocks)
```html
<div class="evidence-grid evidence-grid-2">
  <article class="evidence-card">
    <h3>Faricimab arm</h3>
    <p>Adjusted Week 48 BCVA change of +5.8 letters (Q16W cohort) in TENAYA, with no new safety signals.</p>
  </article>
  <article class="evidence-card">
    <h3>Aflibercept arm</h3>
    <p>Adjusted Week 48 BCVA change of +5.1 letters with Q8W dosing.</p>
  </article>
</div>
```

### Inline SVG bar chart (categorical comparison) — interactive
Use a viewBox-based, responsive SVG. Keep total width 720, height 320, padding 50 on each side. Add `data-interactive="bar"` to the `<svg>` and `data-x`/`data-y`/`data-series` to each `<rect class="bar">`.
```html
<svg class="svg-chart" data-interactive="bar" viewBox="0 0 720 320" role="img" aria-labelledby="chart1-title">
  <title id="chart1-title">Annualized anti-VEGF injection rate by cohort, Week 24</title>
  <line class="axis" x1="60" y1="270" x2="700" y2="270"/>
  <line class="axis" x1="60" y1="20"  x2="60"  y2="270"/>
  <!-- gridlines -->
  <line class="grid-line" x1="60" y1="100" x2="700" y2="100"/>
  <line class="grid-line" x1="60" y1="180" x2="700" y2="180"/>
  <!-- bars (height proportional to value; y = 270 - value*scale) -->
  <rect class="bar"     x="120" y="120" width="80" height="150"
        data-x="3E10 vg/eye" data-y="-84%" data-series="Annualized injection rate"/>
  <rect class="bar alt" x="280" y="60"  width="80" height="210"
        data-x="1E10 vg/eye" data-y="-94%" data-series="Annualized injection rate"/>
  <rect class="bar accent" x="440" y="90" width="80" height="180"
        data-x="6E9 vg/eye"  data-y="-78%" data-series="Annualized injection rate"/>
  <!-- value labels above bars -->
  <text class="value-label" x="160" y="110" text-anchor="middle">-84%</text>
  <text class="value-label" x="320" y="50"  text-anchor="middle">-94%</text>
  <text class="value-label" x="480" y="80"  text-anchor="middle">-78%</text>
  <!-- x-axis labels under bars -->
  <text class="tick-label" x="160" y="290" text-anchor="middle">3E10 vg/eye</text>
  <text class="tick-label" x="320" y="290" text-anchor="middle">1E10 vg/eye</text>
  <text class="tick-label" x="480" y="290" text-anchor="middle">6E9 vg/eye</text>
  <!-- y-axis label -->
  <text class="axis-label" x="20" y="150" transform="rotate(-90 20 150)" text-anchor="middle">Annualized injection rate</text>
</svg>
<details class="data-table-toggle">
  <summary>Show data table</summary>
  <table>
    <thead><tr><th>Cohort</th><th>Annualized injection rate</th></tr></thead>
    <tbody>
      <tr><td>3E10 vg/eye</td><td>-84%</td></tr>
      <tr><td>1E10 vg/eye</td><td>-94%</td></tr>
      <tr><td>6E9 vg/eye</td><td>-78%</td></tr>
    </tbody>
  </table>
</details>
<p class="infographic-caption">Source: <a href="{{DOC_URL}}">{{DOC_TITLE}}</a>.</p>
```

### Inline SVG line chart (time series like BCVA, CST, AH aflibercept) — interactive
Use a single `<polyline class="line">` for the series, plus `<circle class="point">` for each datum. Add `data-interactive="line"` to the `<svg>`, `data-x`/`data-y`/`data-series` on each `<circle>`, and a `<line class="hover-guide"/>` element. Provide y-axis ticks every 25% of range.
```html
<svg class="svg-chart" data-interactive="line" viewBox="0 0 720 320" role="img" aria-labelledby="chart2-title">
  <title id="chart2-title">Mean BCVA over time, 3E10 vg/eye cohort</title>
  <line class="axis" x1="60" y1="270" x2="700" y2="270"/>
  <line class="axis" x1="60" y1="20"  x2="60"  y2="270"/>
  <line class="hover-guide" x1="0" y1="20" x2="0" y2="270"/>
  <polyline class="line" points="120,170 200,180 280,160 360,190 440,170 520,180 600,170"/>
  <circle class="point" cx="120" cy="170" r="4"
          data-x="Week 4"  data-y="54 letters" data-series="3E10 vg/eye"/>
  <circle class="point" cx="200" cy="180" r="4"
          data-x="Week 8"  data-y="52 letters" data-series="3E10 vg/eye"/>
  <!-- ... etc; ONE <circle> per datapoint, every one with data-x/data-y -->
  <text class="value-label" x="600" y="160" text-anchor="middle">51</text>
  <text class="tick-label" x="120" y="290" text-anchor="middle">Wk 4</text>
  <!-- ... -->
</svg>
<div class="chart-legend">
  <span><i></i> 3E10 vg/eye</span>
</div>
```
Multiple series: add a second `<polyline class="line alt">` and a second set of `<circle class="point alt">` points (each with their own data-x/data-y/data-series). Add legend entries `<span><i></i> Series A</span><span><i class="alt"></i> Series B</span>`.

### Donut / pie (proportion)
```html
<svg class="svg-chart" viewBox="0 0 240 240" role="img" aria-labelledby="chart3-title" style="max-width:240px;">
  <title id="chart3-title">Proportion injection-free at Week 36</title>
  <circle cx="120" cy="120" r="90" fill="none" stroke="var(--border-strong)" stroke-width="22"/>
  <!-- circumference = 565.5; 4/5 = 80% = 452.4 -->
  <circle cx="120" cy="120" r="90" fill="none" stroke="var(--company-primary)" stroke-width="22"
          stroke-dasharray="452.4 565.5" transform="rotate(-90 120 120)"/>
  <text x="120" y="115" text-anchor="middle" class="value-label" style="font-size:28px;">80%</text>
  <text x="120" y="140" text-anchor="middle" class="tick-label">4 of 5 injection-free</text>
</svg>
```

### Timeline (events over time)
```html
<div class="timeline">
  <div><strong>2019</strong><span>Phase 1/2 first-in-human dosing.</span></div>
  <div><strong>2022</strong><span>Phase 3 TENAYA/LUCERNE 48-week primary readout.</span></div>
</div>
```

### Callout (a single boxed quote or key conclusion from the source)
```html
<div class="callout">
  <strong>Primary endpoint met</strong>
  <p>Pooled Week 48 BCVA non-inferiority margin was within +/-4 ETDRS letters versus aflibercept 2 mg Q8W.</p>
</div>
```

### Tables (when data is too dense or relational for a chart)
Use plain HTML `<table><thead><tr><th></th></tr></thead><tbody>...</tbody></table>`. The existing CSS theme applies (2rem top margin, 1.1rem header-cell top padding). Do not override these spacings.

**Critical:** if the table contains the same data as a chart above it, wrap it in a disclosure toggle:
```html
<details class="data-table-toggle">
  <summary>Show data table</summary>
  <table>
    <thead><tr><th>Week</th><th>Faricimab up to Q16W (n = 665)</th><th>Aflibercept Q8W (n = 664)</th></tr></thead>
    <tbody>
      <tr><td>0</td><td>0</td><td>0</td></tr>
      <tr><td>4</td><td>4.6</td><td>4.2</td></tr>
      <!-- ... -->
    </tbody>
  </table>
</details>
```
Only show a bare `<table>` when the data is NOT also shown as a chart (e.g., baseline characteristics, safety AE counts, dosing schema details). Repeating identical numbers in both a chart and an open table confuses readers.

## Pattern: how to structure the page

A typical infographic page has these sections in order. Adapt based on what the source contains; never invent a section just to fill space.

1. **Headline stats** (`<div class="stat-grid">`): 2 to 4 numbers that capture the most consequential result. Pull only numbers explicitly in the source.
2. **Study at a glance** (flow-diagram + brief text or evidence-card): study design, population, randomization, dose arms, primary/secondary endpoints. Use a `<table>` if there's a "Key Inclusion Criteria" or "Baseline Characteristics" block in the source.
3. **Efficacy** (charts): BCVA change, CST/CRT change, injection burden, fluid resolution, lesion regression, etc. Use line charts for time-series; bar charts for cohort comparisons; donut for single proportions. **Multi-timepoint or multi-cohort data MUST appear as a chart first**; if the underlying table is useful, wrap it in `<details class="data-table-toggle">` so it is hidden by default.
4. **Safety** (table or evidence-grid): AEs, IOI, IOP, endophthalmitis, vasculitis, hypotony rates. Use the exact n/N and percentages from the source. Safety tables are usually NOT duplicated by a chart, so they can be shown directly without the disclosure wrapper.
5. **Conclusions** (`<div class="callout">` or `<ul>`): direct paraphrase of the source's stated conclusions; do not extend.
6. **Source link**: end with a short `<p class="infographic-caption">` linking back to `{{DOC_URL}}` and (if present) the PDF.

## Quality checks before saving
- [ ] Frontmatter has all required fields.
- [ ] Every chart axis has labels (where there is an axis).
- [ ] Every `<svg>` has a `<title>`.
- [ ] Every percentage in the body matches a value in the source markdown.
- [ ] No em dashes anywhere in the file.
- [ ] No external assets referenced (no remote images, no remote fonts, no JS imports).
- [ ] No hex color literals except `#fff`, `none`, `currentColor`.
- [ ] Every multi-timepoint or multi-cohort dataset is rendered as a chart (line or bar) before any table.
- [ ] No data table sits next to its identical chart in the open. Tables duplicating chart data live inside `<details class="data-table-toggle">`.
- [ ] Every interactive chart has `data-interactive="line"` (or `"bar"`) on the `<svg>` AND `data-x` / `data-y` (and `data-series` if multi-series) on every `<circle class="point">` or `<rect class="bar">`.
- [ ] Every line chart includes a `<line class="hover-guide" x1="0" y1="20" x2="0" y2="270"/>` element.
- [ ] Tables left in the open are followed by a blank line before the next section.

## Workflow
1. Read the entire source markdown at {{SOURCE_MARKDOWN_PATH}}.
2. Sketch on paper (or in your head): what are the 2-4 headline numbers, what are the time-series, what are the cohort comparisons, what is the safety table, what is the conclusion?
3. Write the file at {{OUTPUT_PATH}}.
4. Verify each numeric claim against the source by string-search.
5. Return a short (< 100 word) summary of what you wrote.
```
