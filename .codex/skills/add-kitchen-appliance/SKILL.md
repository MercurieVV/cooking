---
name: add-kitchen-appliance
description: Use when adding or updating a kitchen appliance, attachment, accessory, tool, probe, oven, cooker, blender, mixer, bread maker, air fryer, vacuum sealer, or similar kitchen device in this cooking repository. Downloads the real manual PDF and real product/control/accessory photos, extracts functions, programs, settings and parameters into tables, and updates raw/kitchen-tools plus the wiki. Trigger when the user gives a brand, model, SKU, ASIN, link or photo and wants manuals, pictures, specs, accessories, programmes or features added.
---

# Add Kitchen Appliance

Turn partial appliance info into **files on disk and tables of facts**: manual,
photos, functions/programs, parameters, accessories — traceable to sources and
directly usable by `show-recipe`.

## Definition of done

A device is added only when all of these are true. Anything not achieved is
written down as `NOT ACQUIRED` with the attempt count — never silently dropped.

- [ ] Manual PDF on disk in `raw/kitchen-tools/manuals/`, verified as a real PDF
      — or a logged failure after working the full source ladder.
- [ ] Product photo on disk, marked exact vs representative.
- [ ] Control-panel / function-symbol photo on disk (the thing a cook actually
      looks at while cooking).
- [ ] A photo per included accessory that recipes will use.
- [ ] Functions/programs **table** filled: selector, temperature/setting, use,
      source. Not a sentence saying which chapters the manual has.
- [ ] Specs filled with units: power, capacity, dimensions, ranges, timers.
- [ ] Accessories **table** with part numbers and photo paths.
- [ ] `raw/kitchen-tools/kitchen-appliance-inventory.md` updated in the canonical
      format; `images/README.md` and `ACQUISITION-LOG.md` updated.
- [ ] Wiki article updated and `wiki/log.md` appended.
- [ ] Every number traceable to a linked source; nothing invented.

## Inputs

Any mix of brand, model, SKU, ASIN, retailer link, photo description, label
text, or accessory name. Exact model unclear → research likely matches, mark
them **representative** until the user confirms the rating plate.

## Workflow

1. **Read context first**: `raw/kitchen-tools/kitchen-appliance-inventory.md`,
   `raw/kitchen-tools/images/README.md`, `raw/kitchen-tools/ACQUISITION-LOG.md`
   (do not re-try what failed minutes ago; do re-try old failures),
   `wiki/kitchen-tools/kitchen-appliance-inventory.md`, and any existing file for
   this device.
2. **Identify**: model, PNC/item number, year, family. For AEG/Electrolux the
   spare-parts model page yields the PNC, which unlocks the official manual.
3. **Acquire assets** — this is the job, not an optional extra. Follow
   `references/acquisition-playbook.md` and download with:
   ```bash
   python3 .codex/skills/add-kitchen-appliance/scripts/fetch_asset.py \
     --kind manual --device "<brand model>" --name <slug>-user-manual.pdf \
     --source "<source name>" URL1 URL2 URL3
   ```
   It verifies magic bytes (an HTML gate saved as `.pdf` is rejected), appends
   every attempt to `raw/kitchen-tools/ACQUISITION-LOG.md`, and indexes images in
   `images/README.md`. Exit 1 = nothing acquired; work the next rung of the
   ladder before giving up.
4. **Extract structure, not prose**. From the PDF/pages pull: identity,
   electrical, capacity/dimensions, ranges, timers, **every function/program with
   its selector and temperature**, sensors/connectivity, included accessories
   with part numbers, cleaning/safety limits, and explicit uncertainties. Cite
   page numbers when the source is a PDF.
5. **Crop what a cook needs to see**. Function-symbol charts, program tables and
   control panels from the manual become images (`<slug>-functions.png`) so
   recipe steps can show the real dial instead of describing it.
6. **Write the device section** using `references/device-section-format.md`,
   including the functions/programs table and the accessories table.
7. **Update the wiki** article and append `wiki/log.md`. Keep each wiki fact
   linked to its raw file.
8. **Report**: files downloaded (with sizes), tables filled, what is still
   `NOT ACQUIRED` and which sources were tried, and what needs the rating plate.

## Feeds the recipe skill

`show-recipe` reads this data. Write it so that skill can pick it
up without re-researching:

- accessory rows give it `parts[].image` paths for step photos,
- the functions table gives it the `program` chip — real symbol names for
  rotary appliances, real numbers for programmed ones,
- ranges give it valid temperature/speed chips.

If the appliance has no numbered programs, say so explicitly in the table so the
recipe skill names the dial symbol instead of inventing "Program 3".

## Repository Rules

- `raw/` is source evidence: add new dated files, never rewrite facts in place.
- Every wiki fact traceable to a linked `raw/` file.
- Shell commands use the `rtk` prefix; prefer `rg`/`rg --files` for search.
- Use `apply_patch` for manual file edits.
- Uncertain device → `Status:` + `Representative` notes. Never invent specs.

## References

- `references/acquisition-playbook.md` — source ladder, gated mirrors, image list.
- `references/device-section-format.md` — inventory section, required tables.
- `scripts/fetch_asset.py` — verified, logged downloader.
