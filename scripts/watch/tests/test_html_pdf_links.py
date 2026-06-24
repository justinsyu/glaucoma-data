"""Static HTML PDF link extractor: determinism + correctness fixtures."""

from __future__ import annotations

from glaucoma_watch.extractors.html_pdf_links import extract


SAMPLE_HTML = b"""
<html>
<body>
  <h2>Vabysmo Publications</h2>
  <a href="/pdf/one.pdf">Faricimab TENAYA 1-year</a>
  <a href="https://cdn.example.com/pdf/two.pdf">Faricimab LUCERNE 2-year</a>
  <a href="/pdf/two.pdf?utm_source=email">Faricimab LUCERNE 2-year (email tracking)</a>
  <a href="/research.html">Non-PDF link, must be ignored</a>
  <a href="/pdf/no-title.pdf"></a>
  <a href="/pdf/with-fragment.pdf#page=3">Slide deck</a>
</body>
</html>
"""


def test_extract_finds_pdfs_only():
    links = extract(body=SAMPLE_HTML, source_url="https://medinfo.example.com/vabysmo.html", config={})
    urls = [link.url for link in links]
    # Note: query-string variant resolves to a distinct URL, so dedupe is the
    # candidates layer's job, not the extractor's.
    assert "https://medinfo.example.com/pdf/one.pdf" in urls
    assert "https://cdn.example.com/pdf/two.pdf" in urls
    assert "https://medinfo.example.com/pdf/with-fragment.pdf#page=3" in urls
    assert "https://medinfo.example.com/research.html" not in urls


def test_extract_is_deterministic():
    a = extract(body=SAMPLE_HTML, source_url="https://medinfo.example.com/vabysmo.html", config={})
    b = extract(body=SAMPLE_HTML, source_url="https://medinfo.example.com/vabysmo.html", config={})
    assert [l.to_dict() for l in a] == [l.to_dict() for l in b]


def test_extract_sorted_by_url():
    links = extract(body=SAMPLE_HTML, source_url="https://medinfo.example.com/vabysmo.html", config={})
    urls = [link.url for link in links]
    assert urls == sorted(urls), "links must be sorted for snapshot stability"


def test_extract_resolves_titles_from_anchor_text():
    links = extract(body=SAMPLE_HTML, source_url="https://medinfo.example.com/vabysmo.html", config={})
    by_url = {link.url: link for link in links}
    assert by_url["https://medinfo.example.com/pdf/one.pdf"].title == "Faricimab TENAYA 1-year"
    assert by_url["https://medinfo.example.com/pdf/with-fragment.pdf#page=3"].title == "Slide deck"


def test_extract_falls_back_to_heading_when_anchor_has_no_text():
    html = b"""
    <html><body>
      <h3>Susvimo Refill Resources</h3>
      <div><a href='/sds.pdf'></a></div>
    </body></html>
    """
    links = extract(body=html, source_url="https://medinfo.example.com/susvimo.html", config={})
    assert len(links) == 1
    assert links[0].title == "Susvimo Refill Resources"


def test_extractor_config_can_restrict_via_regex():
    links = extract(
        body=SAMPLE_HTML,
        source_url="https://medinfo.example.com/vabysmo.html",
        config={"url_must_not_match": r"utm_source"},
    )
    urls = [link.url for link in links]
    assert all("utm_source" not in u for u in urls)
