"""
Static guard for the document-action button blocks across the archive.

The three layouts that render the colored action-button row on top of a
document or infographic page are:

    _layouts/document.html                     (4DMT cleaned_markdown docs)
    _layouts/document_infographic.html         (infographics/)
    _layouts/company_document_placeholder.html (company-documents/)

Each wraps its `<a class="button ...">` calls in Liquid guards like
`{% if page.pdf_url %}`. Liquid treats `""` as truthy, so a frontmatter entry
of `pdf_url: ""` would emit `<a href="">View PDF</a>`, which the browser
resolves to the current page URL. The OPTIC infographic surfaced this on
2026-05-27 (https://justinsyu.github.io/retina-data/infographics/adverum-ixo-vec-the-optic-study-of-intravitreal-gene-therapy-with-advm-022-for-neovascular-amd-n/).

This script:
  1. Confirms every conditional that emits a `<a class="button">` for an
     external href in the three layouts uses an explicit `!= ""` guard.
  2. Walks every page using those layouts and lists how many would have
     emitted a self-linking button under the old (un-guarded) Liquid.

The first check is the hard pass/fail. The second is informational, so the
size of the affected surface is visible when the layouts are touched again.

Usage:
    python scripts/audit_document_action_links.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LAYOUTS = REPO_ROOT / "_layouts"

# (layout file, frontmatter field that supplies the href, action-button label)
GUARDS = [
    ("document_infographic.html", "source_url",        "Back to source document"),
    ("document_infographic.html", "pdf_url",           "View PDF"),
    ("document.html",             "pdf_url",           "View PDF"),
    ("document.html",             "plain_text_url",    "View plain text"),
    ("company_document_placeholder.html", "source_url", "View source"),
]

# Pages whose frontmatter, under the OLD un-guarded Liquid, would have
# emitted a button with href="".
PAGE_SETS = [
    # (folder, expected layout, list of fields that drive a button href)
    ("infographics",       "document_infographic",
        ["source_url", "pdf_url"]),
    ("company-documents",  "company_document_placeholder",
        ["source_url"]),
]

CLEANED_MARKDOWN_GLOB = "companies/**/cleaned_markdown/*.md"
CLEANED_MARKDOWN_FIELDS = ["pdf_url", "plain_text_url"]

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
FIELD_RE = re.compile(r'^(?P<key>[A-Za-z_][\w-]*)\s*:\s*(?P<val>.*?)\s*$')


def parse_frontmatter(text: str) -> dict[str, str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}
    out: dict[str, str] = {}
    for line in match.group(1).splitlines():
        m = FIELD_RE.match(line)
        if not m:
            continue
        val = m.group("val")
        if val.startswith('"') and val.endswith('"'):
            val = val[1:-1]
        elif val.startswith("'") and val.endswith("'"):
            val = val[1:-1]
        out[m.group("key")] = val
    return out


def check_layout_guards() -> list[str]:
    """For each (layout, field) pair the layout must reference the field
    inside an `{% if X and X != "" %}` (or equivalent non-empty check)."""
    failures: list[str] = []
    for layout_name, field, label in GUARDS:
        path = LAYOUTS / layout_name
        if not path.exists():
            failures.append(f"missing layout: {layout_name}")
            continue
        body = path.read_text(encoding="utf-8")
        # The accepted forms of a guard are either:
        #   {% if page.<field> and page.<field> != "" %}
        #   {% if page.<field> != "" %}
        #   {% if page.<field> != "" and page.<field> %}
        # Liquid does not coerce "" to false, so a bare `{% if page.<field> %}`
        # is not sufficient.
        nonempty = re.compile(
            r'\{%\s*if[^%]*?page\.' + re.escape(field)
            + r'[^%]*?!=\s*""[^%]*?%\}'
        )
        bare = re.compile(
            r'\{%\s*if\s+page\.' + re.escape(field) + r'\s*%\}'
        )
        if bare.search(body) and not nonempty.search(body):
            failures.append(
                f"{layout_name}: `{{% if page.{field} %}}` is not guarded with "
                f"`!= \"\"` (would emit `<a href=\"\">{label}</a>` when blank)"
            )
        elif not nonempty.search(body):
            # The layout may have removed the reference entirely, in which
            # case neither the button nor the bug exists; that is allowed.
            pass
    return failures


def count_empty_value_pages() -> dict[str, int]:
    counts: dict[str, int] = {}
    for folder, expected_layout, fields in PAGE_SETS:
        for path in sorted((REPO_ROOT / folder).glob("*.md")):
            text = path.read_text(encoding="utf-8")
            meta = parse_frontmatter(text)
            layout = meta.get("layout", "")
            if layout != expected_layout:
                continue
            for field in fields:
                if field in meta and meta[field] == "":
                    key = f"{folder}: empty {field}"
                    counts[key] = counts.get(key, 0) + 1

    for path in sorted(REPO_ROOT.glob(CLEANED_MARKDOWN_GLOB)):
        text = path.read_text(encoding="utf-8")
        meta = parse_frontmatter(text)
        if meta.get("layout") != "document":
            continue
        for field in CLEANED_MARKDOWN_FIELDS:
            if field in meta and meta[field] == "":
                key = f"cleaned_markdown: empty {field}"
                counts[key] = counts.get(key, 0) + 1
    return counts


def main() -> int:
    failures = check_layout_guards()
    counts = count_empty_value_pages()

    if counts:
        print("Pages whose frontmatter has an empty action-button URL "
              "(buttons must be suppressed by the layout):")
        for key, n in sorted(counts.items()):
            print(f"  {key}: {n}")
        print()

    if failures:
        print("FAIL: action-button guard is missing in one or more layouts.")
        print("      Without an explicit `!= \"\"` check, Liquid will emit")
        print("      `<a href=\"\">` for blank frontmatter URLs, which the")
        print("      browser resolves to the current page.\n")
        for f in failures:
            print(f"  {f}")
        return 1

    print("OK: every action-button conditional that emits an external href "
          "uses an `!= \"\"` guard.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
