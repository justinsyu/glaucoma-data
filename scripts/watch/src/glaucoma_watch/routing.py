"""Post-extraction routing and filtering.

Once a driver has returned its ``ExtractedLink`` records, two transformations
may apply before the snapshot is written:

1. **title_filter**: a case-insensitive regex applied to ``f"{url} {title}"``.
   Links that do not match are dropped. Used to confine a shared source page
   (e.g., Clearside, which hosts CLS-TA and DEXTENZA alongside CLS-AX) to the
   program slice the watchlist entry is about.

2. **dest_router / title_router**: a list of ``(pattern, dest)`` rules. The
   first rule whose regex matches sets ``ExtractedLink.extras['suggested_dest']``
   to the matching destination folder. ``title_router`` is applied first so
   manuscripts can be routed away from posters even when both live on the
   same source page; ``dest_router`` is the fallback. If no rule matches and
   the watchlist entry has a default ``dest``, that wins; otherwise the
   suggested_dest field is left unset.

The transformation is library-shaped so it can be called from the pipeline,
a Dagster asset, or a unit test.
"""

from __future__ import annotations

import re
from dataclasses import replace

from .extractors.base import ExtractedLink
from .logging_setup import get_logger
from .watchlist import RouterRule, SourceEntry


def _compile_rules(rules: list[RouterRule]) -> list[tuple[re.Pattern, str]]:
    return [(re.compile(r.pattern, re.IGNORECASE), r.dest) for r in rules]


def apply_routing(entry: SourceEntry, links: list[ExtractedLink]) -> list[ExtractedLink]:
    """Apply title_filter and dest_router/title_router to ``links``.

    Returns a new list; the input is not mutated. ``ExtractedLink`` is frozen,
    so each match returns a fresh record with updated ``extras``.
    """
    if not links:
        return links

    log = get_logger().bind(source_id=entry.source_id)

    if entry.title_filter:
        try:
            title_re = re.compile(entry.title_filter, re.IGNORECASE)
        except re.error as exc:
            log.error("title_filter_invalid_regex", pattern=entry.title_filter, error=str(exc))
            title_re = None
    else:
        title_re = None

    title_rules = _compile_rules(entry.title_router or [])
    dest_rules = _compile_rules(entry.dest_router or [])

    out: list[ExtractedLink] = []
    dropped = 0
    routed = 0
    for link in links:
        needle = f"{link.url} {link.title or ''}"
        if title_re is not None and not title_re.search(needle):
            dropped += 1
            continue

        suggested_dest = entry.dest
        for pat, dest in title_rules:
            if pat.search(needle):
                suggested_dest = dest
                break
        else:
            for pat, dest in dest_rules:
                if pat.search(needle):
                    suggested_dest = dest
                    break

        if suggested_dest:
            new_extras = dict(link.extras)
            new_extras["suggested_dest"] = suggested_dest
            link = replace(link, extras=new_extras)
            routed += 1
        out.append(link)

    if dropped or routed:
        log.info("routing_applied", dropped=dropped, routed=routed, kept=len(out))
    return out
