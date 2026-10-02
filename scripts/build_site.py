#!/usr/bin/env python3
"""Assemble the GitHub Pages site from recipes/ into _site/.

Each recipe folder holding an index.html (directly or one level down) is copied
to _site/<recipe-folder>/ so URLs stay https://<host>/cooking/<recipe>/ and
<recipe>.pdf. A root index.html lists every recipe.
"""
import html
import re
import shutil
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
recipes = root / "recipes"
site = Path(sys.argv[1]) if len(sys.argv) > 1 else root / "_site"

shutil.rmtree(site, ignore_errors=True)
site.mkdir(parents=True)
(site / ".nojekyll").touch()

entries = []
for folder in sorted(p for p in recipes.iterdir() if p.is_dir()):
    pages = sorted(folder.glob("index.html")) or sorted(folder.glob("*/index.html"))
    if not pages:
        continue
    src = pages[0].parent
    dest = site / folder.name
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns("*.json"))
    head = pages[0].read_text(encoding="utf-8", errors="ignore")[:20000]
    m = re.search(r"<title>(.*?)</title>", head, re.S)
    title = html.unescape(m.group(1).strip()) if m else folder.name
    pdfs = sorted(dest.glob("*.pdf"))
    entries.append((title, folder.name, pdfs[0].name if pdfs else None))

items = "\n".join(
    f'<li><a href="{slug}/">{html.escape(title)}</a>'
    + (f' <a class="pdf" href="{slug}/{pdf}">PDF</a>' if pdf else "")
    + "</li>"
    for title, slug, pdf in sorted(entries, key=lambda e: e[0].lower())
)
(site / "index.html").write_text(
    f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Cooking</title>
<style>
body{{font:18px/1.5 system-ui,sans-serif;max-width:640px;margin:0 auto;padding:24px 16px;background:#fff;color:#222}}
@media(prefers-color-scheme:dark){{body{{background:#111;color:#eee}}a{{color:#8ab4f8}}}}
li{{margin:.6em 0}} .pdf{{font-size:.8em;margin-left:.5em}}
</style></head><body>
<h1>Cooking</h1>
<ul>
{items}
</ul>
</body></html>
""",
    encoding="utf-8",
)
print(f"built {len(entries)} recipes into {site}")
