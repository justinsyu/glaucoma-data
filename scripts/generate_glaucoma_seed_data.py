"""Generate the glaucoma-specific seed archive.

This keeps the copied source archive framework intact while replacing the public
data, markdown entry points, placeholder source records, and simple full-name
logo assets with glaucoma-focused content.
"""

from __future__ import annotations

import json
import re
import textwrap
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "_data"


COMPANIES = [
    {
        "slug": "alcon",
        "code": "ALC",
        "folder": "alcon",
        "name": "Alcon",
        "short_name": "Alcon",
        "description": "Marketed Rho kinase and fixed-combination topical glaucoma medicines, including Rhopressa and Rocklatan.",
        "primary": "#003595",
        "secondary": "#0072CE",
        "accent": "#5BC2E7",
        "highlight": "#A6E3FF",
        "brand_site": "https://www.alcon.com/",
        "programs": ["Rhopressa", "Rocklatan"],
    },
    {
        "slug": "abbvie-allergan",
        "code": "ABBV",
        "folder": "abbvie_allergan",
        "name": "AbbVie / Allergan",
        "short_name": "AbbVie",
        "description": "Approved bimatoprost sustained-release intracameral implant materials for open-angle glaucoma and ocular hypertension.",
        "primary": "#071D49",
        "secondary": "#0077C8",
        "accent": "#FF8200",
        "highlight": "#8ED8F8",
        "brand_site": "https://www.abbvie.com/",
        "programs": ["Durysta"],
    },
    {
        "slug": "glaukos",
        "code": "GKOS",
        "folder": "glaukos",
        "name": "Glaukos",
        "short_name": "Glaukos",
        "description": "Approved iDose TR sustained-release travoprost implant and interventional glaucoma platform materials.",
        "primary": "#005F83",
        "secondary": "#64A70B",
        "accent": "#00A9E0",
        "highlight": "#B7E4F5",
        "brand_site": "https://www.glaukos.com/",
        "programs": ["iDose TR"],
    },
    {
        "slug": "santen-ube",
        "code": "SANT",
        "folder": "santen_ube",
        "name": "Santen / UBE",
        "short_name": "Santen",
        "description": "Approved Omlonti omidenepag isopropyl ophthalmic solution records for primary open-angle glaucoma and ocular hypertension.",
        "primary": "#004EA2",
        "secondary": "#00A0DF",
        "accent": "#8DC63F",
        "highlight": "#C9E8FF",
        "brand_site": "https://www.santen.com/",
        "programs": ["Omlonti"],
    },
    {
        "slug": "bausch-lomb-nicox",
        "code": "BLCO",
        "folder": "bausch_lomb_nicox",
        "name": "Bausch + Lomb / Nicox",
        "short_name": "Bausch + Lomb",
        "description": "Approved Vyzulta latanoprostene bunod materials, including nitric oxide-donating prostaglandin analog source records.",
        "primary": "#0057B8",
        "secondary": "#00A3E0",
        "accent": "#FDB913",
        "highlight": "#BDE7F7",
        "brand_site": "https://www.bausch.com/",
        "programs": ["Vyzulta"],
    },
    {
        "slug": "sun-pharma-sparc",
        "code": "SUN",
        "folder": "sun_pharma_sparc",
        "name": "Sun Pharma / SPARC",
        "short_name": "Sun Pharma",
        "description": "Approved Xelpros latanoprost ophthalmic emulsion materials for open-angle glaucoma and ocular hypertension.",
        "primary": "#592C82",
        "secondary": "#F58220",
        "accent": "#00A0DF",
        "highlight": "#F8C180",
        "brand_site": "https://sunpharma.com/",
        "programs": ["Xelpros"],
    },
    {
        "slug": "thea-pharma",
        "code": "THEA",
        "folder": "thea_pharma",
        "name": "Thea Pharma",
        "short_name": "Thea",
        "description": "Approved preservative-free latanoprost materials for Iyuzeh in open-angle glaucoma and ocular hypertension.",
        "primary": "#004B8D",
        "secondary": "#00A9E0",
        "accent": "#95C11F",
        "highlight": "#CAE6F7",
        "brand_site": "https://theapharmainc.com/",
        "programs": ["Iyuzeh"],
    },
    {
        "slug": "nicox",
        "code": "NICOX",
        "folder": "nicox",
        "name": "Nicox",
        "short_name": "Nicox",
        "description": "Investigational NCX 470 glaucoma program records, including Phase 3 Mont Blanc, Denali, and AGS 2026 materials.",
        "primary": "#00539B",
        "secondary": "#00A3AD",
        "accent": "#F2C94C",
        "highlight": "#C7F1F2",
        "brand_site": "https://www.nicox.com/",
        "programs": ["NCX 470"],
    },
    {
        "slug": "qlaris-bio",
        "code": "QLS",
        "folder": "qlaris_bio",
        "name": "Qlaris Bio",
        "short_name": "Qlaris",
        "description": "Investigational QLS-111 episcleral venous pressure-targeting topical therapy records for glaucoma and ocular hypertension.",
        "primary": "#1F6F8B",
        "secondary": "#41B6C4",
        "accent": "#7F4FB3",
        "highlight": "#C8F2F6",
        "brand_site": "https://qlaris.bio/",
        "programs": ["QLS-111"],
    },
    {
        "slug": "spyglass-pharma",
        "code": "SGP",
        "folder": "spyglass_pharma",
        "name": "SpyGlass Pharma",
        "short_name": "SpyGlass",
        "description": "Investigational BIM-IOL System sustained bimatoprost delivery records for glaucoma participants undergoing cataract surgery.",
        "primary": "#0A2540",
        "secondary": "#2C7BE5",
        "accent": "#00C2A8",
        "highlight": "#B8F0E7",
        "brand_site": "https://spyglasspharma.com/",
        "programs": ["BIM-IOL System", "BIM-DRS"],
    },
    {
        "slug": "bayer-perfuse",
        "code": "BAYR",
        "folder": "bayer_perfuse",
        "name": "Bayer / Perfuse Therapeutics",
        "short_name": "Bayer / Perfuse",
        "description": "Investigational PER-001 endothelin receptor antagonist implant records for potential disease-modifying glaucoma treatment.",
        "primary": "#10384F",
        "secondary": "#00BCFF",
        "accent": "#89D329",
        "highlight": "#D4F2A8",
        "brand_site": "https://www.bayer.com/",
        "programs": ["PER-001"],
    },
]


DOCUMENTS = [
    {
        "title": "Rhopressa FDA label",
        "company_slug": "alcon",
        "program": "Rhopressa",
        "indication": "Open-angle glaucoma / ocular hypertension",
        "document_type": "Prescribing information",
        "category": "prescribing_information",
        "year": "2017",
        "conference": "FDA",
        "source_url": "https://www.accessdata.fda.gov/drugsatfda_docs/label/2017/208254s000lbl.pdf",
        "source_page": "https://rhopressa.myalcon.com/",
        "summary": "FDA labeling source for netarsudil ophthalmic solution 0.02%, now marketed by Alcon after the Aerie acquisition.",
    },
    {
        "title": "Rocklatan FDA label",
        "company_slug": "alcon",
        "program": "Rocklatan",
        "indication": "Open-angle glaucoma / ocular hypertension",
        "document_type": "Prescribing information",
        "category": "prescribing_information",
        "year": "2019",
        "conference": "FDA",
        "source_url": "https://www.accessdata.fda.gov/drugsatfda_docs/label/2019/208259s000lbl.pdf",
        "source_page": "https://rocklatan.myalcon.com/",
        "summary": "FDA labeling source for fixed-dose netarsudil and latanoprost ophthalmic solution.",
    },
    {
        "title": "Alcon acquisition of Aerie Pharmaceuticals",
        "company_slug": "alcon",
        "program": "Rhopressa / Rocklatan",
        "indication": "Open-angle glaucoma / ocular hypertension",
        "document_type": "Corporate transaction",
        "category": "press_releases",
        "year": "2022",
        "conference": "Company release",
        "source_url": "https://www.alcon.com/media-release/alcon-acquire-aerie-pharmaceuticals-inc-enhancing-its-ophthalmic-pharmaceutical/",
        "source_page": "https://www.alcon.com/",
        "summary": "Company source documenting the transfer of the Aerie glaucoma portfolio into Alcon.",
    },
    {
        "title": "Durysta FDA approval announcement",
        "company_slug": "abbvie-allergan",
        "program": "Durysta",
        "indication": "Open-angle glaucoma / ocular hypertension",
        "document_type": "Regulatory news",
        "category": "press_releases",
        "year": "2020",
        "conference": "Company release",
        "source_url": "https://news.abbvie.com/index.php?item=123527&s=2429",
        "source_page": "https://www.durystahcp.com/",
        "summary": "Allergan/AbbVie source for FDA approval of the bimatoprost intracameral implant.",
    },
    {
        "title": "iDose TR FDA label",
        "company_slug": "glaukos",
        "program": "iDose TR",
        "indication": "Open-angle glaucoma / ocular hypertension",
        "document_type": "Prescribing information",
        "category": "prescribing_information",
        "year": "2023",
        "conference": "FDA",
        "source_url": "https://www.accessdata.fda.gov/drugsatfda_docs/label/2023/218010s000lbl.pdf",
        "source_page": "https://www.glaukos.com/glaucoma/products/idose-tr/",
        "summary": "FDA labeling source for the travoprost intracameral implant approved for IOP reduction.",
    },
    {
        "title": "Glaukos FDA approval of iDose TR",
        "company_slug": "glaukos",
        "program": "iDose TR",
        "indication": "Open-angle glaucoma / ocular hypertension",
        "document_type": "Regulatory news",
        "category": "press_releases",
        "year": "2023",
        "conference": "Company release",
        "source_url": "https://investors.glaukos.com/news/news-details/2023/Glaukos-Announces-FDA-Approval-of-iDoseTR-travoprost-intracameral-implant/default.aspx",
        "source_page": "https://investors.glaukos.com/",
        "summary": "Company source for the December 2023 FDA approval of iDose TR.",
    },
    {
        "title": "Omlonti FDA label",
        "company_slug": "santen-ube",
        "program": "Omlonti",
        "indication": "Primary open-angle glaucoma / ocular hypertension",
        "document_type": "Prescribing information",
        "category": "prescribing_information",
        "year": "2022",
        "conference": "FDA",
        "source_url": "https://www.accessdata.fda.gov/drugsatfda_docs/label/2022/215092s000lbl.pdf",
        "source_page": "https://www.santen.com/",
        "summary": "FDA labeling source for omidenepag isopropyl ophthalmic solution 0.002%.",
    },
    {
        "title": "Santen and UBE FDA approval of Omlonti",
        "company_slug": "santen-ube",
        "program": "Omlonti",
        "indication": "Primary open-angle glaucoma / ocular hypertension",
        "document_type": "Regulatory news",
        "category": "press_releases",
        "year": "2022",
        "conference": "Company release",
        "source_url": "https://www.ube.com/ube/en/news/2022/santen-and-ube-received-fda-approval-for-omlonti-omidenepag-isopropyl-ophthalmic-solution-0002-for-t.html",
        "source_page": "https://www.ube.com/",
        "summary": "Joint company source documenting the U.S. FDA approval date and indication for Omlonti.",
    },
    {
        "title": "Vyzulta prescribing information",
        "company_slug": "bausch-lomb-nicox",
        "program": "Vyzulta",
        "indication": "Open-angle glaucoma / ocular hypertension",
        "document_type": "Prescribing information",
        "category": "prescribing_information",
        "year": "2017",
        "conference": "FDA",
        "source_url": "https://www.bausch.com/globalassets/pdf/packageinserts/pharma/vyzulta-prescribing-information.pdf",
        "source_page": "https://www.bausch.com/",
        "summary": "Prescribing information for latanoprostene bunod ophthalmic solution 0.024%.",
    },
    {
        "title": "Bausch + Lomb and Nicox FDA approval of Vyzulta",
        "company_slug": "bausch-lomb-nicox",
        "program": "Vyzulta",
        "indication": "Open-angle glaucoma / ocular hypertension",
        "document_type": "Regulatory news",
        "category": "press_releases",
        "year": "2017",
        "conference": "Company release",
        "source_url": "https://www.nicox.com/bausch-lomb-nicox-announce-fda-approval-vyzulta-latanoprostene-bunod-ophthalmic-solution-0-024-2/",
        "source_page": "https://www.nicox.com/",
        "summary": "Joint source for FDA approval of the nitric oxide-donating prostaglandin analog Vyzulta.",
    },
    {
        "title": "Xelpros FDA label",
        "company_slug": "sun-pharma-sparc",
        "program": "Xelpros",
        "indication": "Open-angle glaucoma / ocular hypertension",
        "document_type": "Prescribing information",
        "category": "prescribing_information",
        "year": "2018",
        "conference": "FDA",
        "source_url": "https://www.accessdata.fda.gov/drugsatfda_docs/label/2018/206185s000lbl.pdf",
        "source_page": "https://sunpharma.com/",
        "summary": "FDA labeling source for latanoprost ophthalmic emulsion 0.005%.",
    },
    {
        "title": "Iyuzeh FDA label",
        "company_slug": "thea-pharma",
        "program": "Iyuzeh",
        "indication": "Open-angle glaucoma / ocular hypertension",
        "document_type": "Prescribing information",
        "category": "prescribing_information",
        "year": "2022",
        "conference": "FDA",
        "source_url": "https://www.accessdata.fda.gov/drugsatfda_docs/label/2022/216472s000lbl.pdf",
        "source_page": "https://iyuzeh.com/",
        "summary": "FDA labeling source for preservative-free latanoprost ophthalmic solution 0.005%.",
    },
    {
        "title": "Thea U.S. launch of Iyuzeh",
        "company_slug": "thea-pharma",
        "program": "Iyuzeh",
        "indication": "Open-angle glaucoma / ocular hypertension",
        "document_type": "Commercial news",
        "category": "press_releases",
        "year": "2023",
        "conference": "Company release",
        "source_url": "https://theapharmainc.com/news/thea-pharma-inc-launches-iyuzeh-latanoprost-ophthalmic-solution-0-005-in-the-u-s/",
        "source_page": "https://theapharmainc.com/",
        "summary": "Company source for U.S. launch of preservative-free latanoprost.",
    },
    {
        "title": "NCX 470 Denali Phase 3 topline results",
        "company_slug": "nicox",
        "program": "NCX 470",
        "indication": "Open-angle glaucoma / ocular hypertension",
        "document_type": "Clinical data news",
        "category": "press_releases",
        "year": "2025",
        "conference": "Company release",
        "source_url": "https://www.nicox.com/wp-content/uploads/EN_NCX470DenaliToplineAugust2025_PR_FINAL.pdf",
        "source_page": "https://www.nicox.com/news-and-events/press-releases-archive/",
        "summary": "Nicox source for positive Phase 3 Denali topline data in glaucoma participants.",
    },
    {
        "title": "NCX 470 AGS 2026 Phase 3 data summary",
        "company_slug": "nicox",
        "program": "NCX 470",
        "indication": "Open-angle glaucoma / ocular hypertension",
        "document_type": "Congress news",
        "category": "presentations_posters",
        "year": "2026",
        "conference": "AGS 2026",
        "source_url": "https://www.nicox.com/wp-content/uploads/EN_AGS-2026-posters-presented_FINAL.pdf",
        "source_page": "https://www.nicox.com/",
        "summary": "Nicox source summarizing NCX 470 Phase 3 data presented at the 2026 American Glaucoma Society annual meeting.",
    },
    {
        "title": "QLS-111 Phase II Osprey and Apteryx topline data",
        "company_slug": "qlaris-bio",
        "program": "QLS-111",
        "indication": "Primary open-angle glaucoma / ocular hypertension",
        "document_type": "Clinical data news",
        "category": "press_releases",
        "year": "2025",
        "conference": "Company release",
        "source_url": "https://qlaris.bio/qlaris-bio-announces-positive-topline-data-from-two-phase-ii-trials-of-qls-111-in-patients-with-primary-open-angle-glaucoma-and-ocular-hypertension/",
        "source_page": "https://qlaris.bio/news-events/",
        "summary": "Qlaris source for Phase II Osprey and Apteryx topline data and additive IOP-lowering observations.",
    },
    {
        "title": "Qlaris fixed-dose QLS-111 and latanoprost development update",
        "company_slug": "qlaris-bio",
        "program": "QLS-111",
        "indication": "Open-angle glaucoma / ocular hypertension",
        "document_type": "Pipeline news",
        "category": "press_releases",
        "year": "2025",
        "conference": "Company release",
        "source_url": "https://qlaris.bio/news-events/",
        "source_page": "https://qlaris.bio/news-events/",
        "summary": "Qlaris news roster documenting fixed-dose combination development with QLS-111 and latanoprost.",
    },
    {
        "title": "SpyGlass BIM-IOL Phase 3 clinical trial overview",
        "company_slug": "spyglass-pharma",
        "program": "BIM-IOL System",
        "indication": "Open-angle glaucoma / ocular hypertension",
        "document_type": "Clinical trial overview",
        "category": "clinical_trials",
        "year": "2026",
        "conference": "Company pipeline",
        "source_url": "https://spyglasspharma.com/study-data/",
        "source_page": "https://spyglasspharma.com/pipeline/",
        "summary": "Company source for two parallel registrational Phase 3 BIM-IOL trials.",
    },
    {
        "title": "SpyGlass 2025 results and Phase 3 initiation update",
        "company_slug": "spyglass-pharma",
        "program": "BIM-IOL System",
        "indication": "Open-angle glaucoma / ocular hypertension",
        "document_type": "Corporate update",
        "category": "press_releases",
        "year": "2026",
        "conference": "Company release",
        "source_url": "https://ir.spyglasspharma.com/news-releases/news-release-details/spyglass-pharma-reports-fourth-quarter-and-full-year-2025",
        "source_page": "https://ir.spyglasspharma.com/",
        "summary": "SpyGlass source covering Phase 1/2 results and first randomized participants in Phase 3.",
    },
    {
        "title": "Bayer agreement to acquire Perfuse Therapeutics",
        "company_slug": "bayer-perfuse",
        "program": "PER-001",
        "indication": "Glaucoma / diabetic retinopathy",
        "document_type": "Corporate transaction",
        "category": "press_releases",
        "year": "2026",
        "conference": "Company release",
        "source_url": "https://www.bayer.com/en/us/news-stories/perfuse-therapeutics",
        "source_page": "https://www.bayer.com/",
        "summary": "Bayer source documenting the planned acquisition and Phase II status of PER-001.",
    },
    {
        "title": "PER-001 completed Phase 1/2a glaucoma results",
        "company_slug": "bayer-perfuse",
        "program": "PER-001",
        "indication": "Glaucoma",
        "document_type": "Clinical data news",
        "category": "press_releases",
        "year": "2025",
        "conference": "ARVO 2025",
        "source_url": "https://perfusetherapeutics.com/perfuse-therapeutics-announces-positive-results-from-the-completed-phase-1-2a-clinical-trial-of-per-001-intravitreal-implant-in-patients-with-glaucoma/",
        "source_page": "https://perfusetherapeutics.com/news/",
        "summary": "Perfuse source for 24-week Phase 1/2a PER-001 glaucoma data.",
    },
    {
        "title": "PER-001 Phase 2 glaucoma and diabetic retinopathy results",
        "company_slug": "bayer-perfuse",
        "program": "PER-001",
        "indication": "Glaucoma / diabetic retinopathy",
        "document_type": "Clinical data news",
        "category": "press_releases",
        "year": "2025",
        "conference": "Company release",
        "source_url": "https://perfusetherapeutics.com/perfuse-therapeutics-announces-positive-results-from-phase-2-clinical-trials-in-glaucoma-and-diabetic-retinopathy-patients/",
        "source_page": "https://perfusetherapeutics.com/news/",
        "summary": "Perfuse source for Phase 2 PER-001 results and planned later-stage development.",
    },
]


TRIALS = [
    ("nicox", "NCX 470", "NCT04445519"),
    ("nicox", "NCX 470", "NCT04630808"),
    ("qlaris-bio", "QLS-111", "NCT06016972"),
    ("qlaris-bio", "QLS-111", "NCT06249152"),
    ("qlaris-bio", "QLS-111", "NCT06030193"),
    ("bayer-perfuse", "PER-001", "NCT05822245"),
    ("spyglass-pharma", "BIM-IOL System", "NCT07218783"),
    ("spyglass-pharma", "BIM-IOL System", "NCT07218796"),
    ("spyglass-pharma", "BIM-DRS", "NCT07641296"),
]


def slugify(value: str) -> str:
    value = value.lower()
    value = value.replace("+", " plus ")
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8", newline="\n")


def write_json(path: Path, value) -> None:
    write_text(path, json.dumps(value, indent=2) + "\n")


def profile_by_slug(slug: str) -> dict:
    return next(company for company in COMPANIES if company["slug"] == slug)


def make_profiles(documents: list[dict]) -> list[dict]:
    profiles = []
    for company in COMPANIES:
        company_docs = [doc for doc in documents if doc["company_slug"] == company["slug"]]
        profile = dict(company)
        profile.update(
            {
                "palette_note": "Palette derived from sponsor-facing brand colors and tuned for the Glaucoma Data card system.",
                "background_source": "Generated abstract ophthalmology background local to this repository.",
                "background_image": f"/assets/img/company-backgrounds/{company['slug']}.svg",
                "document_count": len(company_docs),
                "page_url": f"/companies/{company['slug']}/",
                "css_class": f"company-{company['slug']}",
                "logo": f"/assets/img/company-logos/{company['slug']}.svg",
            }
        )
        profiles.append(profile)
    return profiles


def make_document_records() -> list[dict]:
    records = []
    for index, doc in enumerate(DOCUMENTS, 1):
        company = profile_by_slug(doc["company_slug"])
        slug = f"{company['slug']}-{slugify(doc['program'])}-{slugify(doc['title'])}"
        markdown_file = f"/companies/{company['folder']}/{slugify(doc['program'])}/{doc['category']}/{index:03d}_{slugify(doc['title'])}.md"
        records.append(
            {
                "id": f"doc-{index:04d}",
                "row_id": str(index),
                "title": doc["title"],
                "url": f"/company-documents/{slug}/",
                "company": company["name"],
                "company_slug": company["slug"],
                "company_folder": company["folder"],
                "program": doc["program"],
                "program_slug": slugify(doc["program"]).replace("-", "_"),
                "indication": doc["indication"],
                "document_type": doc["document_type"],
                "category": doc["category"],
                "year": doc["year"],
                "conference": doc["conference"],
                "local_file_url": "",
                "source_url": doc["source_url"],
                "source_page": doc["source_page"],
                "status": "source_link",
                "background_image": f"/assets/img/company-backgrounds/{company['slug']}.svg",
                "primary_color": company["primary"],
                "secondary_color": company["secondary"],
                "accent_color": company["accent"],
                "markdown_file_url": markdown_file,
                "summary": doc["summary"],
            }
        )
    return records


def make_programs(documents: list[dict]) -> list[dict]:
    programs = []
    seen = set()
    for doc in documents:
        key = (doc["company_slug"], doc["program"])
        if key in seen:
            continue
        seen.add(key)
        company = profile_by_slug(doc["company_slug"])
        program_docs = [d for d in documents if d["company_slug"] == doc["company_slug"] and d["program"] == doc["program"]]
        programs.append(
            {
                "slug": f"{company['slug']}-{slugify(doc['program'])}",
                "company": company["name"],
                "company_slug": company["slug"],
                "program": doc["program"],
                "program_slug": slugify(doc["program"]).replace("-", "_"),
                "url": f"/programs/{slugify(doc['program'])}/",
                "description": f"{doc['program']} source records for {doc['indication']} from {company['name']}.",
                "document_count": len(program_docs),
                "primary_color": company["primary"],
                "secondary_color": company["secondary"],
                "accent_color": company["accent"],
                "background_image": f"/assets/img/company-backgrounds/{company['slug']}.svg",
            }
        )
    return sorted(programs, key=lambda item: item["program"].lower())


def make_press_releases(documents: list[dict]) -> list[dict]:
    releases = []
    for doc in documents:
        if doc["category"] not in {"press_releases", "presentations_posters", "clinical_trials"}:
            continue
        year = doc["year"] or "2026"
        date = {
            "2017": "2017-11-02",
            "2020": "2020-03-05",
            "2022": "2022-09-26",
            "2023": "2023-12-13",
            "2025": "2025-06-24" if doc["program"] == "PER-001" else "2025-08-21" if doc["program"] == "NCX 470" else "2025-02-05",
            "2026": "2026-05-06" if doc["program"] == "PER-001" else "2026-03-30",
        }.get(year, f"{year}-01-01")
        releases.append(
            {
                "title": doc["title"],
                "date": date,
                "company": doc["company"],
                "company_slug": doc["company_slug"],
                "program": doc["program"],
                "category": doc["document_type"],
                "indication": doc["indication"],
                "summary": doc["summary"],
                "source_url": doc["source_url"],
            }
        )
    return sorted(releases, key=lambda item: item["date"], reverse=True)


def fetch_trial(company_slug: str, program: str, nct_id: str) -> dict:
    company = profile_by_slug(company_slug)
    url = f"https://clinicaltrials.gov/api/v2/studies/{nct_id}"
    fallback = {
        "company": company["name"],
        "program": program,
        "nct_id": nct_id,
        "trial_url": f"https://clinicaltrials.gov/study/{nct_id}",
        "overall_status": "UNKNOWN",
        "has_results": False,
        "last_update_post_date": "",
        "trial_title": f"{program} study",
        "update_details": [{"label": "Source", "value": "ClinicalTrials.gov"}],
    }
    try:
        with urllib.request.urlopen(url, timeout=20) as response:
            study = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return fallback

    protocol = study.get("protocolSection", {})
    identification = protocol.get("identificationModule", {})
    status = protocol.get("statusModule", {})
    results = study.get("hasResults", False)
    last_update = status.get("lastUpdatePostDateStruct", {}).get("date", "")
    start_date = status.get("startDateStruct", {}).get("date", "")
    completion_date = status.get("completionDateStruct", {}).get("date", "")
    phases = protocol.get("designModule", {}).get("phases", [])
    return {
        "company": company["name"],
        "program": program,
        "nct_id": nct_id,
        "trial_url": f"https://clinicaltrials.gov/study/{nct_id}",
        "overall_status": status.get("overallStatus", "UNKNOWN"),
        "has_results": bool(results),
        "last_update_post_date": last_update,
        "trial_title": identification.get("briefTitle", fallback["trial_title"]),
        "update_details": [
            {"label": "Phase", "value": ", ".join(phases) if phases else "Not specified"},
            {"label": "Start", "value": start_date or "Not posted"},
            {"label": "Completion", "value": completion_date or "Not posted"},
        ],
    }


def make_clinical_trials() -> dict:
    checked = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    latest_trials = [fetch_trial(company, program, nct) for company, program, nct in TRIALS]
    dated_trials = [trial for trial in latest_trials if trial.get("last_update_post_date")]
    most_recent_date = max((trial["last_update_post_date"] for trial in dated_trials), default="")
    most_recent_trials = [trial for trial in latest_trials if trial.get("last_update_post_date") == most_recent_date]
    updates = [
        {
            "detected_date": trial.get("last_update_post_date") or checked[:10],
            "event_type": "checked_ok",
            "event_type_label": "Registry row",
            "company": trial["company"],
            "program": trial["program"],
            "nct_id": trial["nct_id"],
            "trial_url": trial["trial_url"],
            "trial_title": trial["trial_title"],
            "changed_fields": trial.get("update_details", []),
            "last_update_post_date": trial.get("last_update_post_date", ""),
        }
        for trial in latest_trials
    ]
    return {
        "summary": {
            "monitored_sources": len(TRIALS),
            "tracked_trials": len(latest_trials),
            "updates_total": len(updates),
            "updates_last_7_days": 0,
            "most_recent_registry_update_date": most_recent_date,
            "latest_capture_at": checked,
        },
        "most_recent_registry_updates": {
            "date": most_recent_date,
            "trials": most_recent_trials,
        },
        "weekly_buckets": [],
        "updates": updates,
        "latest_trials": latest_trials,
    }


def make_automation_audit(profiles: list[dict], releases: list[dict]) -> dict:
    expected_sources = []
    for profile in profiles:
        expected_sources.append(
            {
                "source_family": "publication",
                "source_family_label": "Publication",
                "company_name": profile["name"],
                "tier": "seed",
                "source_kind": "company_site",
                "source_kind_label": "Company Site",
                "fetcher": "manual_seed",
                "fetcher_label": "Manual Seed",
                "source_url": profile["brand_site"],
                "status": "skipped_by_config",
                "discovery_only": True,
                "skip_reason": "Seeded archive. Automation source recipes can be enabled after review.",
            }
        )
    generated = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    return {
        "generated_at_utc": generated,
        "summary": {
            "in_scope_companies": len(profiles),
            "expected_sources": len(expected_sources),
            "publication_expected_sources": len(expected_sources),
            "press_release_expected_sources": len(releases),
            "latest_checked_sources": 0,
            "latest_expected_sources": len(expected_sources),
            "latest_run_status": "not_run",
            "latest_run_status_label": "Not run",
            "open_findings": 0,
        },
        "runs": [],
        "findings": [],
        "expected_sources": expected_sources,
    }


def svg_logo(company: dict) -> str:
    name = company["name"].replace("&", "&amp;")
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="640" height="160" viewBox="0 0 640 160" role="img" aria-labelledby="title">
  <title id="title">{name}</title>
  <rect width="640" height="160" fill="white"/>
  <rect x="24" y="24" width="112" height="112" fill="{company['primary']}"/>
  <circle cx="80" cy="80" r="34" fill="none" stroke="{company['accent']}" stroke-width="10"/>
  <path d="M46 80h68M80 46v68" stroke="{company['secondary']}" stroke-width="8" stroke-linecap="round"/>
  <text x="160" y="91" font-family="Inter, Arial, sans-serif" font-size="42" font-weight="700" fill="{company['primary']}">{name}</text>
</svg>
"""


def svg_background(company: dict) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="520" viewBox="0 0 1200 520" preserveAspectRatio="none">
  <rect width="1200" height="520" fill="#ffffff"/>
  <path d="M0 360 C180 290 260 450 430 360 C610 265 790 245 1200 115 L1200 520 L0 520 Z" fill="{company['primary']}" opacity="0.10"/>
  <path d="M0 120 C210 60 355 200 545 145 C745 90 930 75 1200 140" fill="none" stroke="{company['secondary']}" stroke-width="7" opacity="0.20"/>
  <path d="M60 440 C220 300 415 465 570 315 C710 180 910 230 1130 80" fill="none" stroke="{company['accent']}" stroke-width="5" opacity="0.18"/>
  <g fill="none" stroke="{company['primary']}" opacity="0.18">
    <circle cx="170" cy="165" r="58"/>
    <circle cx="975" cy="330" r="78"/>
    <circle cx="710" cy="220" r="42"/>
  </g>
</svg>
"""


def write_markdown_pages(documents: list[dict], profiles: list[dict], programs: list[dict]) -> None:
    for profile in profiles:
        write_text(
            ROOT / "companies" / f"{profile['slug']}.md",
            textwrap.dedent(
                f"""\
                ---
                layout: company
                title: "{profile['name']} Documents"
                permalink: /companies/{profile['slug']}/
                description: "{profile['description']}"
                company_slug: {profile['slug']}
                ---
                """
            ),
        )

    for program in programs:
        related = [doc for doc in documents if doc["company_slug"] == program["company_slug"] and doc["program"] == program["program"]]
        write_text(
            ROOT / "programs" / f"{slugify(program['program'])}.md",
            textwrap.dedent(
                f"""\
                ---
                layout: default
                title: "{program['program']}"
                permalink: /programs/{slugify(program['program'])}/
                description: "{program['description']}"
                company: "{program['company']}"
                company_slug: {program['company_slug']}
                ---

                <section class="hero">
                  <h1>{program['program']}</h1>
                  <p class="lead">{program['description']}</p>
                </section>

                {{% assign program_documents = site.data.company_documents | where: "program", "{program['program']}" %}}
                {{% include document_list.html documents=program_documents sort_by="year" sort_dir="desc" match_summary_spacing=true %}}
                """
            ),
        )

    indications = {
        "open-angle-glaucoma-ocular-hypertension": {
            "title": "Open-angle glaucoma / ocular hypertension",
            "description": "Approved and investigational IOP-lowering records for open-angle glaucoma and ocular hypertension.",
        },
        "glaucoma-neuroprotection": {
            "title": "Glaucoma neuroprotection / disease modification",
            "description": "Investigational records for glaucoma therapies studying visual field, retinal nerve fiber layer, ocular blood flow, or other non-IOP disease-modifying outcomes.",
        },
    }
    for slug, meta in indications.items():
        write_text(
            ROOT / "indications" / f"{slug}.md",
            textwrap.dedent(
                f"""\
                ---
                layout: default
                title: "{meta['title']}"
                permalink: /indications/{slug}/
                description: "{meta['description']}"
                ---

                <section class="hero">
                  <h1>{meta['title']}</h1>
                  <p class="lead">{meta['description']}</p>
                </section>

                {{% assign all_documents = site.data.company_documents %}}
                {{% include document_list.html documents=all_documents sort_by="year" sort_dir="desc" match_summary_spacing=true %}}
                """
            ),
        )

    for doc in documents:
        company = profile_by_slug(doc["company_slug"])
        slug = doc["url"].strip("/").split("/")[-1]
        content = textwrap.dedent(
            f"""\
            ---
            layout: company_document_placeholder
            title: "{doc['title']}"
            permalink: {doc['url']}
            description: "{doc['summary']}"
            company: "{doc['company']}"
            company_slug: {doc['company_slug']}
            program: "{doc['program']}"
            indication: "{doc['indication']}"
            document_type: "{doc['document_type']}"
            year: "{doc['year']}"
            source_url: "{doc['source_url']}"
            markdown_file_url: "{doc['markdown_file_url']}"
            primary_color: "{company['primary']}"
            secondary_color: "{company['secondary']}"
            accent_color: "{company['accent']}"
            ---

            This placeholder preserves the source record in the same archive framework as Glaucoma Data.

            <dl class="metadata">
              <div>
                <dt>Source page</dt>
                <dd><a href="{doc['source_page']}" rel="noopener">{doc['source_page']}</a></dd>
              </div>
              <div>
                <dt>Source summary</dt>
                <dd>{doc['summary']}</dd>
              </div>
            </dl>
            """
        )
        write_text(ROOT / "company-documents" / slug / "index.md", content)


def main() -> None:
    DATA.mkdir(exist_ok=True)
    docs = make_document_records()
    profiles = make_profiles(docs)
    programs = make_programs(docs)
    releases = make_press_releases(docs)

    write_json(DATA / "company_documents.json", docs)
    write_json(DATA / "company_profiles.json", profiles)
    write_json(DATA / "company_programs.json", programs)
    write_json(DATA / "company_press_releases.yml", releases)
    write_json(DATA / "documents.yml", [])
    write_json(DATA / "pdf_links.yml", [])
    write_json(DATA / "clinicaltrials_updates.json", make_clinical_trials())
    write_json(DATA / "automation_audit.json", make_automation_audit(profiles, releases))
    write_json(DATA / "watch_audit.json", {"generated_at_utc": datetime.now(timezone.utc).isoformat(), "findings": []})
    write_json(DATA / "source_watchlist.yml", [])

    for company in COMPANIES:
        write_text(ROOT / "assets" / "img" / "company-logos" / f"{company['slug']}.svg", svg_logo(company))
        write_text(ROOT / "assets" / "img" / "company-backgrounds" / f"{company['slug']}.svg", svg_background(company))

    write_markdown_pages(docs, profiles, programs)


if __name__ == "__main__":
    main()
