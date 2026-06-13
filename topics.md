---
layout: default
title: Topics
permalink: /topics/
description: Sponsor-organized entry point to glaucoma treatment source maps and comparisons.
---

<section class="hero topic-index-hero">
  <h1>Topics</h1>
  <p class="lead">Topic pages are reserved for cross-source glaucoma summaries and comparisons. The current seed archive starts with sponsor and program entry points so later synthesis can cite stable source records.</p>
</section>

{% assign companies = site.data.company_profiles | sort: "name" %}
<section>
  <h2>Sponsor source maps</h2>
  <ul class="document-list">
    {% for company in companies %}
      <li
        data-company-color="true"
        style="--card-primary: {{ company.primary }}; --card-secondary: {{ company.secondary }}; --card-accent: {{ company.accent }};"
      >
        <a class="topic-card-link" href="{{ company.page_url | relative_url }}">
          <span class="topic-card-title">{{ company.name }}</span>
          <span class="topic-card-meta">{{ company.programs | join: ", " }}</span>
          <span class="topic-card-description">{{ company.description }}</span>
        </a>
      </li>
    {% endfor %}
  </ul>
</section>
