#!/usr/bin/env python3
"""Look up ingredient photos on rimi.lv (Latvian grocery e-shop).

Rimi shows the exact local product the user would actually buy, so its photo
is more useful than a generic Wikipedia illustration for ingredients they
shop for. Search matching on rimi.lv is fuzzy/typo-tolerant, not translated:
an English query like "butter" returns nonsense (Butter Chicken sauce,
"Bitter" drinks, "Botter" wine) because "sviests" is the real Latvian word.
So this is a two-step, human/agent-checked flow rather than a blind
one-shot fetch like fetch_food_photos.py:

  1. List candidates for a Latvian query and eyeball them:
       fetch_rimi_photo.py --list sviests

  2. Once you know which index is actually the ingredient (not a sauce,
     ready meal, or unrelated product with a similar name), download it:
       fetch_rimi_photo.py --pick sviests 0 --slug cold-butter

Saves to raw/food/images/<slug>.jpg and appends provenance (query, chosen
product name/code, rimi.lv product page URL) to raw/food/images/SOURCES.md,
same append-only convention as fetch_food_photos.py.
"""

from __future__ import annotations

import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

CACHE = Path("raw/food/images")
SOURCES = CACHE / "SOURCES.md"
SEARCH_URL = "https://www.rimi.lv/e-veikals/lv/meklesana"
UA = {"User-Agent": "Mozilla/5.0 (cooking-kb personal recipe cards)"}

ITEM_RE = re.compile(
    r'data-product-code="(?P<code>\d+)"[^>]*'
    r'data-gtms-banner-title="(?P<title>[^"]+)".*?'
    r'<a class="card__url[^"]*" href="(?P<href>[^"]+)".*?'
    r'<img src="(?P<img>https://[^"]+backend-fallback\.png/MAT_[^"]+)"',
    re.S,
)


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def search(query: str) -> list[dict]:
    url = SEARCH_URL + "?" + urllib.parse.urlencode({"query": query})
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    results = []
    for m in ITEM_RE.finditer(html):
        # Bump the thumbnail transform up from the default 216px.
        img = m.group("img").replace("h_216,q_1,w_216", "h_600,q_auto,w_600")
        results.append({
            "code": m.group("code"),
            "title": m.group("title"),
            "href": "https://www.rimi.lv" + m.group("href"),
            "img": img,
        })
    return results


def cmd_list(query: str) -> int:
    results = search(query)
    if not results:
        print(f"no results for {query!r} - try a different Latvian term", file=sys.stderr)
        return 1
    for i, r in enumerate(results):
        print(f"[{i}] {r['title']}")
        print(f"      {r['href']}")
    return 0


def cmd_pick(query: str, index: int, target_slug: str) -> int:
    results = search(query)
    if index >= len(results):
        print(f"index {index} out of range ({len(results)} results)", file=sys.stderr)
        return 1
    r = results[index]

    CACHE.mkdir(parents=True, exist_ok=True)
    target = CACHE / f"{target_slug}.jpg"
    with urllib.request.urlopen(urllib.request.Request(r["img"], headers=UA), timeout=30) as resp:
        target.write_bytes(resp.read())

    line = (f"- `{target.name}` — rimi.lv query `{query}` → "
            f"[{r['title']}]({r['href']}) (product code {r['code']}) → {r['img']}\n")
    if not SOURCES.exists():
        SOURCES.write_text(
            "# Food photo cache sources\n\n"
            "> Sources: Wikipedia REST summary thumbnails (Wikimedia Commons images); "
            "rimi.lv product listing photos (picked and confirmed per ingredient, not auto-matched).\n"
            "> Collected by `fetch_food_photos.py` / `fetch_rimi_photo.py`; append-only.\n\n",
            encoding="utf-8")
    with SOURCES.open("a", encoding="utf-8") as handle:
        handle.write(line)
    print(f"saved   {target}  ({r['title']})")
    return 0


def main(argv: list[str]) -> int:
    if argv[:1] == ["--list"] and len(argv) == 2:
        return cmd_list(argv[1])
    if (argv[:1] == ["--pick"] and len(argv) == 5
            and argv[3] == "--slug" and argv[2].isdigit()):
        return cmd_pick(argv[1], int(argv[2]), argv[4])
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
