"""
Lightweight preview server for infographic pages.

Renders only the pages under /infographics/ in a stripped-down Jekyll-like
shell so the user can verify chart rendering, typography, and company-color
theming without installing Ruby/Jekyll. The Jekyll Liquid pipeline is NOT
replicated; this only does enough work to render an infographic page body
inside the same layout shell, with the same CSS variables on <body>.

Usage:
    python scripts/preview_infographic.py
Then open http://localhost:4001/

This is a verification tool, not a substitute for `jekyll serve`.
"""
import http.server
import json
import os
import re
import socketserver
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE_CSS = (ROOT / "assets" / "css" / "site.css").read_text(encoding="utf-8")
CHART_JS = (ROOT / "assets" / "js" / "infographic-charts.js").read_text(encoding="utf-8")
COMPANY_PROFILES = json.loads(
    (ROOT / "_data" / "company_profiles.json").read_text(encoding="utf-8")
)
PROFILE_BY_SLUG = {p["slug"]: p for p in COMPANY_PROFILES}


def parse_frontmatter(text):
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    raw_fm = text[3:end].strip()
    body = text[end + 4 :].lstrip("\n")
    fm = {}
    for line in raw_fm.splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        val = val.strip().strip('"').strip("'")
        fm[key.strip()] = val
    return fm, body


def render_page(md_path: Path):
    text = md_path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)
    slug = fm.get("company_slug", "")
    profile = PROFILE_BY_SLUG.get(slug, {})

    primary = profile.get("primary", "#06254A")
    secondary = profile.get("secondary", "#1C71ED")
    accent = profile.get("accent", "#EA18A8")
    highlight = profile.get("highlight", "#22B3CD")
    bg_image = profile.get("background_image", "")
    code = profile.get("code", "DOC")
    company_name = fm.get("company") or profile.get("name", "Unknown sponsor")
    title = fm.get("title", md_path.stem)
    source_url = fm.get("source_url", "")
    program = fm.get("program", "")
    indication = fm.get("indication", "")
    year = fm.get("year", "")
    conference = fm.get("conference", "")
    doc_type = fm.get("document_type", "")
    pdf_url = fm.get("pdf_url", "")

    body_style = (
        f"--company-primary: {primary}; "
        f"--company-secondary: {secondary}; "
        f"--company-accent: {accent}; "
        f"--company-highlight: {highlight}; "
    )
    if bg_image:
        body_style += f"--company-bg: url('{bg_image}');"

    meta_blocks = []
    if program:
        meta_blocks.append(f"<div><dt>Program</dt><dd>{program}</dd></div>")
    if indication:
        meta_blocks.append(f"<div><dt>Indication</dt><dd>{indication}</dd></div>")
    if conference:
        meta_blocks.append(f"<div><dt>Conference</dt><dd>{conference}</dd></div>")
    metadata_html = "".join(meta_blocks)

    eyebrow = "Infographic"
    if doc_type:
        eyebrow += f" &middot; {doc_type}"
    if year:
        eyebrow += f", {year}"

    actions = []
    if source_url:
        actions.append(
            f'<a class="button button-primary" href="{source_url}">&larr; Back to source document</a>'
        )
    if pdf_url:
        actions.append(
            f'<a class="button button-secondary" href="{pdf_url}" target="_blank" rel="noopener">View PDF</a>'
        )
    actions_html = "".join(actions)

    page = f"""<!doctype html>
<html lang="en-US">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600;700&family=Barlow:wght@400;500;600;700&family=Cormorant+Garamond:wght@400;500;600&family=DM+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&family=Inter:wght@300;400;500;600;700;800&family=Lexend:wght@400;500;600&family=Manrope:wght@400;500;600;700;800&family=Newsreader:opsz,wght@6..72,400;6..72,500;6..72,600&family=Rubik:wght@400;500;600;700&family=Sora:wght@400;500;600;700&family=Source+Sans+3:wght@400;500;600;700&family=Source+Serif+4:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>{SITE_CSS}</style>
</head>
<body class="company company-{slug}" style="{body_style}">
  <header class="site-header">
    <a class="brand" href="/">Glaucoma Data Archive (LOCAL PREVIEW)</a>
    <nav aria-label="Primary navigation">
      <a href="/">All infographics</a>
      <a href="{source_url}" rel="noopener">Source doc (GH Pages)</a>
    </nav>
  </header>
  <main>
    <article class="document document-infographic" style="--company-primary: {primary}; --company-secondary: {secondary}; --company-accent: {accent};">
      <header class="document-header">
        <div class="brand-chip-row">
          <span class="brand-chip">{code}</span>
          <span class="brand-chip-sponsor">{company_name}</span>
        </div>
        <p class="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <dl class="metadata">{metadata_html}</dl>
        <div class="document-actions">{actions_html}</div>
        <p class="document-provenance">
          This infographic is generated from the parsed text of the source document. All quantitative claims trace back to the linked source; no claims are added beyond what the source records.
        </p>
      </header>
      <div class="content infographic-content">
{body}
      </div>
    </article>
  </main>
  <script>{CHART_JS}</script>
</body>
</html>
"""
    return page


def render_index():
    pages = sorted((ROOT / "infographics").glob("*.md"))
    rows = "".join(
        f'<li><a class="topic-card-link" href="/view/{p.stem}"><span class="topic-card-title">{p.stem}</span></a></li>'
        for p in pages
    )
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Infographic preview</title>
<style>{SITE_CSS}</style></head>
<body>
<header class="site-header"><a class="brand" href="/">Infographic preview</a></header>
<main>
<section class="hero"><h1>Local infographic preview</h1>
<p class="lead">Click an entry to preview it with the live site CSS and the right company colors injected.</p></section>
<section><ul class="document-list">{rows}</ul></section>
</main></body></html>
"""


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/" or path == "/index.html":
            self._send_html(render_index())
            return
        m = re.match(r"^/view/([\w\-]+)/?$", path)
        if m:
            stem = m.group(1)
            md_path = ROOT / "infographics" / f"{stem}.md"
            if not md_path.exists():
                self.send_error(404, f"No infographic: {stem}")
                return
            self._send_html(render_page(md_path))
            return
        if path.startswith("/assets/"):
            asset_path = ROOT / path.lstrip("/")
            if asset_path.exists() and asset_path.is_file():
                self.send_response(200)
                ext = asset_path.suffix.lower()
                ct = {
                    ".css": "text/css",
                    ".png": "image/png",
                    ".svg": "image/svg+xml",
                    ".jpg": "image/jpeg",
                    ".js": "application/javascript",
                }.get(ext, "application/octet-stream")
                self.send_header("Content-Type", ct)
                data = asset_path.read_bytes()
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
        self.send_error(404, f"Not found: {path}")

    def _send_html(self, html):
        data = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        sys.stderr.write(f"  {self.address_string()} - {fmt % args}\n")


def main():
    port = int(os.environ.get("PORT", "4001"))
    with socketserver.ThreadingTCPServer(("127.0.0.1", port), Handler) as httpd:
        print(f"Preview server: http://localhost:{port}/", flush=True)
        for p in sorted((ROOT / "infographics").glob("*.md")):
            print(f"  -> http://localhost:{port}/view/{p.stem}", flush=True)
        httpd.serve_forever()


if __name__ == "__main__":
    main()
