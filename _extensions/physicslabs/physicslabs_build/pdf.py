"""The PDF pipeline: Quarto to `.typ`, post-process, compile with standalone Typst.

    .qmd -> Quarto -> .typ (kept beside the page) -> filters -> Typst 0.14+ -> PDF/UA-1

Quarto's bundled Typst compiles too, and may fail (no PDF/UA-1 support, a
`#box` inside math, a percent-encoded image path); its exit code is ignored
because only the kept `.typ` files matter. What is not ignored is a page with
no `.typ`: Quarto aborts a project render on the first document it cannot
compile, and shipping a partial set of PDFs is worse than failing.

Each PDF is compiled straight to its final place, `_site/<page dir>/<name>.pdf`,
next to where the HTML render puts the page; the platform looks for it there
on the deploy branch. When both formats are built, `cli` stashes the PDFs
across the HTML render, which replaces `_site/`.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Callable, Iterable

from . import typ
from .site import Page, Site, project_files

DIAGNOSTIC_LINES = 30


def render_typ(quarto: Path, root: Path, verbose: bool) -> str:
    """Run `quarto render --to typst --profile typst`.

    Returns the tail of Quarto's stderr when it exited non-zero in non-verbose
    mode (in verbose mode the output streamed live), so the render-incomplete
    gate can show it beside the pages it cost.
    """
    print("  Step 1/3: Quarto render -> .typ intermediates")
    # The profile is always named. Quarto accepts one whose _quarto-typst.yml
    # does not exist; a repository with notebooks uses the file to keep them
    # out of the Typst pass.
    cmd = [str(quarto), "render", "--to", "typst", "--profile", "typst"]
    result = subprocess.run(cmd, cwd=root, capture_output=not verbose)
    diagnostic = ""
    if result.returncode != 0:
        print("  Note: Quarto's bundled Typst compile had errors (expected; we use standalone Typst 0.14+)")
        if not verbose and result.stderr:
            stderr_text = result.stderr.decode(errors="replace")
            lines = stderr_text.strip().split("\n")
            tail = lines[-DIAGNOSTIC_LINES:]
            if len(lines) > DIAGNOSTIC_LINES:
                print(f"  Diagnostic: Quarto stderr ({len(lines)} lines, showing last {DIAGNOSTIC_LINES}):")
            else:
                print(f"  Diagnostic: Quarto stderr ({len(lines)} lines):")
            for line in tail:
                print(f"    {line}")
            diagnostic = "\n".join(tail)
    return diagnostic


def kept_typ_files(root: Path) -> list[Path]:
    """The .typ files Quarto kept next to their sources.

    Skips .quarto/ (the Typst package cache: deleting its files makes the next
    render abort with "file not found" under .quarto/typst/packages),
    _extensions/ (the template partials) and _site/.
    """
    return project_files(root, "*.typ")


def remove_orphans(root: Path, site_dir: Path, typ_files: Iterable[Path], verbose: bool) -> list[Path]:
    """Drop kept .typ files that have no .qmd beside them, with their litter.

    A notebook rendered by the Typst pass leaves a .typ, possibly a PDF (beside
    the source and under _site/) and a `<stem>_files/` figure directory.
    Notebooks are served as downloads, not compiled to PDF. Returns the .typ
    files that do have a page.
    """
    kept: list[Path] = []
    for typ_file in typ_files:
        if typ_file.with_suffix(".qmd").exists():
            kept.append(typ_file)
            continue
        typ_file.unlink(missing_ok=True)
        typ_file.with_suffix(".pdf").unlink(missing_ok=True)
        site_pdf = site_dir / typ_file.relative_to(root).with_suffix(".pdf")
        site_pdf.unlink(missing_ok=True)
        for base_dir in (typ_file.parent, site_pdf.parent):
            figure_dir = base_dir / f"{typ_file.stem}_files"
            if figure_dir.is_dir():
                shutil.rmtree(figure_dir)
        if verbose:
            print(f"    Skipped orphan .typ (no .qmd source): {typ_file.name}")
    return kept


def check_complete(root: Path, typ_files: Iterable[Path], diagnostic: str = "") -> bool:
    """Fail loudly if any page has no .typ rather than shipping a partial set of PDFs."""
    produced = {f.with_suffix(".qmd") for f in typ_files}
    expected = project_files(root, "*.qmd")
    missing = [q for q in expected if q not in produced]
    if not missing:
        return True
    print(f"  ERROR: typst render incomplete: {len(missing)} page(s) have no .typ:")
    for q in missing:
        print(f"    {q.relative_to(root)}")
    print("  (Quarto likely aborted on a Typst compile error; check the render log above.)")
    if diagnostic:
        print("  Quarto's last output was:")
        for line in diagnostic.splitlines():
            print(f"    {line}")
    return False


def postprocess_files(root: Path, typ_files: Iterable[Path], filters: list, verbose: bool) -> None:
    """Run the filter chain over every kept .typ, in place."""
    typ_files = list(typ_files)
    print(f"  Step 2/3: Post-processing {len(typ_files)} .typ file(s) for accessibility")
    for typ_file in typ_files:
        page = Page(
            qmd=typ_file.with_suffix(".qmd"),
            typ=typ_file,
            rel=typ_file.relative_to(root).with_suffix(".qmd"),
            verbose=verbose,
        )
        content = typ_file.read_text(encoding="utf-8")
        content = typ.postprocess(content, page, filters)
        typ_file.write_text(content, encoding="utf-8", newline="\n")
        if verbose:
            print(f"    {typ_file.name}: post-processing complete")


def compile_pdfs(
    typst: Path,
    root: Path,
    site_dir: Path,
    fonts_dir: Path,
    typ_files: Iterable[Path],
    pdf_name: Callable[[Path], str],
    verbose: bool,
) -> list[str]:
    """Compile every kept .typ to PDF/UA-1 beside its page under _site/.

    Returns the PDFs that failed. Before each compile the PDF Quarto's bundled
    Typst wrote for the page (`_site/<rel>.pdf`) is removed, so a renamed
    target never sits beside a stale `index.pdf` (the platform's single-PDF
    fallback would then find two and give up). The kept .typ is deleted after
    the compile either way.
    """
    print("  Step 3/3: Compiling PDF/UA-1 with Typst")
    site_dir.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []

    for typ_file in typ_files:
        rel = typ_file.relative_to(root).with_suffix(".qmd")
        quarto_pdf = site_dir / rel.with_suffix(".pdf")
        pdf_path = site_dir / rel.parent / pdf_name(rel)
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        quarto_pdf.unlink(missing_ok=True)
        pdf_rel = pdf_path.relative_to(site_dir)

        cmd = [
            str(typst), "compile",
            "--font-path", str(fonts_dir),
            "--pdf-standard", "ua-1",
            str(typ_file),
            str(pdf_path),
        ]
        result = subprocess.run(
            cmd, cwd=root, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )

        if result.returncode != 0:
            print(f"    FAIL: {pdf_rel}")
            # Show errors (skip lines that are just font warnings)
            for line in result.stderr.strip().split("\n"):
                line = line.strip()
                if line and "warning:" not in line.lower():
                    print(f"      {line}")
            # Also show warnings summary
            warnings = [l for l in result.stderr.split("\n") if "warning:" in l.lower()]
            if warnings:
                print(f"      ({len(warnings)} warnings about missing fonts)")
            failures.append(str(pdf_rel))
        else:
            size_kb = pdf_path.stat().st_size / 1024
            print(f"    OK: {pdf_rel} ({size_kb:.0f} KB)")

        # Clean up intermediate .typ
        typ_file.unlink(missing_ok=True)

    return failures


def build_pdfs(site: Site, quarto: Path, typst: Path, verbose: bool) -> bool:
    """Render Quarto to .typ, post-process, compile to PDF/UA-1 under _site/."""
    print("Building accessible PDFs...")
    root, site_dir = site.root, site.site_dir

    diagnostic = render_typ(quarto, root, verbose)

    typ_files = kept_typ_files(root)
    print(f"  {len(typ_files)} .typ file(s) produced")
    if verbose:
        for tf in typ_files:
            print(f"    {tf.relative_to(root)} ({tf.stat().st_size:,} bytes)")

    typ_files = remove_orphans(root, site_dir, typ_files, verbose)

    # The gate runs before the empty check: zero .typ files with pages to
    # render is the most complete failure there is, not a warning.
    if not check_complete(root, typ_files, diagnostic):
        return False
    if not typ_files:
        print("  WARNING: No .typ files found to process.")
        return True

    postprocess_files(root, typ_files, typ.resolve_filters(site.typ_filters), verbose)

    failures = compile_pdfs(typst, root, site_dir, site.fonts_dir, typ_files, site.pdf_name, verbose)
    if failures:
        print(f"\n  {len(failures)} PDF(s) failed: {', '.join(failures)}")
        return False

    print("  PDFs written to _site/")
    return True
