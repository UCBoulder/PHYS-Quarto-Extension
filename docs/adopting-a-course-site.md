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
  found" under `.quarto/typst/packages`), the local Quarto cache is stale:
  delete `site/.quarto` and rerun. On Windows, `build.py` can then die with a
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

Update this document when a step turns out to be wrong.
