---
layout: default
title: "Xelpros"
permalink: /programs/xelpros/
description: "Xelpros source records for Open-angle glaucoma / ocular hypertension from Sun Pharma / SPARC."
company: "Sun Pharma / SPARC"
company_slug: sun-pharma-sparc
---

<section class="hero">
  <h1>Xelpros</h1>
  <p class="lead">Xelpros source records for Open-angle glaucoma / ocular hypertension from Sun Pharma / SPARC.</p>
</section>

{% assign program_documents = site.data.company_documents | where: "program", "Xelpros" %}
{% include document_list.html documents=program_documents sort_by="year" sort_dir="desc" match_summary_spacing=true %}
