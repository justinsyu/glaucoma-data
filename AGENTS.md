# Glaucoma Data Archive

Project-specific conventions for future work on this repo.

## Content

- Keep scientific, neutral language in rendered pages.
- Avoid em dashes in shipped content, CSS, JS, generated markdown, and prompts.
- Use "trials" or "studies" for clinical work and "participants" for enrollment counts.
- Every claim about approval status, trial status, ownership, or recent pipeline progress should cite a primary source when possible.

## Styling

- Reuse the copied archive framework and its existing CSS components.
- `_data/company_profiles.json` is the single source of truth for sponsor colors and logo paths.
- Company logo assets should be local to this repository and should show the full company name where practical.

## Publishing

- GitHub Pages builds from the repository root on `main`.
- After changing source data, run the Jekyll build locally before handoff.
