# Adopting the extension in an existing course site

This is the recipe for moving a course repository from its hand-maintained
Quarto theme (`site/assets/css/*.scss`, `site/assets/html/header.html` and
`footer.html`, bundled logos) to the `physicslabs` project type. It was
written from the PHYS-4700 pilot and is meant to be followed as-is, one
repository per pull request.

One fact frames the whole job: **the old theme only ever affected local
preview.** The deploy branch carries `.qmd` sources and PDFs, and the platform
renders them with its own chrome and stylesheets, so nothing in the old SCSS or
header ever reached a student. This migration changes what authors see in
`quarto preview`; the live site should come out unchanged, and that is the
post-merge check.

## Before you start

- The course repository keeps its Quarto project in `site/`. Commands below
  run there unless noted.
- Quarto 1.9 or later locally; CI pins its own version in the workflow.
- Work on a branch. The PR touches CI and docs, so it routes to admin review.

## 1. Audit the old chrome for navigation

Open `site/assets/html/header.html`. If it carries a Resources menu or other
links, list them and check each against `site/_nav.yml`. The platform builds
its sidebar from `_nav.yml`; a link that lives only in the old header was never
shown to students. Add the missing pages to `_nav.yml` in this PR (site-relative
paths, no extensions). Do not recreate the menu with `physicslabs.nav`: that
renders in preview only.

## 2. Install the extension

`quarto add` reads `_quarto.yml` before installing, and fails with
"Unsupported project type physicslabs" once the type is declared and the
extension is not yet present. So install first, or move the config aside:

```sh
cd site
quarto add UCBoulder/PHYS-Quarto-Extension@vX.Y.Z --no-prompt
```

Use the latest tag. The files land in `_extensions/UCBoulder/physicslabs/`;
commit them and never edit them in place.

## 3. Rewrite `_quarto.yml`

Change `project.type` to `physicslabs` and remove what the extension now
supplies. Keep anything the course sets deliberately; lists such as `filters`
and `pre-render` merge with the extension's.

Remove:

- `project.resources` entries for the three logo files
- `website.navbar: false`
- `lang`, `date-format`, `toc`, `toc-depth`, `format-links`
- the whole `format.html` block: `theme`, `include-before-body`,
  `include-after-body`, `number-sections`, `link-external-newwindow`, and
  any `css` entries that pointed at the old theme
- `highlight-style`, if present (PHYS-4430 had `github`/`dracula`): the
  platform's stylesheet sets its own token colors and overrides it

Keep:

- `website.title`, `website.favicon`
- `format.typst` and `_quarto-typst.yml`; the PDF build is untouched
- course-specific `format.html` keys such as a Lua `filters` list. A
  top-level `filters` list is fine too: both merge with the extension's
  `format.html.filters`, so the course filter and `chrome.lua` run on every
  page (PHYS-1140 declares its `notebook.lua` that way).

Add:

```yaml
physicslabs:
  title: "PHYS 2150"          # header title; usually the same as website.title
```

## 4. Delete the old theme

```text
site/assets/css/custom.scss
site/assets/css/dark.scss
site/assets/css/light.scss
site/assets/html/header.html
site/assets/html/footer.html
site/assets/img/beboulder_white.png
site/assets/img/cu-boulder-logo-text-black.svg
site/assets/img/cu_boulder-white.svg
```

Keep `site/assets/fonts/` (the Typst template reads it) and the favicon.
Before deleting, grep the repository for `assets/css`, `assets/html`,
`assets/img`, `custom.scss` and `header.html` to be sure nothing else refers to
them. The grep misses prose: `site/CLAUDE.md` and `site/README.md` usually
describe the old theme in a styling section or a directory tree (`css/`,
`html/`, `img/` under `assets/`); rewrite those to point at the extension. Course-specific rules found in `custom.scss` are one of three things:
chrome the extension already has, content styling that belongs on the platform
if it belongs anywhere, or page styling the page should embed itself. None of
it moves into the course repository's config.

## 5. Ignore the generated files

Add to the repository's `.gitignore`:

```text
site/_physicslabs-sidebar.yml
/.luarc.json
```

The first is written by the extension's pre-render step on every render (only
when its content changes). The second is written by the Quarto VS Code
extension, not the CLI: once a Lua file in the workspace is opened and the Lua
language server is set up, it drops `.luarc.json` at the root of the first
workspace folder, holding the absolute path of the local Quarto install. That
is why the entry is anchored at the repository root rather than under
`site/`, and why `quarto render` alone never creates it; do not read its
absence during step 9 as a problem.

## 6. Keep the extension off the deploy branch

In the deploy workflow's "Assemble source + PDFs" step, the find that copies
downloadable resources (`*.py`, `*.csv`, ...) must exclude the extension, as
the image find already does:

```sh
-not -path './_site/*' -not -path './.quarto/*' -not -path './_extensions/*'
```

## 7. Optional: course data in preview

Only for repositories whose `build.py` derives `_course-data.yml` for `meta`
shortcodes. Add a `--course-data` mode to `build.py` that regenerates the file
and exits, writing only when the content changes, then in `_quarto.yml`:

```yaml
project:
  pre-render:
    - python build.py --course-data
metadata-files:
  - _course-data.yml
```

PHYS-4700's `build.py` has the reference implementation. Skip this section if
the repository has no such shortcodes.

## 8. Update the docs

- The build-and-deploy page: a "Site theme" section saying where the look
  comes from, how to update the extension, the install-order gotcha, and what
  stays in the repository. Copy PHYS-4700's section and adjust names.
- `CLAUDE.md`: a sentence in the `site/` bullet pointing at the extension and
  forbidding content styling in the course repository.
- Wherever the course docs state a minimum Quarto version (the build-and-deploy
  page's prerequisites table, `site/CLAUDE.md`), make it 1.9. The extension
  declares `quarto-required: ">=1.9.0"`; 1.4+ was the usual figure before.

## 9. Verify

- `python build.py --html` succeeds; every page in `_site/` contains
  `class="cu-header"`.
- `python build.py --pdf` succeeds (Typst is unaffected, but prove it). If it
  aborts within seconds on a Typst package such as `fontawesome` ("file not
  found" under `.quarto/typst/packages`), delete `site/.quarto` and rerun.
  The cache is not stale; the course's own `build.py` broke it. Its cleanup of
  notebook-generated `.typ` files globs `**/*.typ` over the whole project,
  which includes `.quarto/typst/packages`, and deletes every package `.typ`
  (`lib.typ` and its siblings) because no `.qmd` sits beside it. Each
  `build.py --pdf` run therefore strips the packages it just downloaded, the
  next bundled-Typst compile fails on the first page that imports one, and
  Quarto aborts the render there. Deleting `.quarto` works because the
  packages are downloaded again before the cleanup runs, so expect the abort
  to return after every PDF build until `build.py` excludes `.quarto/` and
  `_extensions/` from that glob. Only PHYS-2150 carried the pattern (fixed in
  its PR #78); the other course repositories' scans already skip those
  directories, or only filter the list rather than delete. If a repository
  shows the abort, check its scan before assuming a cache problem. On Windows,
  `build.py` can die with a
  `charmap` encoding traceback while echoing that Typst error; set
  `PYTHONIOENCODING=utf-8` for the run. Neither is caused by the extension.
- The render log shows `physicslabs: sidebar from _nav.yml (N entries, ...)`
  and no "path not found" lines.
- `quarto preview`: follow sidebar links (the page must change), toggle dark
  mode, expand a collapsible callout, hover a code block for the copy button.
  Dark mode cannot be tested from a `file:` URL; use preview or any HTTP server.
- A second render reports the sidebar file as "unchanged".

## 10. Open the PR

Title: "Adopt the physicslabs Quarto extension". Body: what changed, the
`_nav.yml` additions from step 1, and the three post-merge checks below. The
squash keeps the commit messages, so write them with what and why.

## 11. After the merge

1. Build & Deploy on `main` succeeds.
2. `git ls-tree -r --name-only origin/deploy/django` shows nothing under
   `_extensions/`.
3. Sync Now in the course portal, then open a page live. It should look exactly
   as it did before.

## 12. Moving to v0.2.0: the Typst format and no preview-only menu

Sites adopted on v0.1.0 need one more PR. From `site/`:

1. `quarto update UCBoulder/PHYS-Quarto-Extension` (or `quarto add ...@v0.2.0`)
   and commit the changed files under `_extensions/UCBoulder/physicslabs/`.
2. In `_quarto.yml`, delete the whole `format.typst` block. The extension now
   supplies it: template partials, fonts, page size and margins, numbered
   sections, `syntax-highlighting: idiomatic`, `keep-typ`. Keep
   `_quarto-typst.yml` if the repository has one; it only lists what to render.
   If the site set `physicslabs.nav`, delete it; the key no longer exists, and
   the platform never showed that menu.
3. Delete `site/_extensions/cu-boulder/` (the old template partials) and
   `site/assets/fonts/`. The extension ships both.
4. In `build.py`, point the fonts directory used for the standalone Typst
   compile (`FONTS_DIR`, passed as `--font-path`) at
   `_extensions/UCBoulder/physicslabs/fonts`. Nothing else in `build.py`
   changes: the render still uses `keep-typ`, and the post-processing and
   PDF/UA-1 compile are as before.
5. If the old template's header stamp said something other than the site's
   `physicslabs.title` (Python Resources was stamped "PHYS 2150"), the new
   stamp is the fix, not a regression.
6. Verify as in step 9, and additionally open one PDF: the header carries the
   course name from `physicslabs.title`, a tall figure is capped rather than
   pushed to its own page, and an unlabeled display equation carries no number.
   Without a PDF viewer: `quarto render <page>.qmd --to typst` (add
   `--profile typst` where `_quarto-typst.yml` exists) leaves the kept `.typ`
   next to the source, not in `_site/`. It must contain `course: "<title>"`
   and no line starting with `set math.equation(numbering`; delete it
   afterwards. If that render ends with the bundled Typst failing on
   `fontawesome` (step 9: a previous `build.py --pdf` deleted the package
   sources), the `.typ` is still written and the check stands. A built PDF
   must contain the string `Roboto` (grep its bytes).
7. The deploy workflow's font copy (`assets/fonts` to the deploy branch, where
   present) can go; the platform serves the CI-built PDFs and never compiles
   Typst.
8. Update the docs that named the removed paths. Grep `site/`, `CLAUDE.md` and
   `README.md` for `assets/fonts` and `_extensions/cu-boulder`: the
   build-and-deploy page's "what stays in this repo" bullet, the structure and
   PDF-styling notes in `site/CLAUDE.md`, and the directory tree in
   `site/README.md`. Copy PHYS-4700's "PDFs use the extension too" bullet.

### v0.2.1: install this rather than v0.2.0

v0.2.0 shipped the Roboto Condensed faces alongside Roboto. Typst files them
under the family "Roboto" at normal stretch, so on a Linux runner every
CI-built PDF was set in Condensed, and had been since the course repositories
first bundled those files. v0.2.1 ships Roboto only. Expect live PDFs to
re-wrap wider and gain pages after the first CI build on it; that is the
correction, not a regression. It also fixes the sidebar script rejecting a
page that has a same-named directory beside it.

## 13. Moving to v0.3.0: build.py onto the build core

v0.3.0 ships the build pipeline as a Python package inside the extension
(`_extensions/UCBoulder/physicslabs/physicslabs_build/`), so `site/build.py`
shrinks to a wrapper that names what is specific to the course. The design,
the API and the per-course notes are in
[build-core.md](build-core.md); this section is the recipe. One PR per
repository, in this order: PHYS-Python-Resources (no hooks), then PHYS-3330
and 4430 (naming hooks), then 4700, 1140 and 2150 (course data).

1. `quarto update UCBoulder/PHYS-Quarto-Extension` (or `quarto add ...@v0.3.0`)
   from `site/`, and commit the changed files under
   `_extensions/UCBoulder/physicslabs/`, including the new
   `physicslabs_build/` directory.

2. Before touching `build.py`, record the deploy branch's PDF list; it is the
   post-merge check:

   ```sh
   git fetch origin deploy/django
   git ls-tree -r --name-only origin/deploy/django | grep '\.pdf$' | sort > /tmp/pdfs-before.txt
   ```

3. Replace `build.py` with the wrapper. This is the whole file for a site with
   no hooks (PHYS-Python-Resources); the reference copy is `build.py` at the
   root of the extension repository:

   ```python
   """Build the <course> site: HTML plus accessible PDF/UA-1 PDFs.

   The pipeline lives in the physicslabs extension; this file only names what is
   specific to this course. See docs/build-and-deploy.qmd.
   """

   import sys
   from pathlib import Path

   ROOT = Path(__file__).resolve().parent
   sys.dont_write_bytecode = True   # keep __pycache__ out of _extensions/
   sys.path.insert(0, str(ROOT / "_extensions" / "UCBoulder" / "physicslabs"))
   from physicslabs_build import Site, run  # noqa: E402

   site = Site(
       root=ROOT,
       description="Build <course> site (HTML + accessible PDF).",
       require_api=1,
   )
   raise SystemExit(run(site))
   ```

   `require_api=1` is what makes a later `quarto update` across a breaking
   core change fail with one line instead of a traceback; always pass it.
   Point the docstring's last sentence at wherever the repository keeps its
   build notes: PHYS-Python-Resources has no build-and-deploy page, so its
   wrapper cites the Build section of `CLAUDE.md`.

4. Add the course's own hooks to the `Site`. What each repository keeps
   (build-core.md, section 4):

   - **PHYS-3330**: `pdf_name=` a function that renames
     `lab-guides/labN/index.qmd` to `phys3330-labN.pdf` and leaves every other
     page at its stem (the example wrapper in build-core.md, section 2). Add
     `_quarto-typst.yml` with `project: render: ["**/*.qmd"]` so the Typst
     pass skips the notebooks. Everything else in the old script is core now.
   - **PHYS-4430**: `pdf_name=naming.prefixed("phys4430")`; import `naming`
     with `Site` and `run`. The core gains it notebook validation, the width
     cap and the table normalization.
   - **PHYS-1140**: `course_data=generate_course_data`, an explicit
     `source_passes` list (`resolve_weekly` before `sources.stamp_dates`, then
     `stamp_visibility`, `stamp_course_data`), and a `pdf_name` hook whose
     pattern is `lab-(\d+)`, not `lab(\d+)`: the old one never matched
     `lab-01`, so every lab PDF was `index.pdf`. Its pages keep
     `pdf-download: true`; the platform finds the renamed PDF as the single
     one in the directory. `convert_boxed_math` and `check_weekly_lectures`:
     the first is core, the second stays.
   - **PHYS-4700**: `course_data=generate_course_data` and
     `source_passes=[stamp_course_data, *sources.DEFAULT_PASSES]`, with
     `stamp_course_data` rewritten on `sources.substitute_shortcodes` and its
     season fallback as the resolver. Its own `resolve_variables` goes; the
     core's runs because `_variables.yml` exists.
   - **PHYS-2150**: `course_data=generate_course_data` and the explicit list
     `[sources.validate_notebooks, resolve_weekly, resolve_syllabus,
     sources.stamp_dates, stamp_rubrics, stamp_course_data,
     stamp_visibility]`. `resolve_weekly` and `resolve_syllabus` call
     `ws.add_date_dep(page, *partials)` instead of returning tuples, and a
     small pass before `stamp_dates` registers the rubric YAMLs the same way,
     so the instructor guide's date still follows its sources. The
     lab-guide warning goes; the gate covers it.

   Every course pass takes `(ws, verbose)`, reads through `ws.read`, writes
   through `ws.write`, and raises `physicslabs_build.BuildError` to stop the
   build. Course data must read YAML through `sources.load_yaml`, which fails
   the build when PyYAML is missing rather than skipping.

5. In both workflows (`quarto.yml`, `pr-check.yml`), add the step PHYS-3330
   and 4430 already have, before the build:

   ```yaml
   - name: Install Python dependencies
     run: python -m pip install --upgrade pip pyyaml
   ```

   The core fails the build when a pass needs PyYAML and it is missing; the
   old scripts warned and shipped literal shortcodes.

6. Rewrite the docs that described the old script: the "What build.py does"
   section of the build-and-deploy page (the steps are unchanged, the code
   lives in the extension, and `Requirements` gains PyYAML), the `build.py`
   bullet in `CLAUDE.md`, and the tree in `site/README.md`. PHYS-4700's
   troubleshooting row that blames a stale `.quarto` cache for the
   fontawesome abort describes PHYS-2150's old bug; delete it.
   PHYS-Python-Resources has neither a build-and-deploy page nor a
   `site/README.md`: its build notes are the Build section of `CLAUDE.md`
   and, in `site/docs/scope-and-conventions.qmd`, the "PDFs use the
   extension too" bullet plus the shortcode-resolution callout that sent
   courses to PHYS-4430's `resolve_variables()` as the reference
   implementation (the core's `sources.resolve_variables` now). Grep the
   repository for `build.py` rather than trusting the page names above.

7. Verify locally: `python build.py -v` must end in `Done.`, list every page
   under `Step 3/3` as `OK`, and leave `git status` clean; then the checks in
   step 9 above. Image filenames must not contain spaces: Quarto's own Typst
   compile cannot open the percent-encoded path, aborts the project render
   there, and the build then fails with "typst render incomplete" naming
   every page after it. Rename the file.

8. After the merge, once Build & Deploy has run:

   ```sh
   git fetch origin deploy/django
   git ls-tree -r --name-only origin/deploy/django | grep '\.pdf$' | sort | diff /tmp/pdfs-before.txt -
   ```

   No output means the same PDFs at the same paths. PHYS-1140 is the
   exception: its lab PDFs change from `index.pdf` to `phys1140-labNN.pdf`,
   which is the fix. Then step 11 above.

Update this document when a step turns out to be wrong.
