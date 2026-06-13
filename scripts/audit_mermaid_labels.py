"""
Scan every mermaid code fence in the repo for nodes with empty labels.

A mermaid node like `W0(( ))` (empty parentheses with optional whitespace) is
syntactically valid but renders as an unlabelled circle, so the reader cannot
tell what it represents. The same problem can appear with `Foo[ ]` (empty
square label) and `Foo{ }` (empty diamond/decision label).

This script:
  1. Walks every .md file under companies/ and infographics/.
  2. For each mermaid fence, finds empty-label patterns inside that block.
  3. Proposes a label per pattern:
       * `W<digits>(( ))`  ->  ((<digits>))
       * `Q<digits>W(( ))` ->  ((Q<digits>W))
       * any other `<ID>(( ))`, `<ID>[ ]`, `<ID>{ }` -> ((<ID>)) / [<ID>] / {<ID>}
  4. With --apply, rewrites the files in place. Without --apply, prints a
     dry-run report grouped by file.

Usage:
    python scripts/audit_mermaid_labels.py            # dry run
    python scripts/audit_mermaid_labels.py --apply    # write changes
"""
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Match an entire ```mermaid ... ``` block (multiline, non-greedy).
MERMAID_RE = re.compile(r"```mermaid\r?\n(.*?)\r?\n```", re.DOTALL)

# An empty label is the surface form `(( ))`, `[ ]`, or `{ }` (any whitespace
# inside, including none).  We match a node ID immediately before it.  The ID
# may be letters, digits, underscores.
EMPTY_CIRCLE_RE = re.compile(r"(\b[A-Za-z][A-Za-z0-9_]*)\(\(\s*\)\)")
EMPTY_SQUARE_RE = re.compile(r"(\b[A-Za-z][A-Za-z0-9_]*)\[\s*\]")
EMPTY_DIAMOND_RE = re.compile(r"(\b[A-Za-z][A-Za-z0-9_]*)\{\s*\}")


def fix_block(block_text: str) -> tuple[str, list[tuple[str, str]], list[str]]:
    """Returns (new_block, applied_changes, unhandled_warnings).

    Only `W<digits>(( ))` is auto-fixed (visit-week circles). Other empty
    label shapes are reported as warnings so the surrounding context can be
    used to write an informative label by hand.
    """
    changes: list[tuple[str, str]] = []
    warnings: list[str] = []

    def _replace_w_circle(m):
        nid = m.group(1)
        digits_m = re.fullmatch(r"W(\d+)", nid)
        old = m.group(0)
        if digits_m:
            new = f"{nid}(({digits_m.group(1)}))"
            changes.append((old, new))
            return new
        warnings.append(f"empty circle on non-week node: {old}")
        return old

    out = EMPTY_CIRCLE_RE.sub(_replace_w_circle, block_text)

    for m in EMPTY_SQUARE_RE.finditer(out):
        warnings.append(f"empty square: {m.group(0)}")
    for m in EMPTY_DIAMOND_RE.finditer(out):
        warnings.append(f"empty diamond: {m.group(0)}")

    return out, changes, warnings


def process_file(path: Path, apply: bool) -> tuple[list[tuple[str, str]], list[str]]:
    text = path.read_text(encoding="utf-8")
    file_changes: list[tuple[str, str]] = []
    file_warnings: list[str] = []

    def _rewrite(m):
        block = m.group(1)
        new_block, changes, warnings = fix_block(block)
        file_changes.extend(changes)
        file_warnings.extend(warnings)
        return f"```mermaid\n{new_block}\n```"

    new_text = MERMAID_RE.sub(_rewrite, text)
    if apply and new_text != text:
        path.write_text(new_text, encoding="utf-8", newline="\n")
    return file_changes, file_warnings


def main():
    apply = "--apply" in sys.argv
    targets = []
    # company-documents/*.md is what Jekyll actually renders. companies/**/*.md
    # is the raw upstream extract; keep both in sync so future re-syncs do not
    # regress the fix.
    for d in ("companies", "company-documents", "infographics"):
        base = ROOT / d
        if not base.exists():
            continue
        for p in base.rglob("*.md"):
            targets.append(p)

    total_changes = 0
    files_touched = 0
    total_warnings = 0
    for p in sorted(targets):
        changes, warnings = process_file(p, apply)
        rel = p.relative_to(ROOT).as_posix()
        if changes:
            files_touched += 1
            total_changes += len(changes)
            print(f"{rel}: {len(changes)} W-week fix(es)")
            for old, new in changes[:6]:
                print(f"    {old}   ->   {new}")
            if len(changes) > 6:
                print(f"    ... and {len(changes) - 6} more")
        if warnings:
            total_warnings += len(warnings)
            print(f"{rel}: {len(warnings)} unhandled empty label(s) (need manual review)")
            for w in warnings[:8]:
                print(f"    {w}")
            if len(warnings) > 8:
                print(f"    ... and {len(warnings) - 8} more")
    mode = "applied" if apply else "dry-run"
    print()
    print(f"{mode}: {total_changes} W-week fix(es) across {files_touched} file(s); "
          f"{total_warnings} other empty label(s) need manual review")


if __name__ == "__main__":
    main()
