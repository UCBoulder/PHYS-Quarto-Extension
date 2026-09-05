"""Build the fixture site: HTML plus accessible PDF/UA-1 PDFs.

This is the reference wrapper. A course site keeps a copy of this file as
`site/build.py`, with the extension path changed to
`_extensions/UCBoulder/physicslabs` and its own hooks added to the `Site`;
see docs/build-core.md. The pipeline itself lives in the extension.

    python build.py            # HTML and PDFs
    python build.py --html     # HTML only
    python build.py --pdf -v   # PDFs only, verbose
    python build.py -v --ci    # what CI runs: keep the stamped sources
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.dont_write_bytecode = True   # keep __pycache__ out of _extensions/
sys.path.insert(0, str(ROOT / "_extensions" / "physicslabs"))
from physicslabs_build import Site, run  # noqa: E402

site = Site(
    root=ROOT,
    description="Build the physicslabs fixture site (HTML + accessible PDF).",
    require_api=1,
)
raise SystemExit(run(site))
