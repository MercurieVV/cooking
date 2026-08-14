---
name: show-recipe-by-request-v2
description: Generate a requested recipe as a 3-section photo card PDF and a VR-optimized interactive static HTML SPA (Assumptions, Required incl. timeline, Steps), adapted to the user's owned kitchen appliances, programs, settings, accessories and parts, using real photos for concrete things and icons only for abstract ones. Use when the user asks to show, prepare, plan or generate a recipe/recepee/meal/cooking procedure and wants a precise, scannable, appliance-specific plan, PDF, or interactive VR webpage output.
---

# Show Recipe By Request v2

## Goal

One glanceable cooking plan. A cook reads it standing at the counter with flour
on their hands: they must find the next action in under two seconds, and must be
able to recognise every object by its picture. Or they use it in a VR headset (Quest 3)
with hand tracking where they can swipe page-by-page.

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

## Interactive VR SPA (Webpage)

Opening the compiled HTML in a browser launches a full-screen, responsive Single Page Application (SPA) designed specifically for cooking in VR (e.g. Meta Quest 3):

- **Fixed Timeline Header**: A top navigation bar showing all stages (Overview, Setup, Timeline, Step 1..N, Done). The active page is highlighted and centered. Click or pinch a node to jump.
- **Horizontal Scroll Snapping**: Pages snap horizontally (`scroll-snap-type: x mandatory`). Swipe or use arrow keys to flip pages smoothly.
- **VR-Friendly Arrows**: Huge, high-contrast semi-transparent buttons (`80px x 140px`) float on the screen edges for effortless hand-tracking pinch clicks.
- **3-Column Step Layout**:
  1. *Left column*: Ingredients needed specifically for the current step.
  2. *Center column*: Step title, settings chips, instruction, done cue, diagrams/photos.
  3. *Right column*: **What's Left** (a vertical list of subsequent steps, highlighting the next one).
- **Print stylesheet parity**: In print mode (`@media print`), the SPA controls are hidden and the document prints linearly to WeasyPrint exactly like the PDF card design.


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
2. **Ingredients**: cache them once, reuse forever. Try rimi.lv (Latvian
   grocery e-shop) first — it shows the exact local product the user would
   actually buy, which is more useful than a generic illustration:
   1. `python3 .codex/skills/show-recipe-by-request-v2/scripts/fetch_rimi_photo.py --list <latvian-term>`
      — rimi.lv's search is fuzzy/typo-tolerant, not translated, so an
      English query returns nonsense (`butter` matched "Butter Chicken
      sauce" and "Bitter" drinks, not `sviests`). Translate the ingredient
      to its plain Latvian grocery-shelf name yourself before searching.
   2. Eyeball the listed candidates — pick the plain product (`Sviests
      Rimi 82% 200g`), not a ready-meal, sauce, or unrelated product that
      happens to share a word.
   3. `fetch_rimi_photo.py --pick <latvian-term> <index> --slug <ingredient-slug>`
      downloads the chosen photo into `raw/food/images/<slug>.jpg` and logs
      the query, product name/code and page URL to
      `raw/food/images/SOURCES.md`.
   Only fall back to Wikipedia/Wikimedia when rimi.lv has no reasonable
   match (e.g. spices/flavors not commonly sold as a single retail item):
   `python3 .codex/skills/show-recipe-by-request-v2/scripts/fetch_food_photos.py --spec <spec>.json --write`
   downloads Wikipedia/Wikimedia thumbnails into `raw/food/images/`, appends
   provenance to `raw/food/images/SOURCES.md`, and writes `photo` paths back
   into the spec (already-cached files are skipped; misses need a better
   name, e.g. `fetch_food_photos.py "chicken egg" "bread crumbs"`).
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

- **Simplified appliance names**: Use short, user-friendly names (e.g., "Kenwood mixer" instead of "Kenwood Titanium Chef Patissier XL KWL90.244SI", "AEG oven" instead of "AEG Competence BE3002420M", "Caso water dispenser" instead of "Caso Design HW 660 Turbo").
- **No manual/function chart images in parts**: Never list a manual page or function/speed chart as a tool `part`, and never point a step's `accessory` at one either (e.g. a "Function symbols" page scan). Name the function in the `program` field and the dial symbol/setting in `settings` or the step's `do` text instead — a photo of a printed chart is not a usable picture.
- **Use an appliance's built-in features before adding a separate tool, and make them visible, not just prose.** Check `raw/kitchen-tools/<appliance>*.md` / `wiki/kitchen-tools/kitchen-appliance-inventory.md` for things like an integrated scale, timer, or probe (e.g. the Kenwood mixer's bowl has an integrated scale to 1 g). Whenever a recipe actually needs that feature (any step that weighs an ingredient into that appliance), add it as a `part` on the tool with a matching icon — `{"name": "Integrated scale", "icon": "scale"}` — even if there's no product photo of it, and point that step's `accessory` at it. Say it in `do` too. Do not send the cook to a generic "Worktop" or bare mixing-bowl for a weighing job the appliance already does — and don't add the scale part to a recipe/step that never weighs anything on it.
- Sections 2 and 3: one line per entity, no paragraphs. Budgets are in `references/recipe-card-schema.md`.
- Parameters are chips, one value each: `fan 180 C`, `speed 1-2`, `12 min`, `Program 3`, `probe 74 C`. Never a sentence in a chip.
- Step title = imperative verb first: `Mix shortcrust dough`. **The title must cover everything the step's `do` text does** — if `do` bundles unrelated actions (e.g. lining trays *and* weighing dry ingredients), either split into separate steps or broaden the title so nothing is done off-title.
- **Step `do` text is 1-2 full sentences, not a fragment.** Say what to do and the one detail that prevents a mistake (why it matters, what "sandy" or "thinner" means concretely) — terser than that reads as a checklist item, not an instruction a cook can follow standing at the counter.
- Every step ends with `done`: an **observable** cue (`juices bubble through vents`), never a duration restated.
- Ingredients render as one vertical list: photo, name, amount, note.
- **Step ingredients**: For each step, explicitly list step-specific ingredients under `"ingredients": [{"item": "plain flour", "amount": "900 g"}]` so that they render in a clean, visual step-specific table with photos, names, and amounts. Do not use the legacy `"needs"` string.
- **Ingredients and `do` text must agree.** Every item named in a step's `do` sentence (that is actually being added/measured in that step, not a component already folded in earlier) must appear in that step's `ingredients`, and every listed ingredient must be mentioned in `do`. Before finalizing a step, read `ingredients` and `do` side by side and reconcile any mismatch.
- The renderer already shows a step's `tool`/`accessory` as a photo card with its name (Tools column in the SPA, photo gallery in the PDF) — do not also try to force the tool name into a step's `chips`/icon fields, or it repeats the same appliance twice on one card.

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
6. Cache ingredient photos (above) — **for every recipe, try rimi.lv first
   for every ingredient before falling back to Wikipedia**, not just when
   convenient. Then render from the project root:
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
- [ ] Every ingredient photo was tried on rimi.lv first (`fetch_rimi_photo.py --list/--pick`), Wikipedia only as fallback — for every recipe, not just some.
- [ ] Every step that uses an appliance/part shows it.
- [ ] Icons used only for abstract things (time, heat, speed, done, action).
- [ ] Every step has settings chips and an observable `done` cue.
- [ ] Every unattended appliance has its own timeline lane.
- [ ] Timeline and diagram text readable at 100 % print scale.
- [ ] Uncertain facts appear in Assumptions, never silently inside a step.
- [ ] Metric units; Fahrenheit only when it helps.
- [ ] No tool `part`/step `accessory` points at a manual page or function chart.
- [ ] No step's title is narrower than what its `do` text actually covers.
- [ ] Each step's `ingredients` list and `do` text name the same items, both directions.
- [ ] An appliance's built-in features (integrated scale, timer, probe) are used instead of a separate generic tool for the same job, and shown as a `part` (with a `scale`/matching icon) on any step that actually uses one.

## Scope

Writes recipe artifacts inside a dedicated recipe-specific folder (`recipes/<recipe-name>/index.html` for the SPA, `recipes/<recipe-name>/<recipe-name>.pdf` for the PDF, and `recipes/<recipe-name>/assets/timeline.svg` for the timeline) and the photo cache (`raw/food/images/` + its `SOURCES.md`, append-only). Does not edit `wiki/` or existing `raw/` evidence files.

