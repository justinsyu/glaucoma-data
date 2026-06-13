---
layout: default
title: "OMNI Surgical System"
permalink: /programs/omni-surgical-system/
description: "OMNI Surgical System source records for Primary open-angle glaucoma from Sight Sciences."
company: "Sight Sciences"
company_slug: sight-sciences
---

<section class="hero">
  <h1>OMNI Surgical System</h1>
  <p class="lead">OMNI Surgical System source records for Primary open-angle glaucoma from Sight Sciences.</p>
</section>

{% assign program_documents = site.data.company_documents | where: "program", "OMNI Surgical System" %}
{% include document_list.html documents=program_documents sort_by="year" sort_dir="desc" match_summary_spacing=true %}
