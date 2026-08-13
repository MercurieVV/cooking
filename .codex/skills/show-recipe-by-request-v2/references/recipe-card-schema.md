# Recipe Card JSON Schema (v2)

Feed a UTF-8 JSON file to `scripts/render_recipe_card.py`. It emits a
self-contained `.html` sidecar and the `.pdf` (all images inlined as data URIs).

The document always renders three numbered sections:
`1 Assumptions`, `2 Required`, `3 Steps`.

## Top level

| Field | Required | Meaning |
| --- | --- | --- |
| `title` | yes | Dish name, ≤ 6 words. |
| `output` | yes | Destination PDF path, project-root relative. |
| `servings` | yes | e.g. `20-24 pieces`. |
| `summary` | no | One sentence, ≤ 25 words. |
| `difficulty`, `cooks` | no | `Medium`, `2 cooks`. |
| `assumptions` | yes | See below — the one place sentences are allowed. |
| `required` | yes | `{ time, tools, ingredients, timeline }`. |
| `steps` | yes | See below. |
| `sync_points` | no | Rendered as "Checkpoints" under the timeline. |
| `visuals` | no | Full-width diagrams: `{title, image, caption}`. |
| `food_safety` | no | Short strings. |

## Word budgets

| Entity | Budget |
| --- | --- |
| assumption `text` | ≤ 8 words (headline) |
| assumption `note` | ≤ 25 words (why + how to overrule) |
| ingredient `item` | ≤ 4 words; `notes` ≤ 6 words |
| tool `role` | ≤ 8 words; `settings` ≤ 8 words |
| timeline `task` | ≤ 5 words |
| step `title` | ≤ 5 words, imperative verb first |
| step chip `text` | ≤ 4 words, one parameter per chip |
| step `do` | ≤ 25 words |
| step `done` | ≤ 12 words, observable cue |

Value does not fit? Split it into more entities — do not write longer text.

## Photos vs icons

Every entity gets a picture. The renderer picks, in order:

1. the `photo` / `image` file if it exists,
2. otherwise the `icon` you named,
3. otherwise a keyword-matched pictogram from `scripts/icons.py`.

Use **photos for concrete things** (appliances, parts, ingredients, control
panels, manual pages) and **icons for abstract ones** (time, temperature, speed,
chill, wait, checkpoint, done, the step's action).

Icon names: appliances (`oven`, `mixer`, `blender`, `pot`, `pan`, `bowl`,
`tray`, `fridge`, `microwave`, `airfryer`, `grinder`, `scale`, `knife`,
`rolling-pin`, `whisk`, `spoon`, `plate`, `probe`), parameters (`temp`, `clock`,
`wait`, `speed`, `weight`, `chill`, `steam`, `check`, `warning`, `person`,
`sync`, `servings`, `cut`, `layers`), ingredients (`flour`, `butter`, `sugar`,
`salt`, `egg`, `milk`, `apple`, `lemon`, `herb`, `veg`, `meat`, `fish`,
`cheese`, `grain`, `spice`, `water`, `oil`, `dough`, `nut`).

## Section 1 — assumptions

```json
"assumptions": [
  { "icon": "oven",
    "text": "AEG Competence has no numbered programs",
    "note": "Mid/late-2000s rotary-dial model, exact type unknown. Set the function dial to the fan symbol, not a program number." }
]
```

`text` is the headline; `note` explains why and how to overrule. Plain strings
are accepted but produce a headline with no reasoning — avoid.

## Section 2 — required

```json
"required": {
  "time": { "active": "1:00", "passive": "1:10", "total": "2 h 10 min" },
  "tools": [
    {
      "name": "Kenwood Patissier XL KWL90.244SI",
      "role": "Rubs cold butter into flour",
      "image": "raw/kitchen-tools/images/kenwood-titanium-chef-patissier-xl.jpg",
      "settings": "Speed 1-2, stop at clumps",
      "program": "n/a",
      "parts": [
        { "name": "5L bowl",  "image": "raw/kitchen-tools/images/kenwood-kwl90-5l-stainless-bowl.jpg" },
        { "name": "K-beater", "image": "raw/kitchen-tools/images/kenwood-kwl90-stainless-k-beater.jpg" }
      ]
    }
  ],
  "ingredients": [
    { "amount": "900 g", "item": "plain flour", "notes": "dough",
      "photo": "raw/food/images/plain-flour.jpg" }
  ],
  "timeline": [
    { "time": "0:00", "end": "0:12", "lane": "Cook", "lane_type": "person",
      "task": "Line trays, cube butter" }
  ]
}
```

- `time.active` / `time.passive` drive the hands-on vs unattended bar
  (`H:MM` or `NN min`).
- `parts` is the accessory gallery: bowls, beaters, discs, trays. Each part with
  an `image` renders as a captioned thumbnail; a part with only `icon`/`name`
  renders as a pictogram. Fall back to the flat `accessory` string only when no
  part photo exists.
- `program` renders as its own chip — use it for real program numbers/symbols.
- Ingredient `photo` paths come from `scripts/fetch_food_photos.py`.
- Timeline: `lane_type` is `person` or `appliance`; people lanes sort first.
  Concurrent tasks in one lane are auto-stacked into sub-rows. `end` may be
  replaced by `duration`.

## Section 3 — steps

```json
{
  "n": 2,
  "icon": "mixer",
  "title": "Mix shortcrust dough",
  "cook": "Cook A",
  "tool": "Kenwood Patissier XL KWL90.244SI",
  "accessory": "K-beater",
  "needs": "Flour, butter, eggs, sour cream",
  "chips": [ { "icon": "speed", "text": "speed 1-2" },
             { "icon": "clock", "text": "10-12 min" } ],
  "do": "Mix dry, add butter to sandy, add eggs and cream, stop at clumps.",
  "done": "Dough clumps when squeezed, still short.",
  "photos": [ { "image": "raw/kitchen-tools/manuals/...page.png",
                "caption": "Speed chart" } ],
  "diagram": "recipes/assets/tray-layering.svg"
}
```

- `tool` matching a `required.tools[].name` inherits that appliance photo;
  `accessory` matching one of its `parts[].name` inherits the part photo. Spell
  both exactly as in section 2 — that is what wires the pictures up.
- `photos` adds anything else worth showing: a manual page, a program dial, a
  control panel, a finished-texture reference.
- `diagram` for geometry (layering, cuts, tray positions, loading order).
- Multi-cook: set `cook` on every step and add `sync_points`.

## Checkpoints and safety

```json
"sync_points": [{ "name": "Oven-ready", "when": "0:55",
                  "criteria": "Dough chilled, filling mixed, oven at 180 C" }],
"food_safety": ["Wash hands and boards after raw egg"]
```

Rendered under the timeline as *"Checkpoints — all true before moving on"*.

## Diagram rules

SVG, ≤ 1100 px wide, body text ≥ 24 px, title ≥ 34 px, stroke ≥ 2.5 px. Number
the layers/stages in build order and label them directly. A diagram that needs a
caption to be understood is not finished.

## Back compatibility

The v1 layout still renders (top-level `ingredients` / `appliances` / `timeline`,
steps with `number` / `instruction` / `settings` / `timing`), but without photos,
parts and short entities the output is not v2-quality.
