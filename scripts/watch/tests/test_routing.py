"""title_filter + dest_router unit tests."""

from __future__ import annotations

from glaucoma_watch.extractors.base import ExtractedLink
from glaucoma_watch.routing import apply_routing
from glaucoma_watch.watchlist import RouterRule, SourceEntry


def _src(**kw) -> SourceEntry:
    defaults = dict(
        source_id="x",
        company_slug="acme",
        source_type="html_pdf_links",
        url="https://example.com",
    )
    defaults.update(kw)
    return SourceEntry(**defaults)


def _link(url: str, title: str | None = None) -> ExtractedLink:
    return ExtractedLink(url=url, title=title)


def test_no_filter_no_router_returns_input_unchanged():
    src = _src()
    links = [_link("https://example.com/a.pdf", "A")]
    out = apply_routing(src, links)
    assert [l.url for l in out] == [l.url for l in links]
    assert out[0].extras == {}


def test_title_filter_drops_off_program_links():
    src = _src(title_filter=r"(?i)faricimab|vabysmo")
    links = [
        _link("https://x.com/faricimab-tenaya.pdf", "Faricimab TENAYA"),
        _link("https://x.com/dextenza.pdf", "DEXTENZA cataract"),
    ]
    out = apply_routing(src, links)
    assert len(out) == 1
    assert "faricimab" in out[0].url.lower()


def test_dest_router_sets_suggested_dest():
    src = _src(
        dest="default/",
        dest_router=[
            RouterRule(pattern=r"(?i)4d-150", dest="companies/4dmt/4d_150/posters/"),
            RouterRule(pattern=r"(?i)4d-310", dest="companies/4dmt/4d_310/posters/"),
        ],
    )
    links = [
        _link("https://x.com/4d-150-prism.pdf", "PRISM 4D-150"),
        _link("https://x.com/4d-310-fabry.pdf", "4D-310 Fabry"),
        _link("https://x.com/about.pdf", "company overview"),
    ]
    out = apply_routing(src, links)
    by_url = {l.url: l for l in out}
    assert by_url["https://x.com/4d-150-prism.pdf"].extras["suggested_dest"] == "companies/4dmt/4d_150/posters/"
    assert by_url["https://x.com/4d-310-fabry.pdf"].extras["suggested_dest"] == "companies/4dmt/4d_310/posters/"
    # Unrouted link falls back to entry.dest
    assert by_url["https://x.com/about.pdf"].extras["suggested_dest"] == "default/"


def test_title_router_precedes_dest_router():
    src = _src(
        dest="default-posters/",
        dest_router=[RouterRule(pattern=r".*", dest="default-posters/")],
        title_router=[RouterRule(pattern=r"(?i)journal|publication", dest="manuscripts/")],
    )
    links = [
        _link("https://x.com/abc.pdf", "Journal of Ophthalmology article"),
        _link("https://x.com/def.pdf", "ARVO 2024 Poster"),
    ]
    out = apply_routing(src, links)
    by_url = {l.url: l for l in out}
    assert by_url["https://x.com/abc.pdf"].extras["suggested_dest"] == "manuscripts/"
    assert by_url["https://x.com/def.pdf"].extras["suggested_dest"] == "default-posters/"


def test_invalid_title_filter_regex_logged_and_continues():
    src = _src(title_filter=r"[unclosed")
    links = [_link("https://x.com/a.pdf", "A")]
    out = apply_routing(src, links)
    # Should not drop anything: invalid pattern is treated as no filter.
    assert len(out) == 1
