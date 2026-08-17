#!/usr/bin/env python3
"""Inline SVG pictogram set for recipe cards.

Every icon is a 24x24 stroke drawing that inherits `currentColor`, so it works
in any size/color context and needs no fonts, emoji or network access.
"""

from __future__ import annotations

import re

# name -> inner SVG markup (viewBox 0 0 24 24)
ICONS: dict[str, str] = {
    # --- appliances / equipment -------------------------------------------
    "oven": '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18"/>'
            '<circle cx="6.5" cy="6" r=".9"/><circle cx="9.5" cy="6" r=".9"/>'
            '<rect x="6" y="12" width="12" height="6.5" rx="1"/>',
    "mixer": '<path d="M4 21h13"/><path d="M6.5 21v-3.5"/><path d="M15 21v-3.5"/>'
             '<path d="M5 4h9a3 3 0 0 1 3 3v2H5z"/><path d="M8.5 9v4.5"/><path d="M12 9v4.5"/>',
    "blender": '<path d="M7 3h10l-1.5 9h-7z"/><path d="M8.5 12h7l-.7 6h-5.6z"/><path d="M8 21h8"/>',
    "pot": '<path d="M4 9h16v7a3 3 0 0 1-3 3H7a3 3 0 0 1-3-3z"/><path d="M2 10.5h2"/>'
           '<path d="M20 10.5h2"/><path d="M9 6c0-1 1-1.4 1-2.5"/><path d="M13 6c0-1 1-1.4 1-2.5"/>',
    "pan": '<path d="M3 10h11v3.5a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4z"/><path d="M14 11.5h7"/>',
    "bowl": '<path d="M3 10h18v1.5a7.5 7.5 0 0 1-7.5 7.5h-3A7.5 7.5 0 0 1 3 11.5z"/><path d="M7 6.5c0-1 1-1.5 1-2.5"/>',
    "tray": '<rect x="2.5" y="7" width="19" height="10" rx="2"/><path d="M6 7v10"/><path d="M18 7v10"/>',
    "fridge": '<rect x="5" y="2.5" width="14" height="19" rx="2"/><path d="M5 10h14"/>'
              '<path d="M8 6v2.2"/><path d="M8 12.2v2.4"/>',
    "microwave": '<rect x="2.5" y="5" width="19" height="14" rx="2"/><path d="M15 5v14"/>'
                 '<rect x="5" y="8" width="7" height="8" rx="1"/><circle cx="18" cy="9.5" r=".9"/>',
    "airfryer": '<rect x="4" y="3" width="16" height="18" rx="3"/><path d="M4 8h16"/>'
                '<circle cx="12" cy="5.5" r="1"/><path d="M9 13.5c1.5-1.5 4.5-1.5 6 0"/>',
    "grinder": '<path d="M8 3h8v4H8z"/><path d="M10 7v4"/><path d="M14 7v4"/>'
               '<path d="M6 11h12l-1.5 10h-9z"/>',
    "scale": '<path d="M4 20h16"/><path d="M4 20V9h16v11"/><path d="M9 9V6h6v3"/><path d="M12 12v4"/>',
    "knife": '<path d="M3 20l9-9"/><path d="M12 11l5.5-6.5a2 2 0 0 1 3 2.6L15 13z"/>',
    "rolling-pin": '<path d="M6.5 6.5l11 11"/><path d="M4 9l5-5 3 3-5 5z"/><path d="M15 20l5-5-3-3-5 5z"/>',
    "whisk": '<path d="M12 3v6"/><path d="M9 9c0 5 1 8 3 12"/><path d="M15 9c0 5-1 8-3 12"/><path d="M8.5 9h7"/>',
    "spoon": '<path d="M11 21l2-9"/><ellipse cx="14" cy="7" rx="4" ry="5"/>',
    "plate": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5.5"/>',
    "probe": '<path d="M12 3v11"/><circle cx="12" cy="17.5" r="3.5"/><path d="M14.5 6h3"/><path d="M14.5 9.5h3"/>',

    # --- states / parameters ----------------------------------------------
    "temp": '<path d="M12 3c2 4 5 5.5 5 9a5 5 0 0 1-10 0c0-3.5 3-5 5-9z"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5.2l3.4 2"/>',
    "wait": '<path d="M6 3h12"/><path d="M6 21h12"/><path d="M7.5 3c0 4 4.5 5.5 4.5 9s-4.5 5-4.5 9"/>'
            '<path d="M16.5 3c0 4-4.5 5.5-4.5 9s4.5 5 4.5 9"/>',
    "speed": '<path d="M3.5 17a9 9 0 1 1 17 0"/><path d="M12 13.5l4-3.5"/>',
    "weight": '<path d="M6 8h12l2 12H4z"/><path d="M9.5 8a2.5 2.5 0 1 1 5 0"/>',
    "chill": '<path d="M12 3v18"/><path d="M4 7.5l16 9"/><path d="M20 7.5l-16 9"/>',
    "steam": '<path d="M8 20c0-3 2-3.5 2-6.5S8 9 8 6"/><path d="M14 20c0-3 2-3.5 2-6.5S14 9 14 6"/>',
    "check": '<circle cx="12" cy="12" r="9"/><path d="M8 12.3l2.7 2.7L16 9.5"/>',
    "warning": '<path d="M12 3.5l9 16H3z"/><path d="M12 9.5v4.5"/><circle cx="12" cy="16.8" r=".8"/>',
    "person": '<circle cx="12" cy="7.5" r="3.5"/><path d="M4.5 21c1-4.2 4-6.2 7.5-6.2S18.5 16.8 19.5 21"/>',
    "sync": '<path d="M4 12a8 8 0 0 1 13.7-5.6"/><path d="M20 12a8 8 0 0 1-13.7 5.6"/>'
            '<path d="M18 3v4h-4"/><path d="M6 21v-4h4"/>',
    "servings": '<circle cx="12" cy="13" r="6.5"/><path d="M2.5 13h19"/><path d="M12 6.5V3"/>',
    "cut": '<circle cx="7" cy="18" r="2.6"/><circle cx="17" cy="18" r="2.6"/><path d="M8.7 16L18 4"/><path d="M15.3 16L6 4"/>',
    "layers": '<path d="M12 3l9 4.5-9 4.5-9-4.5z"/><path d="M3 12.5l9 4.5 9-4.5"/><path d="M3 17l9 4.5 9-4.5"/>',

    # --- ingredients -------------------------------------------------------
    "flour": '<path d="M7 8h10l1.5 12.5h-13z"/><path d="M7 8c0-2.5 2-4.5 5-4.5s5 2 5 4.5"/><path d="M9.5 13h5"/>',
    "butter": '<path d="M3 10.5l5-4h13v7l-5 4H3z"/><path d="M8 6.5v7"/><path d="M3 13.5h13"/>',
    "sugar": '<path d="M4 9l8-4 8 4-8 4z"/><path d="M4 9v6l8 4 8-4V9"/><path d="M12 13v6"/>',
    "salt": '<path d="M8 9h8l1 12H7z"/><path d="M8 9a4 4 0 0 1 8 0"/><circle cx="10.5" cy="5.6" r=".7"/>'
            '<circle cx="13.5" cy="5.6" r=".7"/><circle cx="12" cy="3.6" r=".7"/>',
    "egg": '<path d="M12 3c3.6 0 6.5 5 6.5 9.2A6.5 6.5 0 0 1 12 21a6.5 6.5 0 0 1-6.5-8.8C5.5 8 8.4 3 12 3z"/>',
    "milk": '<path d="M8 21V9l-1.5-3V3h11v3L16 9v12z"/><path d="M6.5 6h11"/><path d="M8 13h8"/>',
    "apple": '<path d="M12 8c-3.5-2.5-8 0-8 5s3.5 8 5.5 8c1 0 1.5-.6 2.5-.6s1.5.6 2.5.6c2 0 5.5-3 5.5-8s-4.5-7.5-8-5z"/>'
             '<path d="M12 8V5"/><path d="M12 5c2 0 3-1 3-2.5-2 0-3 1-3 2.5z"/>',
    "lemon": '<ellipse cx="12" cy="12" rx="9" ry="6.5"/><path d="M3 12h18"/><path d="M12 5.5v13"/>',
    "herb": '<path d="M12 21C12 12 16 6 21 4c1 8-3 14-9 14z"/><path d="M12 21c-2-5-5-8-9-9 3-1 6 0 8 2"/>',
    "veg": '<path d="M6 21c8-1 12-5 13-13-8 1-12 5-13 13z"/><path d="M13 8l4-4"/>',
    "meat": '<path d="M6.5 17.5a6 6 0 1 1 8.5-8.5l4 4-4 4-4 4z"/><circle cx="10" cy="13" r="2.2"/>',
    "fish": '<path d="M3 12c4-5 11-5 15 0-4 5-11 5-15 0z"/><path d="M18 12l3-3v6z"/><circle cx="8" cy="12" r=".9"/>',
    "cheese": '<path d="M3 12l9-6 9 6v6H3z"/><circle cx="8" cy="14.5" r="1.2"/><circle cx="14" cy="15" r="1"/>',
    "grain": '<path d="M12 21V8"/><path d="M12 8c0-3 2-5 5-5 0 3-2 5-5 5z"/><path d="M12 13c0-3 2-5 5-5 0 3-2 5-5 5z"/>'
             '<path d="M12 8C12 5 10 3 7 3c0 3 2 5 5 5z"/><path d="M12 13c0-3-2-5-5-5 0 3 2 5 5 5z"/>',
    "spice": '<circle cx="12" cy="12" r="8.5"/><circle cx="9.5" cy="10" r="1"/><circle cx="14" cy="11" r="1"/>'
             '<circle cx="11.5" cy="14.5" r="1"/>',
    "water": '<path d="M12 3c4 5 6.5 7.7 6.5 11a6.5 6.5 0 0 1-13 0C5.5 10.7 8 8 12 3z"/>',
    "oil": '<path d="M9 4h6v3l4 4v10H5V11l4-4z"/><path d="M9 7h6"/>',
    "dough": '<ellipse cx="12" cy="14" rx="8.5" ry="5.5"/><path d="M6 10c2-2 10-2 12 0"/>',
    "nut": '<circle cx="12" cy="12" r="8.5"/><path d="M12 3.5v17"/><path d="M6 7c3 3 3 7 0 10"/><path d="M18 7c-3 3-3 7 0 10"/>',
    "dot": '<circle cx="12" cy="12" r="6"/>',
}

# substring -> icon name. First match wins, so order matters.
KEYWORDS: list[tuple[str, str]] = [
    (r"oven|bake|baking tray|broil|grill", "oven"),
    (r"kenwood|stand mixer|patissier|k-?beater|paddle|mixer", "mixer"),
    (r"blend|smoothie|food processor", "blender"),
    (r"actifry|air ?fry", "airfryer"),
    (r"instant pot|pressure|slow cook|stock ?pot|saucepan|\bpot\b|boil|simmer", "pot"),
    (r"skillet|frying|\bpan\b|saut|sear", "pan"),
    (r"grind|mince", "grinder"),
    (r"microwave", "microwave"),
    (r"fridge|refriger|chill|cold storage", "fridge"),
    (r"freez|\bice\b|frozen", "chill"),
    (r"scale|weigh", "scale"),
    (r"knife|slice|chop|dice|cut", "knife"),
    (r"rolling pin|roll out", "rolling-pin"),
    (r"whisk|beat", "whisk"),
    (r"spoon|spatula|stir|fold", "spoon"),
    (r"plate|serve|plating", "plate"),
    (r"probe|thermometer|temppro", "probe"),
    (r"tray|sheet|baking paper", "tray"),
    (r"bowl", "bowl"),
    (r"rest|proof|prove|wait|cool down", "wait"),
    (r"preheat|temperature|degrees|\b\d{2,3} ?c\b|heat", "temp"),
    (r"min\b|hour|hr\b|timer|time", "clock"),
    (r"speed|rpm", "speed"),
    (r"\bg\b|gram|kg\b|weight", "weight"),
    (r"steam|vent", "steam"),
    (r"cook\b|person|chef|hands", "person"),
    (r"sync|join|handoff", "sync"),
    (r"serving|portion|piece|yield", "servings"),
    (r"layer|assembl|stack", "layers"),
    (r"safety|caution|warn|raw egg|hygiene", "warning"),
    # ingredients
    (r"flour|semolina|breadcrumb|starch|corn ?flour", "flour"),
    (r"butter|margarine|ghee", "butter"),
    (r"sugar|honey|syrup|sweeten", "sugar"),
    (r"salt|pepper", "salt"),
    (r"egg", "egg"),
    (r"milk|cream|yogurt|yoghurt|buttermilk|sour cream", "milk"),
    (r"apple|pear|berry|banana|fruit|peach|plum", "apple"),
    (r"lemon|lime|orange|citrus", "lemon"),
    (r"cinnamon|vanilla|spice|cardamom|nutmeg|clove|paprika|cumin", "spice"),
    (r"herb|basil|parsley|thyme|dill|mint|bay leaf", "herb"),
    (r"onion|garlic|carrot|potato|tomato|pepper|vegetable|celery|leek|cabbage", "veg"),
    (r"chicken|beef|pork|lamb|meat|bacon|sausage", "meat"),
    (r"fish|salmon|cod|shrimp|prawn", "fish"),
    (r"cheese|parmesan|mozzarella", "cheese"),
    (r"rice|oat|wheat|barley|grain|pasta|noodle", "grain"),
    (r"yeast|dough|pastry|shortcrust|batter", "dough"),
    (r"nut|almond|walnut|hazelnut|seed", "nut"),
    (r"oil|olive", "oil"),
    (r"water|stock|broth|juice|wine|liquid", "water"),
    (r"baking powder|soda", "spice"),
]

_COMPILED = [(re.compile(pattern), name) for pattern, name in KEYWORDS]


def pick_icon(*texts: object, explicit: object = None, default: str = "dot") -> str:
    """Resolve an icon name: explicit wins, otherwise keyword-match the texts."""
    name = str(explicit or "").strip()
    if name in ICONS:
        return name
    haystack = " ".join(str(t) for t in texts if t).lower()
    for pattern, icon in _COMPILED:
        if pattern.search(haystack):
            return icon
    return default


def svg(name: str, cls: str = "ico") -> str:
    body = ICONS.get(name) or ICONS["dot"]
    return (
        f'<svg class="{cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        f'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" '
        f'aria-hidden="true">{body}</svg>'
    )


def icon_for(*texts: object, explicit: object = None, cls: str = "ico", default: str = "dot") -> str:
    return svg(pick_icon(*texts, explicit=explicit, default=default), cls)
