---
layout: default
title: "iDose TR"
permalink: /programs/idose-tr/
description: "iDose TR source records for Open-angle glaucoma / ocular hypertension from Glaukos."
company: "Glaukos"
company_slug: glaukos
---

<section class="hero">
  <h1>iDose TR</h1>
  <p class="lead">iDose TR source records for Open-angle glaucoma / ocular hypertension from Glaukos.</p>
</section>

{% assign program_documents = site.data.company_documents | where: "program", "iDose TR" %}
{% include document_list.html documents=program_documents sort_by="year" sort_dir="desc" match_summary_spacing=true %}
