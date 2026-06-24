"""Worklist writer tests."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from glaucoma_watch import worklist as wl_mod
from glaucoma_watch.extractors.base import ExtractedLink
from glaucoma_watch.watchlist import SourceEntry
from glaucoma_watch.worklist import maybe_emit_worklist


@pytest.fixture
def repo_root_tmp(monkeypatch):
    tmp = Path(tempfile.mkdtemp())
    monkeypatch.setattr(wl_mod, "repo_root", lambda: tmp)
    return tmp


def _src(**kw) -> SourceEntry:
    defaults = dict(
        source_id="acme-worklist-source",
        company_slug="acme",
        source_type="playwright_hcp",
        url="https://example.com",
    )
    defaults.update(kw)
    return SourceEntry(**defaults)


def test_non_discovery_only_is_noop(repo_root_tmp):
    src = _src(discovery_only=False)
    links = [ExtractedLink(url="https://x.com/a.pdf", title="A")]
    n = maybe_emit_worklist(entry=src, run_id="r1", links=links)
    assert n == 0
    assert not any(repo_root_tmp.rglob("_worklist_pending_*.md"))


def test_discovery_only_without_dest_worklist_logs_and_skips(repo_root_tmp):
    src = _src(discovery_only=True, dest_worklist=None)
    links = [ExtractedLink(url="https://x.com/a.pdf", title="A")]
    n = maybe_emit_worklist(entry=src, run_id="r1", links=links)
    assert n == 0


def test_discovery_only_appends_rows(repo_root_tmp):
    src = _src(
        discovery_only=True,
        dest_worklist="companies/acme/_worklist_pending_hcp.md",
        dest="companies/acme/program/presentations_posters/",
    )
    links = [
        ExtractedLink(url="https://x.com/a.pdf", title="Title A"),
        ExtractedLink(url="https://x.com/b.pdf", title="Title B"),
    ]
    n = maybe_emit_worklist(entry=src, run_id="r1", links=links)
    assert n == 2
    p = repo_root_tmp / "companies/acme/_worklist_pending_hcp.md"
    assert p.is_file()
    text = p.read_text(encoding="utf-8")
    assert "Title A" in text
    assert "Title B" in text
    assert "r1" in text
    assert "manual HCP retrieval" in text


def test_subsequent_runs_append_without_duplicating_header(repo_root_tmp):
    src = _src(
        discovery_only=True,
        dest_worklist="companies/acme/_worklist_pending_hcp.md",
    )
    maybe_emit_worklist(entry=src, run_id="r1", links=[ExtractedLink(url="https://x.com/a.pdf", title="A")])
    maybe_emit_worklist(entry=src, run_id="r2", links=[ExtractedLink(url="https://x.com/b.pdf", title="B")])
    p = repo_root_tmp / "companies/acme/_worklist_pending_hcp.md"
    text = p.read_text(encoding="utf-8")
    # Header should appear once
    assert text.count("# Worklist") == 1
    assert "Title A" not in text  # we used "A" / "B" as titles
    assert "**A**" in text and "**B**" in text
    assert "r1" in text and "r2" in text
