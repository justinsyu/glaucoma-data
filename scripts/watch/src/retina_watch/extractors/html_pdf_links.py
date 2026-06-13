"""Generic HTML extractor that pulls PDF anchors out of a page.

This is the default extractor for medinfo / publications portal pages where
documents are exposed as ``<a href="*.pdf">Title</a>`` lists. The title is
inferred from the anchor's visible text, then the surrounding caption (``aria-label``,
nearest preceding heading) as a fallback.

Configurable via the watchlist entry's ``extractor_config``:

* ``link_selector`` (default ``a[href]``): CSS selector for the anchors to consider.
* ``url_must_match`` (default ``r"\\.pdf(?:[?#].*)?$"``): regex applied to the
  resolved href to decide whether the link is in scope.
* ``url_must_not_match`` (default None): optional regex that excludes matches.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import ExtractedLink, register


DEFAULT_URL_PATTERN = re.compile(r"\.pdf(?:[?#].*)?$", re.IGNORECASE)


def _resolve_title(anchor) -> str | None:
    text = (anchor.get_text(" ", strip=True) or "").strip()
    if text:
        return text
    for attr in ("aria-label", "title"):
        v = anchor.get(attr)
        if v:
            return v.strip()
    parent = anchor.find_parent()
    if parent is not None:
        heading = parent.find_previous(["h1", "h2", "h3", "h4", "h5", "h6"])
        if heading is not None:
            return heading.get_text(" ", strip=True) or None
    return None


@register("html_pdf_links")
def extract(*, body: bytes, source_url: str, config: dict) -> list[ExtractedLink]:
    selector = config.get("link_selector", "a[href]")
    url_must_match = config.get("url_must_match")
    url_must_not_match = config.get("url_must_not_match")

    match_re = re.compile(url_must_match, re.IGNORECASE) if url_must_match else DEFAULT_URL_PATTERN
    exclude_re = re.compile(url_must_not_match, re.IGNORECASE) if url_must_not_match else None

    soup = BeautifulSoup(body or b"", "lxml")
    out: dict[str, ExtractedLink] = {}

    for anchor in soup.select(selector):
        href = (anchor.get("href") or "").strip()
        if not href:
            continue
        absolute = urljoin(source_url, href)
        if not match_re.search(absolute):
            continue
        if exclude_re is not None and exclude_re.search(absolute):
            continue
        title = _resolve_title(anchor)
        if absolute in out:
            existing = out[absolute]
            if not existing.title and title:
                out[absolute] = ExtractedLink(url=absolute, title=title)
            continue
        out[absolute] = ExtractedLink(url=absolute, title=title)

    return sorted(out.values(), key=lambda link: link.url)
