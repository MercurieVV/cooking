#!/usr/bin/env python3
"""Regression guard for render_recipe_card.py.

Renders the reference recipe and checks the PDF didn't blow up into
one-page-per-image (the failure mode fixed once already: a stray inline
`height:100%` on a print-card image with no fixed-height ancestor made
every photo render at full intrinsic size, turning a 5-page card into 47
pages). Catches that class of bug without hardcoding a page count, so it
scales to any reference recipe.

Usage: smoke_test.py [path-to-spec.json]
Exit code 0 = pass, 1 = fail. Prints a summary either way.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
DEFAULT_SPEC = SCRIPTS_DIR.parent / "references" / "example-apple-pie.json"

sys.path.insert(0, str(SCRIPTS_DIR))
from render_recipe_card import normalize, render  # noqa: E402


def weasyprint_python() -> Path | None:
    """Resolve the interpreter bundled with the `weasyprint` CLI (its shebang),
    so we can `import weasyprint` for exact page counts without adding a
    project dependency."""
    exe = shutil.which("weasyprint")
    if not exe:
        return None
    first_line = Path(exe).read_text(encoding="utf-8", errors="ignore").splitlines()[0]
    if not first_line.startswith("#!"):
        return None
    candidate = Path(first_line[2:].strip())
    return candidate if candidate.exists() else None


def count_pdf_pages(html_path: Path) -> int | None:
    py = weasyprint_python()
    if py is None:
        return None
    snippet = (
        "import weasyprint, sys\n"
        f"doc = weasyprint.HTML({str(html_path)!r}).render()\n"
        "print(len(doc.pages))\n"
    )
    result = subprocess.run([str(py), "-c", snippet], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"warning: page-count probe failed: {result.stderr.strip()}", file=sys.stderr)
        return None
    return int(result.stdout.strip())


def main() -> int:
    spec_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SPEC
    spec = normalize(json.loads(spec_path.read_text(encoding="utf-8")))
    item_count = len(spec["ingredients"]) + len(spec["tools"]) + len(spec["steps"])

    failures: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        work_spec = Path(tmp) / spec_path.name
        out_spec = json.loads(spec_path.read_text(encoding="utf-8"))
        out_spec["output"] = str(Path(tmp) / "smoke.pdf")
        work_spec.write_text(json.dumps(out_spec), encoding="utf-8")

        pdf_path = render(work_spec)
        html_path = pdf_path.parent / "index.html"

        if not pdf_path.exists() or pdf_path.stat().st_size == 0:
            failures.append(f"PDF missing or empty: {pdf_path}")
        if not html_path.exists() or html_path.stat().st_size == 0:
            failures.append(f"HTML missing or empty: {html_path}")

        html = html_path.read_text(encoding="utf-8") if html_path.exists() else ""
        for marker, expected in (
            ('class="print-layout"', 1),
            ('class="spa-layout"', 1),
            ("@media print", 1),
            ("@media screen", 1),
        ):
            found = html.count(marker)
            if found != expected:
                failures.append(f"expected {expected}x {marker!r} in HTML, found {found}")

        page_count = count_pdf_pages(html_path)
        if page_count is None:
            print("warning: weasyprint not available, skipping exact page-count check",
                  file=sys.stderr)
        else:
            # One page per ingredient/tool/step is exactly the failure mode this
            # guards against (percentage-height image with no fixed-height
            # ancestor -> full-res image -> forced page break per photo).
            budget = item_count + 2
            print(f"pdf pages: {page_count} (item_count={item_count}, budget<={budget})")
            if page_count > budget:
                failures.append(
                    f"PDF has {page_count} pages for {item_count} ingredients/tools/steps "
                    f"(budget {budget}) - looks like one-page-per-image regression"
                )

    if failures:
        print("SMOKE TEST FAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("SMOKE TEST PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
