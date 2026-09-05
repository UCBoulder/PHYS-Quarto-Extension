# PHYS-Quarto-Extension

The `physicslabs` Quarto project type for CU Boulder Physics Undergraduate Labs
course sites. It makes a `quarto preview` page look like the same page on
[physicslabs.colorado.edu](https://physicslabs.colorado.edu), so authors can
judge a page locally before it ships, and it keeps that look in one place
instead of a copy per course repository.

## Install in a course site

From the directory that holds `_quarto.yml`:

```sh
quarto add UCBoulder/PHYS-Quarto-Extension
```

Quarto vendors the files under `_extensions/UCBoulder/physicslabs/`; commit
them. Later releases are picked up with:

```sh
quarto update UCBoulder/PHYS-Quarto-Extension
```

Pin a release with `@`, for example `quarto add UCBoulder/PHYS-Quarto-Extension@v0.1.0`.

**Installing into a site that already declares `project: type: physicslabs`**
(for example a fresh adoption where `_quarto.yml` was edited first, or a
checkout whose `_extensions/` was deleted) fails with "Unsupported project
type physicslabs": Quarto reads `_quarto.yml` before it installs anything.
Move `_quarto.yml` aside for the `quarto add`, then restore it.

Then in `_quarto.yml`:

```yaml
project:
  type: physicslabs

website:
  title: "Quantum Forge"

physicslabs:
  title: "Quantum Forge"                    # HTML header title and PDF page stamp
  subtitle: "Physics Undergraduate Labs"    # optional; this is the default
```

Site navigation comes from `_nav.yml`, the same file the platform reads; there
is no preview-only menu.

Add `/_physicslabs-sidebar.yml` to the site's `.gitignore`; see below.

Moving an existing course site off its hand-maintained theme is a longer
recipe: see [docs/adopting-a-course-site.md](docs/adopting-a-course-site.md).

## What it provides

- **`project: type: physicslabs`** sets the website defaults every course site
  shares: numbered sections, a sidebar table of contents, light and dark
  Bootstrap themes, no Quarto navbar, English language and date format.
- **CU Boulder chrome.** The header, nav bar (home button, dark-mode toggle,
  mobile menu and table of contents), footer and back-to-top button are
  injected as raw HTML by `filters/chrome.lua` and moved out of Quarto's grid
  by `html/after-body.html`. Logos are embedded as data URIs.
- **The platform's content stylesheets** in `css/`. They are copied from
  `physicslabs/static/css/` in PHYS-Undergraduate-Labs-Web by
  `tools/sync-css.py`, with one change: the platform scopes content rules to
  its `.quarto-page-content` container, and the copy retargets that selector to
  Quarto's `main.content`. Headings, callouts, code, tables, figures, math and
  cross-references render with the platform's own rules.
- **The course sidebar from `_nav.yml`.** The platform builds its left
  navigation from `_nav.yml`; `nav-to-sidebar.py` runs as a Quarto pre-render
  script, translates that file into a docked `website.sidebar`, and writes
  `_physicslabs-sidebar.yml`, which the extension lists under
  `metadata-files`. The file is a build artifact and is rewritten only when
  its content changes, because `quarto preview` watches metadata files. Paths
  that resolve to no page are reported in the render log. The sidebar is
  styled after the platform's course sidebar; for a page `_nav.yml` does not
  list, the nearest listed ancestor is marked active and its section expanded.
- **A dark-mode bridge.** The platform switches modes on `html[data-theme]`;
  `html/head.html` sets it from Quarto's stored scheme before first paint and
  `html/after-body.html` keeps it in step with the toggle. Roboto and Roboto
  Condensed load from Google Fonts, as on the platform.
- **The platform's copy button** on code blocks, added the same way the
  platform's `quarto-content.js` adds it. Quarto's own button is turned off.
- **`css/quarto-bridge.css`**, the one hand-written stylesheet: each rule
  documents a place where Quarto's markup differs from the platform's.
- **Chrome-only SCSS** in `scss/`. Content styling is deliberately absent so it
  cannot drift from the platform.

- **The accessible-PDF Typst format.** `format.typst` defaults (Roboto from the
  extension's `fonts/`, US letter, margins, numbered sections, idiomatic
  syntax highlighting, `keep-typ`) and the CU template partials in `typst/`.
  The page header stamp is `physicslabs.title`, so one setting names the
  course in the HTML header and on every PDF page. The template is the union
  of the fixes the course repositories had accumulated separately: figures are
  capped at a maximum height, code blocks keep their gold fill, and only
  labeled equations are numbered, as in the HTML. Course build scripts keep
  the `.typ`, post-process it, and compile with standalone Typst for
  PDF/UA-1; that part stays in each repository.

The chrome filter only acts on HTML output.

## Maintenance

- `python tools/sync-css.py [path-to-platform-checkout]` refreshes
  `_extensions/physicslabs/css/` from the platform. Without an argument it
  looks for a sibling `PHYS-Undergraduate-Labs-Web` checkout.
- `python tools/gen-logos.py` regenerates `filters/logos.lua` after a logo in
  `_extensions/physicslabs/assets/img/` changes.
- A stylesheet change on the platform's `main` syncs itself: the platform's
  `sync-quarto-extension` workflow runs `tools/sync-css.py`, bumps the patch
  version, and pushes the commit and an annotated `vX.Y.Z` tag over a deploy
  key. Pull before committing here; that sync may have advanced `main`.
- Pushing any `v*` tag makes CI publish the GitHub release once the fixture
  renders. A hand-made release is: bump `version` in
  `_extensions/physicslabs/_extension.yml`, commit, `git tag -a vX.Y.Z`, and
  push both.
- `quarto render` at the repository root renders the fixture site in `guide/`,
  which exercises every element the platform styles. CI does the same on every
  push.

## Layout

```text
_extensions/physicslabs/
  _extension.yml          project-type and html format contributions
  css/                    platform content stylesheets (generated by tools/sync-css.py)
  css/quarto-bridge.css   hand-written rules for Quarto/platform markup differences
  scss/                   chrome.scss, light.scss, dark.scss
  filters/chrome.lua      header, nav bar, footer injection
  filters/logos.lua       logo data URIs (generated by tools/gen-logos.py)
  html/head.html          fonts and the data-theme bootstrap
  html/after-body.html    chrome placement, toggle sync, sidebar toggle, mobile TOC,
                          copy buttons, back-to-top
  nav-to-sidebar.py       pre-render: _nav.yml -> _physicslabs-sidebar.yml
  typst/                  typst-template.typ, typst-show.typ (accessible-PDF format)
  fonts/                  Roboto for the Typst build (Condensed is HTML-only, via Google Fonts)
  assets/img/             logo sources
tools/                    maintainer scripts (not installed into course sites)
_quarto.yml, _nav.yml, index.qmd, guide/   fixture site rendered by CI
```
