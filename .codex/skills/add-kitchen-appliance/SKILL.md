---
name: add-kitchen-appliance
description: Use when adding or updating a kitchen appliance, attachment, accessory, tool, probe, oven, cooker, blender, mixer, bread maker, air fryer, vacuum sealer, or similar kitchen device in this cooking repository. Trigger when the user provides partial product info and wants manuals, schematics, specifications, pictures, icons, accessories/tools, feature extraction, and updates under raw/kitchen-tools.
---

# Add Kitchen Appliance

Use this skill to turn partial appliance/tool information into traceable source evidence and a normalized inventory entry.

## Inputs

The user may provide any mix of:

- Brand, model, SKU, ASIN, retailer link, photo description, manual, label text, or accessory name.
- A request to add manuals, pictures, icons, specs, tools, accessories, programmes, features, or parameters.

If the exact model is unclear, research likely matches but mark them as representative until the user confirms the label/model.

## Workflow

1. Inspect existing inventory context:
   - `raw/kitchen-tools/kitchen-appliance-inventory.md`
   - `raw/kitchen-tools/images/README.md`
   - `wiki/kitchen-tools/kitchen-appliance-inventory.md`
   - Relevant existing files under `raw/kitchen-tools/`
2. Research current sources. Prefer official manufacturer pages, official support/manual pages, retailer pages supplied by the user, certification/device-report pages, and reputable manual mirrors when official PDFs are unavailable.
3. Download or create source evidence in `raw/kitchen-tools/`:
   - PDFs/manuals/safety sheets/spec sheets: `raw/kitchen-tools/manuals/`
   - Product, tool, accessory, feature, and icon images: `raw/kitchen-tools/images/`
   - Markdown source extracts when sources are HTML, PDF download is blocked, or the model is representative.
4. Validate downloaded files with `file`; do not keep HTML wrappers with `.pdf` extensions.
5. Extract structured facts:
   - identity: brand, model, type, SKU, item no., ASIN/EAN when known
   - manuals/source paths
   - electrical parameters, dimensions, weight, capacity, temperature range, pressure levels, speeds, timers, programmes, presets, app/connectivity, sensors, safety/cleaning features
   - included tools/accessories and their model numbers where published
   - feature/parameter icons or images when available
   - limitations/uncertainties
6. Update `raw/kitchen-tools/kitchen-appliance-inventory.md` using the canonical format in `references/device-section-format.md`.
7. Update `raw/kitchen-tools/images/README.md` for every new image/icon.
8. Update the compiled wiki article and append `wiki/log.md` if wiki files are changed.
9. Final response should summarize changed files, downloaded manuals/images, representative assumptions, and verification performed.

## Repository Rules

- Treat `raw/` as source evidence. Add new evidence files instead of silently replacing facts.
- Keep every fact in wiki traceable to `raw/`.
- Use the repo command convention: shell commands should use the `rtk` prefix.
- Use `rg`/`rg --files` before slower search tools.
- Use `apply_patch` for manual file edits.
- Do not invent specs for uncertain devices. Use `Status:` and `Representative` notes.

## Format Reference

Read `references/device-section-format.md` before editing the inventory.
