# Asset Acquisition Playbook

Manuals and photos are the point of this skill. A prose "source extract" is the
**fallback**, never the plan. This file says how to actually get files onto disk
and what to do when you cannot.

Always download through the helper — it verifies magic bytes, rejects Cloudflare
HTML saved as `.pdf`, and logs every attempt:

```bash
python3 .codex/skills/add-kitchen-appliance/scripts/fetch_asset.py \
  --kind manual --device "AEG Competence BE3002420M" \
  --name aeg-be3002420m-user-manual.pdf --source "AEG official manuals" \
  URL1 URL2 URL3      # fallback ladder, first verified hit wins
```

Add `--kind image [--exact]` for photos (it also indexes `images/README.md`), and
`--referer <page-url>` for hosts that check it.

## Ladder — try in this order, stop at the first verified file

1. **Official manual portal**, model or PNC keyed.
   - AEG / Electrolux / Zanussi: `www.aeg.<tld>/support/user-manuals/`,
     documents served from `electrolux-ui.com`; the PNC (e.g. `94418586600`)
     works when the model string does not. Spare-part shops
     (`shop.aeg.co.uk/model/m/<MODEL>`) give the PNC, part numbers and wattages.
   - Kenwood: `kenwoodworld.com` product page → *Downloads*.
   - Instant Pot, Sage, Tefal, Princess, Morphy Richards, CASO, Samsung: product
     support page → *Manuals/Downloads*.
2. **Official regional sites** — `.co.uk`, `.de`, `.nl`, `.ch`. Old models
   often survive on one locale only.
3. **Retailer listing supplied by the user** (Amazon ASIN page) — good for
   product photos, accessory photos, dimensions, wattage.
4. **Certification / device databases** — FCC, EPREL/EU energy label, VDE. These
   give verifiable electrical and efficiency data.
5. **Manual mirrors** (manualslib, manualzz, manymanuals, bedienungsanleitu.ng).
   Usually Cloudflare-gated: the download URL returns HTTP 403 or an HTML
   wrapper. Their *page text* is still citable evidence — table of contents,
   function lists, specs. Cite the page, do not fake the PDF.

## What counts as failure

- HTTP 403/404/timeout, or a file whose magic bytes are not the extension.
- The helper logs these to `raw/kitchen-tools/ACQUISITION-LOG.md` and exits 1.
- Then, and only then, write a markdown source extract — and set
  `Manual: NOT ACQUIRED` in the device section with the attempt count. Never let
  a missing manual disappear into a Notes sentence.

## Images to collect per device

| Image | Why | Filename |
| --- | --- | --- |
| Product shot | recipe cards, recognition | `<slug>-product.jpg` |
| Control panel / dials close-up | steps show real settings | `<slug>-controls.jpg` |
| Function/program symbols | rotary ovens have symbols, not numbers | `<slug>-functions.jpg` |
| Each included accessory | recipe steps show the part | `<slug>-<part>.jpg` |

`<slug>` = brand-model, kebab-case (`aeg-be3002420m`). Mark a photo `--exact`
only when the source page is that exact model; otherwise it is representative
and must say so in `images/README.md`.

Manual pages are usable as images: crop the function table or the program chart
out of the PDF and store it as `<slug>-functions.png`, cited to page N. Recipe
steps render those directly.

## Never

- Never save an HTML page as `.pdf` (the helper blocks it — do not work around it).
- Never invent a model, PNC, wattage, temperature, program number or capacity.
- Never hotlink: recipe rendering inlines local files only.
- Never delete or rewrite an existing raw evidence file; add a new dated one.
