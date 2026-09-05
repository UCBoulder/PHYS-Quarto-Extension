"""Locate Quarto and standalone Typst.

Quarto bundles its own Typst, which has no PDF/UA-1 support; the PDF step
needs a standalone Typst 0.14 or newer. Both finders check PATH first and
then the usual install locations.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
from pathlib import Path

MIN_TYPST = (0, 14)


def find_quarto() -> Path | None:
    """Find the Quarto CLI."""
    q = shutil.which("quarto")
    if q:
        return Path(q)
    # Common install locations
    candidates = [
        Path("C:/Program Files/Quarto/bin/quarto.exe"),
        Path("/usr/local/bin/quarto"),
        Path("/opt/quarto/bin/quarto"),
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def find_typst() -> Path | None:
    """Find standalone Typst 0.14+ (NOT Quarto's bundled 0.13)."""
    # Check PATH first
    t = shutil.which("typst")
    if t:
        return Path(t)

    system = platform.system()
    if system == "Windows":
        candidates = [
            Path.home() / "AppData/Local/Microsoft/WinGet/Packages/Typst.Typst_Microsoft.Winget.Source_8wekyb3d8bbwe/typst-x86_64-pc-windows-msvc/typst.exe",
            Path("C:/Program Files/typst/typst.exe"),
            Path.home() / "scoop/apps/typst/current/typst.exe",
            Path.home() / ".cargo/bin/typst.exe",
        ]
    elif system == "Darwin":
        candidates = [
            Path("/opt/homebrew/bin/typst"),
            Path("/usr/local/bin/typst"),
            Path.home() / ".cargo/bin/typst",
        ]
    else:
        candidates = [
            Path("/usr/bin/typst"),
            Path("/usr/local/bin/typst"),
            Path.home() / ".cargo/bin/typst",
        ]

    for p in candidates:
        if p.exists():
            return p
    return None


def typst_version(typst: Path) -> str:
    """Return the Typst version string, or empty if not runnable."""
    try:
        result = subprocess.run(
            [str(typst), "--version"], capture_output=True, text=True, timeout=10
        )
        # Output is like "typst 0.14.2 (abc1234)"
        return result.stdout.strip().split()[1] if result.returncode == 0 else ""
    except Exception:
        return ""


def version_tuple(version: str) -> tuple[int, ...]:
    """'0.14.2' -> (0, 14, 2), so versions compare numerically, not as strings."""
    parts: list[int] = []
    for piece in version.split("."):
        digits = ""
        for ch in piece:
            if not ch.isdigit():
                break
            digits += ch
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts)


def install_hint() -> str:
    """How to install Typst on this platform."""
    return {
        "Windows": "winget install Typst.Typst",
        "Darwin": "brew install typst",
    }.get(platform.system(), "cargo install typst-cli")
