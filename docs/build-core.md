# The shared build core

Design for moving the six course sites' `site/build.py` pipelines into one
Python package that ships inside this extension. Phase 1: study, decide,
document. Nothing here is implemented yet, and no course repository changes
until the core exists and the fixture CI exercises it.

Studied: `site/build.py`, `_quarto.yml`, `_quarto-typst.yml`, both workflows
and the build docs in PHYS-4700, PHYS-2150, PHYS-1140, PHYS-3330, PHYS-4430 and
PHYS-Python-Resources (all on extension v0.2.1); the platform's PDF lookup in
PHYS-Undergraduate-Labs-Web; and three experiments run locally against Quarto
1.9.37 and Typst 0.14.2, cited where they decide something.

## The decision

**The core is a Python package inside the extension, and each course's
`build.py` becomes a thin wrapper that imports it and registers its own
hooks.** The study supports this shape; the alternatives are weaker:

- *A package on PyPI or installed from git.* A second install and upgrade
  path next to `quarto add`, a `pip install` in every workflow and on every
  author's machine, and the post-processor can drift from the Typst template
  it depends on. The `add_math_alt_text` preamble split keys on the
  `doc,\n)\n` line that `typst/typst-show.typ` emits; the fontawesome strip
  keys on what Quarto's callouts emit for this template. Those belong in one
  versioned unit.
- *A git submodule.* Every clone needs `--recurse-submodules`, and the
  Windows-side friction is real for the authors who run `quarto preview`.
- *Keep copying, add a sync script.* This is what exists today, de facto,
  and it is how six scripts forked into six `build_pdfs` and four
  `stamp_dates`.
- *A Quarto `post-render` script in the extension.* Attractive for the PDF
  step alone (Quarto hands post-render scripts the output list), but the
  pipeline also edits sources before the render and restores them after,
  with `--ci` deciding whether to restore. That orchestration has no home in
  a post-render hook. Worth revisiting if source stamping ever moves to the
  platform; see the open questions.

Two facts make the in-extension shape safe:

- `quarto add` copies the whole extension directory, including a Python
  package. Verified with a local copy of this extension carrying
  `build/__init__.py`, `build/pdf.py` and `build/_internal/__init__.py`:
  `quarto add <path>` installed all three. The installed file list of
  PHYS-4700's `_extensions/UCBoulder/physicslabs/` is identical to this
  repository's `_extensions/physicslabs/`.
- The extension already ships a Python script that course sites execute on
  every render (`nav-to-sidebar.py`), so "Python inside `_extensions/`" is
  not new.

One deviation from the brief: the package directory is
`_extensions/physicslabs/physicslabs_build/`, not `.../build/`. The wrapper
that imports it is itself named `build.py`, so `import build` inside
`build.py` resolves to the wrapper in Pylance and in any tooling where the
site directory precedes the extension on `sys.path`, and PyPA's `build`
package is installed on many developer machines. At runtime the import would
work because the wrapper puts the extension first on `sys.path`, but the
name buys confusion for nothing. The location is otherwise as proposed.

Runtime floor: Python 3.10 (the existing scripts already use `X | None`
annotations at definition time), Quarto 1.9, Typst 0.14. PyYAML is required
by any source pass that reads YAML; see behavior 8 below.

## 1. The shared functions

Function bodies were extracted with `ast` from all six scripts and grouped
by identical source. Ten of the seventeen are byte-identical across all six;
seven differ. `restore_dates` (five repos) and `restore_sources` (PHYS-4700)
are the same function under two names, so it is listed as an eighteenth row.
"Best" means the variant the core keeps, or what replaces it.

| Function | Variants | Keep | Why | Status |
| --- | --- | --- | --- | --- |
| `find_quarto` | identical ×6 | as is | PATH first, then the usual install paths. | generic |
| `find_typst` | identical ×6 | as is | PATH first, then winget, scoop, cargo, Homebrew paths. | generic |
| `check_typst_version` | identical ×6 | as is, but compare a parsed `(major, minor)` tuple | Every script compares strings: `"0.9" < "0.14"` is `False`, so a hypothetical 0.9 would pass. Harmless today, wrong in principle. | generic |
| `_protect_code_spans` | 3: base (4700, 2150, 4430, Py); 1140 adds `#XxxTok(...)` guards; 3330 adds `#Skylighting((...));` guards | union of all three | With the extension's `syntax-highlighting: idiomatic`, Quarto emits fenced raw blocks in the `.typ` (the fixture's `elements.typ` has a ```` ```python ```` block and no `Tok` or `Skylighting` calls), which the base regex protects. The two extra guards are no-ops on that output and matter only if a page or Quarto version falls back to Skylighting; a `$` that escapes protection becomes an inline equation and the compile fails. Union costs nothing. | generic |
| `_restore_code_spans` | identical ×6 | as is | | generic |
| `_generate_alt_text` | identical ×6 | as is | Crude (`x^2` becomes "x superscript 2", `frac(...)` is left alone) but it is what every PDF ships with today. Improving it is a separate change. | generic |
| `_process_quarto_block_math` | 3: 4700/2150/Py; 3330/4430; 1140. Differ only in the numbering-token regex (`[\w-]+` vs `[a-zA-Z_][a-zA-Z0-9_-]*`) and a comment | 4700/2150/Py | Same behavior; this one carries the docstring explaining why the bare `equation-numbering` identifier must match (labeled equations use it, and a miss leaves the outer block without alt text). | generic |
| `_process_standalone_block_math` | 2: 1140 adds `re.DOTALL`; the other five do not | 1140 | With `--pdf-standard ua-1`, Typst 0.14.2 refuses to compile any equation that lacks alt text (verified: `$ a &= b + c \ &= d $` fails with "PDF/UA-1 error: missing alt text"). Without `DOTALL` a display equation that spans lines gets no alt text and the page's PDF fails. The non-greedy match still stops at the first line that ends with a space and a dollar sign. | generic |
| `_process_inline_math` | identical ×6 | as is | | generic |
| `strip_fontawesome` | identical ×6 | as is | Coupled to Quarto's callout output for this template; one reason the core belongs with the template. | generic |
| `_extract_image_alt_texts` | 2: 3330/4430/Py `unquote()` the filename; 4700/2150/1140 do not | 3330/4430/Py | Superset. Quarto percent-encodes image paths, so `beam profile.png` in the `.qmd` must match `beam%20profile.png` in the `.typ`. Pairs with `decode_image_paths`. | generic |
| `add_image_alt_text` | identical ×6 | as is | Keyed by basename; two images with the same basename on one page share the last alt text. Note it, do not fix it here. | generic |
| `add_math_alt_text` | identical ×6 | as is | Splits preamble from body at the `doc,\n)\n` line of `typst-show.typ`. | generic |
| `build_html` | identical ×6 | as is | | generic |
| `build_pdfs` | 6, in two families. A (4700, 2150, Py): `--profile typst`, a stderr diagnostic when Quarto exits non-zero, a `.typ` census, `.quarto/` and `_extensions/` excluded by path, orphan cleanup, the render-incomplete gate. B (1140, 3330, 4430): no profile, a one-line "Note" on failure, `.quarto` excluded by path part and `_extensions` only by the two partial filenames, per-course `index.pdf` renames, extra `.typ` filters. 2150 also warns about missing `labs/*/lab-guide.typ`. | rebuilt from family A, plus family B's filters as core steps and a naming hook | Family A is the more defensive structure and includes PR #78. The 2150 lab-guide warning is dropped: the render-incomplete gate already fails on any `.qmd` without a `.typ`, which is a superset. See section 3 for every behavior. | generic, with hooks |
| `_git_date` | 2: 2150 splits into a cached `_commit_date` and `_format_date` and accepts dependency paths; the other five are one function | 2150 | Superset. Dependencies are what let a page assembled from partials carry the newest date of its sources; the cache keeps repeated `git log` calls cheap. | generic |
| `stamp_dates` | 4: 4700/Py (`.qmd` only, `date: false` opt-out); 1140 (`.qmd` only, no opt-out); 3330/4430 (`.qmd` and `.ipynb`, opt-out); 2150 (`.qmd` and `.ipynb`, opt-out, `date_deps`) | 2150 | Superset. Notebook stamping writes the first raw cell, which the platform reads for the title and date. No repo uses `date: false` today (0 files), but it is documented in PHYS-4700's stamp checker and costs nothing. Unify the quoting: `.qmd` gets `date: "March 3, 2026"` and `.ipynb` gets it unquoted in every variant; quote both. | generic |
| `restore_dates` / `restore_sources` | identical body, two names | replaced by `Workspace.restore()` | See behavior 7. | generic |
| `main` | 6 | replaced by `cli.main()` | Identical flag set (`--html`, `--pdf`, `--ci`, `-v`), identical PDF-then-HTML stash logic, identical messages and exit codes; they differ only in which source passes run and in what order. | generic, with hooks |

Functions that are not in all six but earn a place in the core:

| Function | Where | Keep | Why | Status |
| --- | --- | --- | --- | --- |
| `validate_notebooks` | 2150, 3330 | 3330 | Handles invalid JSON and uses the shared frontmatter regex. Runs whenever any `.ipynb` exists outside `_site/`. PHYS-4430 has four notebooks and no check today. | generic |
| `resolve_variables` | 4700, 3330, 4430 | any (identical apart from comments and the helper's name) | Three copies of the same pass. Runs whenever `_variables.yml` exists. | generic |
| `decode_image_paths` | 3330, 4430, Py | any (identical apart from the docstring) | Standalone Typst opens the literal `%20` name and fails. Always on; `unquote` is a no-op on paths without `%`. | generic |
| `cap_image_widths` | 3330 | as is | The template caps figure *height*; an explicit `width="20cm"` in the `.qmd` still overflows the 7 in (17.78 cm) text block. PHYS-3330 has five figures at 20 cm and one at 18 cm, which this filter caps today; PHYS-4430's `gaussian-beams/week-3` figure is 20 cm and ships overflowing. Always on. | generic |
| `normalize_table_columns` | 3330 | as is | Pandoc emits `#table(columns: 3,` (the fixture does); the platform's `tables.css` sets tables to `width: 100%`, so full-width `1fr` columns in the PDF match the HTML. Anchored to `#table(`. Always on, checked visually on the fixture before the first release (open question 3). | generic |
| `convert_boxed_math` | 1140 | as is | Pandoc's `\boxed{}` output puts `#box()` inside math, which Typst rejects. Four PHYS-1140 pages use `\boxed`; no-op elsewhere. Always on. | generic |
| `stamp_course_data` | 4700 (with a season fallback); 2150, 1140 (plain) | the walk becomes a core primitive; the resolver stays in the wrapper | The "walk every `.qmd`, substitute, snapshot, write bytes" loop is the same code that `resolve_variables`, `stamp_rubrics`, `resolve_syllabus` and both `resolve_weekly` variants also carry. The core provides it once; the `{{< meta >}}` resolver is course data. | primitive generic, resolver course-specific |

Clearly course-specific, staying in the wrappers: PHYS-4700's `generate_course_data`, `_links_file`, `_term_week_dates` and the season fallback in `stamp_course_data`; PHYS-2150's `generate_course_data`, `resolve_weekly`, `_generate_deliverables_table`, `_generate_schedule_table`, `resolve_syllabus`, `stamp_rubrics`, `stamp_visibility` (week-keyed) and helpers; PHYS-1140's `generate_course_data`, `check_weekly_lectures`, `resolve_weekly`, `_generate_deliverables_table`, `stamp_visibility` (lab-keyed, with day offsets and a first-lab exemption, so not the same function as 2150's).

## 2. Package layout and public API

```text
_extensions/physicslabs/physicslabs_build/
  __init__.py     API_VERSION, Site, run; re-exports of the modules below
  cli.py          argparse (--html --pdf --ci -v; --course-data when the hook is set), main()
  site.py         Site (root, paths, hooks) and Workspace (originals, date deps, restore)
  tools.py        find_quarto, find_typst, typst_version
  sources.py      stamp_dates, resolve_variables, validate_notebooks,
                  substitute_shortcodes, frontmatter regexes, git dates
  typ.py          pure text transforms on a kept .typ (the post-processor)
  pdf.py          render to .typ, census, orphan cleanup, render-incomplete gate,
                  compile, build_pdfs
  html.py         build_html
  naming.py       PDF filename helpers: page_stem (default), prefixed(course)
```

Tests live at `tests/` in this repository, beside `tools/`, so they are not
installed into course sites.

The paths the package needs come from its own location, not from the
wrapper: `fonts_dir` is `Path(__file__).parent.parent / "fonts"`, which is
right both in a course site (`_extensions/UCBoulder/physicslabs/fonts`) and
in this repository's fixture (`_extensions/physicslabs/fonts`). The project
root comes from the wrapper.

### The wrapper a course site keeps

This is PHYS-3330's, the median case. Every `build.py` reduces to this
shape; section 4 lists what each one adds.

```python
"""Build the PHYS 3330 site: HTML plus accessible PDF/UA-1 PDFs.

The pipeline lives in the physicslabs extension; this file only names what is
specific to this course. See docs/build-and-deploy.qmd.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.dont_write_bytecode = True   # keep __pycache__ out of _extensions/
sys.path.insert(0, str(ROOT / "_extensions" / "UCBoulder" / "physicslabs"))
from physicslabs_build import Site, naming, run  # noqa: E402


def lab_guide_name(rel: Path) -> str:
    """lab-guides/labN/index.qmd -> phys3330-labN.pdf; everything else keeps its stem."""
    m = re.fullmatch(r"lab(\d+)", rel.parent.name)
    if m and rel.name == "index.qmd":
        return f"phys3330-lab{m.group(1)}.pdf"
    return naming.page_stem(rel)


site = Site(
    root=ROOT,
    description="Build PHYS 3330 site (HTML + accessible PDF).",
    pdf_name=lab_guide_name,
)
raise SystemExit(run(site))
```

The fixture's wrapper at this repository's root is the same file with
`_extensions/physicslabs` on the path and no hooks.

### `Site`

```python
Site(
    root: Path,
    description: str,
    source_passes: list[SourcePass] | None = None,
    typ_filters: list[TypFilter] | None = None,
    pdf_name: Callable[[Path], str] = naming.page_stem,
    course_data: Callable[[bool], None] | None = None,
    require_api: int = API_VERSION,
)
```

- `source_passes` is the ordered list of passes that edit sources before the
  render. `None` means the core default:
  `[sources.validate_notebooks, sources.resolve_variables, sources.stamp_dates]`.
  Each of those is a no-op when its input is absent (no `.ipynb`, no
  `_variables.yml`). A wrapper that needs its own order lists the full
  sequence, mixing core passes and its own; PHYS-2150's list is in section 4.
- `typ_filters` are appended after the core chain by default. The core chain,
  in order: `strip_fontawesome`, `decode_image_paths`, `convert_boxed_math`,
  `cap_image_widths`, `normalize_table_columns`, `add_image_alt_text`,
  `add_math_alt_text`. Alt text runs last so every earlier filter sees the
  original `image()` and math forms. A wrapper that must run something
  earlier passes `typ_filters=typ.chain(before=[...], after=[...])`.
- `pdf_name` maps a page's project-relative `.qmd` path to the PDF filename
  written beside it in `_site/`. The default keeps the page stem
  (`index.qmd` gives `index.pdf`). `naming.prefixed("phys4430")` is
  PHYS-4430's scheme (every segment below the top-level directory, so
  `lab-guides/gaussian-beams/week-1/index.qmd` gives
  `phys4430-gaussian-beams-week-1.pdf`), shipped because it is the most
  general of the three schemes in use.
- `course_data` is the pre-render generator. When set, the CLI gains
  `--course-data`, which calls it, writes the comment-only placeholder if
  `_course-data.yml` is still missing (Quarto fails on a missing
  `metadata-files` entry), and exits. A normal build also calls it first,
  as PHYS-4700, PHYS-2150 and PHYS-1140 do today. The `_quarto.yml`
  pre-render line stays `python build.py --course-data`.
- `require_api` lets a wrapper refuse to run against a core whose
  `API_VERSION` differs, so a `quarto update` that crosses a breaking change
  fails with one clear line instead of a traceback.

### Hook signatures

```python
SourcePass = Callable[[Workspace, bool], None]   # (ws, verbose)
TypFilter  = Callable[[str, Page], str]           # (text, page) -> text
```

`Page` carries `qmd` (source path), `typ` (kept file), `rel` (project-relative
`.qmd` path) and `verbose`. A pure `str -> str` function is wrapped with
`typ.pure(fn)`.

### `Workspace`

The one object every source pass edits through.

```python
class Workspace:
    root: Path
    site_dir: Path
    def pages(self) -> list[Path]                 # every .qmd outside _site/, _extensions/, .quarto/
    def notebooks(self) -> list[Path]
    def read(self, path: Path) -> str
    def write(self, path: Path, text: str) -> None  # snapshots the first version, writes bytes
    def add_date_dep(self, page: Path, *deps: Path) -> None
    def restore(self) -> None                     # called unless --ci
```

`write` records the file's bytes the first time it is touched and never
again, and writes with `write_bytes` so CRLF files survive on Windows. That
single rule replaces the four different "merge the originals dicts" idioms in
the six `main()` functions (PHYS-2150's reverse-order `update`, PHYS-1140's
`setdefault` helper, PHYS-3330's and 4430's inline `setdefault` loops,
PHYS-4700's filtered `update`), all of which exist to express "the earliest
snapshot wins". `add_date_dep` is how `resolve_weekly` tells `stamp_dates`
which partials a page was built from, replacing 2150's tuple return values.

`sources.substitute_shortcodes(ws, name, resolver, verbose)` is the primitive
under `resolve_variables` and under every course's `{{< meta >}}`,
`{{< rubric >}}` and `{{< syllabus >}}` pass: it walks `ws.pages()`, skips
files that contain no `{{< name` opener, substitutes through
`resolver(key, page) -> str | None` (None leaves the shortcode in place and
reports it), and writes through `ws.write`.

### Build order in `run(site)`

1. Reconfigure stdout and stderr to UTF-8 with `errors="replace"`.
2. `site.course_data(verbose)` if set.
3. Find Quarto; find Typst and check its version if PDFs are requested. Fail
   here, before any source is touched. (PHYS-3330 and 4430 already do this;
   the other four stamp first and fail after.)
4. Run `source_passes` in order.
5. Build: PDFs, stash them, HTML, restore them (both); or one of the two.
6. `ws.restore()` unless `--ci`, in a `finally`.
7. Print `Done.` or `Build completed with errors.`; exit 0 or 1.

The CI entry point, `python build.py -v --ci` from `site/`, and the four flags
are unchanged. Nothing in any workflow changes for the migration except an
explicit PyYAML install where one is missing (section 4).

## 3. Behaviors to unify

1. **Profile use.** Always render with `--profile typst`. Quarto 1.9.37 accepts
   a profile that has no `_quarto-typst.yml` (verified on the fixture: exit 0,
   three `.typ` files, no warning), so the core can pass it unconditionally
   and a repository decides what the profile does. Repositories with notebooks
   keep the profile file that limits the Typst pass to `**/*.qmd`; PHYS-3330
   should add one (it has ten notebooks, renders them to Typst today, and then
   deletes the litter). PHYS-4430 excludes notebooks from every format through
   `project.render` and needs nothing.

2. **The `_site/pdf` staging directory.** It does not exist. All six scripts
   set `PDF_DIR = SITE_DIR` and compile each PDF straight to
   `_site/<page dir>/<name>.pdf`; only the `build_pdfs` docstrings in
   PHYS-1140 (line 792), PHYS-3330 (431) and PHYS-4430 (386) still describe a
   `_site/pdf/` step, a leftover from the Jekyll-to-Quarto migration in
   February. The only staging anywhere is the temporary-directory stash in
   `main()` that carries PDFs across the HTML render, which every script has
   and the core keeps. Chosen: compile to the final location, stash across the
   HTML render, and drop the stale docstrings.

3. **The orphan scan.** One census, PHYS-2150's `kept_typ_files` (line 1411,
   PR #78): every `**/*.typ` under the project except those under `.quarto/`,
   `_extensions/` and `_site/`, by path prefix. A kept `.typ` with no sibling
   `.qmd` is an orphan; the core deletes it together with any PDF Quarto's
   bundled Typst wrote for it (beside the source and under `_site/`) and its
   `<stem>_files/` figure directory. PHYS-1140 and 3330 exclude `.quarto` by
   path part but `_extensions` only by the two partial filenames, which works
   until the extension ships a third `.typ`; PHYS-4430 only filters and never
   deletes, which is fine only because its profile-free render never produces
   orphans. The render-incomplete gate (every `.qmd` must have a `.typ`) uses
   the same exclusions for the expected set. No repository has a `.qmd` under
   an underscore or dot directory that Quarto would skip, so the gate's
   "every `.qmd`" rule is accurate today; open question 6 covers the day it
   is not.

4. **The PHYS-1140 rename.** `re.match(r"lab(\d+)", ...)` at line 864 never
   matches `lab-01` through `lab-12`, so every PHYS-1140 PDF is `index.pdf`.
   The platform still finds each one: `find_pdf_for_page` in
   `physicslabs/quarto/services/content_service.py` tries the exact page name
   first, then, for an `index.html` page, the single PDF in the directory, and
   all fifteen PHYS-1140 pages that offer a PDF use `pdf-download: true`. So
   the visible effect is only the download filename students see:
   `index.pdf` where PHYS-3330 students get `phys3330-lab1.pdf`. Chosen: the
   core never renames; naming is the `pdf_name` hook with `page_stem` as the
   default, and the three repositories that rename keep their scheme in their
   wrapper. PHYS-1140's wrapper fixes the pattern to `lab-(\d+)` and names
   `phys1140-lab01.pdf`, which the platform resolves through the same
   single-PDF fallback PHYS-3330 relies on. The alternative, dropping the
   rename, is a one-line difference; the owner's call (open question 2).

   The rename is also why the scripts delete stale `index.pdf` files: when the
   target is renamed, Quarto's own `index.pdf` would sit beside it and the
   platform's single-PDF fallback would find two and return nothing. The core
   replaces the `rglob("index.pdf")` sweeps (PHYS-4430's runs over the whole
   project and would remove a resource that happened to be named `index.pdf`)
   with a precise rule: for each page, delete `_site/<rel>.pdf`, the path
   Quarto's bundled compile wrote, before compiling to the chosen name.

5. **Error reporting when Quarto's bundled Typst fails.** A non-zero exit from
   `quarto render --to typst` is expected and tolerated: only the `.typ`
   files matter. Chosen: family A's handling (PHYS-4700 lines 396 to 411).
   In non-verbose mode the core captures Quarto's output and, on a non-zero
   exit, prints the last 30 lines under a "Diagnostic" header; in verbose mode
   the output streams live. The only failure condition is the
   render-incomplete gate, and when it fires the core prints the missing pages
   and, in non-verbose mode, the captured tail once more beside them, so the
   cause and the effect land together. Family B prints one "Note" line and
   nothing else (PHYS-1140 line 806, 3330 line 445, 4430 line 404), which in a
   local non-verbose build leaves an author with "render incomplete" and no
   Typst error to read. Standalone Typst failures keep the per-file `FAIL`
   block with warning lines filtered and a warning count, plus the summary
   line. The UTF-8 reconfiguration in step 1 of `run` ends the Windows
   `charmap` traceback the adoption runbook works around with
   `PYTHONIOENCODING`.

6. **Verbose output.** Default: one line per step, the `.typ` count, the
   source-pass summaries (each pass prints one line when it changed something,
   as today), and `OK`/`FAIL` per PDF with its size. `-v` adds live Quarto
   output, the kept `.typ` list with sizes, per-page post-processing notes
   (the `n/m images updated` line) and the passes' per-file warnings. This is
   family A's behavior extended to the passes; no flag changes.

7. **Restoring sources.** `Workspace.write` snapshots first and only once, so
   "earliest original wins" is structural instead of a comment in each
   `main()`. `restore` runs in a `finally` unless `--ci`, as now.
   PHYS-4700's `check_no_build_stamps.py` guard keeps working unchanged: the
   stamps it detects are the same stamps.

8. **PyYAML.** When `_variables.yml` exists and PyYAML is missing, fail the
   build. Today the pass warns and skips, and PHYS-3330's workflow comment
   spells out the consequence: a green PR that ships literal `{{< var >}}`
   text to students. The same goes for the course-data passes, which the
   wrappers write on the core primitive and which raise instead of returning
   an empty dict.

9. **Tool discovery before source edits** (step 3 of `run`), and the Typst
   version compared numerically. Both are small; both are decisions rather
   than inheritances.

## 4. Per-repo migration notes

Each site's wrapper keeps only what is its own. Every migration also deletes
the copied functions, rewrites the "What build.py does" section of its build
doc and the `build.py` bullet in `CLAUDE.md`, and adds
`sys.dont_write_bytecode = True` so nothing lands under `_extensions/`
(all six already ignore `__pycache__/`).

**PHYS-4700.** Keeps `generate_course_data` with its two-season links files
and term-week dates, the `stamp_course_data` resolver with the
`canvas-<season>-` fallback (on `substitute_shortcodes`), and
`course_data=`. Loses its copies of `resolve_variables` and everything in
section 1. Its pass list is `stamp_course_data` followed by the core
default. Today it stamps dates before variables and the default does the
reverse; the two never rewrite the same line and `Workspace` keeps the first
snapshot either way, so the swap changes nothing.
The build doc's troubleshooting row that blames a stale `.quarto` cache for
the fontawesome abort describes PHYS-2150's bug, not 4700's; fix it in the
same PR. Add an explicit `pip install pyyaml` step to both workflows, which
PHYS-3330 and 4430 already carry.

**PHYS-2150.** Keeps `generate_course_data`, `resolve_weekly` (now calling
`ws.add_date_dep` for each inlined partial instead of returning a tuple),
`resolve_syllabus`, `stamp_rubrics` and `_rubric_deps` (also registering
deps), the plain `stamp_course_data` resolver and the week-keyed
`stamp_visibility`. Its explicit pass list, preserving today's order:
`[validate_notebooks, resolve_weekly, resolve_syllabus, stamp_dates,
stamp_rubrics, stamp_course_data, stamp_visibility]`. Loses the lab-guide
warning (subsumed by the gate) and `_commit_date`, `_format_date`,
`kept_typ_files`, which become the core's. Keeps `_quarto-typst.yml`.

**PHYS-1140.** Keeps `generate_course_data` and `check_weekly_lectures`, its
`resolve_weekly` with the deliverables table, the lab-keyed
`stamp_visibility`, the plain `stamp_course_data` resolver, and a
`pdf_name` hook with the corrected `lab-(\d+)` pattern. Today its order is
dates, weekly, visibility, course data, so the instructor guide's date
ignores edits to the partials it is built from; listing `resolve_weekly`
before `stamp_dates` and registering deps fixes that at no cost. Gains the
`date: false` opt-out and `decode_image_paths`; `convert_boxed_math`
continues to run, now from the core. `filters/notebook.lua` is Quarto-side
and untouched. Add the PyYAML install step.

**PHYS-3330.** Keeps `lab_guide_name` (the wrapper above). Loses its copies
of `cap_image_widths`, `normalize_table_columns`, `decode_image_paths`,
`validate_notebooks` and `resolve_variables`, all now core. Adds
`_quarto-typst.yml` with `render: ["**/*.qmd"]` so the Typst pass skips its
ten notebooks instead of compiling and deleting them. Its build doc's note
that only lab guides are renamed stays true.

**PHYS-4430.** Keeps `pdf_name=naming.prefixed("phys4430")`, which is its
own scheme moved into the core because it is the general one; the page with
`pdf-download: "phys4430-gaussian-beams-week-1.pdf"` keeps working. Loses
`resolve_variables` and `decode_image_paths`. Gains `validate_notebooks` for
its four notebooks, `cap_image_widths` for the 20 cm Gauss-Hermite figure,
and `normalize_table_columns`. Keeps `project.render: ["**/*.qmd"]`.

**PHYS-Python-Resources.** The wrapper is the fixture's: root, description,
no hooks. Its `main()` description still reads "PHYS 4700 (Quantum Forge)",
a copy artifact that the rewrite removes. `_quarto-typst.yml` can go (no
notebooks) or stay; it is harmless.

Order of migration: PHYS-Python-Resources first (no hooks, so it tests the
core alone), then PHYS-3330 and 4430 (naming hook, notebooks), then 4700,
1140 and 2150 (course data). One PR per repository, each verified with the
adoption runbook's step 9 plus a diff of the deploy branch's PDF list against
the previous build.

## 5. Testing the core in the fixture CI

The fixture site at this repository's root gains a `build.py` wrapper, which
doubles as the reference wrapper, and `render.yml` runs it instead of a bare
`quarto render`. Because `--pdf-standard ua-1` makes Typst refuse any image or
equation without alt text (verified on 0.14.2 for both), a successful compile
of the fixture is itself the assertion that the post-processor reached every
image and equation. Typst is the validator.

`render.yml` changes:

1. Install Typst 0.14.2 the way the course workflows do, with the sha256
   check from PHYS-2150's; `pip install pyyaml pytest`.
2. `python -m pytest tests/`: unit tests for `typ.py` and `sources.py` on
   short inline strings, each pair taken from real kept output. Required
   cases: a labeled equation using the bare `equation-numbering` identifier,
   a multi-line aligned display equation, inline math beside a `$` inside a
   fenced code block and inside a `#Skylighting` block, a `\boxed{}`
   equation, a percent-encoded image path, an image at `width: 20cm`, an
   integer `#table(columns: 3,`, the fontawesome import and an `fa-` call,
   the preamble split, frontmatter with and without a `date:` line and with
   `date: false`, a notebook whose first cell is not raw, and `Workspace`
   snapshotting a file written twice.
3. `python build.py -v` (no `--ci`), then `git status --porcelain` must be
   empty: stamping and restore round-trip. Then the existing output checks,
   plus `_site/index.pdf`, `_site/guide/index.pdf`, `_site/guide/elements.pdf`
   beside their pages, no kept `.typ` left in the tree, and the existing
   Roboto greps on the PDF bytes.
4. `python build.py -v --ci --pdf`, then `grep -q '^date: "' index.qmd`:
   `--ci` keeps the stamp.

The fixture content has to grow for step 3 to mean anything: `elements.typ`
today holds one labeled equation, one inline equation, one integer-column
table, one fontawesome import, and no `image()` call and no unlabeled
display math. `guide/elements.qmd` gains an image with `fig-alt` (a small
PNG committed under `guide/`), a second image whose filename contains a
space and carries `width="20cm"`, an unlabeled display equation, a
multi-line aligned one, a code block containing a `$`, and a `\boxed{}`
equation. All of these are content elements the platform styles, so they
belong in the fixture anyway.

The Quarto pin stays 1.9.38 to match the course workflows; the fixture runs
Python 3.12.

## 6. Open questions for review

1. **Package name.** `physicslabs_build` as argued above, or `build/` as in
   the brief with an `importlib` shim in every wrapper to avoid the name
   clash. The shim is five lines of the copy-pasted kind this design removes.
2. **PHYS-1140 naming.** Fix the pattern so students download
   `phys1140-lab01.pdf` (recommended, consistent with PHYS-3330 and with the
   1140 build doc's own wording about "CI-renamed PDFs"), or drop the rename
   and keep `index.pdf`. Related: whether PHYS-3330 wants `naming.prefixed`
   for all index pages or, as its doc says, lab guides only.
3. **`normalize_table_columns` on by default.** It changes every
   integer-column table in five sites' PDFs to full width. Check the fixture
   and one PHYS-2150 lab guide side by side before the release; if a course
   wants auto-width tables the wrapper can remove the filter.
4. **PyYAML hard failure** versus the current warn-and-skip, and whether the
   core should also fail when a `.ipynb` exists and `validate_notebooks`
   cannot parse it (proposed: yes to both).
5. **Auto-enabled passes.** `validate_notebooks` and `resolve_variables` run
   by file presence under the default pass list. A wrapper that lists passes
   explicitly opts out by omission; is an explicit `disable=` clearer?
6. **The render-incomplete gate and `project.render`.** The gate expects a
   `.typ` for every `.qmd`. A repository that excludes a `.qmd` through
   `project.render` would fail it. None does today; the fix when one does is
   an `exclude` glob on `Site`, or reading the render list from
   `quarto inspect`.
7. **Notebook date quoting.** Unifying to the quoted form changes what the
   deploy branch carries for notebooks; confirm the platform's frontmatter
   reader accepts both before switching.
8. **Version coupling.** `API_VERSION` plus the extension's semver: a
   breaking core change is a minor bump and a runbook section, as v0.2.0
   was. Is that enough, or should the wrapper also pin the extension
   version it was written against?
9. **A PDF/UA validator in CI.** Typst's own check covers alt text and
   heading structure; veraPDF would cover the rest of the standard. Worth a
   separate look; not needed for the migration.
10. **The future of `--ci`.** If page dates and Canvas links ever come from
    the platform instead of stamped sources, the source passes disappear and
    the PDF step could become a Quarto post-render script contributed by the
    extension, shrinking each `build.py` to nothing. Out of scope; noted so
    the package boundaries (sources versus typ/pdf) are drawn with it in mind.
