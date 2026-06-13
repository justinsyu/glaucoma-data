---
layout: default
title: "OTX-TIC"
permalink: /programs/otx-tic/
description: "OTX-TIC source records for Open-angle glaucoma / ocular hypertension from Ocular Therapeutix."
company: "Ocular Therapeutix"
company_slug: ocular-therapeutix
---

<section class="hero">
  <h1>OTX-TIC</h1>
  <p class="lead">OTX-TIC source records for Open-angle glaucoma / ocular hypertension from Ocular Therapeutix.</p>
</section>

{% assign program_documents = site.data.company_documents | where: "program", "OTX-TIC" %}
{% include document_list.html documents=program_documents sort_by="year" sort_dir="desc" match_summary_spacing=true %}
