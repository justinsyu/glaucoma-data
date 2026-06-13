# Manuscripts to retrieve full text for

**36 documents** in the Retina Data Archive currently have no parsed full-text markdown, so their topic-page citations and infographics cannot be generated. Each entry below carries the original source URL plus its current archive page so the eventual full-text drop can be matched back to the right slot.

Status flag meanings (from `_data/company_documents.json`):

| Flag | What it means |
|---|---|
| `downloaded` / `downloaded_manual` | PDF was fetched at ingest; full text was not parsed into markdown. Re-run the parser on the local PDF if it is on disk, otherwise re-download from the source URL. |
| `downloaded_pubmed_xml` | Only the PubMed XML (abstract + metadata) is on disk. Full text is paywalled in most cases; check PMC for an open mirror first. |
| `downloaded_pmc_html` | PMC HTML was fetched but never converted to clean markdown. Free to parse; rerun the cleaner. |
| `placeholder_pdf_available` | A PDF exists locally but no source URL was captured. Title may also be a placeholder if the PDF metadata was empty. |

---

## A. Open-access on PubMed Central (5 manuscripts)

Full text is already public; the parser just needs to run against the PMC HTML/XML. These can be unblocked without paid access.

- **Bayer / Eylea / Eylea HD** — ARIES treat-and-extend randomized clinical trial
  - Source: <https://pmc.ncbi.nlm.nih.gov/articles/PMC8384251/>
  - Archive page: <https://justinsyu.github.io/retina-data/company-documents/bayer-eylea-eylea-hd-aries-treat-and-extend-randomized-clinical-trial/>
  - Status flag: `downloaded`

- **Bayer / Eylea / Eylea HD** — ALTAIR treat-and-extend 52 and 96 week findings
  - Source: <https://pmc.ncbi.nlm.nih.gov/articles/PMC7089719/>
  - Archive page: <https://justinsyu.github.io/retina-data/company-documents/bayer-eylea-eylea-hd-altair-treat-and-extend-52-and-96-week-findings/>
  - Status flag: `downloaded`

- **Regeneron / Eylea HD** — CANDELA high-dose intravitreal aflibercept 8 mg in nAMD
  - Source: <https://pmc.ncbi.nlm.nih.gov/articles/PMC12278850/>
  - Archive page: <https://justinsyu.github.io/retina-data/company-documents/regeneron-eylea-hd-candela-high-dose-intravitreal-aflibercept-8-mg-in-namd/>
  - Status flag: `downloaded_pmc_html`

- **Sandoz / Enzeevu / Enzeevum** — MYLIGHT 52-week results proposed biosimilar aflibercept SDZ-AFL in nAMD
  - Source: <https://pmc.ncbi.nlm.nih.gov/articles/PMC11398290/>
  - Archive page: <https://justinsyu.github.io/retina-data/company-documents/sandoz-enzeevu-enzeevum-mylight-52-week-results-proposed-biosimilar-aflibercept-sdz-afl-in-namd/>
  - Status flag: `downloaded`

- **Formycon / Klinge Biopharma / Ahzantive** — Randomised double-masked trial FYB203 vs reference aflibercept in nAMD
  - Source: <https://pmc.ncbi.nlm.nih.gov/articles/PMC12778319/>
  - Archive page: <https://justinsyu.github.io/retina-data/company-documents/formycon-klinge-biopharma-ahzantive-randomised-double-masked-trial-fyb203-vs-reference-afliberce/>
  - Status flag: `downloaded_pmc_html`

## B. PubMed-indexed (full text typically paywalled — 8 manuscripts)

Only the PubMed XML (abstract + metadata) is on disk. To populate the archive, obtain the full text via institutional access or a direct request to the publisher and drop a markdown extraction into the matching `companies/<sponsor>/<program>/published_manuscripts/` folder.

- **Roche / Genentech / Lucentis** — Ranibizumab for Neovascular Age-Related Macular Degeneration
  - Source: <https://pubmed.ncbi.nlm.nih.gov/17021318/>
  - Archive page: <https://justinsyu.github.io/retina-data/company-documents/roche-genentech-lucentis-ranibizumab-for-neovascular-age-related-macular-degeneration/>
  - Status flag: `downloaded_pubmed_xml`

- **Roche / Genentech / Lucentis** — Ranibizumab versus Verteporfin for nAMD
  - Source: <https://pubmed.ncbi.nlm.nih.gov/17021319/>
  - Archive page: <https://justinsyu.github.io/retina-data/company-documents/roche-genentech-lucentis-ranibizumab-versus-verteporfin-for-namd/>
  - Status flag: `downloaded_pubmed_xml`

- **Roche / Genentech / Lucentis** — HARBOR 12-Month Ranibizumab nAMD Results
  - Source: <https://pubmed.ncbi.nlm.nih.gov/23352196/>
  - Archive page: <https://justinsyu.github.io/retina-data/company-documents/roche-genentech-lucentis-harbor-12-month-ranibizumab-namd-results/>
  - Status flag: `downloaded_pubmed_xml`

- **Roche / Genentech / Lucentis** — HARBOR 24-Month Ranibizumab nAMD Results
  - Source: <https://pubmed.ncbi.nlm.nih.gov/25015215/>
  - Archive page: <https://justinsyu.github.io/retina-data/company-documents/roche-genentech-lucentis-harbor-24-month-ranibizumab-namd-results/>
  - Status flag: `downloaded_pubmed_xml`

- **Roche / Genentech / Susvimo** — Archway Phase 3 PDS Trial for nAMD
  - Source: <https://pubmed.ncbi.nlm.nih.gov/34597713/>
  - Archive page: <https://justinsyu.github.io/retina-data/company-documents/roche-genentech-susvimo-archway-phase-3-pds-trial-for-namd/>
  - Status flag: `downloaded_pubmed_xml`

- **Novartis / Beovu** — HAWK and HARRIER 96-week outcomes
  - Source: <https://pubmed.ncbi.nlm.nih.gov/32574761/>
  - Archive page: <https://justinsyu.github.io/retina-data/company-documents/novartis-beovu-hawk-and-harrier-96-week-outcomes/>
  - Status flag: `downloaded_pubmed_xml`

- **Regeneron / Eylea** — Intravitreal aflibercept VEGF Trap-Eye in wet age-related macular degeneration
  - Source: <https://pubmed.ncbi.nlm.nih.gov/23084240/>
  - Archive page: <https://justinsyu.github.io/retina-data/company-documents/regeneron-eylea-intravitreal-aflibercept-vegf-trap-eye-in-wet-age-related-macular-degeneration/>
  - Status flag: `downloaded_pubmed_xml`

- **Regeneron / Eylea HD** — Intravitreal aflibercept 8 mg in nAMD 96-week PULSAR results
  - Source: <https://pubmed.ncbi.nlm.nih.gov/40876598/>
  - Archive page: <https://justinsyu.github.io/retina-data/company-documents/regeneron-eylea-hd-intravitreal-aflibercept-8-mg-in-namd-96-week-pulsar-results/>
  - Status flag: `downloaded_pubmed_xml`

## C. Paywalled journal articles (18 manuscripts)

Status `downloaded_manual` typically means a PDF was fetched at ingest and sits in the local `companies/.../` folder, but the full text was never parsed. If the PDF is on disk, the parser can convert it. If not, the source URL below points to the journal landing page (ScienceDirect / Lancet / JAMA / BMJ Ophth / BJO).

- **Roche / Genentech / Vabysmo** — Efficacy, durability, and safety of intravitreal faricimab up to every 16 weeks for neovascular age-related macular degeneration (TENAYA and LUCERNE): two randomised, double-masked, phase 3, non-inferiority trials
  - Source: <https://www.sciencedirect.com/science/article/pii/S0140673622000101>
  - Archive page: <https://justinsyu.github.io/retina-data/company-documents/roche-genentech-vabysmo-efficacy-durability-and-safety-of-intravitreal-faricimab-up-to-every-16/>
  - Status flag: `downloaded_manual`

- **Roche / Genentech / Vabysmo** — TENAYA and LUCERNE: Two-Year Results from the Phase 3 Neovascular Age-Related Macular Degeneration Trials of Faricimab with Treat-and-Extend Dosing in Year 2
  - Source: <https://www.sciencedirect.com/science/article/pii/S0161642024001349>
  - Archive page: <https://justinsyu.github.io/retina-data/company-documents/roche-genentech-vabysmo-tenaya-and-lucerne-two-year-results-from-the-phase-3-neovascular-age-rel/>
  - Status flag: `downloaded_manual`

- **Roche / Genentech / Susvimo** — Archway Phase 3 Trial of the Port Delivery System with Ranibizumab for Neovascular Age-Related Macular Degeneration: 2-Year Results
  - Source: <https://www.sciencedirect.com/science/article/pii/S0161642023001355>
  - Archive page: <https://justinsyu.github.io/retina-data/company-documents/roche-genentech-susvimo-archway-phase-3-trial-of-the-port-delivery-system-with-ranibizumab-for-n/>
  - Status flag: `downloaded_manual`

- **Roche / Genentech / Susvimo** — End-of-Study Results for the Ladder Phase 2 Trial of the Port Delivery System with Ranibizumab for Neovascular Age-Related Macular Degeneration
  - Source: <https://www.sciencedirect.com/science/article/pii/S2468653020304474>
  - Archive page: <https://justinsyu.github.io/retina-data/company-documents/roche-genentech-susvimo-end-of-study-results-for-the-ladder-phase-2-trial-of-the-port-delivery-s/>
  - Status flag: `downloaded_manual`

- **Roche / Genentech / Susvimo** — Exudation in Patients With Neovascular Age-Related Macular Degeneration Treated With the Port Delivery System or Monthly Injections
  - Source: <https://www.sciencedirect.com/science/article/pii/S0002939423002817>
  - Archive page: <https://justinsyu.github.io/retina-data/company-documents/roche-genentech-susvimo-exudation-in-patients-with-neovascular-age-related-macular-degeneration/>
  - Status flag: `downloaded_manual`

- **Novartis / Beovu** — HAWK and HARRIER: Phase 3, Multicenter, Randomized, Double-Masked Trials of Brolucizumab for Neovascular Age-Related Macular Degeneration
  - Source: <https://www.sciencedirect.com/science/article/pii/S0161642018330185>
  - Archive page: <https://justinsyu.github.io/retina-data/company-documents/novartis-beovu-hawk-and-harrier-phase-3-multicenter-randomized-double-masked-trials-of-brolucizu/>
  - Status flag: `downloaded_manual`

- **Novartis / Lucentis** — Efficacy and Safety of Ranibizumab With or Without Verteporfin Photodynamic Therapy for Polypoidal Choroidal Vasculopathy: A Randomized Clinical Trial
  - Source: <https://jamanetwork.com/journals/jamaophthalmology/fullarticle/2656454>
  - Archive page: <https://justinsyu.github.io/retina-data/company-documents/novartis-lucentis-efficacy-and-safety-of-ranibizumab-with-or-without-verteporfin-photodynamic-th/>
  - Status flag: `downloaded_manual`

- **Novartis / Lucentis** — Comparison of Ranibizumab With or Without Verteporfin Photodynamic Therapy for Polypoidal Choroidal Vasculopathy: The EVEREST II Randomized Clinical Trial
  - Source: <https://jamanetwork.com/journals/jamaophthalmology/fullarticle/2768203>
  - Archive page: <https://justinsyu.github.io/retina-data/company-documents/novartis-lucentis-comparison-of-ranibizumab-with-or-without-verteporfin-photodynamic-therapy-for/>
  - Status flag: `downloaded_manual`

- **Bayer / Eylea / Eylea HD** — Intravitreal aflibercept 8 mg in neovascular age-related macular degeneration (PULSAR): 48-week results from a randomised, double-masked, non-inferiority, phase 3 trial
  - Source: <https://www.sciencedirect.com/science/article/pii/S0140673624000631>
  - Archive page: <https://justinsyu.github.io/retina-data/company-documents/bayer-eylea-eylea-hd-intravitreal-aflibercept-8-mg-in-neovascular-age-related-macular-degenerati/>
  - Status flag: `downloaded_manual`

- **Bayer / Eylea / Eylea HD** — Intravitreal Aflibercept Injection for Neovascular Age-related Macular Degeneration: Ninety-Six-Week Results of the VIEW Studies
  - Source: <https://www.sciencedirect.com/science/article/pii/S016164201300729X>
  - Archive page: <https://justinsyu.github.io/retina-data/company-documents/bayer-eylea-eylea-hd-intravitreal-aflibercept-injection-for-neovascular-age-related-macular-dege/>
  - Status flag: `downloaded_manual`

- **Regeneron / Eylea HD** — Intravitreal aflibercept 8 mg in neovascular age-related macular degeneration (PULSAR): 48-week results from a randomised, double-masked, non-inferiority, phase 3 trial
  - Source: <https://www.sciencedirect.com/science/article/pii/S0140673624000631>
  - Archive page: <https://justinsyu.github.io/retina-data/company-documents/regeneron-eylea-hd-intravitreal-aflibercept-8-mg-in-neovascular-age-related-macular-degeneration/>
  - Status flag: `downloaded_manual`

- **Regeneron / Eylea HD** — Aflibercept 8 mg in Polypoidal Choroidal Vasculopathy: Post Hoc Analysis of the PULSAR Randomized Clinical Trial
  - Source: <https://jamanetwork.com/journals/jamaophthalmology/fullarticle/2842906>
  - Archive page: <https://justinsyu.github.io/retina-data/company-documents/regeneron-eylea-hd-aflibercept-8-mg-in-polypoidal-choroidal-vasculopathy-post-hoc-analysis-of-th/>
  - Status flag: `downloaded_manual`

- **Amgen / Pavblu** — Randomized Trial of Biosimilar ABP 938 Compared with Reference Aflibercept in Adults with Neovascular Age-Related Macular Degeneration
  - Source: <https://www.sciencedirect.com/science/article/pii/S2468653025003513>
  - Archive page: <https://justinsyu.github.io/retina-data/company-documents/amgen-pavblu-randomized-trial-of-biosimilar-abp-938-compared-with-reference-aflibercept-in-adult/>
  - Status flag: `downloaded_manual`

- **Biogen / Samsung Bioepis / Byooviz** — Efficacy and Safety of a Proposed Ranibizumab Biosimilar Product vs a Reference Ranibizumab Product for Patients With Neovascular Age-Related Macular Degeneration: A Randomized Clinical Trial
  - Source: <https://jamanetwork.com/journals/jamaophthalmology/fullarticle/2772987>
  - Archive page: <https://justinsyu.github.io/retina-data/company-documents/biogen-samsung-bioepis-byooviz-efficacy-and-safety-of-a-proposed-ranibizumab-biosimilar-product/>
  - Status flag: `downloaded_manual`

- **Biogen / Samsung Bioepis / Byooviz** — Biosimilar SB11 versus reference ranibizumab in neovascular age-related macular degeneration: 1-year phase III randomised clinical trial outcomes
  - Source: <https://bjo.bmj.com/content/107/3/384>
  - Archive page: <https://justinsyu.github.io/retina-data/company-documents/biogen-samsung-bioepis-byooviz-biosimilar-sb11-versus-reference-ranibizumab-in-neovascular-age-r/>
  - Status flag: `downloaded_manual`

- **Samsung Bioepis / Biogen / Opuviz** — Efficacy and Safety of the Aflibercept Biosimilar SB15 in Neovascular Age-Related Macular Degeneration: A Phase 3 Randomized Clinical Trial
  - Source: <https://jamanetwork.com/journals/jamaophthalmology/fullarticle/2805760>
  - Archive page: <https://justinsyu.github.io/retina-data/company-documents/samsung-bioepis-biogen-opuviz-efficacy-and-safety-of-the-aflibercept-biosimilar-sb15-in-neovascu/>
  - Status flag: `downloaded_manual`

- **Samsung Bioepis / Biogen / Opuviz** — Biosimilar SB15 versus reference aflibercept in neovascular age-related macular degeneration: 1-year and switching results of a phase 3 clinical trial
  - Source: <https://bmjophth.bmj.com/content/8/1/e001561>
  - Archive page: <https://justinsyu.github.io/retina-data/company-documents/samsung-bioepis-biogen-opuviz-biosimilar-sb15-versus-reference-aflibercept-in-neovascular-age-re/>
  - Status flag: `downloaded_manual`

- **Sandoz / Cimerli** — Efficacy and Safety of Biosimilar FYB201 Compared with Ranibizumab in Neovascular Age-Related Macular Degeneration
  - Source: <https://www.sciencedirect.com/science/article/pii/S0161642021003250>
  - Archive page: <https://justinsyu.github.io/retina-data/company-documents/sandoz-cimerli-efficacy-and-safety-of-biosimilar-fyb201-compared-with-ranibizumab-in-neovascular/>
  - Status flag: `downloaded_manual`

## D. Placeholder PDFs on disk with no source URL (5 records)

These have a PDF file but the source URL was never captured at ingest, and several have placeholder titles (`Review`, `ARTICLE`) suggesting the title field could not be read from the PDF metadata. The local PDF is the only handle.

- **Clearside Biomedical / CLS-AX** — Review
  - Archive page: <https://justinsyu.github.io/retina-data/company-documents/clearside-biomedical-cls-ax-review/>
  - Status flag: `placeholder_pdf_available`

- **Clearside Biomedical / CLS-AX** — Evaluation of Long-Lasting Potential of Suprachoroidal Axitinib Suspension Via Ocular and Systemic Disposition in Rabbits
  - Archive page: <https://justinsyu.github.io/retina-data/company-documents/clearside-biomedical-cls-ax-evaluation-of-long-lasting-potential-of-suprachoroidal-axitinib-susp/>
  - Status flag: `placeholder_pdf_available`

- **Clearside Biomedical / CLS-AX** — ARTICLE
  - Archive page: <https://justinsyu.github.io/retina-data/company-documents/clearside-biomedical-cls-ax-article/>
  - Status flag: `placeholder_pdf_available`

- **Ocular Therapeutix / AXPAXLI / OTX-TKI** — OTX-TKI, Sustained-Release Axitinib Hydrogel Implant, for Neovascular Age-Related Macular Degeneration
  - Archive page: <https://justinsyu.github.io/retina-data/company-documents/ocular-therapeutix-axpaxli-otx-tki-2023-retina-society-avery-final-10-12-2023-v2-0/>
  - Status flag: `placeholder_pdf_available`

- **Ocular Therapeutix / AXPAXLI / OTX-TKI** — OTX-TKI From Phase 1 to Phase 3: SOL-1 and SOL-R Trials for Neovascular AMD
  - Archive page: <https://justinsyu.github.io/retina-data/company-documents/ocular-therapeutix-axpaxli-otx-tki-angiogenesis-2025-danzig-final/>
  - Status flag: `placeholder_pdf_available`

---

Once a full-text markdown drops into `companies/<sponsor>/<program>/published_manuscripts/<filename>.md`, run:

```
python scripts/build_infographic_manifest.py > scripts/infographic_manifest.json
```

then dispatch the infographic-generation subagent for the new record (see `scripts/infographic_generation_prompt.md`).
