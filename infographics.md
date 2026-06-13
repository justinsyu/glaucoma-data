---
layout: default
title: Infographics
permalink: /infographics/
description: Visual one-page infographics generated from parsed source documents in the Glaucoma Data Archive.
---

<section class="hero infographics-index-hero">
  <h1>Infographics</h1>
  <p class="lead">Each infographic is a chart-first visualization of one parsed source document. All quantitative claims trace back to the original document; no claims are added beyond what the source records. Select a sponsor to see its available infographics.</p>
</section>

{% assign infographic_pages = site.pages | where_exp: "p", "p.layout == 'document_infographic'" %}
{% assign infographic_count = infographic_pages | size %}

{% if infographic_count == 0 %}
  <section>
    <p>No infographics have been generated yet. Per-document infographics are added incrementally; check back soon.</p>
  </section>
{% else %}
  {% include document_list.html documents=site.data.company_documents sort_by="title" sort_dir="asc" infographic_mode=true match_summary_spacing=true %}
{% endif %}
