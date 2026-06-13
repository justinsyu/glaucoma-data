---
layout: default
title: "Nicotinamide / Pyruvate"
permalink: /programs/nicotinamide-pyruvate/
description: "Nicotinamide / Pyruvate source records for Glaucoma neuroprotection / disease modification from Neurotech / Stanford."
company: "Neurotech / Stanford"
company_slug: neurotech-stanford
---

<section class="hero">
  <h1>Nicotinamide / Pyruvate</h1>
  <p class="lead">Nicotinamide / Pyruvate source records for Glaucoma neuroprotection / disease modification from Neurotech / Stanford.</p>
</section>

{% assign program_documents = site.data.company_documents | where: "program", "Nicotinamide / Pyruvate" %}
{% include document_list.html documents=program_documents sort_by="year" sort_dir="desc" match_summary_spacing=true %}
