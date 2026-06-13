---
layout: default
title: Glaucoma Data Archive
description: Open index of public source records for approved and investigational glaucoma treatments.
---

{% assign doc_count = site.data.company_documents | size %}
{% assign press_release_count = site.data.company_press_releases | size %}
{% assign company_count = site.data.company_profiles | size %}
{% assign named_programs = site.data.company_programs | where_exp: "p", "p.program != 'Uncategorized'" %}
{% assign program_count = named_programs | size %}

<section class="hero">
  <h1>Approved and investigational glaucoma treatment source records</h1>
  <p class="lead">A direct index of labels, sponsor releases, congress updates, and trial records from {{ company_count }} sponsors developing or commercializing glaucoma and ocular hypertension treatments. Each record links to the original public source so the material can be cited, searched, and machine-read.</p>
</section>

<section class="summary-grid" aria-label="Archive summary">
  <div>
    <strong>Documents</strong>
    <span>{{ doc_count }}</span>
  </div>
  <div>
    <strong>News</strong>
    <span>{{ press_release_count }}</span>
  </div>
  <div>
    <strong>Companies</strong>
    <span>{{ company_count }}</span>
  </div>
  <div>
    <strong>Programs</strong>
    <span>{{ program_count }}</span>
  </div>
</section>

<section>
  <h2>Browse</h2>
  <ul class="document-list">
    <li>
      <a class="topic-card-link" href="{{ '/documents/' | relative_url }}">
        <span class="topic-card-title">Documents</span>
        <span class="topic-card-description">Complete source index with sponsor, program, indication, source type, year, and original source links.</span>
      </a>
    </li>
    <li>
      <a class="topic-card-link" href="{{ '/clinical-trials/' | relative_url }}">
        <span class="topic-card-title">Trials</span>
        <span class="topic-card-description">ClinicalTrials.gov records for tracked investigational glaucoma programs and relevant sustained-delivery platforms.</span>
      </a>
    </li>
    <li>
      <a class="topic-card-link" href="{{ '/press-releases/' | relative_url }}">
        <span class="topic-card-title">News</span>
        <span class="topic-card-description">Official sponsor and investor releases filtered to glaucoma assets, studies, regulatory updates, and publication announcements.</span>
      </a>
    </li>
    <li>
      <a class="topic-card-link" href="{{ '/companies/' | relative_url }}">
        <span class="topic-card-title">Companies</span>
        <span class="topic-card-description">Sponsor landing pages with company-level program lists and source records.</span>
      </a>
    </li>
    <li>
      <a class="topic-card-link" href="{{ '/programs/' | relative_url }}">
        <span class="topic-card-title">Programs</span>
        <span class="topic-card-description">Product- and pipeline-level entry points for marketed and development-stage assets.</span>
      </a>
    </li>
    <li>
      <a class="topic-card-link" href="{{ '/indications/' | relative_url }}">
        <span class="topic-card-title">Indications</span>
        <span class="topic-card-description">Disease-setting entry points for open-angle glaucoma, ocular hypertension, and disease-modifying glaucoma research.</span>
      </a>
    </li>
    <li>
      <a class="topic-card-link" href="{{ '/topics/' | relative_url }}">
        <span class="topic-card-title">Topics</span>
        <span class="topic-card-description">Cross-source summaries and comparisons with inline links back to source records.</span>
      </a>
    </li>
  </ul>
</section>

<section>
  <h2>Program entry points</h2>
  {% assign featured_programs = named_programs | sort: "program" %}
  <ul class="document-list">
    {% for program in featured_programs %}
      <li
        data-company-color="true"
        style="--card-primary: {{ program.primary_color }}; --card-secondary: {{ program.secondary_color }}; --card-accent: {{ program.accent_color }};"
      >
        <a class="topic-card-link" href="{{ program.url | relative_url }}">
          <span class="topic-card-title">{{ program.program }}</span>
          <span class="topic-card-meta">{{ program.company }}, {{ program.document_count }} documents</span>
        </a>
      </li>
    {% endfor %}
  </ul>
</section>
