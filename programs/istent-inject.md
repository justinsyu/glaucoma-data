---
layout: default
title: "iStent inject"
permalink: /programs/istent-inject/
description: "iStent inject source records for Mild to moderate primary open-angle glaucoma from Glaukos."
company: "Glaukos"
company_slug: glaukos
---

<section class="hero">
  <h1>iStent inject</h1>
  <p class="lead">iStent inject source records for Mild to moderate primary open-angle glaucoma from Glaukos.</p>
</section>

{% assign program_documents = site.data.company_documents | where: "program", "iStent inject" %}
{% include document_list.html documents=program_documents sort_by="year" sort_dir="desc" match_summary_spacing=true %}
