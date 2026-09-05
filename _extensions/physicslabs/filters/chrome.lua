-- physicslabs chrome filter (HTML only).
--
-- Injects the CU Boulder header, nav bar, footer and back-to-top button as raw
-- HTML blocks around the page body. The header title comes from
-- `physicslabs.title` in _quarto.yml. The after-body script moves the chrome
-- out of Quarto's grid. Site navigation comes from _nav.yml (nav-to-sidebar.py),
-- the same source the platform uses, so there is no preview-only menu here.
--
-- The body itself is left untouched: Pandoc builds the table of contents only
-- from top-level sections, so wrapping them in a container would empty it.
-- The platform's content stylesheets are retargeted to Quarto's own container
-- (`main.content`) by sync-css.py instead.

local logos = dofile(quarto.utils.resolve_path("logos.lua"))

local function stringify(v)
  if v == nil then return nil end
  return pandoc.utils.stringify(v)
end

local function esc(s)
  s = s:gsub("&", "&amp;")
  s = s:gsub("<", "&lt;")
  s = s:gsub(">", "&gt;")
  s = s:gsub([["]], "&quot;")
  return s
end

local HOME_ICON = [[<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="currentColor" viewBox="0 0 16 16" aria-hidden="true"><path d="M8.707 1.5a1 1 0 0 0-1.414 0L.646 8.146a.5.5 0 0 0 .708.708L8 2.207l6.646 6.647a.5.5 0 0 0 .708-.708L13 5.793V2.5a.5.5 0 0 0-.5-.5h-1a.5.5 0 0 0-.5.5v1.293L8.707 1.5Z"/><path d="m8 3.293 6 6V13.5a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 2 13.5V9.293l6-6Z"/></svg>]]
local MOON = [[<svg class="cu-toggle-icon cu-icon-moon" xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>]]
local SUN = [[<svg class="cu-toggle-icon cu-icon-sun" xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="4.22" x2="19.78" y2="5.64"/></svg>]]
local UP = [[<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="18 15 12 9 6 15"/></svg>]]

local function header_html(title, subtitle)
  return table.concat({
    [[<header class="cu-header" role="banner">]],
    [[<a href="#quarto-document-content" class="cu-skip-link">Skip to main content</a>]],
    [[<div class="cu-header-row"><div class="cu-header-row-inner">]],
    [[<a href="https://www.colorado.edu" class="cu-logo" aria-label="University of Colorado Boulder">]],
    [[<img id="cu-header-logo" src="]], logos.light, [[" data-logo-light="]], logos.light,
    [[" data-logo-dark="]], logos.dark, [[" alt="University of Colorado Boulder"></a>]],
    [[</div></div>]],
    [[<div class="cu-header-title"><div class="cu-header-title-inner">]],
    [[<h1 class="cu-header-h1"><a id="cu-header-home-link" href="">]], esc(title), [[</a></h1>]],
    [[<p class="cu-header-subtitle">]], esc(subtitle), [[</p>]],
    [[</div></div></header>]],
    [[<nav class="cu-header-nav" role="navigation" aria-label="Site navigation"><div class="cu-header-nav-inner">]],
    [[<div class="cu-header-nav-start">]],
    [[<a id="cu-header-home-btn" href="" class="cu-header-home-btn" title="Home" aria-label="Home">]], HOME_ICON, [[</a>]],
    [[</div>]],
    [[<div class="cu-header-actions">]],
    [[<a href="" class="quarto-color-scheme-toggle" onclick="window.quartoToggleColorScheme(); return false;" title="Toggle dark mode" aria-label="Toggle dark mode">]],
    MOON, SUN, [[</a></div></div></nav>]]
  })
end

local function footer_html()
  return table.concat({
    [[<button class="cu-back-to-top" aria-label="Back to top" title="Back to top">]], UP, [[</button>]],
    [[<footer class="cu-footer" role="contentinfo"><div class="cu-footer-content">]],
    [[<div class="cu-footer-info"><strong>Physics Undergraduate Laboratories</strong><br>]],
    [[Department of Physics<br>University of Colorado Boulder</div>]],
    [[<div class="cu-footer-brand"><img id="cu-footer-logo" src="]], logos.beboulder, [[" alt="Be Boulder">]],
    [[<div class="cu-footer-brand-text">&copy; Regents of the University of Colorado</div>]],
    [[</div></div></footer>]]
  })
end

function Pandoc(doc)
  if not quarto.doc.is_format("html") then return doc end
  local pl = doc.meta.physicslabs or {}
  local title = stringify(pl.title) or "Physics Undergraduate Labs"
  local subtitle = stringify(pl.subtitle) or "Physics Undergraduate Labs"

  local blocks = pandoc.List({ pandoc.RawBlock("html", header_html(title, subtitle)) })
  blocks:extend(doc.blocks)
  blocks:insert(pandoc.RawBlock("html", footer_html()))
  doc.blocks = blocks
  return doc
end
