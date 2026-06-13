# Glaucoma Data Archive

This repository publishes a GitHub Pages archive of public source records for approved and investigational glaucoma treatments.

## Structure

- `_data/` contains the generated manifests used by index pages.
- `companies/`, `programs/`, `indications/`, and `company-documents/` contain stable Jekyll entry points.
- `scripts/generate_glaucoma_seed_data.py` regenerates the seed data, placeholder pages, local logo SVGs, and ClinicalTrials.gov roster.
- `llamaparse.py` is copied from the source framework for future document parsing with the same LlamaIndex/LlamaParse workflow.

## Regenerate Seed Data

```sh
python scripts/generate_glaucoma_seed_data.py
```

## Publish With GitHub Pages

1. Push this repository to GitHub.
2. In the GitHub repo, open **Settings > Pages**.
3. Set **Build and deployment** to **Deploy from a branch**.
4. Select the `main` branch and `/ (root)` folder.
5. Save, then wait for the Pages deployment to finish.

The current Pages settings in `_config.yml` assume:

```yml
url: "https://justinsyu.github.io"
baseurl: "/glaucoma-data"
```
