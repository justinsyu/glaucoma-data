---
layout: default
title: "iDose TREX / GLK-102"
permalink: /programs/idose-trex-glk-102/
description: "iDose TREX / GLK-102 source records for Open-angle glaucoma / ocular hypertension from Glaukos."
company: "Glaukos"
company_slug: glaukos
---

<section class="hero">
  <h1>iDose TREX / GLK-102</h1>
  <p class="lead">iDose TREX / GLK-102 source records for Open-angle glaucoma / ocular hypertension from Glaukos.</p>
</section>

{% assign program_documents = site.data.company_documents | where: "program", "iDose TREX / GLK-102" %}
{% include document_list.html documents=program_documents sort_by="year" sort_dir="desc" match_summary_spacing=true %}
