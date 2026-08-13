# Device Section Format

Use this format in `raw/kitchen-tools/kitchen-appliance-inventory.md`. Keep
headings device-specific and preserve existing source statements.

A device section has three mandatory blocks — **header**, **assets**, **specs** —
plus two tables that make the device usable in a recipe: **functions/programs**
and **accessories**. A section without those tables is not finished; a bullet
saying "the manual covers oven functions" is a table of contents, not a fact.

## 1. Header

```markdown
### Brand device type - model / exact-or-representative identity

Title: Manufacturer product title, if sourced
- Status: Exact / user-stated / assumed closest match / representative only / not purchased.
- User input: short pointer to supplied link, ASIN, photo, or statement.
- Identity: brand, model, SKU/item no., PNC, ASIN, EAN, type, approx. year.
```

## 2. Assets

Every line is a path or the literal word `NOT ACQUIRED` plus the attempt count.
Missing assets stay visible so a later run retries them.

```markdown
- Manual: manuals/aeg-be3002420m-user-manual.pdf
  (or) Manual: NOT ACQUIRED — 5 sources tried, see ACQUISITION-LOG.md 2026-08-13
- Source extracts: manuals/<slug>-source-extract.md
- Product photo: images/<slug>-product.jpg (exact | representative)
- Control-panel photo: images/<slug>-controls.jpg
- Function-symbol photo: images/<slug>-functions.png (manual p. 7)
- Accessory photos: images/<slug>-<part>.jpg; ...
```

## 3. Specs

One line per axis, units always, source-traceable:

```markdown
- Electrical: 2400 W fan element / 1000-1900 W top element, 230 V.
- Capacity/dimensions: 74 L gross, 60 cm built-in niche, ...
- Operating ranges: 50-275 C; timer 0-120 min; 3 shelf levels.
- Controls/connectivity: 2 rotary dials + red electronic programmer; no app.
- Cleaning/safety/limits: catalytic liners, max fill, warnings affecting usage.
- Notes/uncertainty: what still needs rating-plate/manual confirmation.
```

## 4. Functions / programs table (mandatory)

This is what recipes select. Rotary appliances have **symbols, not numbers** —
then the Selector column names the symbol and the photo shows it.

```markdown
| # | Function / program | Selector | Temp / setting | Use for | Source |
| --- | --- | --- | --- | --- | --- |
| 1 | Fan cooking | fan symbol, left dial | 50-275 C | multi-level baking | manual p. 12 |
| 2 | Top/bottom heat | two-bar symbol | 50-275 C | single tray, cakes | manual p. 12 |
| 3 | Pizza setting | pizza symbol | 180-250 C | crisp base | manual p. 14 |
```

If the appliance has no programs at all, write one row: `none — manual dials
only`, sourced. Do not leave the table out and do not guess rows.

## 5. Accessories / included tools table (mandatory when parts exist)

Recipe steps show these photos, so the path column is the whole point.

```markdown
| Accessory | Model/part no. | Photo | Used for |
| --- | --- | --- | --- |
| 5 L stainless bowl | KAT91 | images/kenwood-kwl90-5l-stainless-bowl.jpg | doughs, batters |
| K-beater | — | images/kenwood-kwl90-stainless-k-beater.jpg | rubbing butter into flour |
```

Unknown part number: `—`. Missing photo: leave the cell empty and log the
acquisition attempt — do not delete the row.

## Confidence Language

- Exact model: user's link/model, official page and downloaded manual agree.
- User-stated model: user supplied a model, no official source confirms ownership.
- Assumed closest match: photo/description points strongly to a model, label unseen.
- Representative only: same-brand/same-family source, owned model unknown.
- Not purchased: planned device; do not download owned-device manuals yet.

## Source Extracts

For HTML pages, blocked PDF downloads, or representative sources, create a
markdown source extract under `raw/kitchen-tools/manuals/`:

```markdown
# Product name - source extract

> Source: Official/manual/retailer/source name.
> Source URL: https://example.com/product
> Collected: YYYY-MM-DD
> Published: Unknown

## Identity

- Product:
- Model/SKU/PNC:

## Confirmed functions and parameters

- ...

## Uncertainty

- ...
```

## Image Index Entries

In `raw/kitchen-tools/images/README.md` (the helper appends these automatically):

- Exact-model photos/icons: source model matches the confirmed appliance/tool.
- Generic/representative photos: useful visual match, exact model unconfirmed.

Include source identity in one sentence. Update entries when a model is confirmed.
