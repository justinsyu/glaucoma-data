---
layout: default
title: Programs
permalink: /programs/
description: Program-level and product-level entry points for glaucoma company archive records.
---

<section class="hero">
  <h1>Programs</h1>
  <p class="lead">Program and product cards are colored by their sponsoring company's palette. Cards link to focused pages for marketed and development-stage glaucoma assets.</p>
</section>

{% assign program_cards = site.data.company_programs | sort: "program" %}
<section>
  <ul class="document-list">
    {% for program in program_cards %}
      <li
        data-company-color="true"
        style="--card-primary: {{ program.primary_color }}; --card-secondary: {{ program.secondary_color }}; --card-accent: {{ program.accent_color }};"
      >
        <a class="topic-card-link" href="{{ program.url | relative_url }}">
          <span class="topic-card-title">{{ program.program }}</span>
          <span class="topic-card-meta">{{ program.company }} · {{ program.document_count }} documents</span>
          <span class="topic-card-description">{{ program.description }}</span>
        </a>
      </li>
    {% endfor %}
  </ul>
</section>
