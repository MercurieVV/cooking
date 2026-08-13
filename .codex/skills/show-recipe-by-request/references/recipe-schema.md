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
- `timeline`: array of `{ "time": "...", "task": "...", "cook": "..." }`; the renderer turns this into an SVG timeline image.
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
