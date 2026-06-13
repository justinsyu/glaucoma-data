---
layout: default
title: "Rocklatan"
permalink: /programs/rocklatan/
description: "Rocklatan source records for Open-angle glaucoma / ocular hypertension from Alcon."
company: "Alcon"
company_slug: alcon
---

<section class="hero">
  <h1>Rocklatan</h1>
  <p class="lead">Rocklatan source records for Open-angle glaucoma / ocular hypertension from Alcon.</p>
</section>

{% assign program_documents = site.data.company_documents | where: "program", "Rocklatan" %}
{% include document_list.html documents=program_documents sort_by="year" sort_dir="desc" match_summary_spacing=true %}
