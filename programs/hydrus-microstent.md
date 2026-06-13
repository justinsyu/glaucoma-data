---
layout: default
title: "Hydrus Microstent"
permalink: /programs/hydrus-microstent/
description: "Hydrus Microstent source records for Mild to moderate primary open-angle glaucoma from Alcon."
company: "Alcon"
company_slug: alcon
---

<section class="hero">
  <h1>Hydrus Microstent</h1>
  <p class="lead">Hydrus Microstent source records for Mild to moderate primary open-angle glaucoma from Alcon.</p>
</section>

{% assign program_documents = site.data.company_documents | where: "program", "Hydrus Microstent" %}
{% include document_list.html documents=program_documents sort_by="year" sort_dir="desc" match_summary_spacing=true %}
