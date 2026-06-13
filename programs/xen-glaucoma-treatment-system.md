---
layout: default
title: "XEN Glaucoma Treatment System"
permalink: /programs/xen-glaucoma-treatment-system/
description: "XEN Glaucoma Treatment System source records for Refractory glaucoma from AbbVie / Allergan."
company: "AbbVie / Allergan"
company_slug: abbvie-allergan
---

<section class="hero">
  <h1>XEN Glaucoma Treatment System</h1>
  <p class="lead">XEN Glaucoma Treatment System source records for Refractory glaucoma from AbbVie / Allergan.</p>
</section>

{% assign program_documents = site.data.company_documents | where: "program", "XEN Glaucoma Treatment System" %}
{% include document_list.html documents=program_documents sort_by="year" sort_dir="desc" match_summary_spacing=true %}
