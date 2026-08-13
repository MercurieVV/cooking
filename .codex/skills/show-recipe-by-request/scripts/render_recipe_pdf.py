#!/usr/bin/env python3
"""Render an appliance-aware recipe JSON spec to Markdown and PDF via Pandoc."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import textwrap
from html import escape
from pathlib import Path


def s(value) -> str:
    return "" if value is None else str(value)


def cell(value) -> str:
    return s(value).replace("\n", "<br>").replace("|", "\\|")


def md_table(headers: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    out.extend("| " + " | ".join(cell(col) for col in row) + " |" for row in rows)
    return "\n".join(out)


def write_timeline_svg(items: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row_height = 62
    top = 38
    height = max(120, top + row_height * len(items) + 22)
    width = 820
    line_x = 132
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="Recipe timeline">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<line x1="{line_x}" y1="{top}" x2="{line_x}" y2="{height - 28}" stroke="#477b84" stroke-width="4"/>',
    ]
    for idx, item in enumerate(items):
        y = top + idx * row_height
        time = escape(s(item.get("time", "")))
        cook = escape(s(item.get("cook", "")))
        task_lines = textwrap.wrap(s(item.get("task", "")), width=66)[:2]
        parts += [
            f'<text x="104" y="{y + 8}" font-family="Arial, sans-serif" font-size="18" font-weight="700" text-anchor="end" fill="#1f3a44">{time}</text>',
            f'<circle cx="{line_x}" cy="{y + 2}" r="8" fill="#477b84" stroke="#dfeaec" stroke-width="3"/>',
            f'<rect x="154" y="{y - 20}" width="612" height="48" rx="6" fill="#f7fafb" stroke="#b8c8cc"/>',
            f'<text x="170" y="{y - 2}" font-family="Arial, sans-serif" font-size="14" font-weight="700" fill="#455a64">{cook}</text>',
        ]
        for line_idx, line in enumerate(task_lines):
            parts.append(
                f'<text x="170" y="{y + 17 + line_idx * 17}" font-family="Arial, sans-serif" font-size="15" fill="#17202a">{escape(line)}</text>'
            )
    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def recipe_markdown(spec: dict) -> str:
    lines: list[str] = [f"# {s(spec.get('title', 'Recipe'))}", ""]
    meta = [
        ("Servings", spec.get("servings")),
        ("Total time", spec.get("total_time")),
        ("Active time", spec.get("active_time")),
        ("Passive time", spec.get("passive_time")),
        ("Difficulty", spec.get("difficulty")),
    ]
    for label, value in meta:
        if value:
            lines.append(f"**{label}:** {s(value)}  ")
    if spec.get("summary"):
        lines += ["", s(spec["summary"])]

    if spec.get("assumptions"):
        lines += ["", "## Assumptions", ""]
        lines += [f"- {s(item)}" for item in spec["assumptions"]]

    appliances = spec.get("appliances") or []
    if appliances:
        lines += ["", "## Appliance Plan", ""]
        for appliance in appliances:
            lines.append(f"### {s(appliance.get('name'))}")
            if appliance.get("image"):
                lines.append(f"![{s(appliance.get('name'))}]({s(appliance.get('image'))})")
            lines.append("")
            lines.append(f"**Use:** {s(appliance.get('role'))}  ")
            lines.append(f"**Settings/program:** {s(appliance.get('settings'))}  ")
            lines.append(f"**Accessory:** {s(appliance.get('accessory'))}")
            lines.append("")

    lines += ["", "## Ingredients", ""]
    ingredient_rows = [
        [i.get("amount", ""), i.get("item", ""), i.get("notes", "")]
        for i in spec.get("ingredients", [])
    ]
    lines.append(md_table(["Amount", "Ingredient", "Notes"], ingredient_rows))

    if spec.get("timeline"):
        lines += ["", "## Timeline", ""]
        lines.append(f"![Timeline]({s(spec.get('timeline_image'))})")

    if spec.get("visuals"):
        lines += ["", "## Visuals", ""]
        for visual in spec["visuals"]:
            lines.append(f"### {s(visual.get('title', 'Diagram'))}")
            if visual.get("image"):
                lines.append(f"![{s(visual.get('title', 'Diagram'))}]({s(visual.get('image'))})")
            if visual.get("caption"):
                lines.append(f"**Note:** {s(visual.get('caption'))}")
            lines.append("")

    lines += ["", "## Method", ""]
    for idx, step in enumerate(spec.get("steps", []), start=1):
        number = step.get("number", idx)
        lines.append(f"### {number}. {s(step.get('title', 'Step'))}")
        if step.get("image"):
            lines.append(f"![{s(step.get('title', 'Step'))}]({s(step.get('image'))})")
            lines.append("")
        if step.get("diagram"):
            lines.append(f"![{s(step.get('title', 'Step'))} diagram]({s(step.get('diagram'))})")
            lines.append("")
        lines.append(f"**Cook:** {s(step.get('cook', 'Cook'))}  ")
        if step.get("needs"):
            lines.append(f"**Need:** {s(step.get('needs'))}  ")
        lines.append(f"**Tool:** {s(step.get('appliance'))}; {s(step.get('accessory'))}  ")
        lines.append(f"**Set:** {s(step.get('settings'))}; {s(step.get('timing'))}  ")
        lines.append(f"**Do:** {s(step.get('instruction'))}  ")
        lines.append(f"**Done:** {s(step.get('done'))}")
        lines.append("")

    if spec.get("sync_points"):
        lines += ["", "## Sync Points", ""]
        sync_rows = [[sp.get("name", ""), sp.get("when", ""), sp.get("criteria", "")] for sp in spec["sync_points"]]
        lines.append(md_table(["Point", "When", "Readiness criteria"], sync_rows))

    if spec.get("food_safety"):
        lines += ["", "## Food Safety", ""]
        lines += [f"- {s(item)}" for item in spec["food_safety"]]

    return "\n".join(lines) + "\n"


def recipe_css() -> str:
    return """
@page {
  size: A4;
  margin: 15mm 14mm;
}

html {
  color: #17202a;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  font-size: 10.5pt;
  line-height: 1.38;
}

body {
  max-width: 100%;
}

h1, h2, h3 {
  color: #1f3a44;
  font-weight: 700;
  line-height: 1.18;
  margin: 0;
}

h1 {
  border-bottom: 2px solid #9bb7bf;
  font-size: 22pt;
  margin-bottom: 6mm;
  padding-bottom: 3mm;
}

h2 {
  background: #edf4f5;
  border-left: 4px solid #477b84;
  font-size: 14pt;
  margin-top: 7mm;
  padding: 2mm 3mm;
}

h3 {
  background: #f7fafb;
  border-left: 3px solid #9bb7bf;
  font-size: 11.5pt;
  margin-top: 5mm;
  padding: 1.5mm 2mm;
}

p {
  margin: 1.6mm 0 1.6mm 4mm;
}

ul {
  margin: 2mm 0 3mm 5mm;
  padding-left: 4mm;
}

li {
  margin: 1mm 0;
}

strong {
  color: #263238;
}

table {
  border-collapse: collapse;
  margin: 3mm 0 5mm;
  width: 100%;
}

th {
  background: #dfeaec;
  color: #17202a;
  font-weight: 700;
  text-align: left;
}

th, td {
  border: 0.35pt solid #b8c8cc;
  padding: 2mm;
  vertical-align: top;
}

tbody tr:nth-child(even) {
  background: #f7fafb;
}

img {
  display: block;
  max-height: 42mm;
  max-width: 72mm;
  object-fit: contain;
  margin: 2mm 0 3mm;
}

hr {
  border: 0;
  border-top: 1px solid #d5e1e4;
}
""".strip() + "\n"


def escape_pdf_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def write_basic_pdf(output: Path, markdown: str) -> None:
    plain = []
    for line in markdown.splitlines():
        line = line.replace("#", "").replace("**", "").replace("<br>", " ").strip()
        if line.startswith("!["):
            line = "Image: " + line.split("](", 1)[-1].rstrip(")")
        plain.append(line)

    pages: list[list[str]] = []
    current: list[str] = []
    for line in plain:
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

    font_id = add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    page_ids: list[int] = []
    for page in pages or [["Recipe"]]:
        ops = ["BT", "/F1 10 Tf", "50 790 Td", "14 TL"]
        for line in page:
            ops += [f"({escape_pdf_text(line)}) Tj", "T*"]
        ops.append("ET")
        stream = "\n".join(ops)
        content_id = add(f"<< /Length {len(stream.encode('latin-1', 'replace'))} >>\nstream\n{stream}\nendstream")
        page_ids.append(add(f"<< /Type /Page /Parent 0 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >>"))

    pages_id = add(f"<< /Type /Pages /Kids [{' '.join(f'{p} 0 R' for p in page_ids)}] /Count {len(page_ids)} >>")
    catalog_id = add(f"<< /Type /Catalog /Pages {pages_id} 0 R >>")
    objects = [obj.replace("/Parent 0 0 R", f"/Parent {pages_id} 0 R") for obj in objects]

    chunks = ["%PDF-1.4\n"]
    offsets = [0]
    for idx, obj in enumerate(objects, start=1):
        offsets.append(sum(len(chunk.encode("latin-1", "replace")) for chunk in chunks))
        chunks.append(f"{idx} 0 obj\n{obj}\nendobj\n")
    xref = sum(len(chunk.encode("latin-1", "replace")) for chunk in chunks)
    chunks.append(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n")
    chunks.extend(f"{off:010d} 00000 n \n" for off in offsets[1:])
    chunks.append(f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\nstartxref\n{xref}\n%%EOF\n")
    output.write_bytes("".join(chunks).encode("latin-1", "replace"))


def render(spec_path: Path) -> Path:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    output = Path(spec.get("output") or spec_path.with_suffix(".pdf"))
    output.parent.mkdir(parents=True, exist_ok=True)
    if spec.get("timeline") and not spec.get("timeline_image"):
        timeline_path = output.parent / "assets" / f"{output.stem}-timeline.svg"
        write_timeline_svg(spec["timeline"], timeline_path)
        try:
            spec["timeline_image"] = str(timeline_path.relative_to(Path.cwd()))
        except ValueError:
            spec["timeline_image"] = str(timeline_path)

    markdown = recipe_markdown(spec)
    md_path = output.with_suffix(".md")
    css_path = output.with_suffix(".css")
    md_path.write_text(markdown, encoding="utf-8")
    css_path.write_text(recipe_css(), encoding="utf-8")

    if shutil.which("pandoc") and shutil.which("weasyprint"):
        resource_paths = [str(Path.cwd()), str(spec_path.parent), str(output.parent)]
        subprocess.run(
            [
                "pandoc",
                str(md_path),
                "-o",
                str(output),
                "--pdf-engine=weasyprint",
                "--css",
                str(css_path),
                "--resource-path=" + ":".join(resource_paths),
                "--metadata",
                f"title={s(spec.get('title', 'Recipe'))}",
            ],
            check=True,
        )
    else:
        write_basic_pdf(output, markdown)
    return output


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: render_recipe_pdf.py recipe-spec.json", file=sys.stderr)
        raise SystemExit(2)
    print(render(Path(sys.argv[1])))
