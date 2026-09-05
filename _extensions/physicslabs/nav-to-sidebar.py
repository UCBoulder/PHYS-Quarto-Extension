"""Quarto pre-render script: build a docked sidebar from the platform's _nav.yml.

The platform renders its course sidebar from `_nav.yml` (a tree of
`label` / `path` / `children` items). Quarto knows nothing about that file, so
this script translates it into `website.sidebar` configuration and writes
`_physicslabs-sidebar.yml`, which the extension lists under `metadata-files`.
Quarto recomputes project metadata after pre-render scripts run, so the
sidebar is current on every render, including the first.

Paths in `_nav.yml` are site-relative and extensionless (`docs/`,
`docs/build-and-deploy`). Each is resolved against the project directory to
`<path>/index.qmd` or `<path>.qmd` (also `.md`, `.ipynb`). Paths that resolve
to nothing are kept as written and reported, so a typo shows up in the render
log rather than silently vanishing.

The generated file is a build artifact; ignore it in version control.

Only `_nav.yml`'s documented shape is parsed (see the platform's
COURSE_SITE_NAVIGATION guide): sequences of mappings with `label`, `path`, and
optional nested `children`, plus comments and blank lines. No PyYAML needed.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

NAV_FILE = "_nav.yml"
OUT_FILE = "_physicslabs-sidebar.yml"
PAGE_SUFFIXES = (".qmd", ".md", ".ipynb")

_KEY_RE = re.compile(r"^(?P<indent>\s*)(?P<dash>-\s+)?(?P<key>[A-Za-z_][\w-]*):\s*(?P<value>.*)$")


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        inner = value[1:-1]
        return inner.replace('\\"', '"') if value[0] == '"' else inner
    return value


def parse_nav(text: str) -> list[dict]:
    """Parse the `nav:` tree. Returns a list of {label, path, children} dicts."""
    lines = []
    for raw in text.splitlines():
        stripped = raw.split("#", 1)[0] if not re.search(r"[\"'].*#.*[\"']", raw) else raw
        if stripped.strip():
            lines.append(stripped.rstrip())

    # Locate the top-level `nav:` key and take everything indented under it.
    try:
        start = next(i for i, l in enumerate(lines) if re.match(r"^nav:\s*$", l))
    except StopIteration:
        raise ValueError(f"{NAV_FILE}: no top-level 'nav:' key")

    root: list[dict] = []
    # Stack of (indent-of-dash, list-being-filled)
    stack: list[tuple[int, list[dict]]] = [(-1, root)]
    current: dict | None = None

    for line in lines[start + 1:]:
        m = _KEY_RE.match(line)
        if not m:
            raise ValueError(f"{NAV_FILE}: cannot parse line: {line!r}")
        indent = len(m.group("indent"))
        key, value = m.group("key"), m.group("value")

        if m.group("dash"):
            # New item. Pop back to the list whose dash indent matches; a deeper
            # dash is only valid right after a `children:` line.
            while len(stack) > 1 and indent < stack[-1][0]:
                stack.pop()
            if stack[-1][0] == -1:
                stack[-1] = (indent, root)
            elif indent > stack[-1][0]:
                if current is not None and "_pending_children" in current:
                    stack.append((indent, current.pop("_pending_children")))
                else:
                    raise ValueError(f"{NAV_FILE}: unexpected indentation (missing 'children:'?): {line!r}")
            current = {"label": None, "path": None, "children": []}
            stack[-1][1].append(current)
            if key == "children":
                raise ValueError(f"{NAV_FILE}: 'children' cannot start an item: {line!r}")
            current[key] = _unquote(value)
            continue

        if current is None:
            raise ValueError(f"{NAV_FILE}: key outside an item: {line!r}")
        if key == "children":
            current["_pending_children"] = current["children"]
        else:
            # Attribute lines belong to the most recent item at any level.
            current[key] = _unquote(value)

    def clean(items: list[dict]) -> list[dict]:
        out = []
        for it in items:
            it.pop("_pending_children", None)
            it["children"] = clean(it.get("children", []))
            out.append(it)
        return out

    return clean(root)


def resolve_href(path: str | None, project_dir: Path, missing: list[str]) -> str | None:
    if path is None:
        return None
    p = path.strip().strip("/")
    if p == "":
        return "index.qmd"
    # A page file wins even when a directory of the same name sits beside it
    # (PHYS-2150 has resources/instruments.qmd next to resources/instruments/).
    for suffix in PAGE_SUFFIXES:
        if (project_dir / f"{p}{suffix}").is_file():
            return f"{p}{suffix}"
    for suffix in PAGE_SUFFIXES:
        if (project_dir / p / f"index{suffix}").is_file():
            return f"{p}/index{suffix}"
    missing.append(path)
    return path if path.endswith("/") else f"{path}/"


def to_sidebar(items: list[dict], project_dir: Path, missing: list[str]) -> list[dict]:
    out = []
    for it in items:
        href = resolve_href(it.get("path"), project_dir, missing)
        label = it.get("label") or href or "(untitled)"
        if it.get("children"):
            entry = {"section": label, "contents": to_sidebar(it["children"], project_dir, missing)}
            if href:
                entry["href"] = href
        else:
            entry = {"text": label, "href": href}
        out.append(entry)
    return out


def _yaml_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def dump_contents(items: list[dict], indent: int) -> list[str]:
    pad = " " * indent
    lines = []
    for it in items:
        if "section" in it:
            lines.append(f"{pad}- section: {_yaml_str(it['section'])}")
            if it.get("href"):
                lines.append(f"{pad}  href: {_yaml_str(it['href'])}")
            lines.append(f"{pad}  contents:")
            lines.extend(dump_contents(it["contents"], indent + 4))
        else:
            lines.append(f"{pad}- text: {_yaml_str(it['text'])}")
            if it.get("href"):
                lines.append(f"{pad}  href: {_yaml_str(it['href'])}")
    return lines


def main() -> int:
    project_dir = Path(os.getcwd())
    nav_path = project_dir / NAV_FILE
    out_path = project_dir / OUT_FILE
    quiet = os.environ.get("QUARTO_PROJECT_SCRIPT_QUIET") == "1"

    if not nav_path.is_file():
        # No platform nav: leave Quarto without a sidebar, but keep the
        # metadata file present so `metadata-files` never dangles.
        out_path.write_text("# No _nav.yml in this project; no sidebar generated.\n", encoding="utf-8", newline="\n")
        return 0

    items = parse_nav(nav_path.read_text(encoding="utf-8"))
    missing: list[str] = []
    contents = to_sidebar(items, project_dir, missing)

    lines = [
        "# Generated by _extensions/physicslabs/nav-to-sidebar.py from _nav.yml on",
        "# every render. Do not edit; do not commit.",
        "website:",
        "  sidebar:",
        "    style: docked",
        "    search: false",
        "    collapse-level: 1",
        "    contents:",
    ]
    lines.extend(dump_contents(contents, 6))
    text = "\n".join(lines) + "\n"

    # Write only on change. `quarto preview` watches metadata files, and
    # touching this one on every render made it reload the current page
    # whenever a link to a not-yet-rendered page was followed.
    changed = not out_path.is_file() or out_path.read_text(encoding="utf-8") != text
    if changed:
        out_path.write_text(text, encoding="utf-8", newline="\n")

    if not quiet:
        n = sum(1 + len(i["children"]) for i in items)
        state = "updated" if changed else "unchanged"
        print(f"physicslabs: sidebar from {NAV_FILE} ({n} entries, {state})", file=sys.stderr)
        for p in missing:
            print(f"physicslabs: {NAV_FILE} path not found in project: {p}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
