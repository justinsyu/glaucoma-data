---
layout: default
title: "Iyuzeh"
permalink: /programs/iyuzeh/
description: "Iyuzeh source records for Open-angle glaucoma / ocular hypertension from Thea Pharma."
company: "Thea Pharma"
company_slug: thea-pharma
---

<section class="hero">
  <h1>Iyuzeh</h1>
  <p class="lead">Iyuzeh source records for Open-angle glaucoma / ocular hypertension from Thea Pharma.</p>
</section>

{% assign program_documents = site.data.company_documents | where: "program", "Iyuzeh" %}
{% include document_list.html documents=program_documents sort_by="year" sort_dir="desc" match_summary_spacing=true %}
