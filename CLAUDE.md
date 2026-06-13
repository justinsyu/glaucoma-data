# Glaucoma Data Archive

This repo reuses the copied source archive framework for a glaucoma-focused GitHub Pages archive.

## Local workflows

- Regenerate seed data with `python scripts/generate_glaucoma_seed_data.py`.
- Build the site with `bundle exec jekyll build` after data or layout changes.
- Future document parsing should use the copied `llamaparse.py` workflow and a local `.env` file if credentials are added later.

## Data scope

The seed archive tracks public records for approved and investigational glaucoma or ocular hypertension treatments, including FDA labels, sponsor releases, congress updates, and ClinicalTrials.gov records.
