"""The HTML render."""

from __future__ import annotations

import subprocess
from pathlib import Path


def build_html(quarto: Path, root: Path, verbose: bool) -> bool:
    """Render the Quarto project to HTML."""
    print("Building HTML website...")
    cmd = [str(quarto), "render", "--to", "html"]
    result = subprocess.run(cmd, cwd=root, capture_output=not verbose)
    if result.returncode != 0:
        print("ERROR: Quarto HTML render failed.")
        if not verbose and result.stderr:
            print(result.stderr.decode(errors="replace"))
        return False
    print("  HTML site written to _site/")
    return True
