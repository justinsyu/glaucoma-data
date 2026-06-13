---
layout: default
title: News
permalink: /press-releases/
description: Glaucoma-related corporate press releases from the in-scope sponsors in the Glaucoma Data Archive.
---

{% assign release_count = site.data.company_press_releases | size %}
{% assign company_count = site.data.company_press_releases | map: "company_slug" | uniq | size %}

<section class="hero">
  <h1>News</h1>
  <p class="lead">Official company and investor press releases filtered to glaucoma assets, studies, regulatory updates, and publication announcements. Each row links back to the source release.</p>
</section>

<section class="summary-grid press-release-summary summary-grid-no-top" aria-label="News summary">
  <div>
    <strong>Articles</strong>
    <span>{{ release_count }}</span>
  </div>
  <div>
    <strong>Companies</strong>
    <span>{{ company_count }}</span>
  </div>
  <div>
    <strong>Scope</strong>
    <span>Glaucoma</span>
  </div>
</section>

{% include press_release_list.html releases=site.data.company_press_releases sort_by="date" sort_dir="desc" %}
