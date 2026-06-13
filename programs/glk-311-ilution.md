---
layout: default
title: "GLK-311 iLution"
permalink: /programs/glk-311-ilution/
description: "GLK-311 iLution source records for Open-angle glaucoma / ocular hypertension from Glaukos."
company: "Glaukos"
company_slug: glaukos
---

<section class="hero">
  <h1>GLK-311 iLution</h1>
  <p class="lead">GLK-311 iLution source records for Open-angle glaucoma / ocular hypertension from Glaukos.</p>
</section>

{% assign program_documents = site.data.company_documents | where: "program", "GLK-311 iLution" %}
{% include document_list.html documents=program_documents sort_by="year" sort_dir="desc" match_summary_spacing=true %}
