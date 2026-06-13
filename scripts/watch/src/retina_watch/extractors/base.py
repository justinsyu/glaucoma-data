"""Extractor protocol and registry.

An extractor takes the body of a fetched page and returns a deterministic list
of ``ExtractedLink`` records. Determinism rules:

* Output is sorted by URL.
* No timestamps in the link record itself.
* The same input bytes must always produce the same output.

Extractors register themselves via the ``@register`` decorator so the watchlist
``source_type`` field can dispatch to the right implementation without an
explicit if/elif tree.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Callable, Protocol


@dataclass(frozen=True)
class ExtractedLink:
    url: str
    title: str | None = None
    extras: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


class Extractor(Protocol):
    def __call__(self, *, body: bytes, source_url: str, config: dict) -> list[ExtractedLink]: ...


EXTRACTOR_REGISTRY: dict[str, Extractor] = {}


def register(name: str) -> Callable[[Extractor], Extractor]:
    def _inner(fn: Extractor) -> Extractor:
        if name in EXTRACTOR_REGISTRY:
            raise ValueError(f"extractor {name!r} already registered")
        EXTRACTOR_REGISTRY[name] = fn
        return fn

    return _inner
