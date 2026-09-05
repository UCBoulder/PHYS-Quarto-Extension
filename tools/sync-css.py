"""Copy the Physics Labs platform's content stylesheets into this extension.

The platform scopes its content rules to `.quarto-page-content`, the class on
its Django content container. Quarto's equivalent container is
`<main class="content" id="quarto-document-content">`, so the copy rewrites that
one selector token to `main.content`. Everything else is verbatim.

Usage (from the repository root):
    python tools/sync-css.py [path-to-platform-checkout]

The platform path defaults to a sibling checkout of PHYS-Undergraduate-Labs-Web.
"""

from __future__ import annotations

import sys
from pathlib import Path

FILES = [
    "theme-consolidated.css",
    "quarto-content.css",
    "section-numbering.css",
    "code-blocks.css",
    "tables.css",
    "figures.css",
    "equations.css",
    "cross-references.css",
]

PLATFORM_SELECTOR = ".quarto-page-content"
QUARTO_SELECTOR = "main.content"


def find_platform(start: Path) -> Path | None:
    """Walk up from `start` looking for a sibling checkout of the platform."""
    for parent in start.parents:
        candidate = parent / "PHYS-Undergraduate-Labs-Web"
        if candidate.is_dir():
            return candidate
    return None


def main() -> int:
    here = Path(__file__).resolve().parents[1] / "_extensions" / "physicslabs"
    platform = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else find_platform(here)
    if platform is None:
        print("no PHYS-Undergraduate-Labs-Web checkout found above this directory; pass its path")
        return 1
    src_dir = platform / "physicslabs" / "static" / "css"
    if not src_dir.is_dir():
        print(f"platform css directory not found: {src_dir}")
        return 1
    dst_dir = here / "css"
    dst_dir.mkdir(exist_ok=True)
    for name in FILES:
        text = (src_dir / name).read_text(encoding="utf-8")
        n = text.count(PLATFORM_SELECTOR)
        text = text.replace(PLATFORM_SELECTOR, QUARTO_SELECTOR)
        (dst_dir / name).write_text(text, encoding="utf-8", newline="\n")
        print(f"{name}: copied, {n} selector(s) retargeted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
