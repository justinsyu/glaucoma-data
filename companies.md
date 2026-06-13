---
layout: default
title: Companies
permalink: /companies/
description: Company-level entry points for the Glaucoma Data Archive.
---

<section class="hero">
  <h1>Companies</h1>
  <p class="lead">Sponsor entry points for the archive. Each card links to a per-company source index with labels, releases, clinical trial records, and congress updates indexed by program and indication.</p>
</section>

{% assign companies = site.data.company_profiles | sort: "name" %}
<section>
  <ul class="document-list company-card-grid">
    {% for company in companies %}
      <li
        data-company-color="true"
        style="--card-primary: {{ company.primary }}; --card-secondary: {{ company.secondary }}; --card-accent: {{ company.accent }};"
      >
        {% assign logo_class = "company-card-logos" %}
        {% case company.slug %}
          {% when "clearside-biomedical" %}{% assign logo_class = "company-card-logos logo-on-dark" %}
          {% when "ocular-therapeutix" %}{% assign logo_class = "company-card-logos logo-on-dark" %}
          {% when "regenxbio-abbvie" %}{% assign logo_class = "company-card-logos logo-on-dark" %}
          {% when "bayer" %}{% assign logo_class = "company-card-logos logo-square" %}
        {% endcase %}
        <a class="topic-card-link company-card-link" href="{{ company.page_url | relative_url }}">
          <span class="brand-chip">{{ company.code }}</span>
          {% if company.logo %}
            <span class="{{ logo_class }}" aria-hidden="true">
              <img class="company-card-logo" src="{{ company.logo | relative_url }}" alt="" loading="lazy">
              {% if company.secondary_logo %}
                <img class="company-card-logo company-card-logo-secondary" src="{{ company.secondary_logo | relative_url }}" alt="" loading="lazy">
              {% endif %}
            </span>
          {% endif %}
          <span class="topic-card-title">{{ company.name }}</span>
          <span class="topic-card-meta">{{ company.document_count }} documents</span>
          <span class="topic-card-description">{{ company.description }}</span>
        </a>
      </li>
    {% endfor %}
  </ul>
</section>
