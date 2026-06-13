---
layout: default
title: "iStent infinite"
permalink: /programs/istent-infinite/
description: "iStent infinite source records for Primary open-angle glaucoma from Glaukos."
company: "Glaukos"
company_slug: glaukos
---

<section class="hero">
  <h1>iStent infinite</h1>
  <p class="lead">iStent infinite source records for Primary open-angle glaucoma from Glaukos.</p>
</section>

{% assign program_documents = site.data.company_documents | where: "program", "iStent infinite" %}
{% include document_list.html documents=program_documents sort_by="year" sort_dir="desc" match_summary_spacing=true %}
