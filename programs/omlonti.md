---
layout: default
title: "Omlonti"
permalink: /programs/omlonti/
description: "Omlonti source records for Primary open-angle glaucoma / ocular hypertension from Santen / UBE."
company: "Santen / UBE"
company_slug: santen-ube
---

<section class="hero">
  <h1>Omlonti</h1>
  <p class="lead">Omlonti source records for Primary open-angle glaucoma / ocular hypertension from Santen / UBE.</p>
</section>

{% assign program_documents = site.data.company_documents | where: "program", "Omlonti" %}
{% include document_list.html documents=program_documents sort_by="year" sort_dir="desc" match_summary_spacing=true %}
