"""Make the in-tree package importable the way a wrapper does."""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.dont_write_bytecode = True   # keep __pycache__ out of _extensions/
sys.path.insert(0, str(REPO / "_extensions" / "physicslabs"))
