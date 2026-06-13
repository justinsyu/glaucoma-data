---
layout: default
title: "KDB Glide"
permalink: /programs/kdb-glide/
description: "KDB Glide source records for Primary open-angle glaucoma from New World Medical."
company: "New World Medical"
company_slug: new-world-medical
---

<section class="hero">
  <h1>KDB Glide</h1>
  <p class="lead">KDB Glide source records for Primary open-angle glaucoma from New World Medical.</p>
</section>

{% assign program_documents = site.data.company_documents | where: "program", "KDB Glide" %}
{% include document_list.html documents=program_documents sort_by="year" sort_dir="desc" match_summary_spacing=true %}
