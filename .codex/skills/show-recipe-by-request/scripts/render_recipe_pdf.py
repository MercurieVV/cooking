#!/usr/bin/env python3
"""Render an appliance-aware recipe JSON spec to Markdown and PDF via Pandoc."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path


def s(value) -> str:
    return "" if value is None else str(value)


def cell(value) -> str:
    return s(value).replace("\n", "<br>").replace("|", "\\|")


def md_table(headers: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    out.extend("| " + " | ".join(cell(col) for col in row) + " |" for row in rows)
    return "\n".join(out)


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
        timeline_rows = [[t.get("time", ""), t.get("cook", ""), t.get("task", "")] for t in spec["timeline"]]
        lines.append(md_table(["Time", "Cook", "Task"], timeline_rows))

    lines += ["", "## Method", ""]
    for idx, step in enumerate(spec.get("steps", []), start=1):
        number = step.get("number", idx)
        lines.append(f"### {number}. {s(step.get('title', 'Step'))}")
        lines.append(f"**Cook:** {s(step.get('cook', 'Cook'))}  ")
        lines.append(f"**Appliance:** {s(step.get('appliance'))}  ")
        lines.append(f"**Accessory:** {s(step.get('accessory'))}  ")
        lines.append(f"**Settings/program:** {s(step.get('settings'))}  ")
        lines.append(f"**Timing:** {s(step.get('timing'))}  ")
        lines.append("")
        lines.append(s(step.get("instruction")))
        lines.append("")
        lines.append(f"**Done when:** {s(step.get('done'))}")
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
  border-bottom: 1px solid #d5e1e4;
  font-size: 11.5pt;
  margin-top: 5mm;
  padding-bottom: 1mm;
}

p {
  margin: 2.2mm 0;
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
