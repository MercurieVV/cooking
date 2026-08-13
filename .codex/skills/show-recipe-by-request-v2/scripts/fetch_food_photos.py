#!/usr/bin/env python3
"""Cache ingredient photos locally from Wikipedia/Wikimedia.

Photos live in `raw/food/images/<slug>.jpg` and are reused by later recipes.
Provenance (query -> article -> image URL) is appended to
`raw/food/images/SOURCES.md`, matching the repo rule that `raw/` keeps evidence.

Usage:
  fetch_food_photos.py apple "sour cream" cinnamon
  fetch_food_photos.py --spec recipes/foo.json     # every ingredient in a spec
  fetch_food_photos.py --spec recipes/foo.json --write   # also patch the spec

Already-cached slugs are skipped, so re-running is cheap and offline-safe.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.parse
import time
import urllib.request
from pathlib import Path

CACHE = Path("raw/food/images")
SOURCES = CACHE / "SOURCES.md"
API = "https://en.wikipedia.org/api/rest_v1/page/summary/"
UA = {"User-Agent": "cooking-kb/1.0 (personal recipe cards)"}
# Words that describe state, not the food itself.
NOISE = re.compile(
    r"\b(cold|warm|hot|fresh|plain|fine|coarse|ground|large|small|firm|thick|"
    r"unsalted|salted|white|brown|optional|beaten|melted|chopped|sliced|for|the)\b"
)


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def query_for(name: str) -> str:
    core = NOISE.sub(" ", name.lower())
    core = re.sub(r"\s+", " ", core).strip() or name
    return core


def fetch(name: str) -> Path | None:
    CACHE.mkdir(parents=True, exist_ok=True)
    target = CACHE / f"{slug(name)}.jpg"
    if target.exists():
        print(f"cached  {target}")
        return target

    query = query_for(name)
    url = API + urllib.parse.quote(query.replace(" ", "_"))
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as resp:
            data = json.load(resp)
    except Exception as exc:  # network or 404
        print(f"MISS    {name}: {exc}", file=sys.stderr)
        return None

    src = (data.get("thumbnail") or {}).get("source")
    if not src:
        print(f"MISS    {name}: no thumbnail on '{data.get('title')}'", file=sys.stderr)
        return None
    src = src.split("?")[0]  # Wikimedia rejects arbitrary thumbnail widths

    try:
        with urllib.request.urlopen(urllib.request.Request(src, headers=UA), timeout=30) as resp:
            target.write_bytes(resp.read())
        time.sleep(0.4)  # stay friendly to the API
    except Exception as exc:
        print(f"MISS    {name}: {exc}", file=sys.stderr)
        return None

    line = (f"- `{target.name}` — query `{query}` → "
            f"[{data.get('title')}]({(data.get('content_urls') or {}).get('desktop', {}).get('page', '')}) → {src}\n")
    if not SOURCES.exists():
        SOURCES.write_text(
            "# Food photo cache sources\n\n"
            "> Source: Wikipedia REST summary thumbnails (Wikimedia Commons images)\n"
            "> Collected by `fetch_food_photos.py`; append-only.\n\n", encoding="utf-8")
    with SOURCES.open("a", encoding="utf-8") as handle:
        handle.write(line)
    print(f"saved   {target}")
    return target


def main(argv: list[str]) -> int:
    write_back = "--write" in argv
    argv = [a for a in argv if a != "--write"]

    if argv[:1] == ["--spec"]:
        spec_path = Path(argv[1])
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        items = (spec.get("required") or {}).get("ingredients") or spec.get("ingredients") or []
        for ing in items:
            name = ing.get("item", "")
            got = fetch(name)
            if got and write_back and not ing.get("photo"):
                ing["photo"] = str(got)
        if write_back:
            spec_path.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n",
                                 encoding="utf-8")
            print(f"patched {spec_path}")
        return 0

    if not argv:
        print(__doc__, file=sys.stderr)
        return 2
    for name in argv:
        fetch(name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
