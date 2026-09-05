"""The parts of the PDF pipeline that need neither Quarto nor Typst."""

from pathlib import Path

import pytest

from physicslabs_build import pdf


@pytest.fixture
def rendered(tmp_path: Path) -> Path:
    """A project after `quarto render --to typst`: kept .typ files beside pages,
    a notebook's orphan output, the package cache and the template partials."""
    for rel in ("index.qmd", "guide/index.qmd", "guide/elements.qmd"):
        page = tmp_path / rel
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text("---\ntitle: x\n---\n", encoding="utf-8")
        page.with_suffix(".typ").write_text("= x\n", encoding="utf-8")
    # A notebook rendered by the Typst pass: .typ, stray PDFs, figure directory.
    nb = tmp_path / "guide" / "analysis"
    nb.with_suffix(".ipynb").write_text("{}", encoding="utf-8")
    nb.with_suffix(".typ").write_text("= nb\n", encoding="utf-8")
    nb.with_suffix(".pdf").write_bytes(b"%PDF")
    (tmp_path / "guide" / "analysis_files" / "figure-typst").mkdir(parents=True)
    site_nb = tmp_path / "_site" / "guide" / "analysis"
    site_nb.parent.mkdir(parents=True)
    site_nb.with_suffix(".pdf").write_bytes(b"%PDF")
    # Never page output.
    for rel in (".quarto/typst/packages/preview/fontawesome/0.5.0/lib.typ",
                "_extensions/physicslabs/typst/typst-template.typ",
                "_extensions/physicslabs/typst/typst-show.typ",
                "_site/index.typ"):
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("// not a page\n", encoding="utf-8")
    return tmp_path


def rel(root: Path, paths) -> list[str]:
    return sorted(p.relative_to(root).as_posix() for p in paths)


def test_kept_typ_files_skips_cache_extension_and_output(rendered: Path):
    assert rel(rendered, pdf.kept_typ_files(rendered)) == [
        "guide/analysis.typ", "guide/elements.typ", "guide/index.typ", "index.typ",
    ]


def test_remove_orphans_deletes_notebook_litter_and_keeps_pages(rendered: Path, capsys):
    kept = pdf.remove_orphans(rendered, rendered / "_site", pdf.kept_typ_files(rendered), verbose=True)
    assert rel(rendered, kept) == ["guide/elements.typ", "guide/index.typ", "index.typ"]
    assert not (rendered / "guide" / "analysis.typ").exists()
    assert not (rendered / "guide" / "analysis.pdf").exists()
    assert not (rendered / "_site" / "guide" / "analysis.pdf").exists()
    assert not (rendered / "guide" / "analysis_files").exists()
    # The package cache is untouched: deleting it breaks the next render.
    assert (rendered / ".quarto/typst/packages/preview/fontawesome/0.5.0/lib.typ").exists()
    assert "Skipped orphan .typ (no .qmd source): analysis.typ" in capsys.readouterr().out


def test_gate_passes_when_every_page_has_a_typ(rendered: Path):
    kept = pdf.remove_orphans(rendered, rendered / "_site", pdf.kept_typ_files(rendered), verbose=False)
    assert pdf.check_complete(rendered, kept)


def test_gate_names_the_pages_without_a_typ_and_shows_quartos_output(rendered: Path, capsys):
    (rendered / "guide" / "index.typ").unlink()
    kept = pdf.remove_orphans(rendered, rendered / "_site", pdf.kept_typ_files(rendered), verbose=False)
    assert not pdf.check_complete(rendered, kept, diagnostic="error: file not found\nERROR: Typst compilation failed")
    out = capsys.readouterr().out
    assert "1 page(s) have no .typ" in out
    assert "guide/index.qmd" in out.replace("\\", "/")
    assert "ERROR: Typst compilation failed" in out


def test_gate_fails_when_quarto_produced_nothing(rendered: Path):
    for t in pdf.kept_typ_files(rendered):
        t.unlink()
    assert not pdf.check_complete(rendered, [])
