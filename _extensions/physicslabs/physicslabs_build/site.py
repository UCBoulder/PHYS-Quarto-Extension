"""The project a wrapper describes (`Site`) and the object every source pass
edits through (`Workspace`).

`Workspace.write` records a file's bytes the first time the file is touched and
never again, so the earliest snapshot always wins and `restore()` returns the
working tree to its true pre-build state no matter how many passes edited the
same file. Writes go through `write_bytes`, which keeps CRLF files intact on
Windows (`write_text` turns CRLF into CRCRLF).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import naming

API_VERSION = 1

# Directories under the project root that never hold page sources or kept
# .typ output: Quarto's output, the installed extension (template partials),
# and Quarto's cache (the Typst package store). See docs/build-core.md,
# behavior 3.
EXCLUDED_DIRS = ("_site", "_extensions", ".quarto")


class BuildError(Exception):
    """A failure the build reports as one line and exits 1 on.

    Raised by source passes that must stop the build (an invalid notebook, a
    missing PyYAML with a `_variables.yml` present). `run()` prints the
    message, restores the sources unless `--ci`, and returns 1.
    """


@dataclass
class Page:
    """One page of the Typst pass, handed to every `.typ` filter."""

    qmd: Path       # the source file
    typ: Path       # the kept .typ Quarto wrote beside it
    rel: Path       # the .qmd path relative to the project root
    verbose: bool = False


def project_files(root: Path, pattern: str) -> list[Path]:
    """Every file matching `pattern` under `root`, excluding EXCLUDED_DIRS."""
    excluded = tuple(root / d for d in EXCLUDED_DIRS)
    return sorted(
        p for p in root.rglob(pattern)
        if p.is_file() and not any(p.is_relative_to(d) for d in excluded)
    )


class Workspace:
    """The working tree during a build: source access, snapshots, restore."""

    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.site_dir = self.root / "_site"
        self.originals: dict[Path, bytes] = {}
        self.date_deps: dict[Path, list[Path]] = {}

    def pages(self) -> list[Path]:
        """Every .qmd outside _site/, _extensions/ and .quarto/."""
        return project_files(self.root, "*.qmd")

    def notebooks(self) -> list[Path]:
        """Every .ipynb outside _site/, _extensions/ and .quarto/."""
        return project_files(self.root, "*.ipynb")

    def read(self, path: Path) -> str:
        return Path(path).read_bytes().decode("utf-8")

    def write(self, path: Path, content: str | bytes) -> None:
        """Write a source file, snapshotting its current bytes on first touch."""
        path = Path(path)
        if path not in self.originals:
            self.originals[path] = path.read_bytes()
        data = content.encode("utf-8") if isinstance(content, str) else content
        path.write_bytes(data)

    def add_date_dep(self, page: Path, *deps: Path) -> None:
        """Record files a page is assembled from; stamp_dates dates it by the newest."""
        entry = self.date_deps.setdefault(Path(page), [])
        for dep in deps:
            dep = Path(dep)
            if dep not in entry:
                entry.append(dep)

    def restore(self) -> None:
        """Put every touched file back to its pre-build bytes."""
        for path, content in self.originals.items():
            path.write_bytes(content)


# Hook types. A source pass edits sources through the workspace; a .typ filter
# maps the kept file's text to new text.
SourcePass = Callable[[Workspace, bool], None]
TypFilter = Callable[[str, Page], str]


@dataclass
class Site:
    """What a course's build.py tells the core about the project.

    root            the Quarto project directory (the one holding _quarto.yml)
    description     the argparse description
    source_passes   ordered passes run before the render; None means the core
                    default (validate_notebooks, resolve_variables, stamp_dates)
    typ_filters     .typ filters appended after the core chain; pass
                    typ.chain(before=..., after=...) for another order
    pdf_name        maps a page's project-relative .qmd path to its PDF filename
    course_data     regenerates _course-data.yml; enables --course-data
    require_api     the core API the wrapper was written against
    """

    root: Path
    description: str
    source_passes: list[SourcePass] | None = None
    typ_filters: list[TypFilter] | None = None
    pdf_name: Callable[[Path], str] = naming.page_stem
    course_data: Callable[[bool], None] | None = None
    require_api: int = API_VERSION
    extension_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent)

    def __post_init__(self) -> None:
        self.root = Path(self.root).resolve()

    @property
    def site_dir(self) -> Path:
        return self.root / "_site"

    @property
    def fonts_dir(self) -> Path:
        """Roboto ships with the extension; standalone Typst gets it as --font-path."""
        return self.extension_dir / "fonts"

    @property
    def course_data_file(self) -> Path:
        return self.root / "_course-data.yml"
