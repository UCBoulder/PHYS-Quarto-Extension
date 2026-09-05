"""Source passes: the edits made to `.qmd` and `.ipynb` files before the render.

Every pass has the signature `(ws: Workspace, verbose: bool) -> None`, edits
files only through `ws.write` (so they are restored after a local build and
kept with `--ci`), prints one summary line when it changed something, and
raises `BuildError` to stop the build.

The platform renders the deployed `.qmd` with Pandoc, which knows nothing of
Quarto shortcodes or git history, so anything derived at build time has to be
written into the sources: the last-commit date each page shows, the values
behind `{{< var >}}` shortcodes, and whatever a course adds on
`substitute_shortcodes`.
"""

from __future__ import annotations

import datetime
import json
import platform
import re
import subprocess
from pathlib import Path
from typing import Any, Callable, Iterable

from .site import BuildError, SourcePass, Workspace

# The YAML block at the top of a page, and the `date:` line inside it.
FRONTMATTER_RE = re.compile(
    r"^(---\s*\n)(.*?)(^---\s*$)", re.MULTILINE | re.DOTALL
)
DATE_LINE_RE = re.compile(r"^date:.*$", re.MULTILINE)


def set_frontmatter_line(frontmatter: str, line_re: re.Pattern, line: str) -> str:
    """Replace the line `line_re` matches in a frontmatter block, or append `line`."""
    if line_re.search(frontmatter):
        return line_re.sub(lambda m: line, frontmatter)
    return frontmatter.rstrip("\n") + f"\n{line}\n"


# ---------------------------------------------------------------------------
# YAML
# ---------------------------------------------------------------------------


def _import_yaml():
    import yaml  # noqa: PLC0415
    return yaml


def load_yaml(path: Path, needed_for: str) -> Any:
    """Parse a YAML file, failing the build when PyYAML is missing.

    The old scripts warned and skipped, and the failure mode was silent:
    literal `{{< var >}}` text shipped to students. A missing dependency is a
    build error.
    """
    try:
        yaml = _import_yaml()
    except ImportError:
        raise BuildError(
            f"PyYAML is required to read {path.name} ({needed_for}). "
            "Install it with: python -m pip install pyyaml"
        ) from None
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def lookup(data: dict, dotted: str) -> Any:
    """Resolve a dotted key like 'python.daq' against nested dicts."""
    node = data
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


# ---------------------------------------------------------------------------
# Shortcode substitution
# ---------------------------------------------------------------------------


def shortcode_re(name: str) -> re.Pattern:
    """`{{< name key >}}` with a bare (`[\\w.-]+`) or double-quoted key."""
    return re.compile(
        r"\{\{<\s*" + re.escape(name) + r"\s+(?:\"([^\"]+)\"|([\w.-]+))\s*>\}\}"
    )


def substitute_shortcodes(
    ws: Workspace,
    name: str,
    resolver: Callable[[str, Path], Any],
    verbose: bool = False,
) -> tuple[int, list[str]]:
    """Replace `{{< name key >}}` in every page with `resolver(key, page)`.

    A resolver returning None leaves the shortcode in place so a typo shows up
    in the output rather than silently vanishing. Returns the number of files
    changed and the keys left unresolved; the calling pass prints its own
    summary.
    """
    pattern = shortcode_re(name)
    changed = 0
    unresolved: list[str] = []

    for qmd in ws.pages():
        text = ws.read(qmd)
        if not pattern.search(text):
            continue

        def _sub(match: re.Match) -> str:
            key = match.group(1) if match.group(1) is not None else match.group(2)
            value = resolver(key, qmd)
            if value is None:
                if key not in unresolved:
                    unresolved.append(key)
                return match.group(0)
            return str(value)

        new_text = pattern.sub(_sub, text)
        if new_text != text:
            ws.write(qmd, new_text)
            changed += 1

    return changed, unresolved


def resolve_variables(ws: Workspace, verbose: bool = False) -> None:
    """Replace ``{{< var key >}}`` shortcodes with values from _variables.yml.

    Quarto resolves these natively during `quarto preview`, but the Physics Labs
    platform renders the deployed .qmd with Pandoc, which has no notion of Quarto
    shortcodes: an unresolved shortcode would render as literal text on the live
    site. Resolving here means the deploy branch carries real URLs.
    """
    variables_file = ws.root / "_variables.yml"
    if not variables_file.exists():
        return

    data = load_yaml(variables_file, "to resolve {{< var >}} shortcodes")
    changed, unresolved = substitute_shortcodes(
        ws, "var", lambda key, page: lookup(data, key), verbose
    )

    if unresolved:
        print(f"  Warning: no value in {variables_file.name} for: "
              + ", ".join(sorted(unresolved)))
    if verbose or changed:
        print(f"  Resolved variables in {changed} file(s)")


# ---------------------------------------------------------------------------
# Notebooks
# ---------------------------------------------------------------------------


def validate_notebooks(ws: Workspace, verbose: bool = False) -> None:
    """Every .ipynb must open with a raw cell holding YAML frontmatter and a title.

    stamp_dates() writes the build date into that first raw cell, and the
    platform reads the title from it. A notebook without one deploys as an
    untitled page with no date, so fail the build instead.
    """
    notebooks = ws.notebooks()
    if not notebooks:
        return

    errors = []
    for nb_path in notebooks:
        rel = nb_path.relative_to(ws.root)
        try:
            cells = json.loads(nb_path.read_bytes()).get("cells", [])
        except json.JSONDecodeError as exc:
            errors.append(f"  {rel}: not valid JSON ({exc})")
            continue

        if not cells:
            errors.append(f"  {rel}: no cells found")
            continue

        first = cells[0]
        if first.get("cell_type") != "raw":
            errors.append(
                f"  {rel}: first cell must be raw (found {first.get('cell_type')})"
            )
            continue

        src = "".join(first.get("source", []))
        fm = FRONTMATTER_RE.search(src)
        if not fm:
            errors.append(f"  {rel}: first raw cell needs YAML frontmatter (---)")
            continue

        if not re.search(r"^title:", fm.group(2), re.MULTILINE):
            errors.append(f"  {rel}: frontmatter must include a title")

    if errors:
        print(f"ERROR: {len(errors)} notebook(s) failed validation:")
        for e in errors:
            print(e)
        raise BuildError(f"{len(errors)} notebook(s) failed validation")

    if verbose:
        print(f"  Validated {len(notebooks)} notebook(s)")


# ---------------------------------------------------------------------------
# Dates from git history
# ---------------------------------------------------------------------------

_COMMIT_DATE_CACHE: dict[Path, datetime.date | None] = {}


def commit_date(path: Path, root: Path) -> datetime.date | None:
    """Last commit date for one path, or None if git can't tell us."""
    path = Path(path)
    if path not in _COMMIT_DATE_CACHE:
        _COMMIT_DATE_CACHE[path] = None
        try:
            result = subprocess.run(
                ["git", "log", "-1", "--format=%ai", "--", str(path)],
                capture_output=True, text=True, cwd=root,
            )
            if result.returncode == 0 and result.stdout.strip():
                # Parse "2026-03-31 12:00:08 -0600" into a date
                iso = result.stdout.strip().split()[0]
                _COMMIT_DATE_CACHE[path] = datetime.date.fromisoformat(iso)
        except FileNotFoundError:
            pass  # git unavailable
    return _COMMIT_DATE_CACHE[path]


def clear_date_cache() -> None:
    _COMMIT_DATE_CACHE.clear()


def format_date(d: datetime.date) -> str:
    """Format as 'Month Day, Year' with no zero-padded day."""
    if platform.system() == "Windows":
        return d.strftime("%B %d, %Y").replace(" 0", " ")
    return d.strftime("%B %-d, %Y")


def git_date(path: Path, root: Path, deps: Iterable[Path] = ()) -> str:
    """Date to stamp on a page: newest commit date across it and its sources.

    A page assembled at build time is only as fresh as what it is assembled
    from, so an edit to an inlined partial or a rubric YAML has to move the
    page's date. The file's own history alone reports the instructor guide as
    untouched for a whole semester of weekly-partial edits.
    """
    dates = [d for d in (commit_date(p, root) for p in (path, *deps)) if d]
    # Fallback to today if git is unavailable
    return format_date(max(dates) if dates else datetime.date.today())


def stamp_dates(ws: Workspace, verbose: bool = False) -> None:
    """Stamp each file's last-modified date from git history.

    Stamps the `date:` frontmatter field of every .qmd, except those whose
    frontmatter contains `date: false` (which suppresses the date), and the
    first raw cell of every .ipynb. Dependencies registered with
    `ws.add_date_dep` count toward a page's date.
    """
    stamped = 0

    # QMD files: all except those with date: false
    for qmd in ws.pages():
        text = ws.read(qmd)
        m = FRONTMATTER_RE.search(text)
        if not m:
            continue
        frontmatter = m.group(2)
        if "date: false" in frontmatter:
            continue
        file_date = git_date(qmd, ws.root, ws.date_deps.get(qmd, ()))
        new_fm = set_frontmatter_line(frontmatter, DATE_LINE_RE, f'date: "{file_date}"')
        if new_fm != frontmatter:
            ws.write(qmd, text[:m.start(2)] + new_fm + text[m.end(2):])
            stamped += 1

    # Notebooks: stamp date in the first raw cell's YAML frontmatter
    for nb_path in ws.notebooks():
        nb = json.loads(nb_path.read_bytes())
        changed = False
        for cell in nb.get("cells", []):
            if cell.get("cell_type") != "raw":
                continue
            src = "".join(cell["source"])
            m = FRONTMATTER_RE.search(src)
            if not m:
                continue
            fm = m.group(2)
            file_date = git_date(nb_path, ws.root, ws.date_deps.get(nb_path, ()))
            new_fm = set_frontmatter_line(fm, DATE_LINE_RE, f'date: "{file_date}"')
            if new_fm != fm:
                new_src = src[:m.start(2)] + new_fm + src[m.end(2):]
                cell["source"] = new_src.splitlines(keepends=True)
                if cell["source"] and not cell["source"][-1].endswith("\n"):
                    cell["source"][-1] += "\n"
                changed = True
            break  # only process the first raw cell
        if changed:
            ws.write(nb_path, json.dumps(nb, indent=1, ensure_ascii=False) + "\n")
            stamped += 1

    if verbose or stamped:
        print(f"  Stamped dates (from git history) on {stamped} file(s)")


# The passes a Site runs when it lists none of its own. Each is a no-op when
# its input is absent.
DEFAULT_PASSES: list[SourcePass] = [validate_notebooks, resolve_variables, stamp_dates]
