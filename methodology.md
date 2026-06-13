---
layout: default
title: Plain Text vs PDF Search Test
permalink: /methodology/
description: Methodology for comparing AI search discovery of plain-text HTML pages against PDF-only publication.
published: false
---

<section class="hero">
  <h1>Plain Text vs PDF Search Test</h1>
  <p class="lead">This archive is structured to compare whether direct HTML text is discovered, retrieved, and cited more reliably than equivalent PDF-only content.</p>
</section>

## Archive Provenance

Each document page is generated from a cleaned Markdown extraction of a publicly linked source PDF. The HTML page is the canonical crawlable version; the linked plain-text file is a secondary machine-readable export. Document pages retain source filenames, source PDF URLs, company, program, indication, document type, year, and conference metadata where available.

The archive is maintained by Justin Yu in the public source repository linked in the site footer. Issues with extraction quality, source attribution, or metadata can be raised through that repository.

## Recommended Test Design

1. Publish each document as a canonical HTML page in this archive.
2. Publish a matched PDF-only version under a separate URL path.
3. Add a unique, harmless test phrase to each matched pair.
4. Submit the sitemap to Google Search Console and Bing Webmaster Tools.
5. Query exact phrases and document-specific facts in Google, Bing, ChatGPT Search, and Perplexity.
6. Record discovery date, indexed URL, snippet quality, citation behavior, and whether the answer uses the HTML page or the PDF.

## Metrics

- Time from publication to first crawl.
- Time from publication to first indexed result.
- Whether exact phrase search finds the page.
- Whether AI search cites the page.
- Whether metadata such as title, program, indication, year, and source filename appear in snippets or answers.
