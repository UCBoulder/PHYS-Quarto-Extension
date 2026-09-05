"""Post-processing of a kept `.typ` file before the PDF/UA-1 compile.

Quarto writes the `.typ` beside the page (`keep-typ: true` in the extension's
Typst format). Standalone Typst 0.14 with `--pdf-standard ua-1` refuses any
image or equation without alt text, so the two alt-text passes run last, after
every filter that rewrites `image()` calls or math. The other filters repair
what Quarto or Pandoc emit for this template: Font Awesome icon calls the
callouts carry, percent-encoded image paths, `\boxed{}` rendered as a `#box`
inside math, explicit widths wider than the text block, and integer table
column counts.

Every transform here is a pure function on the file text. `CORE_CHAIN` is the
order the core runs them in; a wrapper appends its own filters after it, or
builds another order with `chain()`.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, Iterable
from urllib.parse import unquote

from .site import Page, TypFilter

# ---------------------------------------------------------------------------
# Math alt text
# ---------------------------------------------------------------------------


def _protect_code_spans(text: str) -> tuple[str, dict[str, str]]:
    """Replace code spans/blocks with placeholders to avoid regex false matches.

    Four forms, in this order: Skylighting code blocks (`#Skylighting((...));`,
    what Quarto emits without `syntax-highlighting: idiomatic`), fenced raw
    blocks (what it emits with it), inline raw spans, and inline Skylighting
    tokens such as `#NormalTok("$B$1")`. Each can contain `$` characters (a
    matplotlib label like "$V$ (V)") that the math passes would otherwise turn
    into equations.
    """
    placeholders: dict[str, str] = {}
    counter = [0]

    def replace_code(match: re.Match) -> str:
        key = f"\x01CODE{counter[0]}\x01"
        placeholders[key] = match.group(0)
        counter[0] += 1
        return key

    # Typst-rendered code blocks: Quarto emits #Skylighting((...));. Protect the
    # whole block before anything inside it can match.
    text = re.sub(r"#Skylighting\([\s\S]*?\)\);", replace_code, text)
    text = re.sub(r"```[\s\S]*?```", replace_code, text)
    text = re.sub(r"`[^`\n]+`", replace_code, text)

    # Inline syntax-highlighting tokens (e.g. #NormalTok("$B$1")). Skip tokens
    # that already contain placeholders from the steps above.
    def replace_tok(match: re.Match) -> str:
        if "\x01" in match.group(0):
            return match.group(0)
        return replace_code(match)

    text = re.sub(r"#[A-Z][a-zA-Z]*Tok\([^)]*\);?", replace_tok, text)
    return text, placeholders


def _restore_code_spans(text: str, placeholders: dict[str, str]) -> str:
    """Restore protected code spans from placeholders."""
    for key, value in placeholders.items():
        text = text.replace(key, value)
    return text


def _generate_alt_text(math_content: str) -> str:
    """Convert Typst math notation to human-readable alt text."""
    alt = math_content
    alt = re.sub(r"_\(([^)]+)\)", r" subscript \1", alt)   # V_(oc) -> V subscript oc
    alt = re.sub(r"\^(\w+)", r" superscript \1", alt)       # x^2 -> x superscript 2
    alt = re.sub(r"_(\w)", r" subscript \1", alt)            # x_i -> x subscript i
    alt = alt.replace("~", " approximately ")
    alt = alt.replace("&", "")
    alt = alt.replace("\\", " ")
    alt = " ".join(alt.split())
    # Escape quotes for Typst string literals
    alt = alt.replace('"', '\\"')
    return alt


def _process_quarto_block_math(typ_content: str) -> str:
    """Add alt text to Quarto-generated numbered block equations.

    Quarto outputs either form, depending on whether the equation is labeled:
        #math.equation(block: true, numbering: "(1)", [ $ CONTENT $ ])
        #math.equation(block: true, numbering: equation-numbering, [ $ CONTENT $ ])<label>

    We inject alt: "..." before the content bracket. Matching both the quoted
    string and the bare `equation-numbering` variable matters: labeled
    (cross-referenced) equations use the variable, and missing them leaves the
    outer block equation without alt text, a hard PDF/UA-1 failure.
    """
    def replace_quarto_block(match: re.Match) -> str:
        prefix = match.group(1)   # #math.equation(block: true, numbering: "(1)",
        content = match.group(2)  # math content between $ $
        suffix = match.group(3)   # ])<label> or ])
        alt = _generate_alt_text(content)
        return f'{prefix} alt: "{alt}", [ $ {content} $ {suffix}'

    return re.sub(
        r'(#math\.equation\(block:\s*true,\s*numbering:\s*(?:"[^"]*"|[\w-]+),)\s*\[\s*\$\s*(.*?)\s*\$\s*(\]\)(?:<[^>]+>)?)',
        replace_quarto_block,
        typ_content,
        flags=re.DOTALL,
    )


def _process_standalone_block_math(typ_content: str) -> str:
    """Add alt text to unnumbered standalone block math.

    Typst block math: '$ content $' on its own line(s). DOTALL lets the match
    span lines, which an aligned derivation (`&=` rows joined by `\\`) needs;
    without it the equation keeps no alt text and the PDF/UA-1 compile fails.
    Uses null-byte placeholders so the inline pass won't rematch.
    """
    def replace_block(match: re.Match) -> str:
        content = match.group(1)
        alt = _generate_alt_text(content)
        return f'#math.equation(block: true, alt: "{alt}", \x00{content}\x00)'

    return re.sub(
        r"^\$ (.*?) \$$", replace_block, typ_content,
        flags=re.MULTILINE | re.DOTALL,
    )


def _process_inline_math(typ_content: str) -> str:
    """Add alt text to inline math: $content$ -> #box[#math.equation(alt: ..., $content$)]."""
    def replace_inline(match: re.Match) -> str:
        content = match.group(1)
        alt = _generate_alt_text(content)
        return f'#box[#math.equation(alt: "{alt}", ${content}$)]'

    # Negative lookbehind: skip escaped dollar signs (\$) used for currency
    return re.sub(r"(?<!\\)\$([^$]+)\$", replace_inline, typ_content)


def _split_preamble(typ_content: str) -> tuple[str, str]:
    """Split the Quarto/Pandoc template preamble from the document body.

    The preamble ends at the closing ')' of the '#show: doc => article(...)'
    call that typst-show.typ emits: the line "  doc," followed by ")".
    """
    split_marker = "\n  doc,\n)\n"
    split_pos = typ_content.find(split_marker)
    if split_pos == -1:
        # Fallback: try without leading newline
        split_marker = "  doc,\n)\n"
        split_pos = typ_content.find(split_marker)
    if split_pos != -1:
        boundary = split_pos + len(split_marker)
        return typ_content[:boundary], typ_content[boundary:]
    # No preamble found: process the entire file (shouldn't happen with Quarto)
    return "", typ_content


def add_math_alt_text(typ_content: str) -> str:
    """Add alt text to all math equations for PDF/UA-1 accessibility.

    Only processes the document BODY, not the Quarto/Pandoc template preamble
    (which contains $ signs in regex strings and Pandoc template variables).
    """
    preamble, body = _split_preamble(typ_content)

    body, code_placeholders = _protect_code_spans(body)
    body = _process_quarto_block_math(body)
    body = _process_standalone_block_math(body)
    body = _process_inline_math(body)
    body = body.replace("\x00", "$")
    body = _restore_code_spans(body, code_placeholders)

    return preamble + body


# ---------------------------------------------------------------------------
# Image alt text
# ---------------------------------------------------------------------------

QMD_IMAGE_ALT_RE = re.compile(
    r'\]\(([^)]+|<[^>]+>)\)\s*\{[^}]*?fig-alt="([^"]+)"',
    re.DOTALL,
)
TYPST_IMAGE_RE = re.compile(r'image\("([^"]+)"([^)]*)\)')


def extract_image_alt_texts(qmd_path: Path) -> dict[str, str]:
    """Read a .qmd file and return {filename: alt_text} for all fig-alt attributes."""
    text = qmd_path.read_text(encoding="utf-8")
    result: dict[str, str] = {}
    for match in QMD_IMAGE_ALT_RE.finditer(text):
        filename = match.group(1).split("/")[-1]  # bare filename
        # Strip angle brackets from filenames with spaces
        filename = filename.strip("<>")
        # Decode URL-encoded filenames (e.g., %20 -> space)
        filename = unquote(filename)
        alt_text = match.group(2)
        result[filename] = alt_text
    return result


def add_image_alt_text(typ_content: str, qmd_path: Path, verbose: bool = False) -> str:
    """Add alt text to image() calls for PDF/UA-1 accessibility.

    Reads fig-alt attributes from the corresponding .qmd source file and
    injects them as alt: parameters into Typst image() calls. Calls that
    already carry `alt:` (Quarto 1.9 writes it itself) are left alone.
    """
    if not qmd_path.exists():
        if verbose:
            print(f"    {qmd_path.name}: .qmd not found, skipping image alt text")
        return typ_content

    alt_texts = extract_image_alt_texts(qmd_path)
    if not alt_texts:
        if verbose:
            print(f"    image alt text: 0 fig-alt attributes found in {qmd_path.name}")
        return typ_content

    # Split preamble from body (same boundary as add_math_alt_text)
    preamble, body = _split_preamble(typ_content)

    updated = 0
    total = 0

    def replace_image(match: re.Match) -> str:
        nonlocal updated, total
        total += 1
        filename = match.group(1)
        rest = match.group(2)

        # Forward-compat: skip if alt already present
        if "alt:" in rest:
            return match.group(0)

        basename = filename.split("/")[-1]
        alt = alt_texts.get(basename)
        if alt is None:
            return match.group(0)

        # Escape for Typst string literal
        alt_escaped = alt.replace("\\", "\\\\").replace('"', '\\"')
        updated += 1
        return f'image("{filename}", alt: "{alt_escaped}"{rest})'

    body = TYPST_IMAGE_RE.sub(replace_image, body)

    if verbose:
        print(f"    image alt text: {updated}/{total} image(s) updated")

    return preamble + body


# ---------------------------------------------------------------------------
# Repairs to what Quarto and Pandoc emit
# ---------------------------------------------------------------------------


def strip_fontawesome(typ_content: str) -> str:
    """Remove Font Awesome icon calls from Quarto callouts.

    Quarto always emits FA icons in Typst callouts regardless of callout-icon
    settings. These cause PDF/UA-1 errors when FA fonts aren't installed.
    Remove the import and icon function calls.
    """
    # Remove the fontawesome import line
    typ_content = re.sub(
        r'#import "@preview/fontawesome:[^"]*": \*\n?', "", typ_content
    )
    # Replace icon function calls with none (they're values for icon: parameters)
    typ_content = re.sub(r'fa-[a-z-]+\(\)', "none", typ_content)
    return typ_content


def decode_image_paths(typ_content: str) -> str:
    """URL-decode image() source paths.

    Quarto percent-encodes image paths (e.g. emits
    ``image("beam profile.png")`` as ``image("beam%20profile.png")``). Browsers
    decode this automatically so the HTML build works, but standalone Typst
    looks for the literal ``%20`` name and fails. Decode the path so Typst
    finds the real file.
    """
    return re.sub(
        r'image\("([^"]+)"',
        lambda m: 'image("' + unquote(m.group(1)) + '"',
        typ_content,
    )


def convert_boxed_math(typ_content: str) -> str:
    r"""Fix Pandoc's \boxed{} output for Typst math blocks.

    Pandoc converts LaTeX \boxed{content} to #box(stroke: black, inset: 3pt, [$ content $])
    inside Typst math. This doesn't work because #box() is a content function that
    can't appear inside math mode.

    Case 1, a standalone block equation:
        $ #box(stroke: black, inset: 3pt, [$ content $]) $
      becomes:
        #align(center, box(stroke: 0.5pt + black, inset: 5pt, [$ content $]))

    Case 2, the last line of an aligned block:
        $ a &= b\
        #box(stroke: black, inset: 3pt, [$ content $]) $
      The box is stripped and the content inlined as regular math.
    """
    # Case 1: standalone block equation that is entirely a box.
    # The outer $ ... $ wraps a single #box() call: lift the box outside
    # and center it to match normal block math alignment.
    typ_content = re.sub(
        r"^\$ #box\(stroke:\s*black,\s*inset:\s*3pt,\s*\[\$ (.*?) \$\]\) \$$",
        r"#align(center, box(stroke: 0.5pt + black, inset: 5pt, [$ \1 $]))",
        typ_content,
        flags=re.MULTILINE,
    )

    # Case 2: #box() inside a multi-line math block (e.g. aligned equations).
    # Strip the box wrapper and inline the math content directly.
    typ_content = re.sub(
        r"#box\(stroke:\s*black,\s*inset:\s*3pt,\s*\[\$ (.*?) \$\]\)",
        r"\1",
        typ_content,
    )
    return typ_content


def cap_image_widths(typ_content: str, max_cm: float = 17.0) -> str:
    """Cap oversized image widths to 100% of available text area.

    Quarto may emit image(width: 20cm) which exceeds the PDF text area
    (US letter with 0.75in margins = 17.78cm).  Replace with width: 100%
    so the image scales to fit.
    """
    def _cap(match: re.Match) -> str:
        full = match.group(0)
        def _replace_width(w: re.Match) -> str:
            if float(w.group(1)) > max_cm:
                return "width: 100%"
            return w.group(0)
        return re.sub(r"width:\s*(\d+(?:\.\d+)?)cm", _replace_width, full)

    return re.sub(r"image\([^)]+\)", _cap, typ_content)


def normalize_table_columns(typ_content: str) -> str:
    """Convert integer table column counts to fractional widths.

    Pandoc may emit ``#table(columns: N, ...)`` (auto-sized) for some tables;
    expand the integer to ``(1fr, 1fr, ...)`` so the table fills the text
    width. (Most tables already render as percentage arrays, which are left
    untouched.)

    Anchored to ``#table(`` so it never matches the page's
    ``#set page(columns: 1)`` setting. That must remain an integer, and a
    broad ``columns:`` match would corrupt it into an array.
    """
    def _expand(match: re.Match) -> str:
        prefix = match.group(1)   # "#table(" plus any trailing whitespace
        n = int(match.group(2))
        fracs = ", ".join(["1fr"] * n)
        # Trailing comma keeps a single column as a 1-element array: (1fr,).
        return f"{prefix}columns: ({fracs},),"
    return re.sub(r"(#table\(\s*)columns:\s*(\d+),", _expand, typ_content)


# ---------------------------------------------------------------------------
# The filter chain
# ---------------------------------------------------------------------------


def pure(fn: Callable[[str], str]) -> TypFilter:
    """Adapt a `str -> str` transform to the `(text, page) -> str` filter signature."""
    def filt(text: str, page: Page) -> str:
        return fn(text)
    filt.__name__ = getattr(fn, "__name__", "filter")
    filt.__doc__ = fn.__doc__
    return filt


def _image_alt_filter(text: str, page: Page) -> str:
    return add_image_alt_text(text, page.qmd, verbose=page.verbose)


# Alt text runs last so every earlier filter sees the original image() and
# math forms. Order matters within the repairs too: paths are decoded before
# alt text is matched by filename, and boxes leave math before math is wrapped.
CORE_CHAIN: list[TypFilter] = [
    pure(strip_fontawesome),
    pure(decode_image_paths),
    pure(convert_boxed_math),
    pure(cap_image_widths),
    pure(normalize_table_columns),
    _image_alt_filter,
    pure(add_math_alt_text),
]


class Chain(list):
    """A complete filter order, as opposed to a plain list appended to the core chain."""


def chain(before: Iterable[TypFilter] = (), after: Iterable[TypFilter] = ()) -> Chain:
    """The core chain with course filters placed before and/or after it."""
    return Chain([*before, *CORE_CHAIN, *after])


def resolve_filters(typ_filters: list[TypFilter] | None) -> list[TypFilter]:
    """What a Site's `typ_filters` means: None or a plain list appends to the core; a Chain is complete."""
    if typ_filters is None:
        return list(CORE_CHAIN)
    if isinstance(typ_filters, Chain):
        return list(typ_filters)
    return [*CORE_CHAIN, *typ_filters]


def postprocess(text: str, page: Page, filters: Iterable[TypFilter]) -> str:
    """Run the filters over one kept .typ file's text."""
    for filt in filters:
        text = filt(text, page)
    return text
