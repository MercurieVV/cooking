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


def resolve(path_text: str) -> Path | None:
    if not path_text:
        return None
    candidate = Path(path_text)
    if candidate.is_absolute():
        return candidate if candidate.exists() else None
    for base in SEARCH_BASES:
        found = base / candidate
        if found.exists():
            return found
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
                elif gap >= 96:  # narrow bar: label to its right
                    tx, chars, stacked = bx + bw + 7, int(gap / 7.2), True
                else:
                    tx, chars, stacked = bx + 7, max(6, int(bw / 7.0)), False
                task = textwrap.shorten(row["task"], width=max(6, chars), placeholder="…")
                if stacked:
                    p.append(f'<text x="{tx:.1f}" y="{by + 17:.1f}" font-size="13" '
                             f'font-weight="700" fill="{color}">{escape(span)}</text>')
                    p.append(f'<text x="{tx:.1f}" y="{by + 33:.1f}" font-size="14" '
                             f'fill="#17202a">{escape(task)}</text>')
                else:
                    p.append(f'<text x="{tx:.1f}" y="{by + 26:.1f}" font-size="13" '
                             f'font-weight="700" fill="{color}">{escape(task)}</text>')

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
    return f'<figure class="{cls}"><img src="{uri}" alt="{e(alt)}">{cap}</figure>'


def photo_or_icon(path_text: str, *hints, explicit=None, alt: str = "", cls: str = "th",
                  caption: str = "") -> str:
    """Prefer a real photo of a concrete thing; fall back to a pictogram."""
    art = thumb(path_text, alt=alt, cls=cls, caption=caption)
    if art:
        return art
    return f'<span class="ico-box">{icon_for(*hints, explicit=explicit, cls="ico-l")}</span>'


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
                chip(s(tool.get("program")), "program", explicit="oven"),
            ])
        )
        parts = "".join(
            photo_or_icon(s(part.get("image")), part.get("name"), explicit=part.get("icon"),
                          alt=s(part.get("name")), cls="th part",
                          caption=s(part.get("name"))) or ""
            for part in (tool.get("parts") or [])
        )
        if not parts and s(tool.get("accessory")):
            parts = f'<div class="chips">{chip(s(tool.get("accessory")), "accessory", explicit="whisk")}</div>'
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
        note_html = f'<span class="ing-note">{e(note)}</span>' if note else ""
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
        chips = "".join(
            filter(None, [
                chip(s(st.get("tool")), s(st.get("tool")), explicit=st.get("tool_icon")),
                chip(s(st.get("accessory")), "accessory", explicit="whisk"),
                *[chip(s(c.get("text") if isinstance(c, dict) else c),
                       s(c.get("text") if isinstance(c, dict) else c),
                       explicit=(c.get("icon") if isinstance(c, dict) else None))
                  for c in st["chips"]],
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
        for extra in (st.get("image"), st.get("diagram")):
            if s(extra) and s(extra) not in seen:
                seen.append(s(extra))
                gallery.append({"image": s(extra), "caption": ""})
        for shot in gallery:
            shots += thumb(s(shot.get("image")), alt=s(shot.get("caption")),
                           cls="th shot", caption=s(shot.get("caption")))
        shots = f'<div class="shots">{shots}</div>' if shots else ""

        needs = f'<p class="need">{svg("bowl", "ico-s")}{e(st["needs"])}</p>' if s(st.get("needs")) else ""
        do = f'<p class="do">{e(st["do"])}</p>' if s(st.get("do")) else ""
        done = (f'<p class="done">{svg("check", "ico-s")}{e(st["done"])}</p>'
                if s(st.get("done")) else "")
        cook = f'<span class="cook">{svg("person", "ico-s")}{e(st["cook"])}</span>' if s(st.get("cook")) else ""
        cards += (
            f'<li class="step"><div class="rail"><span class="num">{e(st["n"])}</span>{icon}</div>'
            f'<div class="body"><h4>{e(st["title"])}{cook}</h4>'
            f'<div class="chips">{chips}</div>{needs}{do}{done}{shots}</div></li>'
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

    return (
        f"<!doctype html><html><head><meta charset=\"utf-8\"><title>{title}</title>"
        f"<style>{CSS}</style></head><body>{header}{sec1}{sec2}{sec3}{extras}</body></html>"
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

.visuals { margin-top: 4mm; }
.visual { break-inside: avoid; margin-bottom: 3mm; }
.visual img { width: 100%; }
.visual figcaption { font-size: 8.6pt; color: #64777c; margin-top: 1mm; }
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
    output = Path(spec.get("output") or spec_path.with_suffix(".pdf"))
    output.parent.mkdir(parents=True, exist_ok=True)

    timeline_uri = ""
    if spec["timeline"]:
        markup = timeline_svg(spec["timeline"])
        if markup:
            asset = output.parent / "assets" / f"{output.stem}-timeline.svg"
            asset.parent.mkdir(parents=True, exist_ok=True)
            asset.write_text(markup + "\n", encoding="utf-8")
            timeline_uri = "data:image/svg+xml;base64," + base64.b64encode(
                markup.encode("utf-8")).decode("ascii")

    html_path = output.with_suffix(".html")
    html_path.write_text(build_html(spec, timeline_uri), encoding="utf-8")

    if shutil.which("weasyprint"):
        subprocess.run(["weasyprint", str(html_path), str(output)], check=True)
    elif shutil.which("pandoc"):
        subprocess.run(["pandoc", str(html_path), "-o", str(output)], check=True)
    else:
        write_text_pdf(output, outline_text(spec))
    return output


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: render_recipe_card.py recipe-spec.json", file=sys.stderr)
        raise SystemExit(2)
    print(render(Path(sys.argv[1])))
