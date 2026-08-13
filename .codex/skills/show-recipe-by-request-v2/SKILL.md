---
name: show-recipe-by-request-v2
description: Generate a requested recipe as a 3-section photo card PDF (Assumptions, Required incl. timeline, Steps), adapted to the user's owned kitchen appliances, programs, settings, accessories and parts, using real photos for concrete things and icons only for abstract ones. Use when the user asks to show, prepare, plan or generate a recipe/recepee/meal/cooking procedure and wants a precise, scannable, appliance-specific plan or PDF output.
---

# Show Recipe By Request v2

## Goal

One glanceable cooking plan. A cook reads it standing at the counter with flour
on their hands: they must find the next action in under two seconds, and must be
able to recognise every object by its picture.

Precision comes from **structure and pictures, not prose**.

## Output contract

Exactly three numbered sections, always in this order:

| # | Section | Answers |
| --- | --- | --- |
| 1 | **Assumptions** | What I decided for you, why, and how to overrule it |
| 2 | **Required** | Time budget, timeline, tools + parts, ingredients |
| 3 | **Steps** | Do this, with this thing (shown), at this setting, until this |

Checkpoints render under the timeline. Diagrams and food safety come last.
Nothing else is a top-level section.

## Pictures beat words

- **Concrete thing → photo.** Appliances, attachments, bowls, beaters, discs,
  ingredients, control panels, program dials. Photos come from
  `raw/kitchen-tools/images/` (appliances and their parts) and
  `raw/food/images/` (ingredients).
- **Abstract thing → icon.** Time, temperature, speed, waiting, chilling,
  checkpoints, "done", the step's own action. `scripts/icons.py` has the set.
- Missing photo? The renderer falls back to the matching icon automatically —
  but first try to get the photo (see caching below).
- **A step shows what it uses.** Name the step's `tool` exactly as the tool card
  in section 2 and the renderer reuses that appliance photo; name `accessory`
  exactly as one of its `parts` and that part photo is shown too. Add
  `photos: [{image, caption}]` for anything else the step needs to show — a
  manual page, a control-dial photo, a program symbol.
- **Diagrams must survive print.** Minimum 24 px type in a ≤1100 px-wide SVG,
  numbered layers matching the build order, direct labels, no legend keys. If
  the label needs a sentence, put the sentence in the diagram, not in a caption.

## Photo sourcing and caching

1. **Appliances and parts**: search `raw/kitchen-tools/` — the accessory photos
   are usually already downloaded and listed in a per-appliance raw file, e.g.
   `raw/kitchen-tools/2026-08-13-kenwood-kwl90-244si-full-set.md` maps every
   bundled tool (5L bowl, K-beater, whisk, dough hook, spatula, splashguard,
   food-processor discs) to an image path. Use those paths in `parts`.
2. **Ingredients**: cache them once, reuse forever:
   `python3 .codex/skills/show-recipe-by-request-v2/scripts/fetch_food_photos.py --spec <spec>.json --write`
   downloads Wikipedia/Wikimedia thumbnails into `raw/food/images/`, appends
   provenance to `raw/food/images/SOURCES.md`, and writes `photo` paths back
   into the spec. Already-cached files are skipped. Anything it misses
   (disambiguation pages, rate limits): rerun with a better name, e.g.
   `fetch_food_photos.py "chicken egg" "bread crumbs"`.
3. Never hotlink a remote URL from the spec — the PDF inlines local files only.

## Section 1 — Assumptions is prose-allowed

This is the one section that may use sentences. Each assumption is:

- a **short headline** (≤ 8 words), plus
- a **note** (≤ 25 words) that says *why* and *what to do if the user disagrees*.

State the interpretation of the request, equipment guesses, unconfirmed
programs, and any ingredient judgement (apple type, sweetness, tray size).

## Programs: look for the real one

Before writing "program unconfirmed", dig:

- `wiki/kitchen-tools/kitchen-appliance-inventory.md`
- `raw/kitchen-tools/<appliance>*.md` and `raw/kitchen-tools/manuals/`

Then say precisely what is known. Some appliances have numbered programs
(Instant Pot, bread maker); some are rotary-symbol machines with **no program
numbers at all** — for those, name the dial symbol to select ("fan/convection
symbol on the left dial") and record in Assumptions that the model is
unidentified. Never invent a program ID, model number, temperature or timing.

## Entity rules

- Sections 2 and 3: one line per entity, no paragraphs. Budgets are in
  `references/recipe-card-schema.md`.
- Parameters are chips, one value each: `fan 180 C`, `speed 1-2`, `12 min`,
  `Program 3`, `probe 74 C`. Never a sentence in a chip.
- Step title = imperative verb first: `Mix shortcrust dough`.
- Every step ends with `done`: an **observable** cue (`juices bubble through
  vents`), never a duration restated.
- Ingredients render as one vertical list: photo, name, amount, note.

## Workflow

1. Read the local knowledge base: `wiki/kitchen-tools/kitchen-appliance-inventory.md`,
   then `raw/kitchen-tools/` for models, parts, programs, photos. No inventory →
   ask for the appliance list, or proceed and log the guess as an assumption.
2. Resolve only blocking unknowns (servings, dish, diet, deadline, cooks).
   Everything else: sane default, recorded in section 1.
3. Assign appliances. Treat anything in `wiki/` or `raw/` as owned — never write
   `if available` for confirmed tools.
4. Build the timeline before the steps: one lane per person, one lane per
   appliance that runs unattended. Lanes are what prove the plan is parallel.
5. Multi-cook: `cook` on every step plus `sync_points` with exact readiness
   criteria.
6. Cache ingredient photos (above), then render from the project root:
   `python3 .codex/skills/show-recipe-by-request-v2/scripts/render_recipe_card.py <spec>.json`
7. Report the PDF path and any assumption the user may want to overrule.

## Renderer notes

- Spec format: `references/recipe-card-schema.md`; worked example:
  `references/example-apple-pie.json`.
- Icons auto-resolve from text; set `icon` only to override a wrong guess. Add
  new pictograms to `ICONS` in `scripts/icons.py` rather than shipping a
  generic dot.
- Images are inlined as data URIs; use project-root-relative paths.
- The timeline SVG is generated from `required.timeline` — never hand-write
  timeline HTML and never show raw markup to the user.
- PDF engine: `weasyprint`, then `pandoc`, then a plain-text PDF. Only the first
  gives the designed layout.

## Quality bar

- [ ] Three sections, in order, nothing else at top level.
- [ ] Every assumption has a headline **and** a why/override note.
- [ ] Every appliance shows a photo; its used parts show photos too.
- [ ] Every ingredient shows a photo (icon only where no photo exists).
- [ ] Every step that uses an appliance/part shows it.
- [ ] Icons used only for abstract things (time, heat, speed, done, action).
- [ ] Every step has settings chips and an observable `done` cue.
- [ ] Every unattended appliance has its own timeline lane.
- [ ] Timeline and diagram text readable at 100 % print scale.
- [ ] Uncertain facts appear in Assumptions, never silently inside a step.
- [ ] Metric units; Fahrenheit only when it helps.

## Scope

Writes recipe artifacts (`recipes/*.json|html|pdf`, `recipes/assets/*.svg`) and
the photo cache (`raw/food/images/` + its `SOURCES.md`, append-only). Does not
edit `wiki/` or existing `raw/` evidence files.
