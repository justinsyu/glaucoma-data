---
layout: default
title: "Vyzulta"
permalink: /programs/vyzulta/
description: "Vyzulta source records for Open-angle glaucoma / ocular hypertension from Bausch + Lomb / Nicox."
company: "Bausch + Lomb / Nicox"
company_slug: bausch-lomb-nicox
---

<section class="hero">
  <h1>Vyzulta</h1>
  <p class="lead">Vyzulta source records for Open-angle glaucoma / ocular hypertension from Bausch + Lomb / Nicox.</p>
</section>

{% assign program_documents = site.data.company_documents | where: "program", "Vyzulta" %}
{% include document_list.html documents=program_documents sort_by="year" sort_dir="desc" match_summary_spacing=true %}
