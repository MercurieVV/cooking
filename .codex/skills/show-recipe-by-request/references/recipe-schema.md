# Recipe PDF JSON Schema

Pass a UTF-8 JSON file to `scripts/render_recipe_pdf.py`.

Required top-level fields:

- `title`: recipe title.
- `output`: destination PDF path.
- `servings`: string or number.
- `summary`: short paragraph.
- `ingredients`: array of `{ "item": "...", "amount": "...", "notes": "..." }`.
- `steps`: array of step objects.

Recommended optional fields:

- `assumptions`: array of strings.
- `total_time`, `active_time`, `passive_time`, `difficulty`.
- `appliances`: array of appliance objects.
- `timeline`: array of timeline items; the renderer turns this into a horizontal SVG swimlane timeline.
- `visuals`: array of vector/image objects for sketches or diagrams that replace wordy explanations.
- `sync_points`: array of `{ "name": "...", "when": "...", "criteria": "..." }`.
- `food_safety`: array of strings.

Appliance object:

```json
{
  "name": "Tefal YV9708 ActiFry Genius XL 2-in-1",
  "role": "Roast potatoes while sauce is made",
  "image": "raw/kitchen-tools/images/tefal-actifry-genius-xl.jpg",
  "settings": "Program 1 if confirmed, otherwise Manual 190 C",
  "accessory": "Stirring arm"
}
```

Visual object:

```json
{
  "title": "Tray layout",
  "image": "recipes/assets/apple-pie-tray-layout.svg",
  "caption": "Two lined trays: base dough, crumb layer, apple filling, vented top."
}
```

Timeline item:

```json
{
  "time": "00:10",
  "end": "00:22",
  "lane": "Kenwood Titanium Chef Patissier XL",
  "lane_type": "appliance",
  "task": "Mix shortcrust dough"
}
```

Use `lane_type: "person"` for cooks and `lane_type: "appliance"` for appliance rows. If `end` is omitted, `duration` may be used, for example `"duration": "12 min"`. Keep tasks short enough to fit inside a horizontal block. Use separate rows for people and active appliances in every generated recipe timeline.

All diagram images must be self-explanatory: labeled, direct, and tied to a cooking action. Do not include abstract or decorative diagrams.

Step object:

```json
{
  "number": 1,
  "cook": "Cook A",
  "title": "Pressure-cook stock",
  "needs": "Chicken, water, aromatics, salt",
  "image": "raw/kitchen-tools/images/instant-pot-pro-plus.jpg",
  "diagram": "recipes/assets/stock-pot-fill-line.svg",
  "appliance": "Instant Pot 5.7L Pro Plus",
  "accessory": "Inner pot",
  "settings": "Pressure Cook, High, 12 min; natural release 10 min",
  "timing": "25 min total",
  "instruction": "Add chicken, water, aromatics, and salt. Lock lid and cook.",
  "done": "Chicken reaches safe temperature and pulls apart easily."
}
```

For single-cook recipes, omit `cook` or use `Cook`.
