"""Watchlist schema validation."""

from __future__ import annotations

import pytest
from retina_watch.watchlist import SourceEntry


def test_minimal_valid_entry():
    e = SourceEntry(
        source_id="acme-product-host",
        company_slug="acme",
        source_type="html_pdf_links",
        url="https://example.com/publications",
    )
    assert e.enabled is True
    assert e.manual_review is False
    assert e.render == "static"


def test_source_id_rejects_whitespace():
    with pytest.raises(ValueError):
        SourceEntry(
            source_id="bad id",
            company_slug="acme",
            source_type="html_pdf_links",
            url="https://example.com",
        )


def test_source_id_rejects_empty():
    with pytest.raises(ValueError):
        SourceEntry(
            source_id="",
            company_slug="acme",
            source_type="html_pdf_links",
            url="https://example.com",
        )
