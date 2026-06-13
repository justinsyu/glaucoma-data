#!/usr/bin/env python3
"""Download and parse glaucoma publication/congress PDFs.

The seed generator reads ``scripts/glaucoma_downloaded_documents.json`` and
folds these local files into the Jekyll document index. This script owns that
manifest so downloaded PDFs do not depend on ``retina-data``.
"""

from __future__ import annotations

import html
import json
import re
import sys
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from requests.exceptions import JSONDecodeError

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "scripts" / "glaucoma_downloaded_documents.json"
SEED_DOCS = ROOT / "_data" / "company_documents.json"

sys.path.insert(0, str(ROOT))
from llamaparse import local_pdf_to_markdown  # noqa: E402


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

COMPANY_FOLDERS = {
    "alcon": "alcon",
    "abbvie-allergan": "abbvie_allergan",
    "glaukos": "glaukos",
    "santen-ube": "santen_ube",
    "bausch-lomb-nicox": "bausch_lomb_nicox",
    "sun-pharma-sparc": "sun_pharma_sparc",
    "thea-pharma": "thea_pharma",
    "nicox": "nicox",
    "qlaris-bio": "qlaris_bio",
    "spyglass-pharma": "spyglass_pharma",
    "bayer-perfuse": "bayer_perfuse",
    "polyactiva": "polyactiva",
    "ocular-therapeutix": "ocular_therapeutix",
    "sight-sciences": "sight_sciences",
    "new-world-medical": "new_world_medical",
    "mediprint-ophthalmics": "mediprint_ophthalmics",
    "neurotech-stanford": "neurotech_stanford",
    "skye-bioscience": "skye_bioscience",
    "ache-laboratorios": "ache_laboratorios",
}


class LinkScanner(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self.href: str | None = None
        self.text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        href = next((value for key, value in attrs if key.lower() == "href" and value), None)
        if href:
            self.href = href
            self.text = []

    def handle_data(self, data: str) -> None:
        if self.href:
            self.text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self.href:
            label = " ".join(part.strip() for part in self.text if part.strip())
            self.links.append((self.href, label))
            self.href = None
            self.text = []


def slugify(value: str) -> str:
    value = value.lower().replace("+", " plus ")
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "document"


def title_from_filename(url: str) -> str:
    name = Path(urlparse(url).path).stem
    name = re.sub(r"(?i)(vfinal|final|read-only|draft|lr|mpf|bmw3|urc2?|pdf)$", "", name)
    name = re.sub(r"[_-]+", " ", name).strip()
    name = re.sub(r"\s+", " ", name)
    return name[:1].upper() + name[1:]


def infer_year(*values: str) -> str:
    for value in values:
        match = re.search(r"(20[0-2][0-9])", value)
        if match:
            return match.group(1)
    return ""


def infer_conference(value: str) -> str:
    for token, label in [
        ("ARVO", "ARVO"),
        ("AGS", "AGS"),
        ("ISER", "ISER"),
        ("WGC", "WGC"),
        ("Eyecelerator", "Eyecelerator"),
        ("TM Society", "TM Society"),
    ]:
        if re.search(token, value, re.I):
            return label
    return ""


def qlaris_program(url: str) -> str:
    text = url.lower()
    if "fdc" in text or "latanoprost" in text:
        return "QLS-111 FDC"
    return "QLS-111"


def poly_program(url: str) -> str:
    text = url.lower()
    if "pa5346" in text:
        return "PA5346"
    return "PA5108"


DISCOVERY_SOURCES = [
    {
        "company_slug": "qlaris-bio",
        "source_pages": [
            "https://qlaris.bio/publications-posters/",
            "https://qlaris.bio/publications-posters/page/2/",
            "https://qlaris.bio/publications-posters/page/3/",
            "https://qlaris.bio/publications-posters/page/4/",
        ],
        "category": "presentations_posters",
        "document_type": "Presentation/Poster",
        "indication": "Open-angle glaucoma / ocular hypertension",
        "program": qlaris_program,
        "title_filter": r"(?i)\.pdf|QLS|glaucoma|ocular|latanoprost|trabecular|episcleral|potassium|AGS|ARVO|WGC|ISER",
    },
    {
        "company_slug": "polyactiva",
        "source_pages": ["https://polyactiva.com/news/"],
        "category": "presentations_posters",
        "document_type": "Presentation/Poster",
        "indication": "Open-angle glaucoma / ocular hypertension",
        "program": poly_program,
        "title_filter": r"(?i)Phase-2|Phase 2|glaucoma|latanoprost|PA5108|PA5346|Eyecelerator|ocular",
    },
    {
        "company_slug": "alcon",
        "source_pages": [
            "https://www.alconscience.com/en-ES/resource/hydrus-microstent-clinical-science-compendium/",
        ],
        "category": "published_manuscripts",
        "document_type": "Medical information",
        "indication": "Open-angle glaucoma / ocular hypertension",
        "program": lambda _url: "Hydrus Microstent",
        "title_filter": r"(?i)Hydrus|Microstent|glaucoma",
    },
]


PUBMED_SOURCES = [
    ("abbvie-allergan", "Durysta", '"bimatoprost implant" OR "bimatoprost sustained release"', "Allergan"),
    ("abbvie-allergan", "XEN Glaucoma Treatment System", '"XEN gel stent"', "Allergan"),
    ("glaukos", "iDose TR", '"iDose TR" OR "travoprost intraocular implant"', "Glaukos"),
    ("glaukos", "iStent inject", '"iStent inject"', "Glaukos"),
    ("nicox", "NCX 470", '"NCX 470"', "Nicox"),
    ("qlaris-bio", "QLS-111", '"QLS-111"', "Qlaris"),
    ("polyactiva", "PA5108", '"PA5108" OR "PolyActiva" AND latanoprost', "PolyActiva"),
    ("ocular-therapeutix", "OTX-TIC", '"OTX-TIC" OR "travoprost intracameral hydrogel"', "Ocular Therapeutix"),
    ("mediprint-ophthalmics", "LL-BMT1", '"LL-BMT1" OR "MediPrint" AND bimatoprost', "MediPrint"),
    ("spyglass-pharma", "BIM-IOL System", '"BIM-IOL" OR "SpyGlass Pharma"', "SpyGlass"),
]


def load_seed_records() -> list[dict]:
    if not SEED_DOCS.exists():
        return []
    return json.loads(SEED_DOCS.read_text(encoding="utf-8"))


def seed_pdf_records() -> list[dict]:
    records = []
    for doc in load_seed_records():
        if ".pdf" not in doc.get("source_url", "").lower():
            continue
        records.append(
            {
                "company_slug": doc["company_slug"],
                "program": doc["program"],
                "title": doc["title"],
                "category": doc["category"],
                "document_type": doc["document_type"],
                "year": doc.get("year", ""),
                "conference": doc.get("conference", ""),
                "indication": doc["indication"],
                "source_url": doc["source_url"],
                "source_page": doc.get("source_page") or doc["source_url"],
                "summary": doc.get("summary", ""),
            }
        )
    return records


def discover_page_pdfs() -> list[dict]:
    records = []
    seen = set()
    for source in DISCOVERY_SOURCES:
        pattern = re.compile(source["title_filter"])
        for page_url in source["source_pages"]:
            response = requests.get(page_url, headers=HEADERS, timeout=60)
            response.raise_for_status()
            scanner = LinkScanner()
            scanner.feed(response.text)
            for href, label in scanner.links:
                pdf_url = html.unescape(urljoin(page_url, href))
                if ".pdf" not in pdf_url.lower():
                    continue
                needle = f"{pdf_url} {label}"
                if not pattern.search(needle):
                    continue
                if pdf_url in seen:
                    continue
                seen.add(pdf_url)
                title = label.strip() or title_from_filename(pdf_url)
                if len(title) < 10 or re.fullmatch(r"(?i)view\s+(poster|pdf|publication|presentation)", title):
                    title = title_from_filename(pdf_url)
                records.append(
                    {
                        "company_slug": source["company_slug"],
                        "program": source["program"](pdf_url),
                        "title": title,
                        "category": source["category"],
                        "document_type": source["document_type"],
                        "year": infer_year(pdf_url, title),
                        "conference": infer_conference(f"{pdf_url} {title}"),
                        "indication": source["indication"],
                        "source_url": pdf_url,
                        "source_page": page_url,
                        "summary": f"Downloaded from {page_url}.",
                    }
                )
    return records


def pubmed_pmc_records(max_per_source: int = 5) -> list[dict]:
    records = []
    session = requests.Session()
    for company_slug, program, terms, affiliation in PUBMED_SOURCES:
        term = f"({terms}) AND ({affiliation}[Affiliation])"
        params = {
            "db": "pubmed",
            "term": term,
            "retmode": "json",
            "retmax": str(max_per_source),
            "tool": "glaucoma-data-archive",
            "email": "justinbcyu@gmail.com",
        }
        try:
            response = session.get(
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                params=params,
                headers=HEADERS,
                timeout=60,
            )
            response.raise_for_status()
            pmids = response.json().get("esearchresult", {}).get("idlist", [])
        except Exception as exc:  # noqa: BLE001
            print(f"warning: PubMed esearch failed for {program}: {exc}", file=sys.stderr)
            time.sleep(1.0)
            continue
        if not pmids:
            continue
        time.sleep(0.75)
        summary = session.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
            params={
                "db": "pubmed",
                "id": ",".join(pmids),
                "retmode": "json",
                "tool": "glaucoma-data-archive",
                "email": "justinbcyu@gmail.com",
            },
            headers=HEADERS,
            timeout=60,
        )
        summary.raise_for_status()
        summaries = summary.json().get("result", {})
        pmid_to_pmc = {}
        for pmid in pmids:
            time.sleep(0.75)
            try:
                links = session.get(
                    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi",
                    params={
                        "dbfrom": "pubmed",
                        "db": "pmc",
                        "id": pmid,
                        "retmode": "json",
                        "tool": "glaucoma-data-archive",
                        "email": "justinbcyu@gmail.com",
                    },
                    headers=HEADERS,
                    timeout=60,
                )
                links.raise_for_status()
                linksets = links.json().get("linksets", [])
            except (json.JSONDecodeError, JSONDecodeError, requests.RequestException) as exc:
                print(f"warning: PubMed elink failed for {program} PMID {pmid}: {exc}", file=sys.stderr)
                continue
            for linkset in linksets:
                ids = linkset.get("ids", [])
                if not ids:
                    continue
                for db in linkset.get("linksetdbs", []):
                    if db.get("dbto") == "pmc" and db.get("linkname") == "pubmed_pmc" and db.get("links"):
                        pmid_to_pmc[str(ids[0])] = str(db["links"][0])
        for pmid in pmids:
            pmcid = pmid_to_pmc.get(pmid)
            if not pmcid:
                continue
            item = summaries.get(pmid, {})
            title = re.sub(r"\.$", "", item.get("title") or f"PMID {pmid}")
            year = ""
            if item.get("pubdate"):
                year = infer_year(item["pubdate"])
            records.append(
                {
                    "company_slug": company_slug,
                    "program": program,
                    "title": title,
                    "category": "published_manuscripts",
                    "document_type": "Manuscript",
                    "year": year,
                    "conference": "PubMed Central",
                    "indication": "Open-angle glaucoma / ocular hypertension",
                    "source_url": f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmcid}/pdf/",
                    "source_page": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                    "summary": f"Open-access PubMed Central manuscript discovered from PubMed query for {program}.",
                }
            )
    return records


def relative_url(path: Path) -> str:
    return "/" + path.relative_to(ROOT).as_posix()


def destination(record: dict) -> Path:
    folder = COMPANY_FOLDERS[record["company_slug"]]
    program_slug = slugify(record["program"])
    category = record["category"]
    basename = slugify(record["title"])[:90] + ".pdf"
    return ROOT / "companies" / folder / program_slug / category / basename


def download_pdf(url: str, dest: Path) -> bool:
    if dest.exists() and dest.stat().st_size > 4:
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(url, headers={**HEADERS, "Accept": "application/pdf,*/*;q=0.8"}, timeout=120)
    response.raise_for_status()
    data = response.content
    if not data.startswith(b"%PDF"):
        if "ncbi.nlm.nih.gov/pmc" in url:
            text = data.decode("utf-8", errors="ignore")
            match = re.search(r'href=["\']([^"\']+\.pdf[^"\']*)["\']', text, re.I)
            if match:
                pdf_url = urljoin(url, html.unescape(match.group(1)))
                response = requests.get(
                    pdf_url,
                    headers={**HEADERS, "Accept": "application/pdf,*/*;q=0.8"},
                    timeout=120,
                )
                response.raise_for_status()
                data = response.content
                if data.startswith(b"%PDF"):
                    url = pdf_url
        if data.startswith(b"%PDF"):
            tmp = dest.with_suffix(dest.suffix + ".part")
            tmp.write_bytes(data)
            tmp.replace(dest)
            return True
        print(f"skip invalid pdf: {url} first bytes={data[:16]!r}")
        return False
    tmp = dest.with_suffix(dest.suffix + ".part")
    tmp.write_bytes(data)
    tmp.replace(dest)
    return True


def parse_pdf(pdf_path: Path) -> Path:
    md_path = pdf_path.with_suffix(".md")
    image_dir = pdf_path.with_name(f"{pdf_path.stem}_images")
    if md_path.exists() and md_path.stat().st_size > 0:
        return md_path
    image_count = local_pdf_to_markdown(pdf_path, md_path, image_dir)
    print(f"parsed {pdf_path.name} -> {md_path.name} ({image_count} images)")
    return md_path


def unique_records(records: list[dict]) -> list[dict]:
    output = []
    seen = set()
    for record in records:
        key = (record["company_slug"], record["program"], record["title"], record["source_url"])
        if key in seen:
            continue
        seen.add(key)
        output.append(record)
    return output


def main() -> int:
    candidates = unique_records([*seed_pdf_records(), *discover_page_pdfs(), *pubmed_pmc_records()])
    manifest = []
    downloaded = 0
    skipped = 0
    for record in candidates:
        pdf_path = destination(record)
        try:
            if not download_pdf(record["source_url"], pdf_path):
                skipped += 1
                continue
            md_path = parse_pdf(pdf_path)
        except Exception as exc:  # noqa: BLE001
            print(f"warning: {record['source_url']} failed: {exc}", file=sys.stderr)
            skipped += 1
            continue
        downloaded += 1
        manifest.append(
            {
                **record,
                "status": "downloaded",
                "local_file_url": relative_url(pdf_path),
                "markdown_file_url": relative_url(md_path),
            }
        )
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(manifest)} records to {MANIFEST}")
    print(f"downloaded/verified {downloaded}; skipped {skipped}")
    return 0 if manifest else 1


if __name__ == "__main__":
    raise SystemExit(main())
