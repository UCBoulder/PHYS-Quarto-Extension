"""PDF filename schemes.

A scheme maps a page's project-relative `.qmd` path to the name of the PDF
written beside it under `_site/`. The platform finds a page's PDF by exact
name first and, for an `index` page, by the single PDF in its directory, so a
renamed `index.pdf` still resolves as long as it is alone in the directory.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable


def page_stem(rel: Path) -> str:
    """The default: `index.qmd` gives `index.pdf`, `setup.qmd` gives `setup.pdf`."""
    return Path(rel).with_suffix(".pdf").name


def prefixed(course: str) -> Callable[[Path], str]:
    """PHYS-4430's scheme: `index.pdf` becomes `<course>-<path>.pdf`.

    The name is built from every path segment below the top-level category
    directory, not just the immediate parent: multi-part guides keep their
    pages a level deeper (`lab-guides/gaussian-beams/week-1/`), and naming
    from the parent alone gave every guide the same `week-1` download.
    `lab-guides/zeeman-effect/index.qmd` gives `<course>-zeeman-effect.pdf`,
    `lab-guides/gaussian-beams/week-1/index.qmd` gives
    `<course>-gaussian-beams-week-1.pdf`, a top-level `index.qmd` gives
    `<course>.pdf`, and pages that are not `index.qmd` keep their stem.
    """

    def name(rel: Path) -> str:
        rel = Path(rel)
        if rel.name != "index.qmd":
            return page_stem(rel)
        parts = rel.parent.parts
        if not parts:
            return f"{course}.pdf"
        segments = parts[1:] or parts
        return f"{course}-{'-'.join(segments)}.pdf"

    return name
