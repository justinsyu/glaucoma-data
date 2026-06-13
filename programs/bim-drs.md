---
layout: default
title: "BIM-DRS"
permalink: /programs/bim-drs/
description: "BIM-DRS source records for Open-angle glaucoma / ocular hypertension from SpyGlass Pharma."
company: "SpyGlass Pharma"
company_slug: spyglass-pharma
---

<section class="hero">
  <h1>BIM-DRS</h1>
  <p class="lead">BIM-DRS source records for Open-angle glaucoma / ocular hypertension from SpyGlass Pharma.</p>
</section>

{% assign program_documents = site.data.company_documents | where: "program", "BIM-DRS" %}
{% include document_list.html documents=program_documents sort_by="year" sort_dir="desc" match_summary_spacing=true %}
