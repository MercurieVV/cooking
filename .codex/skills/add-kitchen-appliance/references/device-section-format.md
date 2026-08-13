# Device Section Format

Use this format in `raw/kitchen-tools/kitchen-appliance-inventory.md`. Keep headings device-specific and preserve existing source statements.

```markdown
### Brand device type - model / exact-or-representative identity

Title: Manufacturer product title, if sourced
- Status: Exact / user-stated / assumed closest match / representative only / not purchased.
- User input: short pointer to supplied link, ASIN, photo, or statement when useful.
- Local manual: manuals/example-manual.pdf
- Local manuals: manuals/example-manual.pdf; manuals/example-safety.pdf
- Local source extract: manuals/example-source-extract.md
- Product images: images/example-product.jpg
- Feature images/icons: images/example-feature.webp; images/example-icon.svg
- Identity: brand, model, SKU/item number, ASIN, EAN, type.
- Electrical: wattage, voltage, frequency, battery, charging.
- Capacity/dimensions: bowl/tank/loaf/probe capacity, dimensions, weight.
- Operating ranges: temperature, pressure, speeds, timers, presets, programmes.
- Controls/connectivity: display, app, WiFi/Bluetooth, sensors, scales, probe, lights.
- Included tools/accessories: model numbers and names; note when model numbers are not published.
- Cleaning/safety/limits: dishwasher-safe parts, non-stick, overheat protection, fill limits, max dough/flour/yeast, warnings that affect usage.
- Notes/uncertainty: what still needs label/photo/manual confirmation.
```

## Confidence Language

- Exact model: use when the user's link/model, official page, and downloaded manual match.
- User-stated model: use when the user supplied a model but no official source confirms ownership.
- Assumed closest match: use when photo/description points strongly to a model but label is not visible.
- Representative only: use for same-brand/same-family sources when the owned model is unknown.
- Not purchased: use for planned devices; do not download owned-device manuals unless the user selected a model.

## Source Extracts

For HTML pages, blocked PDF downloads, or representative sources, create a markdown source extract under `raw/kitchen-tools/manuals/`:

```markdown
# Product name - source extract

> Source: Official/manual/retailer/source name.
> Source URL: https://example.com/product
> Collected: YYYY-MM-DD
> Published: Unknown

## Identity

- Product:
- Model/SKU/item no.:

## Confirmed functions and parameters

- ...

## Uncertainty

- ...
```

## Image Index Entries

In `raw/kitchen-tools/images/README.md`, classify images as:

- Exact-model photos/icons: source model matches confirmed appliance/tool.
- Generic/representative photos: useful visual match, but exact owned model not confirmed.

Include source identity in one sentence. Update entries when a model is confirmed.
