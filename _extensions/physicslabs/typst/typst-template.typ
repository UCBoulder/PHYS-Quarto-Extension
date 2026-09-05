// CU Boulder Physics Undergraduate Labs — Quarto Typst template
//
// Defines the document layout function. Quarto calls it through
// typst-show.typ, which maps YAML metadata to the arguments. The `course`
// argument is the header stamp and comes from `physicslabs.title` in the
// site's _quarto.yml, so one setting names the course in the HTML header and
// on every PDF page.

// Color palette (CU Boulder brand)
#let cu-gold = rgb("#CFB87C")
#let cu-black = rgb("#000000")
#let cu-dark-gray = rgb("#565A5C")
#let cu-light-gray = rgb("#A2A4A3")
#let cu-light-gold = rgb("#F3F0E9")

// Largest height a figure may occupy, so a tall photo cannot claim a whole page.
#let fig-max-height = 3.4in

// Scale `body` down to `max-h` if it is taller, preserving aspect ratio.
// `layout` supplies the container width so percentage-sized content measures
// against the real text block rather than infinite space.
#let fit-height(body, max-h) = layout(size => context {
  let sized = block(width: size.width, body)
  let m = measure(sized)
  if m.height > max-h and m.height > 0pt {
    let s = max-h / m.height
    block(width: size.width * s, scale(s * 100%, origin: top + center, reflow: true, sized))
  } else {
    body
  }
})

#let article(
  title: none,
  authors: none,
  date: none,
  abstract: none,
  abstract-title: none,
  course: none,
  cols: 1,
  margin: (x: 0.75in, y: 0.5in),
  paper: "us-letter",
  lang: "en",
  region: "US",
  font: "Roboto",
  fontsize: 10.5pt,
  sectionnumbering: none,
  toc: false,
  toc-title: none,
  toc-depth: none,
  toc-indent: 1.5em,
  doc,
) = {
  // Document metadata for accessibility
  set document(
    title: title,
    author: if authors != none { authors.map(a => a.name) } else { () },
  )
  set text(lang: lang, region: region)

  // Page setup
  set page(
    paper: paper,
    margin: margin,
    header-ascent: 30%,
    footer-descent: 30%,
    header: context [
      #set text(9pt, fill: cu-dark-gray, font: font)
      #grid(
        columns: (1fr, 1fr),
        align: (left, right),
        [CU Boulder Physics Undergraduate Labs],
        [#if course != none { course }]
      )
      #v(6pt)
    ],
    footer: context [
      #v(6pt)
      #set text(9pt, fill: cu-dark-gray, font: font)
      #grid(
        columns: (1fr, 1fr),
        align: (left, right),
        [#if date != none { date }],
        [#counter(page).display()]
      )
    ]
  )

  // Base typography
  set text(font: font, size: fontsize, fill: cu-black)
  set par(leading: 0.65em, justify: false, spacing: 1.2em)

  // Heading hierarchy
  // Use #it (not #it.body) to preserve heading structure tags for PDF/UA-1.
  // H1 — document title
  show heading.where(level: 1): it => {
    set text(20pt, font: font, weight: "bold", fill: cu-black)
    block(below: 12pt)[
      #it
      #v(-16pt)
      #line(length: 100%, stroke: (paint: cu-gold, thickness: 2.5pt, cap: "square"))
    ]
  }

  // H2 — section headings with gold underline
  show heading.where(level: 2): it => {
    set text(14pt, font: font, weight: "bold", fill: cu-black)
    v(10pt)
    block(below: 10pt, breakable: false)[
      #it
      #v(-10pt)
      #line(length: 100%, stroke: (paint: cu-gold, thickness: 1.5pt, cap: "square"))
    ]
  }

  // H3 — subsections
  show heading.where(level: 3): it => {
    set text(12pt, font: font, weight: "bold", fill: cu-black)
    block(above: 18pt, below: 8pt, breakable: false)[#it]
  }

  // H4 — sub-subsections
  show heading.where(level: 4): it => {
    set text(11pt, font: font, weight: "medium", fill: cu-black)
    block(above: 14pt, below: 8pt, breakable: false)[#it]
  }

  // H5 — minor headings
  show heading.where(level: 5): it => {
    set text(11pt, font: font, weight: "regular", style: "italic", fill: cu-black)
    block(above: 12pt, below: 8pt, breakable: false)[#it]
  }

  // Lists
  set list(indent: 20pt, body-indent: 8pt, spacing: 8pt, marker: ("•", "◦", "‣"))
  set enum(indent: 20pt, body-indent: 8pt, spacing: 8pt)
  show list: it => { set par(spacing: 6pt); v(4pt); it }
  show enum: it => { set par(spacing: 6pt); v(4pt); it }

  // Links — blue
  show link: it => {
    set text(fill: rgb("#096FAE"))
    it
  }

  // Figures — numbered for cross-referencing
  //
  // Quarto emits bare `image()` calls, which Typst renders at the image's
  // natural size capped at the text width. Portrait photos therefore fill the
  // whole text block and push the surrounding prose to the next page, so a
  // guide with several tall photos ends up one photo per page. Cap image
  // figures at `fig-max-height` to keep them inline with the text; tables
  // (kind "quarto-float-tbl") are left alone so they stay legible.
  set figure(numbering: "1")
  show figure: it => {
    set align(center)
    let body = if it.kind == "quarto-float-fig" {
      fit-height(it.body, fig-max-height)
    } else {
      it.body
    }
    block(above: 8pt, below: 16pt)[
      #box(stroke: none, radius: 3pt, clip: true, body)
      #v(4pt)
      #set text(9pt, style: "italic")
      #it.caption
    ]
  }

  // Blockquotes — gold left border, light gold background
  show quote: it => {
    block(
      fill: cu-light-gold,
      inset: (left: 12pt, right: 12pt, top: 8pt, bottom: 8pt),
      radius: 4pt,
      stroke: (left: 4pt + cu-gold),
      width: 100%,
      above: 10pt,
      below: 10pt,
    )[
      #set text(style: "italic")
      #it.body
    ]
  }

  // Tables — booktabs with alternating row shading
  set table(
    stroke: none,
    inset: (x: 10pt, y: 5pt),
    fill: (_, row) => if calc.odd(row) { cu-light-gold },
  )
  show table: it => {
    set text(10pt)
    block(spacing: 10pt)[#it]
  }
  show table.header: it => {
    set text(weight: 700)
    it
  }

  // Code — inline
  show raw.where(block: false): it => {
    box(fill: cu-light-gold, inset: (x: 4pt, y: 1pt), radius: 2pt)[
      #set text(font: ("Consolas", "DejaVu Sans Mono"), size: 9.5pt)
      #it
    ]
  }

  // Code — blocks
  // Render highlighted lines directly rather than embedding #it. Typst's native
  // raw block adds a gray (#e6e6e6) background that overrides our cu-light-gold
  // fill, creating a visible color mismatch inside the styled container.
  show raw.where(block: true): it => {
    block(fill: cu-light-gold, inset: (x: 12pt, y: 8pt), radius: 4pt, width: 100%)[
      #set text(font: ("Consolas", "DejaVu Sans Mono"), size: 9pt)
      #{it.lines.map(l => l.body).join(linebreak())}
    ]
  }

  // Footnotes
  show footnote.entry: it => {
    set text(9pt, fill: cu-dark-gray)
    it
  }

  // Math. Quarto emits `numbering:` on labeled equations only, matching the
  // HTML output; a global `set math.equation(numbering: ...)` here would also
  // number every unlabeled display equation, so there is none.
  show math.equation.where(block: true): set block(above: 10pt, below: 10pt)

  // Section numbering (if enabled via number-sections in _quarto.yml)
  set heading(numbering: sectionnumbering)

  // Title block
  if title != none {
    align(left)[
      #block(below: 12pt)[
        #set text(20pt, weight: "bold", fill: cu-black)
        #title
        #v(-16pt)
        #line(length: 100%, stroke: (paint: cu-gold, thickness: 2.5pt, cap: "square"))
      ]
    ]
  }

  // Table of contents
  if toc {
    let title = if toc-title == none { auto } else { toc-title }
    block(above: 0em, below: 2em)[
      #outline(title: title, depth: if toc-depth != none { toc-depth } else { none }, indent: toc-indent)
    ]
  }

  // Main body
  if cols == 1 { doc } else { columns(cols, doc) }
}
