"""Source passes and the workspace they edit through."""

import datetime
import json
from pathlib import Path

import pytest

from physicslabs_build import BuildError, Workspace, sources

# The fixture's own frontmatter (guide/elements.qmd).
FRONTMATTER_NO_DATE = '---\ntitle: "Content Elements"\npdf-download: true\n---\n\n## Callouts\n'
FRONTMATTER_WITH_DATE = '---\ntitle: "Content Elements"\ndate: "January 1, 2020"\npdf-download: true\n---\n\nBody.\n'
FRONTMATTER_DATE_FALSE = '---\ntitle: "Content Elements"\ndate: false\n---\n\nBody.\n'


def notebook(first_cell_type: str = "raw", source: str = '---\ntitle: "A notebook"\n---\n') -> str:
    return json.dumps({
        "cells": [
            {"cell_type": first_cell_type, "metadata": {}, "source": source.splitlines(keepends=True)},
            {"cell_type": "code", "metadata": {}, "source": ["print(1)\n"], "outputs": [], "execution_count": None},
        ],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 5,
    }, indent=1) + "\n"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / "_quarto.yml").write_text("project:\n  type: physicslabs\n", encoding="utf-8")
    (tmp_path / "index.qmd").write_text(FRONTMATTER_NO_DATE, encoding="utf-8")
    (tmp_path / "guide").mkdir()
    (tmp_path / "guide" / "elements.qmd").write_text(FRONTMATTER_WITH_DATE, encoding="utf-8")
    # Files the census must never touch.
    (tmp_path / "_site").mkdir()
    (tmp_path / "_site" / "index.qmd").write_text(FRONTMATTER_NO_DATE, encoding="utf-8")
    (tmp_path / "_extensions" / "physicslabs").mkdir(parents=True)
    (tmp_path / "_extensions" / "physicslabs" / "x.qmd").write_text("---\ntitle: x\n---\n", encoding="utf-8")
    (tmp_path / ".quarto").mkdir()
    (tmp_path / ".quarto" / "y.qmd").write_text("---\ntitle: y\n---\n", encoding="utf-8")
    return tmp_path


@pytest.fixture(autouse=True)
def fixed_git_date(monkeypatch):
    sources.clear_date_cache()
    monkeypatch.setattr(sources, "commit_date", lambda path, root: datetime.date(2026, 3, 3))
    yield
    sources.clear_date_cache()


# ---------------------------------------------------------------------------
# Workspace
# ---------------------------------------------------------------------------


def test_workspace_lists_pages_outside_output_extension_and_cache(project: Path):
    ws = Workspace(project)
    assert [p.relative_to(project).as_posix() for p in ws.pages()] == ["guide/elements.qmd", "index.qmd"]


def test_workspace_keeps_the_first_snapshot_when_a_file_is_written_twice(project: Path):
    ws = Workspace(project)
    page = project / "index.qmd"
    original = page.read_bytes()

    ws.write(page, "first edit\n")
    ws.write(page, "second edit\n")
    assert page.read_text(encoding="utf-8") == "second edit\n"
    assert ws.originals[page] == original

    ws.restore()
    assert page.read_bytes() == original


def test_workspace_write_preserves_crlf_bytes(project: Path):
    ws = Workspace(project)
    page = project / "crlf.qmd"
    page.write_bytes(b"---\r\ntitle: x\r\n---\r\n")
    ws.write(page, "---\r\ntitle: y\r\n---\r\n")
    assert page.read_bytes() == b"---\r\ntitle: y\r\n---\r\n"
    ws.restore()
    assert page.read_bytes() == b"---\r\ntitle: x\r\n---\r\n"


def test_add_date_dep_records_each_dependency_once(project: Path):
    ws = Workspace(project)
    page = project / "index.qmd"
    dep = project / "_weekly" / "week-1.md"
    ws.add_date_dep(page, dep)
    ws.add_date_dep(page, dep, project / "other.md")
    assert ws.date_deps[page] == [dep, project / "other.md"]


# ---------------------------------------------------------------------------
# stamp_dates
# ---------------------------------------------------------------------------


def test_stamp_dates_appends_a_quoted_date_line(project: Path, capsys):
    ws = Workspace(project)
    sources.stamp_dates(ws)
    text = (project / "index.qmd").read_text(encoding="utf-8")
    assert text.startswith('---\ntitle: "Content Elements"\npdf-download: true\ndate: "March 3, 2026"\n---\n')
    assert "Stamped dates (from git history) on 2 file(s)" in capsys.readouterr().out


def test_stamp_dates_replaces_an_existing_date_line(project: Path):
    ws = Workspace(project)
    sources.stamp_dates(ws)
    text = (project / "guide" / "elements.qmd").read_text(encoding="utf-8")
    assert 'date: "March 3, 2026"' in text
    assert "January 1, 2020" not in text


def test_stamp_dates_honours_date_false(project: Path):
    page = project / "guide" / "elements.qmd"
    page.write_text(FRONTMATTER_DATE_FALSE, encoding="utf-8")
    ws = Workspace(project)
    sources.stamp_dates(ws)
    assert page.read_text(encoding="utf-8") == FRONTMATTER_DATE_FALSE
    assert page not in ws.originals


def test_stamp_dates_uses_the_newest_dependency(project: Path, monkeypatch):
    dates = {"index.qmd": datetime.date(2026, 1, 5), "week-1.md": datetime.date(2026, 4, 20)}
    monkeypatch.setattr(sources, "commit_date", lambda path, root: dates.get(Path(path).name))
    ws = Workspace(project)
    ws.add_date_dep(project / "index.qmd", project / "week-1.md")
    sources.stamp_dates(ws)
    assert 'date: "April 20, 2026"' in (project / "index.qmd").read_text(encoding="utf-8")


def test_stamp_dates_writes_the_first_raw_cell_of_a_notebook_quoted(project: Path):
    nb_path = project / "guide" / "analysis.ipynb"
    nb_path.write_text(notebook(), encoding="utf-8")
    ws = Workspace(project)
    sources.stamp_dates(ws)
    nb = json.loads(nb_path.read_text(encoding="utf-8"))
    assert "".join(nb["cells"][0]["source"]) == '---\ntitle: "A notebook"\ndate: "March 3, 2026"\n---\n'
    ws.restore()
    assert nb_path.read_text(encoding="utf-8") == notebook()


def test_restore_returns_every_stamped_file(project: Path):
    before = {p: p.read_bytes() for p in (project / "index.qmd", project / "guide" / "elements.qmd")}
    ws = Workspace(project)
    sources.stamp_dates(ws)
    assert all(p.read_bytes() != b for p, b in before.items())
    ws.restore()
    assert all(p.read_bytes() == b for p, b in before.items())


# ---------------------------------------------------------------------------
# validate_notebooks
# ---------------------------------------------------------------------------


def test_validate_notebooks_accepts_a_titled_raw_first_cell(project: Path, capsys):
    (project / "ok.ipynb").write_text(notebook(), encoding="utf-8")
    sources.validate_notebooks(Workspace(project), verbose=True)
    assert "Validated 1 notebook(s)" in capsys.readouterr().out


def test_validate_notebooks_fails_when_the_first_cell_is_not_raw(project: Path, capsys):
    (project / "bad.ipynb").write_text(notebook(first_cell_type="markdown"), encoding="utf-8")
    with pytest.raises(BuildError):
        sources.validate_notebooks(Workspace(project))
    assert "bad.ipynb: first cell must be raw (found markdown)" in capsys.readouterr().out


def test_validate_notebooks_fails_on_invalid_json(project: Path, capsys):
    (project / "broken.ipynb").write_text("{not json", encoding="utf-8")
    with pytest.raises(BuildError):
        sources.validate_notebooks(Workspace(project))
    assert "broken.ipynb: not valid JSON" in capsys.readouterr().out


def test_validate_notebooks_fails_without_a_title(project: Path, capsys):
    (project / "untitled.ipynb").write_text(notebook(source="---\nauthor: x\n---\n"), encoding="utf-8")
    with pytest.raises(BuildError):
        sources.validate_notebooks(Workspace(project))
    assert "frontmatter must include a title" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Shortcodes and variables
# ---------------------------------------------------------------------------


def test_substitute_shortcodes_resolves_bare_and_quoted_keys(project: Path):
    page = project / "index.qmd"
    page.write_text('See {{< var python.daq >}} and {{< syllabus "Late work" >}} and {{< var missing >}}.\n', encoding="utf-8")
    ws = Workspace(project)
    values = {"python.daq": "https://example.org/daq"}
    changed, unresolved = sources.substitute_shortcodes(ws, "var", lambda key, p: values.get(key))
    assert (changed, unresolved) == (1, ["missing"])
    changed, unresolved = sources.substitute_shortcodes(ws, "syllabus", lambda key, p: f"[{key}]")
    assert (changed, unresolved) == (1, [])
    assert page.read_text(encoding="utf-8") == "See https://example.org/daq and [Late work] and {{< var missing >}}.\n"


def test_resolve_variables_reads_variables_yml(project: Path, capsys):
    (project / "_variables.yml").write_text("python:\n  daq: https://example.org/daq\n", encoding="utf-8")
    (project / "index.qmd").write_text("Go to {{< var python.daq >}} and {{< var nope >}}.\n", encoding="utf-8")
    sources.resolve_variables(Workspace(project))
    out = capsys.readouterr().out
    assert (project / "index.qmd").read_text(encoding="utf-8") == "Go to https://example.org/daq and {{< var nope >}}.\n"
    assert "no value in _variables.yml for: nope" in out
    assert "Resolved variables in 1 file(s)" in out


def test_resolve_variables_is_a_no_op_without_the_file(project: Path):
    ws = Workspace(project)
    sources.resolve_variables(ws)
    assert ws.originals == {}


def test_resolve_variables_fails_the_build_without_pyyaml(project: Path, monkeypatch):
    (project / "_variables.yml").write_text("a: 1\n", encoding="utf-8")

    def no_yaml():
        raise ImportError("No module named 'yaml'")

    monkeypatch.setattr(sources, "_import_yaml", no_yaml)
    with pytest.raises(BuildError, match="PyYAML is required to read _variables.yml"):
        sources.resolve_variables(Workspace(project))


def test_set_frontmatter_line_replaces_or_appends():
    assert sources.set_frontmatter_line('title: x\ndate: "old"\n', sources.DATE_LINE_RE, 'date: "new"') == 'title: x\ndate: "new"\n'
    assert sources.set_frontmatter_line("title: x\n", sources.DATE_LINE_RE, 'date: "new"') == 'title: x\ndate: "new"\n'


def test_format_date_has_no_zero_padded_day():
    assert sources.format_date(datetime.date(2026, 3, 3)) == "March 3, 2026"
    assert sources.format_date(datetime.date(2026, 11, 23)) == "November 23, 2026"
