from .base import EXTRACTOR_REGISTRY, ExtractedLink, Extractor, register
from . import html_pdf_links  # noqa: F401  registers static extractor
from . import html_pdf_links_js  # noqa: F401  registers JS-rendering extractor
from . import playwright_hcp  # noqa: F401  registers HCP/Akamai click-through extractor
from . import playwright_loadmore  # noqa: F401  registers Load-More clicker extractor

__all__ = ["EXTRACTOR_REGISTRY", "ExtractedLink", "Extractor", "register"]
