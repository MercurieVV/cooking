#!/usr/bin/env python3
"""Render a recipe JSON spec into a 3-section icon card PDF.

Sections, in fixed order:
  1. ASSUMPTIONS  - one chip per assumption
  2. REQUIRED     - time budget, tools, ingredients, timeline
  3. STEPS        - one card per step: icon, verb title, param chips, done cue

Pipeline: JSON -> self-contained HTML -> PDF (weasyprint, then pandoc, then a
plain-text PDF fallback so the script never hard-fails).

Usage: render_recipe_card.py recipe-spec.json
"""

from __future__ import annotations

import base64
import json
import mimetypes
import shutil
import subprocess
import sys
import textwrap
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from icons import ICONS, icon_for, pick_icon, svg  # noqa: E402

# Directories searched for relative image paths; render() prepends the spec's
# own directory and the project root it belongs to.
SEARCH_BASES: list[Path] = [Path.cwd()]


def register_bases(spec_path: Path) -> None:
    bases = [Path.cwd(), spec_path.resolve().parent]
    for parent in spec_path.resolve().parents:
        bases.append(parent)
        if (parent / ".git").exists() or (parent / "AGENTS.md").exists():
            break
    seen: list[Path] = []
    for base in bases:
        if base not in seen:
            seen.append(base)
    SEARCH_BASES[:] = seen


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def s(value) -> str:
    return "" if value is None else str(value).strip()


def e(value) -> str:
    return escape(s(value))


def parse_minutes(value) -> int | None:
    text = s(value).lower()
    if not text:
        return None
    if ":" in text:
        hour, _, minute = text.partition(":")
        if hour.strip().isdigit() and minute.strip().isdigit():
            return int(hour) * 60 + int(minute)
    nums = "".join(ch if ch.isdigit() else " " for ch in text).split()
    if not nums:
        return None
    amount = int(nums[0])
    if "h" in text and "min" not in text.split("h", 1)[0]:
        extra = int(nums[1]) if len(nums) > 1 else 0
        return amount * 60 + extra
    return amount


def fmt_clock(minutes: int) -> str:
    return f"{minutes // 60}:{minutes % 60:02d}"


def download_placeholder(target_path: Path, label: str) -> bool:
    """Download a high-quality labeled placeholder image on recipe signature teal if missing."""
    import urllib.request
    import urllib.parse
    target_path.parent.mkdir(parents=True, exist_ok=True)
    
    parts = label.split("-")
    if len(parts) > 2 and parts[0] == "step":
        text_label = f"Step {parts[1]}: " + " ".join(parts[2:]).title()
    else:
        text_label = label.replace("-", " ").replace("_", " ").title()
        
    url = f"https://dummyimage.com/300x300/2f6f7a/ffffff.png&text={urllib.parse.quote(text_label)}"
    try:
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            target_path.write_bytes(response.read())
        return True
    except Exception as e:
        print(f"Warning: Could not download placeholder for {label}: {e}", file=sys.stderr)
        return False


def resolve(path_text: str) -> Path | None:
    if not path_text:
        return None
    candidate = Path(path_text)
    if candidate.is_absolute():
        if candidate.exists():
            return candidate
        return None
    for base in SEARCH_BASES:
        found = base / candidate
        if found.exists():
            return found
            
    # Try to download if it is a relative image file path and ends with a recognized image extension
    suffix = candidate.suffix.lower()
    if suffix in (".jpg", ".jpeg", ".png", ".webp", ".svg"):
        target = SEARCH_BASES[0] / candidate
        if download_placeholder(target, candidate.stem):
            return target
            
    return None


def data_uri(path_text: str) -> str:
    """Inline images so the PDF never depends on resource paths."""
    found = resolve(path_text)
    if not found:
        return ""
    mime = mimetypes.guess_type(found.name)[0] or "application/octet-stream"
    if found.suffix.lower() == ".svg":
        mime = "image/svg+xml"
    payload = base64.b64encode(found.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{payload}"


# --------------------------------------------------------------------------- #
# spec normalization (accepts the v1 schema too)
# --------------------------------------------------------------------------- #
def normalize(spec: dict) -> dict:
    required = spec.get("required") or {}

    ingredients = required.get("ingredients") or spec.get("ingredients") or []
    tools = required.get("tools") or spec.get("tools") or spec.get("appliances") or []
    timeline = required.get("timeline") or spec.get("timeline") or []

    time_budget = required.get("time") or {
        "active": spec.get("active_time"),
        "passive": spec.get("passive_time"),
        "total": spec.get("total_time"),
    }

    steps = []
    for idx, raw in enumerate(spec.get("steps") or [], start=1):
        chips = list(raw.get("chips") or [])
        if not chips:
            for value in (raw.get("settings"), raw.get("timing")):
                for piece in [p.strip() for p in s(value).split(";") if p.strip()]:
                    chips.append({"text": piece})
        steps.append(
            {
                "n": raw.get("n") or raw.get("number") or idx,
                "icon": raw.get("icon"),
                "title": raw.get("title") or f"Step {idx}",
                "cook": raw.get("cook"),
                "tool": raw.get("tool") or raw.get("appliance"),
                "accessory": raw.get("accessory"),
                "needs": raw.get("needs") or raw.get("need"),
                "chips": chips[:4],
                "do": raw.get("do") or raw.get("instruction"),
                "done": raw.get("done"),
                "image": raw.get("image"),
                "diagram": raw.get("diagram"),
                "photos": raw.get("photos") or [],
                "ingredients": raw.get("ingredients") or [],
            }
        )

    assumptions = []
    for raw in spec.get("assumptions") or []:
        if isinstance(raw, dict):
            assumptions.append({"icon": raw.get("icon"), "text": raw.get("text"),
                                "note": raw.get("note")})
        else:
            assumptions.append({"icon": None, "text": raw, "note": None})

    return {
        **spec,
        "assumptions": assumptions,
        "ingredients": ingredients,
        "tools": tools,
        "timeline": timeline,
        "time_budget": time_budget,
        "steps": steps,
        "visuals": spec.get("visuals") or [],
        "sync_points": spec.get("sync_points") or [],
        "food_safety": spec.get("food_safety") or [],
    }


# --------------------------------------------------------------------------- #
# timeline SVG (horizontal swimlane gantt)
# --------------------------------------------------------------------------- #
PERSON = "#2f6f7a"
APPLIANCE = "#a3651f"


def timeline_svg(items: list[dict]) -> str:
    rows: list[dict] = []
    for item in items:
        start = parse_minutes(item.get("time") or item.get("start"))
        if start is None:
            continue
        end = parse_minutes(item.get("end"))
        if end is None:
            end = start + (parse_minutes(item.get("duration")) or 15)
        end = max(end, start + 5)
        lane = s(item.get("lane") or item.get("cook") or item.get("appliance") or "Cook")
        lane_type = s(item.get("lane_type")) or ("person" if item.get("cook") else "appliance")
        rows.append({"start": start, "end": end, "lane": lane, "type": lane_type,
                     "task": s(item.get("task")), "icon": item.get("icon")})
    if not rows:
        return ""

    lanes: list[tuple[str, str]] = []
    for wanted in ("person", "appliance"):
        for row in rows:
            key = (row["type"], row["lane"])
            if row["type"] == wanted and key not in lanes:
                lanes.append(key)
    for row in rows:
        key = (row["type"], row["lane"])
        if key not in lanes:
            lanes.append(key)

    lo = min(r["start"] for r in rows) // 15 * 15
    hi = -(-max(r["end"] for r in rows) // 15) * 15
    hi = max(hi, lo + 30)

    width, left, right = 880, 196, 20
    top, row_h, bar_h = 58, 56, 42
    axis = width - left - right
    step = 15 if hi - lo <= 120 else 30 if hi - lo <= 300 else 60
    min_bar = 44.0

    def x(minutes: int) -> float:
        return left + (minutes - lo) / (hi - lo) * axis

    # Pack concurrent tasks of one lane into stacked sub-rows so bars never overlap.
    lane_rows: dict[tuple[str, str], list[list[dict]]] = {}
    for key in lanes:
        packed: list[list[dict]] = []
        for row in sorted((r for r in rows if (r["type"], r["lane"]) == key),
                          key=lambda r: r["start"]):
            row["x"] = x(row["start"])
            row["w"] = max(min_bar, x(row["end"]) - row["x"])
            for sub in packed:
                if sub[-1]["x"] + sub[-1]["w"] + 4 <= row["x"]:
                    sub.append(row)
                    break
            else:
                packed.append([row])
        lane_rows[key] = packed

    lane_y: dict[tuple[str, str], float] = {}
    y_cursor = float(top)
    for key in lanes:
        lane_y[key] = y_cursor
        y_cursor += row_h * max(1, len(lane_rows[key]))
    height = int(y_cursor) + 14

    p: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" font-family="Helvetica, Arial, sans-serif">',
        f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
    ]

    tick = lo
    while tick <= hi:
        gx = x(tick)
        p.append(f'<line x1="{gx:.1f}" y1="{top - 14}" x2="{gx:.1f}" y2="{height - 8}" '
                 f'stroke="#e3ebed" stroke-width="1"/>')
        p.append(f'<text x="{gx:.1f}" y="{top - 22}" font-size="17" text-anchor="middle" '
                 f'fill="#54666a">{fmt_clock(tick)}</text>')
        tick += step

    for idx, key in enumerate(lanes):
        lane_type, lane = key
        y = lane_y[key]
        band = row_h * max(1, len(lane_rows[key]))
        color = PERSON if lane_type == "person" else APPLIANCE
        if idx % 2 == 0:
            p.append(f'<rect x="0" y="{y:.1f}" width="{width}" height="{band}" fill="#fafcfc"/>')
        icon = pick_icon(lane, default="person" if lane_type == "person" else "oven")
        p.append(f'<g transform="translate(14 {y + row_h / 2 - 14:.1f}) scale(1.2)" '
                 f'fill="none" stroke="{color}" stroke-width="1.7" stroke-linecap="round" '
                 f'stroke-linejoin="round">{ICONS.get(icon, ICONS["dot"])}</g>')
        label = lane if len(lane) <= 26 else lane[:25] + "…"
        p.append(f'<text x="48" y="{y + row_h / 2 + 6:.1f}" font-size="18" font-weight="700" '
                 f'fill="#1d3238">{escape(label)}</text>')

        for sub_idx, sub in enumerate(lane_rows[key]):
            for pos, row in enumerate(sub):
                by = y + sub_idx * row_h + (row_h - bar_h) / 2
                bx, bw = row["x"], row["w"]
                p.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{bar_h}" '
                         f'rx="7" fill="{color}" fill-opacity="0.12" stroke="{color}" '
                         f'stroke-width="1.6"/>')
                span = f'{fmt_clock(row["start"])}-{fmt_clock(row["end"])}'
                gap = ((sub[pos + 1]["x"] - (bx + bw)) if pos + 1 < len(sub)
                       else width - right - (bx + bw))
                if bw >= 132:  # label fits inside the bar
                    tx, chars, stacked = bx + 8, int(bw / 7.2), True
                    draw_halo = False
                else:  # narrow bar: label always to its right
                    tx, chars, stacked = bx + bw + 7, max(12, int((width - right - (bx + bw + 7)) / 7.0)), True
                    draw_halo = True

                task = textwrap.shorten(row["task"], width=max(6, chars), placeholder="…")

                def append_text(x_val: float, y_val: float, txt: str, size: int, col: str, fw: str = ""):
                    weight_attr = f' font-weight="{fw}"' if fw else ""
                    if draw_halo:
                        p.append(f'<text x="{x_val:.1f}" y="{y_val:.1f}" font-size="{size}"{weight_attr} '
                                 f'fill="#ffffff" stroke="#ffffff" stroke-width="4" stroke-linejoin="round" '
                                 f'opacity="0.9">{escape(txt)}</text>')
                    p.append(f'<text x="{x_val:.1f}" y="{y_val:.1f}" font-size="{size}"{weight_attr} '
                             f'fill="{col}">{escape(txt)}</text>')

                if stacked:
                    append_text(tx, by + 17, span, 13, color, fw="700")
                    append_text(tx, by + 33, task, 14, "#17202a")
                else:
                    append_text(tx, by + 26, task, 13, color, fw="700")

    p.append("</svg>")
    return "\n".join(p)


# --------------------------------------------------------------------------- #
# HTML
# --------------------------------------------------------------------------- #
def chip(text: str, icon_hint: str = "", explicit=None, kind: str = "") -> str:
    if not s(text):
        return ""
    ico = icon_for(icon_hint or text, explicit=explicit, cls="ico-s")
    return f'<span class="chip {kind}">{ico}<span>{e(text)}</span></span>'


def section(number: str, title: str, body: str, note: str = "") -> str:
    if not body.strip():
        return ""
    tail = f'<span class="sec-note">{e(note)}</span>' if note else ""
    return (
        f'<section class="sec"><h2><span class="sec-n">{number}</span>{e(title)}{tail}</h2>'
        f"{body}</section>"
    )


def thumb(path_text: str, alt: str = "", cls: str = "th", caption: str = "") -> str:
    """Photo tile; empty string when the file is missing."""
    uri = data_uri(path_text)
    if not uri:
        return ""
    cap = f'<figcaption>{e(caption)}</figcaption>' if caption else ""
    # No inline width/height:100% here: print-card `.th` figures are content-sized
    # (no fixed height), so a percentage height resolves to auto and the image
    # falls back to its full intrinsic size, blowing up the PDF to one image per
    # page. Every caller's CSS class (`.ings .th img`, `.shot img`,
    # `figure.spa-cell-img img`, ...) already sets an explicit height.
    return f'<figure class="{cls}"><img src="{uri}" style="max-width:100%; object-fit:contain;" alt="{e(alt)}">{cap}</figure>'


def photo_or_icon(path_text: str, *hints, explicit=None, alt: str = "", cls: str = "th",
                  caption: str = "") -> str:
    """Prefer a real photo of a concrete thing; fall back to a pictogram."""
    art = thumb(path_text, alt=alt, cls=cls, caption=caption)
    if art:
        return art
    return f'<span class="ico-box">{icon_for(*hints, explicit=explicit, cls="ico-l")}</span>'


def get_tool_photo(step: dict, tool_index: dict) -> tuple[str, str]:
    """Reuse the tool card photo (and its named part) for a step."""
    key = s(step.get("tool")).lower()
    tool = tool_index.get(key)
    if tool is None:
        for tname, candidate in tool_index.items():
            if key and (key in tname or tname in key):
                tool = candidate
                break
    if tool is None:
        return "", ""
    part_img = ""
    wanted = s(step.get("accessory")).lower()
    for part in tool.get("parts") or []:
        if wanted and wanted in s(part.get("name")).lower():
            part_img = s(part.get("image"))
            break
    return s(tool.get("image")), part_img


def get_step_time_range(step: dict, timeline: list) -> tuple[int, int]:
    """Resolve the start and end times for a step by matching with timeline items."""
    step_title = s(step.get("title")).lower()
    step_tool = s(step.get("tool")).lower()
    
    best_match = None
    best_score = 0
    
    for item in timeline:
        task = s(item.get("task") or item.get("label")).lower()
        lane = s(item.get("lane") or item.get("cook") or item.get("appliance")).lower()
        
        score = 0
        if step_title and task and (step_title in task or task in step_title):
            score += 5
        if step_tool and lane and (step_tool in lane or lane in step_tool):
            score += 3
            
        # Common word matching
        title_words = set(w for w in step_title.split() if len(w) > 3)
        task_words = set(w for w in task.split() if len(w) > 3)
        common = title_words.intersection(task_words)
        score += len(common) * 2
        
        if score > best_score:
            best_score = score
            best_match = item
            
    if best_match and best_score >= 3:
        start = parse_minutes(best_match.get("time") or best_match.get("start")) or 0
        end = parse_minutes(best_match.get("end"))
        if end is None:
            end = start + (parse_minutes(best_match.get("duration")) or 15)
        return start, end
        
    return 0, 0


def get_step_times(spec: dict) -> tuple[int, dict[int, tuple[int, int]]]:
    """Calculate the total duration and the time window for every step."""
    timeline = spec.get("required", {}).get("timeline") or spec.get("timeline") or []
    steps = spec.get("steps") or []
    
    max_time = 0
    for item in timeline:
        start = parse_minutes(item.get("time") or item.get("start"))
        if start is None:
            continue
        end = parse_minutes(item.get("end"))
        if end is None:
            end = start + (parse_minutes(item.get("duration")) or 15)
        end = max(end, start + 5)
        if end > max_time:
            max_time = end
            
    if max_time == 0:
        max_time = 60
        
    step_times = {}
    for st in steps:
        start, end = get_step_time_range(st, timeline)
        step_times[st["n"]] = (start, end)
        
    return max_time, step_times


def get_step_thumbnail(st: dict, tool_index: dict, ing_index: dict) -> str:
    """Resolve the best thumbnail image for a step from the specification."""
    # 1. Check if step has explicit photos
    photos = st.get("photos") or []
    if photos and isinstance(photos, list):
        p0 = photos[0]
        if isinstance(p0, dict) and s(p0.get("image")):
            return s(p0.get("image"))
        elif isinstance(p0, str) and s(p0):
            return s(p0)
            
    # 2. Check if step has a diagram
    if s(st.get("diagram")):
        return s(st.get("diagram"))
        
    # 3. Check if step has a tool or accessory photo
    auto_tool, auto_part = get_tool_photo(st, tool_index)
    if auto_part:
        return auto_part
    if auto_tool:
        return auto_tool
        
    # 4. Check if step has step-specific ingredients
    if st.get("ingredients"):
        for ing in st["ingredients"]:
            item_name = s(ing.get("item"))
            matched_ing = ing_index.get(item_name.lower())
            if not matched_ing:
                for name, candidate in ing_index.items():
                    if item_name.lower() in name or name in item_name.lower():
                        matched_ing = candidate
                        break
            if matched_ing:
                photo_path = s(matched_ing.get("photo") or matched_ing.get("image"))
                if photo_path:
                    return photo_path
                    
    # 5. Check if step has an image attribute
    if s(st.get("image")):
        return s(st.get("image"))
    # 6. Fallback: generate a custom slug to download a step-labeled placeholder card
    def slugify(text: str) -> str:
        return "".join(c if c.isalnum() or c == "-" else "-" for c in text.lower()).replace("--", "-").strip("-")
    clean_title = slugify(st.get("title") or "step")
    return f"raw/food/images/step-{st['n']}-{clean_title}.jpg"


def build_spa_slides(spec: dict, timeline_img: str) -> str:
    slides_html = []
    
    # Calculate step times & indexes
    tool_index = {s(t.get("name")).lower(): t for t in spec["tools"] if s(t.get("name"))}
    ing_index = {s(i.get("item")).lower(): i for i in spec["ingredients"] if s(i.get("item"))}
    max_time, step_times = get_step_times(spec)
    num_steps = len(spec["steps"])
    
    # --- Slide 0: Overview & Assumptions ---
    title = e(spec.get("title") or "Recipe")
    summary = e(spec.get("summary"))
    budget = spec["time_budget"] or {}
    
    meta_items = []
    if spec.get("servings"):
        meta_items.append(f'<div class="spa-metadata-item">{svg("servings", "ico-m")} <span><b>Servings:</b> {e(spec.get("servings"))}</span></div>')
    if budget.get("total"):
        meta_items.append(f'<div class="spa-metadata-item">{svg("clock", "ico-m")} <span><b>Total Time:</b> {e(budget.get("total"))}</span></div>')
    if budget.get("active"):
        meta_items.append(f'<div class="spa-metadata-item">{svg("person", "ico-m")} <span><b>Hands-on:</b> {e(budget.get("active"))}</span></div>')
    if budget.get("passive"):
        meta_items.append(f'<div class="spa-metadata-item">{svg("wait", "ico-m")} <span><b>Unattended:</b> {e(budget.get("passive"))}</span></div>')
    if spec.get("difficulty"):
        meta_items.append(f'<div class="spa-metadata-item">{svg("speed", "ico-m")} <span><b>Difficulty:</b> {e(spec.get("difficulty"))}</span></div>')
    if spec.get("cooks"):
        meta_items.append(f'<div class="spa-metadata-item">{svg("person", "ico-m")} <span><b>Cooks:</b> {e(spec.get("cooks"))}</span></div>')
        
    meta_html = "".join(meta_items)
    
    assume_items = ""
    for a in spec["assumptions"]:
        text = s(a.get("text"))
        if not text:
            continue
        note = s(a.get("note"))
        note_html = f'<p class="spa-assume-note">{e(note)}</p>' if note else ""
        icon_svg = icon_for(text, note, explicit=a.get("icon"), cls="ico-l")
        assume_items += (
            f'<li class="spa-assume-card">'
            f'<div class="spa-assume-icon">{icon_svg}</div>'
            f'<div class="spa-assume-body"><b>{e(text)}</b>{note_html}</div>'
            f'</li>'
        )
        
    slide_0 = (
        f'<div class="spa-slide slide-2col" data-start="0" data-end="0">'
        f'  <div class="spa-col spa-col-left">'
        f'    <h1 class="spa-slide-title">{title}</h1>'
        f'    <p class="spa-slide-lead">{summary}</p>'
        f'    <h3>Recipe Overview</h3>'
        f'    <div class="spa-metadata-list">{meta_html}</div>'
        f'  </div>'
        f'  <div class="spa-col spa-col-right">'
        f'    <h3>1. Assumptions</h3>'
        f'    <p class="spa-assume-header-desc">What was assumed for this recipe. Override anything here:</p>'
        f'    <ul class="spa-assume-list spa-flex-col">{assume_items}</ul>'
        f'  </div>'
        f'</div>'
    )
    slides_html.append(slide_0)
    
    # --- Slide 1: Required Tools & Ingredients ---
    tools_list = []
    for tool in spec["tools"]:
        name = s(tool.get("name"))
        role = s(tool.get("role"))
        img_uri = s(tool.get("image"))
        img_html = photo_or_icon(img_uri, name, tool.get("role"), explicit=tool.get("icon"), alt=name, cls="spa-cell-img")
        
        settings = s(tool.get("settings") or tool.get("set"))
        program = s(tool.get("program"))
        set_vals = []
        if settings:
            set_vals.append(settings)
        if program:
            set_vals.append(program)
        settings_text = " &middot; ".join(set_vals) if set_vals else (role or "Tool")
        
        tools_list.append(
            f'<div class="spa-needs-cell">'
            f'  {img_html}'
            f'  <span class="spa-cell-title">{e(name)}</span>'
            f'  <span class="spa-cell-amount">{e(settings_text)}</span>'
            f'</div>'
        )
        
        parts = tool.get("parts") or []
        for part in parts:
            pname = s(part.get("name"))
            pimg = s(part.get("image"))
            pimg_html = photo_or_icon(pimg, pname, explicit=part.get("icon"), alt=pname, cls="spa-cell-img")
            # Caption says "Part", not the parent tool's name again - with 2+
            # parts that repeated the appliance name back-to-back on the same
            # grid (e.g. "AEG oven" / "AEG oven" / "AEG oven"), reading as
            # duplicate appliances.
            tools_list.append(
                f'<div class="spa-needs-cell">'
                f'  {pimg_html}'
                f'  <span class="spa-cell-title">{e(pname)}</span>'
                f'  <span class="spa-cell-amount">Part</span>'
                f'</div>'
            )
            
    ingredients_list = []
    for ing in spec["ingredients"]:
        item = s(ing.get("item"))
        amt = s(ing.get("amount"))
        img_uri = s(ing.get("photo") or ing.get("image"))
        img_html = photo_or_icon(img_uri, item, explicit=ing.get("icon"), alt=item, cls="spa-cell-img")
        
        ingredients_list.append(
            f'<div class="spa-needs-cell">'
            f'  {img_html}'
            f'  <span class="spa-cell-title">{e(item)}</span>'
            f'  <span class="spa-cell-amount">{e(amt)}</span>'
            f'</div>'
        )
        
    slide_1 = (
        f'<div class="spa-slide slide-equal-2col" data-start="0" data-end="0">'
        f'  <div class="spa-col spa-col-left">'
        f'    <h3>Required Tools &amp; Parts</h3>'
        f'    <div class="spa-needs-grid-cells">{"".join(tools_list)}</div>'
        f'  </div>'
        f'  <div class="spa-col spa-col-right">'
        f'    <h3>Required Ingredients</h3>'
        f'    <div class="spa-needs-grid-cells">{"".join(ingredients_list)}</div>'
        f'  </div>'
        f'</div>'
    )
    slides_html.append(slide_1)
    
    # --- Slide 2: Timeline Gantt Chart ---
    if timeline_img:
        slide_2 = (
            f'<div class="spa-slide" style="flex-direction:column;" data-start="0" data-end="0">'
            f'  <div class="spa-col spa-timeline-slide-col">'
            f'    <h3>Cooking Timeline</h3>'
            f'    <div class="spa-timeline-img-wrap">'
            f'      <img class="timeline spa-timeline-img" src="{timeline_img}" alt="Timeline">'
            f'    </div>'
            f'  </div>'
            f'</div>'
        )
        slides_html.append(slide_2)
        
    # --- Slides 3 to 3+N-1: Step Slide Pages ---
    for idx, st in enumerate(spec["steps"]):
        # 1. Ingredients Column Cells
        ings_cells_list = []
        if st.get("ingredients"):
            for ing in st["ingredients"]:
                item_name = s(ing.get("item"))
                amount = s(ing.get("amount"))
                matched_ing = ing_index.get(item_name.lower())
                if not matched_ing:
                    for name, candidate in ing_index.items():
                        if item_name.lower() in name or name in item_name.lower():
                            matched_ing = candidate
                            break
                photo_path = s(matched_ing.get("photo") or matched_ing.get("image")) if matched_ing else ""
                explicit_icon = matched_ing.get("icon") if matched_ing else None
                art = photo_or_icon(photo_path, item_name, explicit=explicit_icon, alt=item_name, cls="spa-cell-img")
                ings_cells_list.append(
                    f'<div class="spa-needs-cell">'
                    f'  {art}'
                    f'  <span class="spa-cell-title">{e(item_name)}</span>'
                    f'  <span class="spa-cell-amount">{e(amount)}</span>'
                    f'</div>'
                )
        elif s(st.get("needs")):
            ings_cells_list.append(
                f'<div class="spa-needs-cell">'
                f'  <div class="ico-box spa-cell-img-box">{icon_for("bowl", cls="ico-s")}</div>'
                f'  <span class="spa-cell-title">Needs</span>'
                f'  <span class="spa-cell-amount">{e(st.get("needs"))}</span>'
                f'</div>'
            )
            
        if not ings_cells_list:
            ings_col_html = f'<div class="spa-needs-empty">None required</div>'
        else:
            ings_col_html = f'<div class="spa-needs-grid-cells">{"".join(ings_cells_list)}</div>'

        # 2. Tools & Appliances Column Cells (Full width column layout)
        tools_cells_list = []
        tool_name = s(st.get("tool"))
        if tool_name:
            matched_tool = tool_index.get(tool_name.lower())
            if not matched_tool:
                for name, candidate in tool_index.items():
                    if tool_name.lower() in name or name in tool_name.lower():
                        matched_tool = candidate
                        break
            tool_img_path = s(matched_tool.get("image")) if matched_tool else ""
            explicit_icon = matched_tool.get("icon") if matched_tool else None
            tool_img_uri = data_uri(tool_img_path) if tool_img_path else ""
            if tool_img_uri:
                tool_art = f'<img src="{tool_img_uri}" class="spa-cell-img" style="width:100%; height:100%; max-width:100%; max-height:100%; object-fit:contain;" alt="{e(tool_name)}">'
            else:
                tool_art = f'<div class="ico-box spa-cell-img-box">{icon_for(tool_name, explicit=explicit_icon, cls="ico-s")}</div>'
            
            set_vals = []
            if matched_tool:
                settings = s(matched_tool.get("settings") or matched_tool.get("set"))
                program = s(matched_tool.get("program"))
                if settings:
                    set_vals.append(settings)
                if program:
                    set_vals.append(program)
            for c in st["chips"]:
                text_val = s(c.get("text") if isinstance(c, dict) else c)
                if text_val and text_val not in set_vals:
                    set_vals.append(text_val)
            settings_text = " &middot; ".join(set_vals) if set_vals else "Tool"
            
            tools_cells_list.append(
                f'<div class="spa-needs-cell">'
                f'  {tool_art}'
                f'  <span class="spa-cell-title">{e(tool_name)}</span>'
                f'  <span class="spa-cell-amount">{settings_text}</span>'
                f'</div>'
            )
            
            acc_name = s(st.get("accessory"))
            if acc_name:
                matched_part = None
                if matched_tool:
                    for part in matched_tool.get("parts") or []:
                        if acc_name.lower() in s(part.get("name")).lower():
                            matched_part = part
                            break
                pimg_path = s(matched_part.get("image")) if matched_part else ""
                pimg_uri = data_uri(pimg_path) if pimg_path else ""
                if pimg_uri:
                    part_art = f'<img src="{pimg_uri}" class="spa-cell-img" style="width:100%; height:100%; max-width:100%; max-height:100%; object-fit:contain;" alt="{e(acc_name)}">'
                else:
                    part_art = f'<div class="ico-box spa-cell-img-box">{icon_for(acc_name, cls="ico-s")}</div>'
                tools_cells_list.append(
                    f'<div class="spa-needs-cell">'
                    f'  {part_art}'
                    f'  <span class="spa-cell-title">{e(acc_name)}</span>'
                    f'  <span class="spa-cell-amount">Accessory</span>'
                    f'</div>'
                )
                
        if not tools_cells_list:
            tools_col_html = f'<div class="spa-needs-empty">None required</div>'
        else:
            tools_col_html = f'<div class="spa-needs-grid-cells">{"".join(tools_cells_list)}</div>'

        # Combine into double-column needs block
        needs_block_html = (
            f'<div class="spa-step-needs-grid">'
            f'  <div class="spa-needs-col">'
            f'    <h4 class="spa-needs-section-title">Ingredients</h4>'
            f'    {ings_col_html}'
            f'  </div>'
            f'  <div class="spa-needs-col tools-col">'
            f'    <h4 class="spa-needs-section-title">Tools</h4>'
            f'    {tools_col_html}'
            f'  </div>'
            f'</div>'
        )

        # 3. Chips HTML
        # Tool/accessory already appear as photo cards in the Tools column
        # above - repeating them here just doubled up the same icon/name.
        chips_list = []
        for c in st["chips"]:
            text_val = s(c.get("text") if isinstance(c, dict) else c)
            icon_val = c.get("icon") if isinstance(c, dict) else None
            chips_list.append(chip(text_val, text_val, explicit=icon_val))
        chips_html = "".join(filter(None, chips_list))

        # 4. Do/Done HTML
        do_html = f'<p class="step-large-do">{e(st["do"])}</p>' if s(st.get("do")) else ""
        done_html = f'<div class="step-large-done">{svg("check", "ico-m")} <span><b>Done when:</b> {e(st["done"])}</span></div>' if s(st.get("done")) else ""

        # 5. Action Pic / Diagram / Animated Process Flow HTML
        action_pic_html = ""
        if s(st.get("diagram")):
            diagram_uri = data_uri(s(st.get("diagram")))
            if diagram_uri:
                action_pic_html = f'<div class="spa-action-pic-card"><img src="{diagram_uri}" class="spa-action-pic-img" style="width:100%; height:100%; max-width:100%; max-height:100%; object-fit:contain;" alt="Step {st["n"]} Diagram"></div>'
                
        if not action_pic_html:
            # Build CSS Process Flow Animation
            tool_name = s(st.get("tool")) or "Bowl"
            matched_tool = tool_index.get(tool_name.lower())
            if not matched_tool and tool_name:
                for name, candidate in tool_index.items():
                    if tool_name.lower() in name or name in tool_name.lower():
                        matched_tool = candidate
                        break
            tool_img_path = s(matched_tool.get("image")) if matched_tool else ""
            tool_uri = data_uri(tool_img_path) if tool_img_path else ""
            
            tool_class = ""
            if "whisk" in tool_name.lower() or "mix" in tool_name.lower() or "bowl" in tool_name.lower() or "pot" in tool_name.lower():
                tool_class = "spin-anim"
            elif "oven" in tool_name.lower() or "bake" in tool_name.lower():
                tool_class = "glow-anim"
                
            if tool_uri:
                tool_node_art = f'<img src="{tool_uri}" style="width:100%; height:100%; max-width:100%; max-height:100%; object-fit:contain; border-radius:50%;" alt="{e(tool_name)}">'
            else:
                tool_node_art = icon_for(tool_name, cls=f"ico-m {tool_class}")
                
            # Inputs
            input_nodes_html = ""
            if st.get("ingredients"):
                for ing in st["ingredients"][:3]:
                    item_name = s(ing.get("item"))
                    matched_ing = ing_index.get(item_name.lower())
                    if not matched_ing:
                        for name, candidate in ing_index.items():
                            if item_name.lower() in name or name in item_name.lower():
                                matched_ing = candidate
                                break
                    photo_path = s(matched_ing.get("photo") or matched_ing.get("image")) if matched_ing else ""
                    explicit_icon = matched_ing.get("icon") if matched_ing else None
                    art = photo_or_icon(photo_path, item_name, explicit=explicit_icon, alt=item_name, cls="spa-cell-img")
                    input_nodes_html += f'<div class="spa-diag-node input-node" title="{e(item_name)}">{art}</div>'
            if not input_nodes_html:
                person_art = icon_for(s(st.get("cook")) or "Person", cls="ico-m")
                input_nodes_html = f'<div class="spa-diag-node input-node" title="Cook">{person_art}</div>'
                
            # Output Node
            title_lower = s(st.get("title")).lower()
            out_label = "Result"
            out_icon_name = "plate"
            if "dough" in title_lower or "pastry" in title_lower:
                out_label = "Pie Dough"
                out_icon_name = "dough"
            elif "filling" in title_lower or "apple" in title_lower:
                out_label = "Apple Filling"
                out_icon_name = "pot"
            elif "bake" in title_lower or "oven" in title_lower:
                out_label = "Baked Pie"
                out_icon_name = "pie"
            elif "assemble" in title_lower or "layer" in title_lower:
                out_label = "Assembled"
                out_icon_name = "plate"
            elif "cool" in title_lower or "slice" in title_lower or "serve" in title_lower:
                out_label = "Ready to Serve"
                out_icon_name = "plate"
                
            output_node_art = icon_for(out_icon_name, cls="ico-m")
            
            action_pic_html = (
                f'<div class="spa-process-anim-container">'
                f'  <div class="spa-diag-inputs">'
                f'    {input_nodes_html}'
                f'    <span class="spa-diag-lbl">Inputs</span>'
                f'  </div>'
                f'  <div class="spa-diag-flow flow-left"></div>'
                f'  <div class="spa-diag-process">'
                f'    <div class="spa-diag-node process-node">{tool_node_art}</div>'
                f'    <span class="spa-diag-lbl" style="font-weight:700; color:var(--primary-dark);">{e(tool_name)}</span>'
                f'  </div>'
                f'  <div class="spa-diag-flow flow-right"></div>'
                f'  <div class="spa-diag-output">'
                f'    <div class="spa-diag-node output-node">{output_node_art}</div>'
                f'    <span class="spa-diag-lbl">{e(out_label)}</span>'
                f'  </div>'
                f'</div>'
            )

        # 6. Pane 3: What's Left (Progressed Checklist)
        whats_left_list = []
        for n_idx in range(idx + 1, num_steps):
            next_st = spec["steps"][n_idx]
            is_next_up = (n_idx == idx + 1)
            status_class = "whats-left-item"
            badge_html = ""
            if is_next_up:
                status_class += " next-up"
                badge_html = f'<span class="whats-left-badge next-badge">NEXT</span>'
            thumb_path = get_step_thumbnail(next_st, tool_index, ing_index)
            thumb_uri = data_uri(thumb_path) if thumb_path else ""
            if thumb_uri:
                img_html = f'<div class="whats-left-thumb-box"><img src="{thumb_uri}" style="width:100%; height:100%; max-width:100%; max-height:100%; object-fit:cover; border-radius:4px;" alt="Step {next_st["n"]}"></div>'
            else:
                img_html = f'<div class="ico-box whats-left-thumb-box">{icon_for(next_st.get("tool") or next_st.get("title"), cls="ico-s")}</div>'
            whats_left_list.append(
                f'<div class="{status_class}">'
                f'  <span class="item-num">{next_st["n"]}</span>'
                f'  {img_html}'
                f'  <span class="whats-left-title">{e(next_st["title"])}</span>'
                f'  {badge_html}'
                f'</div>'
            )
        if not whats_left_list:
            whats_left_items = f'<div style="color:var(--text-muted); font-style:italic; text-align:center; padding:20px; background:#fafcfc; border:1px dashed var(--border-color); border-radius:12px;">This is the last step! You are almost done.</div>'
        else:
            whats_left_items = f'<div class="whats-left-list">{"".join(whats_left_list)}</div>'

        cook = f'<span class="cook" style="font-size:0.95rem; font-weight:normal; color:var(--text-muted); display:inline-flex; align-items:center; gap:6px; margin-left:12px;">{svg("person", "ico-s")}{e(st["cook"])}</span>' if s(st.get("cook")) else ""
        start, end = step_times.get(st["n"], (0, 0))
        
        slide_step = (
            f'<div class="spa-slide slide-3col" data-start="{start}" data-end="{end}">'
            f'  <div class="spa-col spa-col-left">'
            f'    <h3>Ingredients &amp; Tools</h3>'
            f'    {needs_block_html}'
            f'  </div>'
            f'  <div class="spa-col spa-col-center" style="overflow:hidden; display:flex; flex-direction:column;">'
            f'    <div class="step-large-num">Step {st["n"]}</div>'
            f'    <div class="step-large-title">{e(st["title"])}{cook}</div>'
            f'    <div class="chips" style="margin-bottom:12px;">{chips_html}</div>'
            f'    <div class="spa-scroll-y-step">{do_html}{done_html}</div>'
            f'    {action_pic_html}'
            f'  </div>'
            f'  <div class="spa-col spa-col-right" style="overflow:hidden; display:flex; flex-direction:column;">'
            f'    <h3>What\'s Left</h3>'
            f'    <div class="spa-scroll-y-whats-left">{whats_left_items}</div>'
            f'  </div>'
            f'</div>'
        )
        slides_html.append(slide_step)
        
    # --- Slide 3+N: Done & Safety ---
    sync_points_html = ""
    if spec.get("sync_points"):
        for sp in spec["sync_points"]:
            sync_points_html += (
                f'<div class="spa-sync-point-card">'
                f'  <div class="ico-box" style="background:var(--accent-light); color:var(--accent);">{svg("sync", "ico-m")}</div>'
                f'  <div>'
                f'    <b style="font-size:1.1rem; color:var(--primary-dark);">{e(sp.get("name"))} &middot; {e(sp.get("when"))}</b>'
                f'    <div style="color:var(--text-muted); margin-top:4px;">{e(sp.get("criteria"))}</div>'
                f'  </div>'
                f'</div>'
            )
            
    safety_html = ""
    if spec.get("food_safety"):
        for fs in spec["food_safety"]:
            safety_html += (
                f'<div class="spa-safety-item">'
                f'  {svg("warning", "ico-s")} <span>{e(fs)}</span>'
                f'</div>'
            )
            
    visuals_html = ""
    for v in spec.get("visuals") or []:
        uri = data_uri(s(v.get("image")))
        if uri:
            visuals_html += (
                f'<figure class="spa-visual-card">'
                f'  <img src="{uri}" class="spa-visual-img">'
                f'  <figcaption style="font-weight:700; color:var(--primary-dark); margin-top:8px; text-align:center;">{e(v.get("caption") or v.get("title"))}</figcaption>'
                f'</figure>'
            )
            
    slide_final = (
        f'<div class="spa-slide slide-equal-2col" data-start="0" data-end="0">'
        f'  <div class="spa-col spa-col-left">'
        f'    <h3>Checkpoints &amp; Safety</h3>'
        f'    <div class="spa-scroll-y">'
        f'      {sync_points_html if sync_points_html else "<p>No checkpoints specified.</p>"}'
        f'      {f"<h4 style=\'margin:24px 0 12px; color:#c53030;\'>Food Safety Guidelines</h4>{safety_html}" if safety_html else ""}'
        f'    </div>'
        f'  </div>'
        f'  <div class="spa-col spa-col-right">'
        f'    <h3>Additional Diagrams</h3>'
        f'    <div class="spa-scroll-y">{visuals_html if visuals_html else "<p style=\'color:var(--text-muted); font-style:italic;\'>No additional diagrams.</p>" }</div>'
        f'  </div>'
        f'</div>'
    )
    slides_html.append(slide_final)
    
    return "\n".join(slides_html)


def build_spa_layout(spec: dict, timeline_img: str) -> str:
    title = e(spec.get("title") or "Recipe")
    max_time, step_times = get_step_times(spec)
    
    people_blocks = []
    appliance_blocks = []
    timeline = spec.get("required", {}).get("timeline") or spec.get("timeline") or []
    for item in timeline:
        start = parse_minutes(item.get("time") or item.get("start"))
        if start is None:
            continue
        end = parse_minutes(item.get("end"))
        if end is None:
            end = start + (parse_minutes(item.get("duration")) or 15)
        end = max(end, start + 5)
        lane_type = s(item.get("lane_type")) or ("person" if item.get("cook") else "appliance")
        
        left = 10 + 80 * (start / max_time)
        width = 80 * ((end - start) / max_time)
        block_html = f'<span class="mini-block" style="left: {left:.1f}%; width: {width:.1f}%;"></span>'
        if lane_type == "person":
            people_blocks.append(block_html)
        else:
            appliance_blocks.append(block_html)
            
    people_lane_html = f'<div class="mini-lane lane-person">{"".join(people_blocks)}</div>'
    appliance_lane_html = f'<div class="mini-lane lane-appliance">{"".join(appliance_blocks)}</div>'
    
    steps_slide_index = 3 if timeline_img else 2
    
    nodes = []
    nodes.append('<button class="timeline-node node-pill" data-slide="0" style="left: 2%;">Overview</button>')
    nodes.append('<button class="timeline-node node-pill" data-slide="1" style="left: 6%;">Setup</button>')
    if timeline_img:
        nodes.append('<button class="timeline-node node-pill" data-slide="2" style="left: 10%;">Timeline</button>')
        
    for idx, st in enumerate(spec["steps"]):
        start, end = step_times.get(st["n"], (0, 0))
        left = 10 + 80 * (start / max_time)
        
        # Get a neat short label
        title_text = s(st["title"])
        if len(title_text) > 18:
            title_text = title_text[:16] + "..."
        node_label = f'{st["n"]}. {title_text}'
        
        nodes.append(f'<button class="timeline-node node-pill" data-slide="{steps_slide_index + idx}" style="left: {left:.1f}%;">{e(node_label)}</button>')
        
    done_slide_index = steps_slide_index + len(spec["steps"])
    nodes.append(f'<button class="timeline-node node-pill" data-slide="{done_slide_index}" style="left: 95%;">Done</button>')
    
    nodes_html = "\n".join(nodes)
    slides_html = build_spa_slides(spec, timeline_img)
    
    layout = (
        f'<div class="spa-layout">'
        f'  <header class="spa-header">'
        f'    <h1 class="spa-title">{title}</h1>'
        f'    <div class="spa-timeline">'
        f'      <div class="mini-gantt">'
        f'        {people_lane_html}'
        f'        {appliance_lane_html}'
        f'      </div>'
        f'      <div class="timeline-highlight"></div>'
        f'      {nodes_html}'
        f'    </div>'
        f'  </header>'
        f'  <div class="spa-slides">{slides_html}</div>'
        f'  <button class="nav-btn prev-btn" aria-label="Previous page">&larr;</button>'
        f'  <button class="nav-btn next-btn" aria-label="Next page">&rarr;</button>'
        f'</div>'
    )
    return layout


def build_html(spec: dict, timeline_img: str) -> str:
    title = e(spec.get("title") or "Recipe")
    summary = e(spec.get("summary"))
    budget = spec["time_budget"] or {}

    meta = "".join(
        filter(
            None,
            [
                chip(s(spec.get("servings")) or s(spec.get("yield")), "servings", explicit="servings", kind="hi"),
                chip(s(budget.get("total")), "total time", explicit="clock", kind="hi"),
                chip(s(spec.get("difficulty")), "difficulty", explicit="speed", kind="hi"),
                chip(s(spec.get("cooks")), "cook", explicit="person", kind="hi"),
            ],
        )
    )
    lead = f'<p class="lead">{summary}</p>' if summary else ""
    header = f'<header><h1>{title}</h1>{lead}<div class="chips">{meta}</div></header>'

    # --- 1 assumptions -----------------------------------------------------
    assume = ""
    for a in spec["assumptions"]:
        text = s(a.get("text"))
        if not text:
            continue
        note = s(a.get("note"))
        note_html = f"<em>{e(note)}</em>" if note else ""
        assume += (f'<li>{icon_for(text, note, explicit=a.get("icon"), cls="ico-m")}'
                   f'<span>{e(text)}{note_html}</span></li>')
    sec1 = section(
        "1", "Assumptions",
        f'<ul class="grid assume">{assume}</ul>' if assume else "",
        note="What I decided for you — override anything here",
    )

    # --- 2 required --------------------------------------------------------
    time_block = tools_block = ing_block = timeline_block = ""

    active = parse_minutes(budget.get("active")) or 0
    passive = parse_minutes(budget.get("passive")) or 0
    if active or passive:
        total = active + passive
        pa = active / total * 100
        time_block = (
            '<div class="block"><h3>' + svg("clock", "ico-m") + "Time</h3>"
            f'<div class="tbar"><span class="t-act" style="width:{pa:.1f}%"></span>'
            f'<span class="t-pas" style="width:{100 - pa:.1f}%"></span></div>'
            f'<div class="chips">{chip(f"hands-on {fmt_clock(active)}", explicit="person")}'
            f'{chip(f"unattended {fmt_clock(passive)}", explicit="wait")}'
            f'{chip(s(budget.get("total")) or f"total {fmt_clock(total)}", explicit="clock", kind="hi")}'
            "</div></div>"
        )

    tools_html = ""
    for tool in spec["tools"]:
        name = s(tool.get("name"))
        art = photo_or_icon(s(tool.get("image")), name, tool.get("role"),
                            explicit=tool.get("icon"), alt=name, cls="th tool-shot")
        chips = "".join(
            filter(None, [
                chip(s(tool.get("settings")) or s(tool.get("set")), name),
                chip(s(tool.get("program")), name),
            ])
        )
        parts = "".join(
            photo_or_icon(s(part.get("image")), part.get("name"), explicit=part.get("icon"),
                          alt=s(part.get("name")), cls="th part",
                          caption=s(part.get("name"))) or ""
            for part in (tool.get("parts") or [])
        )
        if not parts and s(tool.get("accessory")):
            parts = f'<div class="chips">{chip(s(tool.get("accessory")), s(tool.get("accessory")))}</div>'
        else:
            parts = f'<div class="parts">{parts}</div>' if parts else ""
        role = s(tool.get("role"))
        role_html = f"<em>{e(role)}</em>" if role else ""
        tools_html += (
            f'<li class="tool">{art}<div class="tool-body"><b>{e(name)}</b>{role_html}'
            f'<div class="chips">{chips}</div>{parts}</div></li>'
        )
    if tools_html:
        tools_block = ('<div class="block"><h3>' + svg("mixer", "ico-m")
                       + "Tools and parts</h3>"
                       f'<ul class="tools">{tools_html}</ul></div>')

    ing_html = ""
    for ing in spec["ingredients"]:
        item = s(ing.get("item"))
        note = s(ing.get("notes") or ing.get("note"))
        art = photo_or_icon(s(ing.get("photo") or ing.get("image")), item,
                            explicit=ing.get("icon"), alt=item, cls="th ing-shot")
        note_html = f'<span class="ing-note">{e(note)}</span>'
        ing_html += (
            f'<li>{art}<span class="ing-name">{e(item)}</span>'
            f'<span class="ing-amt">{e(ing.get("amount"))}</span>{note_html}</li>'
        )
    if ing_html:
        ing_block = ('<div class="block"><h3>' + svg("bowl", "ico-m") + "Ingredients</h3>"
                     f'<ul class="ings">{ing_html}</ul></div>')

    if timeline_img:
        timeline_block = ('<div class="block wide"><h3>' + svg("clock", "ico-m") + "Timeline</h3>"
                          f'<img class="timeline" src="{timeline_img}" alt="Timeline">')
        sync = "".join(
            f'<li>{svg("sync", "ico-m")}<span><b>{e(sp.get("name"))} · {e(sp.get("when"))}</b>'
            f'<em>{e(sp.get("criteria"))}</em></span></li>'
            for sp in spec["sync_points"]
        )
        if sync:
            timeline_block += (
                '<h3 class="sub">' + svg("sync", "ico-m")
                + "Checkpoints — all true before moving on</h3>"
                f'<ul class="grid sync">{sync}</ul>'
            )
        timeline_block += "</div>"

    sec2 = section("2", "Required", time_block + timeline_block + tools_block + ing_block)

    # --- 3 steps -----------------------------------------------------------
    tool_index = {s(t.get("name")).lower(): t for t in spec["tools"] if s(t.get("name"))}
    ing_index = {s(i.get("item")).lower(): i for i in spec["ingredients"] if s(i.get("item"))}

    def tool_photo(step: dict) -> tuple[str, str]:
        """Reuse the tool card photo (and its named part) for a step."""
        key = s(step.get("tool")).lower()
        tool = tool_index.get(key)
        if tool is None:
            for tname, candidate in tool_index.items():
                if key and (key in tname or tname in key):
                    tool = candidate
                    break
        if tool is None:
            return "", ""
        part_img = ""
        wanted = s(step.get("accessory")).lower()
        for part in tool.get("parts") or []:
            if wanted and wanted in s(part.get("name")).lower():
                part_img = s(part.get("image"))
                break
        return s(tool.get("image")), part_img

    cards = ""
    for st in spec["steps"]:
        icon = icon_for(st["title"], st["tool"], st["do"], explicit=st.get("icon"), cls="ico-l")
        # Tool/accessory are already shown via their photo (gallery below) and
        # the Tools column in the SPA layout - repeating them as chips here
        # just doubled up the same appliance icon/name on the card.
        chips = "".join(
            filter(None, [
                chip(s(c.get("text") if isinstance(c, dict) else c),
                     s(c.get("text") if isinstance(c, dict) else c),
                     explicit=(c.get("icon") if isinstance(c, dict) else None))
                for c in st["chips"]
            ])
        )

        shots = ""
        seen: list[str] = []
        auto_tool, auto_part = tool_photo(st)
        gallery = list(st.get("photos") or [])
        for path_text, caption in [(auto_tool, s(st.get("tool"))), (auto_part, s(st.get("accessory")))]:
            if path_text and path_text not in seen:
                seen.append(path_text)
                gallery.append({"image": path_text, "caption": caption})
        # Note: diagram is handled separately to keep it large and legible.
        # Only put st.get("image") in the small gallery
        for extra in [st.get("image")]:
            if s(extra) and s(extra) not in seen:
                seen.append(s(extra))
                gallery.append({"image": s(extra), "caption": ""})
        for shot in gallery:
            shots += thumb(s(shot.get("image")), alt=s(shot.get("caption")),
                           cls="th shot", caption=s(shot.get("caption")))
        shots = f'<div class="shots">{shots}</div>' if shots else ""

        # Step-specific ingredients table
        step_ings_html = ""
        if st.get("ingredients"):
            rows_html = ""
            for ing in st["ingredients"]:
                item_name = s(ing.get("item"))
                amount = s(ing.get("amount"))
                
                # Find matching main ingredient to inherit photo/icon
                matched_ing = ing_index.get(item_name.lower())
                if not matched_ing:
                    for name, candidate in ing_index.items():
                        if item_name.lower() in name or name in item_name.lower():
                            matched_ing = candidate
                            break
                
                photo_path = ""
                icon_hint = item_name
                explicit_icon = None
                if matched_ing:
                    photo_path = s(matched_ing.get("photo") or matched_ing.get("image"))
                    explicit_icon = matched_ing.get("icon")
                
                art = photo_or_icon(photo_path, icon_hint, explicit=explicit_icon, alt=item_name, cls="th step-ing-shot")
                rows_html += (
                    f'<tr>'
                    f'<td class="step-ing-photo">{art}</td>'
                    f'<td class="step-ing-name"><b>{e(item_name)}</b></td>'
                    f'<td class="step-ing-amt">{e(amount)}</td>'
                    f'</tr>'
                )
            if rows_html:
                step_ings_html = f'<table class="step-ings-table">{rows_html}</table>'

        needs_block = step_ings_html if step_ings_html else (
            f'<p class="need">{svg("bowl", "ico-s")}{e(st["needs"])}</p>' if s(st.get("needs")) else ""
        )

        do = f'<p class="do">{e(st["do"])}</p>' if s(st.get("do")) else ""
        done = (f'<p class="done">{svg("check", "ico-s")}{e(st["done"])}</p>'
                if s(st.get("done")) else "")
        
        # Step diagram (rendered larger under description/done cue)
        diagram_html = ""
        diagram_path = s(st.get("diagram"))
        if diagram_path:
            uri = data_uri(diagram_path)
            if uri:
                diagram_html = f'<figure class="step-diagram"><img src="{uri}" alt="Step Diagram"></figure>'

        cook = f'<span class="cook">{svg("person", "ico-s")}{e(st["cook"])}</span>' if s(st.get("cook")) else ""
        cards += (
            f'<li class="step"><div class="rail"><span class="num">{e(st["n"])}</span>{icon}</div>'
            f'<div class="body"><h4>{e(st["title"])}{cook}</h4>'
            f'<div class="chips">{chips}</div>{needs_block}{do}{done}{shots}{diagram_html}</div></li>'
        )
    sec3 = section("3", "Steps", f'<ol class="steps">{cards}</ol>' if cards else "")

    # --- extras ------------------------------------------------------------
    extras = ""
    visuals = ""
    for v in spec["visuals"]:
        uri = data_uri(s(v.get("image")))
        if uri:
            visuals += (f'<figure class="visual"><img src="{uri}" alt="{e(v.get("title"))}">'
                        f'<figcaption>{e(v.get("caption") or v.get("title"))}</figcaption></figure>')
    if visuals:
        extras += f'<div class="visuals">{visuals}</div>'
    if spec["food_safety"]:
        items = "".join(f'<li>{svg("warning", "ico-s")}<span>{e(x)}</span></li>' for x in spec["food_safety"])
        extras += f'<ul class="grid safety">{items}</ul>'

    # --- compile JSON stepsData for JS injection ---
    tool_index = {s(t.get("name")).lower(): t for t in spec["tools"] if s(t.get("name"))}
    ing_index = {s(i.get("item")).lower(): i for i in spec["ingredients"] if s(i.get("item"))}
    max_time, step_times = get_step_times(spec)

    max_time, _ = get_step_times(spec)
    spa_layout = build_spa_layout(spec, timeline_img)

    return (
        f"<!doctype html><html><head><meta charset=\"utf-8\">"
        f"<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">"
        f"<title>{title}</title>"
        f"<style>{CSS}</style></head><body>"
        f"<div class=\"print-layout\">{header}{sec1}{sec2}{sec3}{extras}</div>"
        f"{spa_layout}"
        f"<script>"
        f"const maxTime = {max_time};\n"
        f"{JS}"
        f"</script>"
        f"</body></html>"
    )


CSS = """
@page { size: A4; margin: 12mm 11mm 10mm; }
* { box-sizing: border-box; }
html { font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
       font-size: 9.6pt; line-height: 1.34; color: #17202a; }
body { margin: 0; }
h1, h2, h3, h4 { margin: 0; color: #12303a; line-height: 1.2; }
b { color: #12303a; }
em { display: block; font-style: normal; color: #64777c; font-size: 8.4pt; }
figure { margin: 0; }

.ico, .ico-s, .ico-m, .ico-l { flex: none; }
.ico-s { width: 3.1mm; height: 3.1mm; }
.ico-m { width: 4.2mm; height: 4.2mm; }
.ico-l { width: 7mm; height: 7mm; }
.ico-box { display: inline-flex; align-items: center; justify-content: center;
           width: 12mm; height: 12mm; border-radius: 1.4mm; background: #eaf3f4;
           color: #2f6f7a; flex: none; }

header { border-bottom: 2.5pt solid #2f6f7a; padding-bottom: 2.5mm; margin-bottom: 3mm; }
h1 { font-size: 19pt; letter-spacing: -.2pt; }
.lead { margin: 1.2mm 0 0; color: #4a5c61; max-width: 150mm; }

.chips { display: flex; flex-wrap: wrap; gap: 1.2mm; margin-top: 1.4mm; }
.chip { display: inline-flex; align-items: center; gap: 1mm; padding: .5mm 1.6mm;
        flex: none; white-space: nowrap;
        border: .3pt solid #c2d3d7; border-radius: 1.4mm; background: #f6fafb;
        color: #33474d; font-size: 8.4pt; }
.chip.hi { background: #2f6f7a; border-color: #2f6f7a; color: #fff; }
.chip.hi svg { color: #fff; }
.chip svg { color: #2f6f7a; }

.sec { margin-top: 4mm; }
.sec h2 { display: flex; align-items: center; gap: 2mm; font-size: 11.5pt;
          text-transform: uppercase; letter-spacing: .6pt; padding-bottom: 1.2mm;
          border-bottom: .6pt solid #cfdde0; }
.sec-n { display: inline-flex; align-items: center; justify-content: center;
         width: 5.4mm; height: 5.4mm; border-radius: 50%; background: #2f6f7a;
         color: #fff; font-size: 9pt; }
.sec-note { margin-left: auto; font-size: 8.4pt; color: #7b8b8f; text-transform: none;
            letter-spacing: 0; }
.sec h3 { display: flex; align-items: center; gap: 1.5mm; font-size: 9.4pt;
          text-transform: uppercase; letter-spacing: .4pt; color: #56696e; margin-bottom: 1.5mm; }
.sec h3.sub { margin-top: 2.5mm; }
.sec h3 svg { color: #2f6f7a; }
.block { margin-top: 3mm; }
.block h3 { break-after: avoid; }

ul, ol { list-style: none; margin: 0; padding: 0; }
.grid { display: flex; flex-wrap: wrap; gap: 1.2mm 2mm; }
.grid > li { display: flex; align-items: flex-start; gap: 1.4mm; }
.grid > li svg { color: #2f6f7a; margin-top: .3mm; }
.assume > li { width: calc(50% - 1mm); padding: 1.6mm; border: .3pt solid #dce7e9;
               border-radius: 1.4mm; background: #f9fcfc; break-inside: avoid; }
.sync > li, .safety > li { width: calc(50% - 1mm); padding: 1.2mm; border-radius: 1.4mm;
                           background: #f6fafb; break-inside: avoid; }
.safety > li svg { color: #a3651f; }
.safety { margin-top: 3mm; }

.ings > li { display: flex; align-items: center; gap: 2.4mm; padding: .8mm 1mm;
             border-bottom: .3pt solid #e6eef0; break-inside: avoid; }
.ings > li:nth-child(even) { background: #fafcfc; }
.ings .th { width: 9mm; }
.ings .th img { height: 9mm; }
.ings .ico-box { width: 7mm; height: 7mm; }
.ings .ico-box svg { width: 4.6mm; height: 4.6mm; }
.ing-name { flex: 1; font-weight: 700; color: #12303a; }
.ing-amt { width: 24mm; text-align: right; font-variant-numeric: tabular-nums; }
.ing-note { width: 48mm; color: #64777c; font-size: 8.6pt; padding-left: 3mm; }

.tools { display: flex; flex-wrap: wrap; gap: 2mm; }
.tool { display: flex; gap: 2mm; align-items: flex-start; width: calc(50% - 1mm);
        padding: 1.8mm; border: .3pt solid #dce7e9; border-radius: 1.6mm;
        background: #f9fcfc; break-inside: avoid; }
.tool-body { flex: 1; }
.th { display: flex; flex-direction: column; align-items: center; gap: .6mm; }
.th img { display: block; max-width: 100%; object-fit: contain; background: #fff;
          border-radius: 1mm; }
.th figcaption { font-size: 7.4pt; color: #7b8b8f; text-align: center; max-width: 20mm; }
.tool-shot { width: 20mm; }
.tool-shot img { height: 18mm; }
.parts { display: flex; flex-wrap: wrap; gap: 1.6mm; margin-top: 1.4mm; }
.part { width: 15mm; }
.part img { height: 12mm; border: .3pt solid #e2ebed; }

.tbar { display: flex; height: 3.6mm; border-radius: 1.8mm; overflow: hidden; background: #eef4f5; }
.t-act { background: #2f6f7a; } .t-pas { background: #cfa25f; }
.timeline { width: 100%; }

.steps { margin-top: 2mm; }
.step { display: flex; gap: 2.4mm; padding: 2mm 0; border-top: .3pt solid #e1ebed;
        break-inside: avoid; }
.step:first-child { border-top: 0; }
.rail { display: flex; flex-direction: column; align-items: center; gap: 1mm; width: 9mm; }
.num { display: inline-flex; align-items: center; justify-content: center; width: 6mm;
       height: 6mm; border-radius: 50%; background: #12303a; color: #fff;
       font-size: 9pt; font-weight: 700; }
.rail svg { color: #2f6f7a; }
.step .body { flex: 1; }
.step h4 { display: flex; align-items: baseline; gap: 2mm; font-size: 10.6pt; }
.cook { margin-left: auto; display: inline-flex; align-items: center; gap: 1mm;
        font-size: 8.4pt; color: #7b8b8f; font-weight: 400; }
.step p { margin: 1mm 0 0; }
.need { color: #64777c; font-size: 8.6pt; display: flex; gap: 1.2mm; align-items: center; }
.need svg, .done svg { color: #2f6f7a; }
.do { color: #17202a; }
.done { display: flex; gap: 1.2mm; align-items: center; color: #2f6f7a; font-size: 8.8pt; }
.shots { display: flex; flex-wrap: wrap; gap: 2mm; margin-top: 1.6mm; }
.shot { width: 22mm; }
.shot img { height: 18mm; border: .3pt solid #e2ebed; }

.step-ings-table { width: 100%; border-collapse: collapse; margin-top: 1.8mm; margin-bottom: 1.8mm; font-size: 8.4pt; }
.step-ings-table tr { border-bottom: .3pt solid #e6eef0; }
.step-ings-table tr:last-child { border-bottom: 0; }
.step-ings-table td { padding: 0.6mm 1mm; vertical-align: middle; }
.step-ing-photo { width: 7mm; }
.step-ing-photo .th { width: 7mm; }
.step-ing-photo .th img { height: 7mm; }
.step-ing-photo .ico-box { width: 6.5mm; height: 6.5mm; }
.step-ing-photo .ico-box svg { width: 4.2mm; height: 4.2mm; }
.step-ing-name { color: #12303a; }
.step-ing-amt { text-align: right; font-weight: 700; color: #2f6f7a; width: 30mm; }

.step-diagram { margin-top: 3mm; break-inside: avoid; border: .3pt solid #c2d3d7; border-radius: 1.6mm; overflow: hidden; background: #fff; padding: 1.5mm; }
.step-diagram img { display: block; width: 100%; max-height: 55mm; object-fit: contain; }

.visuals { margin-top: 4mm; }
.visual { break-inside: avoid; margin-bottom: 3mm; }
.visual img { width: 100%; }
.visual figcaption { font-size: 8.6pt; color: #64777c; margin-top: 1mm; }

@media print {
  .spa-layout, .nav-btn { display: none !important; }
}

@media screen {
  :root {
    --primary: #2f6f7a;
    --primary-dark: #12303a;
    --primary-light: #eaf3f4;
    --accent: #a3651f;
    --accent-light: #fdf6ed;
    --bg-page: #f5f8f9;
    --bg-card: #ffffff;
    --text-main: #17202a;
    --text-muted: #54666a;
    --border-color: #dce7e9;
  }
  
  html {
    font-size: clamp(12px, 1.2vw + 2px, 20px);
  }
  
  html, body {
    margin: 0;
    padding: 0;
    width: 100vw;
    height: 100vh;
    overflow: hidden;
    background-color: var(--bg-page);
    color: var(--text-main);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    -webkit-font-smoothing: antialiased;
  }
  
  .print-layout {
    display: none !important;
  }
  
  .spa-layout {
    display: flex;
    flex-direction: column;
    width: 100vw;
    height: 100vh;
    position: relative;
  }
  
  /* SPA Header & Timeline */
  .spa-header {
    height: 80px;
    background-color: var(--primary-dark);
    color: #ffffff;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 30px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.08);
    z-index: 100;
    flex-shrink: 0;
  }
  
  .spa-title {
    font-size: 1.5rem;
    font-weight: 700;
    letter-spacing: -0.5px;
    margin: 0;
    color: #ffffff;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 25%;
  }
  
  .spa-timeline {
    position: relative;
    flex: 1;
    height: 100%;
    margin: 0 40px;
    overflow: visible;
  }
  
  /* Mini Gantt background timeline representing time progress */
  .mini-gantt {
    position: absolute;
    top: 50%;
    left: 10%;
    width: 80%;
    height: 14px;
    transform: translateY(-50%);
    display: flex;
    flex-direction: column;
    gap: 3px;
    opacity: 0.35;
    pointer-events: none;
  }
  
  .mini-lane {
    position: relative;
    width: 100%;
    height: 5px;
    background: rgba(255, 255, 255, 0.08);
    border-radius: 2px;
  }
  
  .mini-block {
    position: absolute;
    height: 100%;
    border-radius: 2px;
  }
  
  .lane-person .mini-block {
    background-color: #4db6ac; /* High-contrast bright teal */
  }
  
  .lane-appliance .mini-block {
    background-color: #ffb74d; /* High-contrast bright orange */
  }
  
  /* Dashed range indicator that moves with current step */
  .timeline-highlight {
    position: absolute;
    top: 50%;
    height: 38px;
    transform: translateY(-50%);
    background: rgba(255, 255, 255, 0.08);
    border: 1.5px dashed rgba(255, 255, 255, 0.35);
    border-radius: 19px;
    pointer-events: none;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    z-index: 1;
    opacity: 0;
  }
  
  .timeline-node {
    position: absolute;
    top: 50%;
    transform: translate(-50%, -50%);
    background-color: var(--primary-dark);
    color: rgba(255, 255, 255, 0.75);
    font-weight: 700;
    cursor: pointer;
    border: 2px solid rgba(255, 255, 255, 0.35);
    white-space: nowrap;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    z-index: 2;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 4px 10px rgba(0,0,0,0.25);
  }
  
  /* Pills for Overview, Setup, Timeline, Done */
  .node-pill {
    padding: 6px 14px;
    border-radius: 16px;
    font-size: 0.85rem;
    min-height: 32px;
  }
  
  /* Steps are circular badges */
  .node-step {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    font-size: 0.95rem;
  }
  
  .timeline-node:hover {
    background-color: rgba(255, 255, 255, 0.15);
    border-color: #ffffff;
    color: #ffffff;
    transform: translate(-50%, -50%) scale(1.15);
  }
  
  .timeline-node.active {
    background-color: var(--primary);
    border-color: #ffffff;
    color: #ffffff;
    box-shadow: 0 0 12px rgba(77, 182, 172, 0.6);
    transform: translate(-50%, -50%) scale(1.2);
    z-index: 10;
  }
  
  /* Slides Container */
  .spa-slides {
    flex: 1;
    display: flex;
    overflow-x: auto;
    overflow-y: hidden;
    scroll-snap-type: x mandatory;
    scroll-behavior: smooth;
    -webkit-overflow-scrolling: touch;
  }
  
  .spa-slides::-webkit-scrollbar {
    display: none;
  }
  
  .spa-slide {
    width: 100vw;
    height: 100%;
    flex-shrink: 0;
    scroll-snap-align: start;
    display: flex;
    padding: 24px 36px;
    gap: 24px;
    box-sizing: border-box;
    overflow-y: hidden;
  }
  
  /* Columns */
  .spa-col {
    background: var(--bg-card);
    border-radius: 18px;
    box-shadow: 0 6px 24px rgba(0,0,0,0.03);
    padding: 28px;
    overflow-y: auto;
    height: 100%;
    border: 1px solid var(--border-color);
    display: flex;
    flex-direction: column;
  }
  
  .spa-col h3 {
    border-bottom: 2.5px solid var(--primary-light);
    padding-bottom: 14px;
    margin-bottom: 18px;
    font-size: 1.35rem;
    color: var(--primary-dark);
    display: flex;
    align-items: center;
    gap: 10px;
    flex-shrink: 0;
  }
  
  /* Column layout options */
  .slide-2col .spa-col-left {
    width: 35%;
  }
  .slide-2col .spa-col-right {
    width: 65%;
  }
  
  .slide-equal-2col .spa-col-left {
    width: 50%;
  }
  .slide-equal-2col .spa-col-right {
    width: 50%;
  }
  
  .slide-3col .spa-col-left {
    width: 45%;
  }
  .slide-3col .spa-col-center {
    width: 35%;
  }
  .slide-3col .spa-col-right {
    width: 20%;
  }
  
  /* VR Floating Navigation Buttons */
  .nav-btn {
    position: absolute;
    top: 55%;
    transform: translateY(-50%);
    width: 80px;
    height: 140px;
    background-color: rgba(47, 111, 122, 0.75);
    border: 2px solid rgba(255, 255, 255, 0.25);
    border-radius: 40px;
    color: #ffffff;
    font-size: 3rem;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 8px 32px rgba(0,0,0,0.18);
    z-index: 200;
    transition: all 0.2s ease;
  }
  
  .nav-btn:hover {
    background-color: rgba(47, 111, 122, 0.95);
    border-color: rgba(255, 255, 255, 0.6);
    transform: translateY(-50%) scale(1.05);
  }
  
  .nav-btn:active {
    transform: translateY(-50%) scale(0.95);
  }
  
  .prev-btn {
    left: 16px;
    border-top-left-radius: 8px;
    border-bottom-left-radius: 8px;
  }
  
  .next-btn {
    right: 16px;
    border-top-right-radius: 8px;
    border-bottom-right-radius: 8px;
  }
  
  .nav-btn:disabled {
    opacity: 0;
    pointer-events: none;
  }
  
  /* Content formatting */
  .spa-metadata-list {
    display: flex;
    flex-direction: column;
    gap: 20px;
    margin-top: 24px;
  }
  
  .spa-metadata-item {
    display: flex;
    align-items: center;
    gap: 16px;
    font-size: 1.2rem;
  }
  
  .spa-metadata-item svg {
    color: var(--primary);
    width: 28px;
    height: 28px;
  }
  
  /* Assumptions list */
  .spa-assume-list {
    list-style: none;
    padding: 0;
    margin: 0;
  }
  
  .spa-assume-card {
    display: flex;
    gap: 16px;
    align-items: flex-start;
    padding: 16px;
    border: 1px solid var(--border-color);
    border-radius: 12px;
    background-color: #fafcfc;
  }
  
  .spa-assume-icon {
    flex-shrink: 0;
  }
  
  .spa-assume-body {
    flex: 1;
  }
  
  .spa-assume-body b {
    font-size: 1.1rem;
    color: var(--primary-dark);
    display: block;
    margin-bottom: 4px;
  }
  
  .spa-assume-note {
    font-size: 0.95rem;
    color: var(--text-muted);
    margin: 0;
    line-height: 1.4;
  }
  
  /* Required Tools & Ingredients page (Setup) */
  /* Required Tools & Ingredients page (Setup) - Standardized Cells Layout */
  
  /* What's Left component */
  .whats-left-list {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  
  .whats-left-item {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 4px 6px;
    border-radius: 6px;
    border: 1px solid var(--border-color);
    background-color: #fafcfc;
    font-size: 0.85rem;
    transition: all 0.2s ease;
  }
  
  .whats-left-item.completed {
    opacity: 0.55;
    background-color: #f1f5f6;
    border-color: #e2ebed;
  }
  .whats-left-item.completed .whats-left-title {
    text-decoration: line-through;
    color: var(--text-muted);
  }
  
  .whats-left-item.current {
    border-color: var(--primary);
    background-color: var(--primary-light);
    opacity: 1;
    font-weight: 700;
    box-shadow: 0 4px 12px rgba(47, 111, 122, 0.08);
    transform: scale(1.02);
  }
  .whats-left-item.current .whats-left-title {
    color: var(--primary-dark);
  }
  
  .whats-left-item.next-up {
    border-color: var(--accent);
    background-color: var(--accent-light);
    opacity: 1;
    font-weight: 600;
  }
  
  .whats-left-item .item-num {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background-color: var(--text-muted);
    color: white;
    font-size: 0.7rem;
    font-weight: 700;
    flex-shrink: 0;
  }
  
  .whats-left-item.current .item-num {
    background-color: var(--primary);
  }
  
  .whats-left-item.next-up .item-num {
    background-color: var(--accent);
  }
  
  .whats-left-item.completed .item-num {
    background-color: #90a4ae;
  }
  
  .whats-left-thumb {
    width: 20px !important;
    height: 20px !important;
    border-radius: 4px;
    object-fit: cover;
    border: 1px solid var(--border-color);
    background: #ffffff;
    flex-shrink: 0 !important;
  }
  
  .whats-left-thumb-box {
    width: 20px !important;
    height: 20px !important;
    border-radius: 4px;
    flex-shrink: 0 !important;
    background-color: rgba(0, 0, 0, 0.03);
    border: 1px solid var(--border-color);
  }
  
  .whats-left-badge {
    font-size: 0.65rem;
    font-weight: 700;
    padding: 2px 5px;
    border-radius: 3px;
    margin-left: auto;
    flex-shrink: 0;
  }
  
  .done-badge {
    background-color: #e2f4f1;
    color: #00796b;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    border-radius: 50%;
    padding: 0;
  }
  
  .active-badge {
    background-color: var(--primary);
    color: white;
  }
  
  .next-badge {
    background-color: var(--accent);
    color: white;
  }
  
  .whats-left-title {
    flex: 1;
    font-size: 0.9rem;
    line-height: 1.25;
    word-break: break-word;
    color: var(--text-dark);
  }
  
  /* Action Picture in Pane 3 */
  .spa-action-pic-card {
    width: 100%;
    height: 280px;
    background: #ffffff;
    border: 1px solid var(--border-color);
    border-radius: 12px;
    overflow: hidden;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 4px 16px rgba(0,0,0,0.04);
    flex-shrink: 0;
    margin-top: 14px;
    margin-bottom: 12px;
  }
  
  .spa-action-pic-img {
    width: 100%;
    height: 100%;
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
    padding: 8px;
  }
  
  .spa-scroll-y-whats-left {
    flex: 1;
    overflow-y: auto;
    scrollbar-width: none;
    -webkit-overflow-scrolling: touch;
  }
  .spa-scroll-y-whats-left::-webkit-scrollbar {
    display: none;
  }
  
  .spa-scroll-y-step {
    flex: 1;
    min-height: 60px;
    overflow-y: auto;
    scrollbar-width: none;
    -webkit-overflow-scrolling: touch;
    /* Fades the last couple of lines instead of hard-cutting mid-word when
       the do/done text doesn't fit above the fixed-height picture - a clean
       cut with no gap read as the picture overlapping the text. */
    mask-image: linear-gradient(to bottom, black calc(100% - 18px), transparent 100%);
    -webkit-mask-image: linear-gradient(to bottom, black calc(100% - 18px), transparent 100%);
  }
  .spa-scroll-y-step::-webkit-scrollbar {
    display: none;
  }
  
  /* Step tools wrapping */
  .spa-step-tools-wrap {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-top: 8px;
  }
  
  .spa-step-tool-card {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 14px;
    background-color: #fafcfc;
    border: 1px solid var(--border-color);
    border-radius: 10px;
  }
  
  .spa-step-tool-thumb {
    width: 44px;
    height: 44px;
    object-fit: contain;
    border-radius: 6px;
    border: 1px solid var(--border-color);
    background-color: #ffffff;
    flex-shrink: 0;
  }
  
  .spa-step-tool-thumb-box {
    width: 44px;
    height: 44px;
    border-radius: 6px;
    flex-shrink: 0;
  }
  
  .spa-step-part-thumb {
    width: 36px;
    height: 36px;
    object-fit: contain;
    border-radius: 6px;
    border: 1px solid var(--border-color);
    background-color: #ffffff;
    flex-shrink: 0;
  }
  
  .spa-step-part-thumb-box {
    width: 36px;
    height: 36px;
    border-radius: 6px;
    flex-shrink: 0;
  }
  
  .spa-step-tool-info {
    flex: 1;
    display: flex;
    flex-direction: column;
  }
  
  .spa-step-tool-name {
    font-size: 1.1rem;
    color: var(--primary-dark);
    font-weight: 700;
  }
  
  .spa-step-tool-settings {
    font-size: 0.9rem;
    color: var(--accent);
    font-weight: 600;
    margin-top: 2px;
  }
  
  /* Double column needs layout */
  .spa-step-needs-grid {
    display: flex;
    gap: 10px;
    height: 100%;
    overflow: hidden;
  }
  
  .spa-needs-col {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    height: 100%;
  }
  
  .spa-needs-section-title {
    font-size: 1.15rem;
    color: var(--primary-dark);
    margin: 0 0 10px 0;
    padding-bottom: 6px;
    border-bottom: 2px solid var(--primary-light);
    flex-shrink: 0;
  }
  
  .spa-needs-grid-cells {
    display: grid;
    grid-template-columns: repeat(auto-fill, 120px);
    gap: 8px;
    overflow-y: auto;
    flex: 1;
    scrollbar-width: none;
    -webkit-overflow-scrolling: touch;
  }
  .spa-needs-grid-cells::-webkit-scrollbar {
    display: none;
  }
  
  .spa-needs-cell {
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    padding: 8px 6px;
    border: 1px solid var(--border-color);
    border-radius: 10px;
    background-color: #fafcfc;
    box-shadow: 0 2px 6px rgba(0,0,0,0.02);
    width: 120px;
    height: 160px;
    box-sizing: border-box;
  }
  

  
  .spa-cell-img {
    width: 80px;
    height: 80px;
    border-radius: 6px;
    border: 1px solid var(--border-color);
    background-color: #ffffff;
    flex-shrink: 0;
    margin: 0;
    padding: 0;
  }
  
  figure.spa-cell-img {
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
  }
  
  figure.spa-cell-img img {
    width: 100%;
    height: 100%;
    object-fit: contain;
    display: block;
  }
  
  .spa-cell-img-box {
    width: 80px;
    height: 80px;
    border-radius: 6px;
    flex-shrink: 0;
  }
  
  .spa-cell-title {
    font-size: 0.95rem;
    font-weight: 700;
    color: var(--primary-dark);
    margin-top: 8px;
    word-break: break-word;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  
  .spa-cell-amount {
    font-size: 0.85rem;
    color: var(--primary);
    font-weight: 600;
    margin-top: 4px;
  }
  
  .spa-needs-empty {
    color: var(--text-muted);
    font-style: italic;
    text-align: center;
    padding: 20px;
    background: rgba(0,0,0,0.01);
    border: 1px dashed var(--border-color);
    border-radius: 8px;
  }
  
  /* Process animation classes - input (left) -> tool (center) -> output (right) */
  .spa-process-anim-container {
    width: 100%;
    height: 280px;
    background: #ffffff;
    border: 1px solid var(--border-color);
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 12px;
    position: relative;
    overflow: hidden;
    box-shadow: 0 4px 16px rgba(0,0,0,0.04);
    margin-top: 14px;
    margin-bottom: 12px;
    flex-shrink: 0;
  }

  .spa-diag-inputs {
    display: flex;
    flex-direction: column;
    gap: 10px;
    align-items: center;
    justify-content: center;
    z-index: 2;
    min-width: 60px;
  }
  
  .spa-diag-node {
    width: 44px;
    height: 44px;
    border-radius: 50%;
    background-color: var(--primary-light);
    color: var(--primary-dark);
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 4px 10px rgba(0,0,0,0.08);
    position: relative;
    border: 2px solid var(--border-color);
    overflow: hidden;
  }
  
  .spa-diag-node figure.spa-cell-img,
  .spa-diag-node .spa-cell-img-box {
    width: 100% !important;
    height: 100% !important;
    border: none !important;
    background: transparent !important;
    margin: 0 !important;
    padding: 0 !important;
    box-shadow: none !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
  }
  
  .spa-diag-node img,
  .spa-diag-node figure.spa-cell-img img {
    width: 30px !important;
    height: 30px !important;
    object-fit: contain !important;
    border-radius: 4px !important;
    display: block !important;
  }
  
  .spa-diag-node svg {
    width: 26px !important;
    height: 26px !important;
  }
  
  .spa-diag-node.input-node {
    animation: bounce-in 1s ease-out;
  }
  
  .spa-diag-node.process-node {
    width: 64px;
    height: 64px;
    background-color: var(--primary);
    color: #ffffff;
    border-color: var(--primary);
    animation: pulse-tool 2s infinite ease-in-out;
  }
  
  .spa-diag-node.process-node img {
    width: 40px !important;
    height: 40px !important;
    object-fit: contain !important;
    border-radius: 4px !important;
    display: block !important;
  }
  
  .spa-diag-node.process-node svg {
    width: 38px !important;
    height: 38px !important;
  }
  
  .spa-diag-node.output-node {
    background-color: var(--accent-light);
    border-color: var(--accent);
    color: var(--accent);
    animation: rotate-in 1.2s ease-out;
  }
  
  .spa-diag-node.output-node img, .spa-diag-node.output-node svg {
    width: 30px !important;
    height: 30px !important;
  }
  
  .spa-diag-flow {
    flex: 1;
    height: 4px;
    background-color: var(--border-color);
    position: relative;
    overflow: hidden;
    margin: 0 4px;
  }
  
  .spa-diag-flow::after {
    content: '';
    position: absolute;
    top: 0;
    left: -100%;
    width: 100%;
    height: 100%;
    background: linear-gradient(90deg, transparent, var(--accent), transparent);
    animation: flow-line 2s infinite linear;
  }
  
  .spa-diag-flow.flow-right::after {
    animation-delay: 0.5s;
  }
  
  .spa-diag-output {
    display: flex;
    flex-direction: column;
    align-items: center;
    z-index: 2;
    min-width: 60px;
  }
  
  .spa-diag-process {
    display: flex;
    flex-direction: column;
    align-items: center;
    z-index: 2;
    position: relative;
  }
  
  .spa-diag-lbl {
    font-size: 0.85rem;
    font-weight: 700;
    color: var(--text-muted);
    margin-top: 8px;
    text-align: center;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 90px;
  }
  
  /* SVG Process Animations */
  .spa-diag-node.process-node svg.spin-anim {
    animation: rotate-whisk 3s linear infinite;
    transform-origin: center;
  }
  
  .spa-diag-node.process-node svg.glow-anim {
    animation: pulse-glow 2s infinite ease-in-out;
  }
  
  @keyframes rotate-whisk {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }
  
  @keyframes pulse-glow {
    0%, 100% { opacity: 0.7; filter: drop-shadow(0 0 2px rgba(216, 122, 76, 0.4)); }
    50% { opacity: 1; filter: drop-shadow(0 0 8px #d87a4c); }
  }
  
  @keyframes flow-line {
    0% { left: -100%; }
    100% { left: 100%; }
  }
  
  @keyframes pulse-tool {
    0%, 100% { transform: scale(1); box-shadow: 0 4px 10px rgba(47, 111, 122, 0.3); }
    50% { transform: scale(1.05); box-shadow: 0 4px 20px rgba(47, 111, 122, 0.5); }
  }
  
  @keyframes bounce-in {
    0% { transform: scale(0.3); opacity: 0; }
    50% { transform: scale(1.05); }
    70% { transform: scale(0.9); }
    100% { transform: scale(1); opacity: 1; }
  }
  
  @keyframes rotate-in {
    0% { transform: rotate(-180deg) scale(0.3); opacity: 0; }
    100% { transform: rotate(0deg) scale(1); opacity: 1; }
  }
  
  /* Step details layout */
  .step-large-num {
    font-size: 3.5rem;
    font-weight: 800;
    color: var(--primary);
    line-height: 1;
    margin-bottom: 6px;
  }
  
  .step-large-title {
    font-size: 2rem;
    font-weight: 700;
    color: var(--primary-dark);
    margin-bottom: 20px;
    line-height: 1.25;
  }
  
  .step-large-do {
    font-size: 1.35rem;
    line-height: 1.55;
    margin: 24px 0;
    color: var(--text-main);
  }
  
  .step-large-done {
    font-size: 1.25rem;
    background-color: var(--primary-light);
    color: var(--primary-dark);
    padding: 18px 22px;
    border-radius: 14px;
    border-left: 6px solid var(--primary);
    margin-top: 24px;
    display: flex;
    align-items: center;
    gap: 14px;
  }
  
  .step-large-done svg {
    flex-shrink: 0;
    color: var(--primary);
    width: 24px;
    height: 24px;
  }
  
  .step-ings-table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 15px;
    font-size: 1.15rem;
  }
  .step-ings-table tr {
    border-bottom: 1px solid var(--border-color);
  }
  .step-ings-table tr:last-child {
    border-bottom: 0;
  }
  .step-ings-table td {
    padding: 12px 8px;
    vertical-align: middle;
  }
  .step-ing-photo {
    width: 50px;
  }
  .step-ing-photo .th, .step-ing-photo .ico-box {
    width: 48px;
    height: 48px;
  }
  .step-ing-photo img {
    height: 48px;
    width: 48px;
    object-fit: contain;
  }
  .step-ing-name {
    color: var(--primary-dark);
  }
  .step-ing-amt {
    text-align: right;
    font-weight: 700;
    color: var(--primary);
    width: 80px;
  }
  
  .need {
    font-size: 1.2rem;
    color: var(--text-muted);
    display: flex;
    gap: 10px;
    align-items: center;
    background: var(--primary-light);
    padding: 12px 16px;
    border-radius: 8px;
    margin-top: 12px;
  }
  .need svg {
    width: 24px;
    height: 24px;
    color: var(--primary);
  }
}
"""

JS = """
document.addEventListener("DOMContentLoaded", function() {
  const container = document.querySelector(".spa-slides");
  const nodes = document.querySelectorAll(".timeline-node");
  const prevBtn = document.querySelector(".prev-btn");
  const nextBtn = document.querySelector(".next-btn");
  const highlightBar = document.querySelector(".timeline-highlight");
  
  if (!container || nodes.length === 0) return;
  
  function updateActiveSlide() {
    const scrollLeft = container.scrollLeft;
    const slideWidth = container.clientWidth;
    if (slideWidth === 0) return;
    const activeIndex = Math.round(scrollLeft / slideWidth);
    
    // Update timeline active node
    nodes.forEach((node, idx) => {
      if (idx === activeIndex) {
        node.classList.add("active");
        node.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
      } else {
        node.classList.remove("active");
      }
    });
    
    // Update current active slide's timeline highlight
    const activeSlide = container.children[activeIndex];
    if (activeSlide) {
      const start = parseFloat(activeSlide.getAttribute("data-start") || "0");
      const end = parseFloat(activeSlide.getAttribute("data-end") || "0");
      if (highlightBar) {
        if (end > start && maxTime > 0) {
          const left = 10 + 80 * (start / maxTime);
          const width = 80 * ((end - start) / maxTime);
          highlightBar.style.left = `calc(${left}% - 5px)`;
          highlightBar.style.width = `calc(${width}% + 10px)`;
          highlightBar.style.opacity = "1";
        } else {
          highlightBar.style.opacity = "0";
        }
      }
    }
    
    // Update prev/next button visibility
    if (prevBtn) prevBtn.disabled = (activeIndex === 0);
    if (nextBtn) nextBtn.disabled = (activeIndex === container.children.length - 1);
  }
  
  // Slide navigation by clicking timeline node
  nodes.forEach((node) => {
    node.addEventListener("click", () => {
      const slideIdx = parseInt(node.getAttribute("data-slide") || "0");
      const slideWidth = container.clientWidth;
      container.scrollTo({
        left: slideIdx * slideWidth,
        behavior: "smooth"
      });
      setTimeout(updateActiveSlide, 100);
    });
  });
  
  // Slide navigation by next/prev buttons
  if (prevBtn) {
    prevBtn.addEventListener("click", () => {
      const slideWidth = container.clientWidth;
      const activeIndex = Math.round(container.scrollLeft / slideWidth);
      if (activeIndex > 0) {
        container.scrollTo({
          left: (activeIndex - 1) * slideWidth,
          behavior: "smooth"
        });
      }
    });
  }
  
  if (nextBtn) {
    nextBtn.addEventListener("click", () => {
      const slideWidth = container.clientWidth;
      const activeIndex = Math.round(container.scrollLeft / slideWidth);
      if (activeIndex < container.children.length - 1) {
        container.scrollTo({
          left: (activeIndex + 1) * slideWidth,
          behavior: "smooth"
        });
      }
    });
  }
  
  // Keyboard navigation
  document.addEventListener("keydown", function(e) {
    if (e.key === "ArrowLeft") {
      if (prevBtn && !prevBtn.disabled) prevBtn.click();
    } else if (e.key === "ArrowRight" || e.key === " ") {
      if (nextBtn && !nextBtn.disabled) {
        e.preventDefault();
        nextBtn.click();
      }
    }
  });
  
  let scrollTimeout;
  container.addEventListener("scroll", function() {
    clearTimeout(scrollTimeout);
    scrollTimeout = setTimeout(updateActiveSlide, 50);
  });
  
  window.addEventListener("resize", updateActiveSlide);
  
  // Initial setup
  updateActiveSlide();
});
"""



# --------------------------------------------------------------------------- #
# fallback text PDF
# --------------------------------------------------------------------------- #
def outline_text(spec: dict) -> str:
    out = [s(spec.get("title")), ""]
    out += ["ASSUMPTIONS"] + [f"- {s(a['text'])}" for a in spec["assumptions"]] + [""]
    out += ["REQUIRED"]
    out += [f"- {s(i.get('amount'))} {s(i.get('item'))}" for i in spec["ingredients"]]
    out += [f"- Tool: {s(t.get('name'))} | {s(t.get('settings') or t.get('set'))}" for t in spec["tools"]]
    out += [""]
    out += ["STEPS"]
    for st in spec["steps"]:
        out += [f"{st['n']}. {s(st['title'])}",
                f"   do: {s(st.get('do'))}",
                f"   done: {s(st.get('done'))}"]
    return "\n".join(out)


def write_text_pdf(output: Path, text: str) -> None:
    pages, current = [], []
    for line in text.splitlines():
        for part in textwrap.wrap(line, width=92) or [""]:
            current.append(part)
            if len(current) >= 54:
                pages.append(current)
                current = []
    if current:
        pages.append(current)

    objects: list[str] = []

    def add(obj: str) -> int:
        objects.append(obj)
        return len(objects)

    font = add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    page_ids = []
    for page in pages or [["Recipe"]]:
        ops = ["BT", "/F1 10 Tf", "50 790 Td", "14 TL"]
        for line in page:
            safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            ops += [f"({safe}) Tj", "T*"]
        ops.append("ET")
        stream = "\n".join(ops)
        content = add(f"<< /Length {len(stream.encode('latin-1', 'replace'))} >>\nstream\n{stream}\nendstream")
        page_ids.append(add(
            "<< /Type /Page /Parent 0 0 R /MediaBox [0 0 595 842] /Resources "
            f"<< /Font << /F1 {font} 0 R >> >> /Contents {content} 0 R >>"))
    pages_id = add(f"<< /Type /Pages /Kids [{' '.join(f'{p} 0 R' for p in page_ids)}] /Count {len(page_ids)} >>")
    catalog = add(f"<< /Type /Catalog /Pages {pages_id} 0 R >>")
    objects = [o.replace("/Parent 0 0 R", f"/Parent {pages_id} 0 R") for o in objects]

    chunks, offsets = ["%PDF-1.4\n"], []
    for idx, obj in enumerate(objects, start=1):
        offsets.append(sum(len(c.encode("latin-1", "replace")) for c in chunks))
        chunks.append(f"{idx} 0 obj\n{obj}\nendobj\n")
    xref = sum(len(c.encode("latin-1", "replace")) for c in chunks)
    chunks.append(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n")
    chunks += [f"{o:010d} 00000 n \n" for o in offsets]
    chunks.append(f"trailer\n<< /Size {len(objects) + 1} /Root {catalog} 0 R >>\nstartxref\n{xref}\n%%EOF\n")
    output.write_bytes("".join(chunks).encode("latin-1", "replace"))


# --------------------------------------------------------------------------- #
def render(spec_path: Path) -> Path:
    register_bases(spec_path)
    spec = normalize(json.loads(spec_path.read_text(encoding="utf-8")))
    orig_output = Path(spec.get("output") or spec_path.with_suffix(".pdf"))
    
    # Create dedicated subfolder named after the recipe stem
    recipe_dir = orig_output.parent / orig_output.stem
    recipe_dir.mkdir(parents=True, exist_ok=True)
    
    pdf_output = recipe_dir / f"{orig_output.stem}.pdf"
    html_output = recipe_dir / "index.html"

    timeline_uri = ""
    if spec["timeline"]:
        markup = timeline_svg(spec["timeline"])
        if markup:
            asset = recipe_dir / "assets" / "timeline.svg"
            asset.parent.mkdir(parents=True, exist_ok=True)
            asset.write_text(markup + "\n", encoding="utf-8")
            timeline_uri = "data:image/svg+xml;base64," + base64.b64encode(
                markup.encode("utf-8")).decode("ascii")

    html_output.write_text(build_html(spec, timeline_uri), encoding="utf-8")

    if shutil.which("weasyprint"):
        subprocess.run(["weasyprint", str(html_output), str(pdf_output)], check=True)
    elif shutil.which("pandoc"):
        subprocess.run(["pandoc", str(html_output), "-o", str(pdf_output)], check=True)
    else:
        write_text_pdf(pdf_output, outline_text(spec))
    return pdf_output


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: render_recipe_card.py recipe-spec.json", file=sys.stderr)
        raise SystemExit(2)
    print(render(Path(sys.argv[1])))
