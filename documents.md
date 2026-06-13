---
layout: default
title: Documents
permalink: /documents/
description: Canonical complete list of source records in the Glaucoma Data Archive.
---

<section class="hero">
  <h1>Documents</h1>
  <p class="lead">This is the canonical complete source index for the archive. Each record uses its sponsor's palette so approved and investigational glaucoma treatment records can be scanned by company.</p>
</section>

{% include document_list.html documents=site.data.company_documents sort_by="title" sort_dir="asc" match_summary_spacing=true %}
