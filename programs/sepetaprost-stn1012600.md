---
layout: default
title: "Sepetaprost / STN1012600"
permalink: /programs/sepetaprost-stn1012600/
description: "Sepetaprost / STN1012600 source records for Glaucoma / ocular hypertension from Santen / UBE."
company: "Santen / UBE"
company_slug: santen-ube
---

<section class="hero">
  <h1>Sepetaprost / STN1012600</h1>
  <p class="lead">Sepetaprost / STN1012600 source records for Glaucoma / ocular hypertension from Santen / UBE.</p>
</section>

{% assign program_documents = site.data.company_documents | where: "program", "Sepetaprost / STN1012600" %}
{% include document_list.html documents=program_documents sort_by="year" sort_dir="desc" match_summary_spacing=true %}
