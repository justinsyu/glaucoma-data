---
layout: default
title: "Durysta"
permalink: /programs/durysta/
description: "Durysta source records for Open-angle glaucoma / ocular hypertension from AbbVie / Allergan."
company: "AbbVie / Allergan"
company_slug: abbvie-allergan
---

<section class="hero">
  <h1>Durysta</h1>
  <p class="lead">Durysta source records for Open-angle glaucoma / ocular hypertension from AbbVie / Allergan.</p>
</section>

{% assign program_documents = site.data.company_documents | where: "program", "Durysta" %}
{% include document_list.html documents=program_documents sort_by="year" sort_dir="desc" match_summary_spacing=true %}
