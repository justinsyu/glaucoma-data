---
layout: default
title: "BIM-IOL System"
permalink: /programs/bim-iol-system/
description: "BIM-IOL System source records for Open-angle glaucoma / ocular hypertension from SpyGlass Pharma."
company: "SpyGlass Pharma"
company_slug: spyglass-pharma
---

<section class="hero">
  <h1>BIM-IOL System</h1>
  <p class="lead">BIM-IOL System source records for Open-angle glaucoma / ocular hypertension from SpyGlass Pharma.</p>
</section>

{% assign program_documents = site.data.company_documents | where: "program", "BIM-IOL System" %}
{% include document_list.html documents=program_documents sort_by="year" sort_dir="desc" match_summary_spacing=true %}
