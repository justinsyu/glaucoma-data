---
layout: default
title: "Reformulated PG324"
permalink: /programs/reformulated-pg324/
description: "Reformulated PG324 source records for Open-angle glaucoma / ocular hypertension from Alcon."
company: "Alcon"
company_slug: alcon
---

<section class="hero">
  <h1>Reformulated PG324</h1>
  <p class="lead">Reformulated PG324 source records for Open-angle glaucoma / ocular hypertension from Alcon.</p>
</section>

{% assign program_documents = site.data.company_documents | where: "program", "Reformulated PG324" %}
{% include document_list.html documents=program_documents sort_by="year" sort_dir="desc" match_summary_spacing=true %}
