#!/usr/bin/env python3
"""Download an appliance manual or photo into raw/kitchen-tools, verified and logged.

Why this exists: hand-rolled `curl` runs silently produce Cloudflare HTML saved as
`.pdf`, or get skipped entirely and replaced by a prose "source extract". This
script makes the download the cheap path and makes every failure visible.

What it does:
  1. fetches the URL with a browser UA and a referer,
  2. checks the magic bytes (PDF/JPEG/PNG/WEBP/GIF) — HTML wrappers are rejected,
  3. writes to `raw/kitchen-tools/manuals/` or `raw/kitchen-tools/images/`,
  4. appends the attempt (success OR failure, with HTTP status) to
     `raw/kitchen-tools/ACQUISITION-LOG.md`,
  5. for images, appends an entry to `raw/kitchen-tools/images/README.md`.

Usage:
  fetch_asset.py --kind manual --device "AEG BE3002420M" \
      --name aeg-be3002420m-user-manual.pdf \
      --source "AEG official manuals page" URL [URL ...]
  fetch_asset.py --kind image --device "AEG BE3002420M" \
      --name aeg-be3002420m-product.jpg --exact --source "shop.aeg.co.uk" URL

Several URLs = fallback ladder, tried in order; first verified hit wins.
Exit code 0 = asset on disk. Exit code 1 = every candidate failed (and the
failures are now in the log; record `NOT ACQUIRED` in the inventory).
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path("raw/kitchen-tools")
LOG = ROOT / "ACQUISITION-LOG.md"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

MAGIC = {
    "pdf": [b"%PDF-"],
    "jpg": [b"\xff\xd8\xff"],
    "jpeg": [b"\xff\xd8\xff"],
    "png": [b"\x89PNG\r\n\x1a\n"],
    "webp": [b"RIFF"],
    "gif": [b"GIF8"],
    "svg": [b"<svg", b"<?xml"],
}


def sniff_ok(name: str, blob: bytes) -> tuple[bool, str]:
    ext = name.rsplit(".", 1)[-1].lower()
    heads = MAGIC.get(ext)
    if heads is None:
        return True, f"no magic check for .{ext}"
    head = blob[:16].lstrip() if ext == "svg" else blob[:16]
    if any(head.startswith(h) for h in heads):
        return True, f"valid {ext}"
    if blob[:64].lstrip().lower().startswith((b"<!doctype", b"<html")):
        return False, "HTML wrapper (gate/captcha), not a file"
    return False, f"bytes are not {ext}: {blob[:12]!r}"


def log(line: str) -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    if not LOG.exists():
        LOG.write_text(
            "# Asset acquisition log\n\n"
            "> Every manual/photo download attempt, successful or not.\n"
            "> Written by `add-kitchen-appliance/scripts/fetch_asset.py`; append-only.\n"
            "> A `FAIL` line is evidence, not a dead end — retry it when a better\n"
            "> source appears.\n\n", encoding="utf-8")
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def index_image(path: Path, device: str, exact: bool, source: str, url: str) -> None:
    readme = ROOT / "images" / "README.md"
    if not readme.exists():
        return
    kind = "exact-model" if exact else "generic/representative"
    entry = (f"- `{path.name}` — {device} ({kind}); source: {source or url}\n")
    text = readme.read_text(encoding="utf-8")
    if path.name in text:
        return
    readme.write_text(text.rstrip("\n") + "\n" + entry, encoding="utf-8")


def get(url: str, referer: str | None) -> tuple[int, bytes, str]:
    # Some hosts block the full Chrome UA as bot-like, others require it. Try both.
    last = (0, b"", "not attempted")
    for ua in (UA, "Mozilla/5.0"):
        headers = {"User-Agent": ua, "Accept": "*/*",
                   "Accept-Language": "en-US,en;q=0.9"}
        if referer:
            headers["Referer"] = referer
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.status, resp.read(), ""
        except urllib.error.HTTPError as exc:
            last = (exc.code, b"", str(exc))
        except Exception as exc:  # DNS, TLS, timeout
            last = (0, b"", str(exc))
    return last


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("urls", nargs="+")
    ap.add_argument("--kind", choices=["manual", "image"], required=True)
    ap.add_argument("--device", required=True, help="Brand + model, as in the inventory")
    ap.add_argument("--name", required=True, help="Target filename with extension")
    ap.add_argument("--source", default="", help="Human name of the source")
    ap.add_argument("--referer", default=None)
    ap.add_argument("--exact", action="store_true",
                    help="Image is an exact-model photo, not a representative one")
    args = ap.parse_args(argv)

    out_dir = ROOT / ("manuals" if args.kind == "manual" else "images")
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / args.name
    today = dt.date.today().isoformat()

    if target.exists():
        print(f"cached  {target}")
        return 0

    for url in args.urls:
        status, blob, err = get(url, args.referer)
        if not blob:
            log(f"- {today} FAIL {args.device} — {args.kind} — HTTP {status} {err} — {url}")
            print(f"FAIL    HTTP {status} {err} {url}", file=sys.stderr)
            continue
        ok, why = sniff_ok(args.name, blob)
        if not ok:
            log(f"- {today} FAIL {args.device} — {args.kind} — {why} — {url}")
            print(f"FAIL    {why} {url}", file=sys.stderr)
            continue
        target.write_bytes(blob)
        log(f"- {today} OK {args.device} — {args.kind} — `{target}` "
            f"({len(blob) // 1024} KB, {why}) — source: {args.source or url} — {url}")
        if args.kind == "image":
            index_image(target, args.device, args.exact, args.source, url)
        print(f"saved   {target} ({len(blob) // 1024} KB)")
        return 0

    print(f"NOT ACQUIRED: {args.device} {args.kind} — all {len(args.urls)} candidates failed",
          file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
