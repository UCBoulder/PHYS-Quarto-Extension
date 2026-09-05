"""The .typ post-processor.

Every input is a line Quarto 1.9.37 wrote into a kept .typ: the fixture's
guide/elements.typ (rendered with the extension, so `syntax-highlighting:
idiomatic`), or a scratch page rendered without it for the Skylighting forms.
"""

from pathlib import Path

import pytest

from physicslabs_build import Page, typ

# --- guide/elements.typ ------------------------------------------------------

LABELED = ('#math.equation(block: true, numbering: equation-numbering, '
           '[ $ I \\( x \\) = I_0 / 2 [1 - "erf" (frac(sqrt(2) thin x, w))] $ ])<eq-knife>')
INLINE = "Inline $E = h nu$ and display:"
UNLABELED = "$ E = m c^2 $"
ALIGNED = "$ P & = I V\\\n & = I^2 R $"
BOXED = "$ #box(stroke: black, inset: 3pt, [$ F = m a $]) $"
FENCE = ('```python\n'
         'ax.set_xlabel("$V$ (V)")   # matplotlib reads the $...$ itself\n'
         '```')
IMAGE_WITH_ALT = ('#box(image("beam-profile.png", alt: "Intensity profile of a Gaussian beam, '
                  'brightest at the center and fading toward every edge."))')
WIDE_IMAGE = ('#box(image("wide%20plot.png", alt: "A horizontal gradient from dark on the left '
              'to light on the right.", width: 20cm))')
TABLE = ('#table(\n'
         '  columns: 3,\n'
         '  align: (auto,auto,auto,),\n'
         '  table.header([Quantity], [Symbol], [Unit],),\n'
         '  table.hline(),\n'
         '  [Beam radius], [$w$], [m],\n'
         '  [Voltage], [$V$], [V],\n'
         ')')
FA_IMPORT = '#import "@preview/fontawesome:0.5.0": *\n'
FA_COMMENT = '// 2023-10-09: #fa-icon("fa-info") is not working, so we\'ll eval "#fa-info()" instead\n'

# The end of the `#show: doc => article(...)` call typst-show.typ emits, which
# separates the template preamble from the page body.
PREAMBLE = ('#show: doc => article(\n'
            '  title: [Content Elements],\n'
            '  toc-title: "Table of contents",\n'
            '  toc-depth: 3,\n'
            '  cols: 1,\n'
            '  doc,\n'
            ')\n')

# The fixture's markdown for the two figures.
FIXTURE_QMD = ('---\ntitle: "Content Elements"\n---\n\n'
               '![A Gaussian beam profile.](beam-profile.png){#fig-beam fig-alt="Intensity profile of a '
               'Gaussian beam, brightest at the center and fading toward every edge."}\n\n'
               '![A plot declared wider than the page.](<wide plot.png>){fig-alt="A horizontal gradient '
               'from dark on the left to light on the right." width="20cm"}\n')

# --- a page rendered without the extension (Pandoc Skylighting) ----------------

SKYLIGHTING = ('#Skylighting(([#NormalTok("ax.set_xlabel(");#StringTok("\\"$V$ (V)\\"");'
               '#NormalTok(")   ");#CommentTok("# a $ in a string");],\n'
               '[#BuiltInTok("print");#NormalTok("(x)");],));\n'
               'Inline #NormalTok("a $b$ c"); and math $x^2$ here.')


def page(tmp_path: Path, qmd_text: str = FIXTURE_QMD, verbose: bool = False) -> Page:
    qmd = tmp_path / "elements.qmd"
    qmd.write_text(qmd_text, encoding="utf-8")
    return Page(qmd=qmd, typ=qmd.with_suffix(".typ"), rel=Path("guide/elements.qmd"), verbose=verbose)


# ---------------------------------------------------------------------------
# Math
# ---------------------------------------------------------------------------


def test_labeled_equation_with_the_bare_numbering_identifier_gets_alt_text():
    out = typ.add_math_alt_text(PREAMBLE + LABELED + "\n")
    body = out[len(PREAMBLE):]
    assert body.startswith('#math.equation(block: true, numbering: equation-numbering, alt: "')
    assert "I subscript 0" in body
    assert body.rstrip().endswith("])<eq-knife>")
    # The numbered pass leaves the content between plain `$`, so the inline
    # pass wraps it once more. That nested form is what every course script
    # produced, and Typst accepts it; see docs/build-core.md, section 7.
    assert ('[ #box[#math.equation(alt: "I ( x ) = I subscript 0 / 2 [1 - \\"erf\\" (frac(sqrt(2) thin x, w))]", '
            '$ I \\( x \\) = I_0 / 2 [1 - "erf" (frac(sqrt(2) thin x, w))] $)] ]') in body


def test_unlabeled_display_equation_gets_alt_text():
    body = typ.add_math_alt_text(PREAMBLE + UNLABELED + "\n")[len(PREAMBLE):]
    assert body == '#math.equation(block: true, alt: "E = m c superscript 2", $E = m c^2$)\n'


def test_multi_line_aligned_equation_is_one_equation_with_alt_text():
    body = typ.add_math_alt_text(PREAMBLE + ALIGNED + "\n")[len(PREAMBLE):]
    assert body.count("#math.equation(block: true, alt:") == 1
    assert body.startswith('#math.equation(block: true, alt: "P = I V = I superscript 2 R"')
    # Nothing is left as a bare `$ ... $` block for Typst to reject under UA-1.
    assert not body.startswith("$ ")


def test_inline_math_gets_alt_text():
    body = typ.add_math_alt_text(PREAMBLE + INLINE + "\n")[len(PREAMBLE):]
    assert body == 'Inline #box[#math.equation(alt: "E = h nu", $E = h nu$)] and display:\n'


def test_a_dollar_inside_a_fenced_code_block_is_not_math():
    text = PREAMBLE + FENCE + "\n\n" + INLINE + "\n"
    body = typ.add_math_alt_text(text)[len(PREAMBLE):]
    assert body.startswith(FENCE)
    assert '#box[#math.equation(alt: "E = h nu"' in body


def test_a_dollar_inside_a_skylighting_block_or_token_is_not_math():
    body = typ.add_math_alt_text(PREAMBLE + SKYLIGHTING + "\n")[len(PREAMBLE):]
    block, prose = body.split("\nInline ", 1)
    assert block + "\n" == SKYLIGHTING.split("\nInline ")[0] + "\n"
    assert prose.startswith('#NormalTok("a $b$ c"); and math #box[#math.equation(alt: "x superscript 2", $x^2$)] here.')


def test_the_preamble_is_left_alone():
    preamble = PREAMBLE.replace("  cols: 1,\n", '  pattern: regex("\\$[^$]+\\$"),\n  cols: 1,\n')
    out = typ.add_math_alt_text(preamble + INLINE + "\n")
    assert out.startswith(preamble)
    assert "#math.equation" not in out[:len(preamble)]


def test_boxed_math_leaves_math_mode():
    out = typ.convert_boxed_math(BOXED)
    assert out == "#align(center, box(stroke: 0.5pt + black, inset: 5pt, [$ F = m a $]))"
    aligned = "$ a & = b\\\n#box(stroke: black, inset: 3pt, [$ c = d $]) $"
    assert typ.convert_boxed_math(aligned) == "$ a & = b\\\nc = d $"


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------


def test_percent_encoded_image_path_is_decoded_and_oversize_width_capped():
    out = typ.cap_image_widths(typ.decode_image_paths(WIDE_IMAGE))
    assert 'image("wide plot.png", alt:' in out
    assert "width: 100%" in out
    assert "20cm" not in out


def test_widths_within_the_text_block_are_kept():
    assert typ.cap_image_widths('image("a.png", width: 15cm)') == 'image("a.png", width: 15cm)'


def test_image_alt_text_is_injected_from_fig_alt_when_quarto_did_not_write_it(tmp_path: Path, capsys):
    # Quarto 1.8 emitted image() without alt; the fig-alt comes from the page.
    text = PREAMBLE + '#box(image("beam-profile.png"))\n#box(image("wide%20plot.png", width: 20cm))\n'
    text = typ.decode_image_paths(text)
    out = typ.add_image_alt_text(text, page(tmp_path, verbose=True).qmd, verbose=True)
    assert 'image("beam-profile.png", alt: "Intensity profile of a Gaussian beam' in out
    assert 'image("wide plot.png", alt: "A horizontal gradient' in out
    assert "image alt text: 2/2 image(s) updated" in capsys.readouterr().out


def test_image_alt_text_already_written_by_quarto_is_left_alone(tmp_path: Path):
    text = PREAMBLE + IMAGE_WITH_ALT + "\n"
    assert typ.add_image_alt_text(text, page(tmp_path).qmd) == text


# ---------------------------------------------------------------------------
# Tables, callouts
# ---------------------------------------------------------------------------


def test_integer_table_columns_become_fractions_and_page_columns_do_not():
    out = typ.normalize_table_columns("#set page(columns: 1)\n" + TABLE)
    assert out.startswith("#set page(columns: 1)\n#table(\n  columns: (1fr, 1fr, 1fr,),\n  align:")


def test_fontawesome_import_and_icon_calls_are_removed():
    out = typ.strip_fontawesome(FA_IMPORT + FA_COMMENT + "icon: fa-info(),\n")
    assert FA_IMPORT not in out
    assert out == FA_COMMENT.replace("#fa-info()", "#none") + "icon: none,\n"


# ---------------------------------------------------------------------------
# The chain
# ---------------------------------------------------------------------------


def test_core_chain_over_the_fixture_body(tmp_path: Path):
    body = "\n\n".join([FENCE, IMAGE_WITH_ALT, WIDE_IMAGE, TABLE, INLINE, LABELED, UNLABELED, ALIGNED, BOXED]) + "\n"
    out = typ.postprocess(FA_IMPORT + PREAMBLE + body, page(tmp_path), typ.CORE_CHAIN)
    # Every equation and image carries alt text, in the forms Typst accepts:
    # two images, the inline equation, the labeled one (outer block plus the
    # nested inline wrap), the unlabeled and aligned ones, the boxed one, and
    # the two inline equations in table cells.
    assert out.count("alt:") == 2 + 1 + 2 + 1 + 1 + 1 + 2
    assert "fontawesome" not in out
    assert "columns: (1fr, 1fr, 1fr,)," in out
    assert "width: 100%" in out
    assert FENCE in out


def test_resolve_filters_appends_a_plain_list_and_takes_a_chain_as_is():
    extra = typ.pure(lambda text: text)
    assert typ.resolve_filters(None) == typ.CORE_CHAIN
    assert typ.resolve_filters([extra]) == [*typ.CORE_CHAIN, extra]
    assert typ.resolve_filters(typ.chain(before=[extra])) == [extra, *typ.CORE_CHAIN]
    assert typ.resolve_filters(typ.chain(after=[extra])) == [*typ.CORE_CHAIN, extra]


def test_pure_adapts_a_text_transform_to_the_filter_signature(tmp_path: Path):
    filt = typ.pure(str.upper)
    assert filt("abc", page(tmp_path)) == "ABC"
    assert filt.__name__ == "upper"


@pytest.mark.parametrize("content, alt", [
    ("V_(oc)", "V subscript oc"),
    ("x^2", "x superscript 2"),
    ("x_i", "x subscript i"),
    ('"erf"', '\\"erf\\"'),
    ("a ~ b", "a approximately b"),
])
def test_generate_alt_text(content, alt):
    assert typ._generate_alt_text(content) == alt
