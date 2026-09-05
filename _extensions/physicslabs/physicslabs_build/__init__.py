"""The shared build core for Physics Labs course sites.

A course's `build.py` is a thin wrapper around this package: it puts the
installed extension on `sys.path`, describes the project as a `Site`, and
calls `run`. Everything the six course scripts had in common lives here:
tool discovery, the source passes (dates from git history, `{{< var >}}`
resolution, notebook validation), the `.typ` post-processor that makes the
PDFs PDF/UA-1 compliant, and the two renders. See docs/build-core.md in the
extension repository for the design.

    from physicslabs_build import Site, run
    raise SystemExit(run(Site(root=ROOT, description="...", require_api=1)))

`API_VERSION` changes only when a wrapper written against the previous API
would break; a `Site` declares the API it was written for through
`require_api`, and `run` refuses a mismatch with one clear line.
"""

from .site import (  # noqa: F401
    API_VERSION,
    BuildError,
    Page,
    Site,
    SourcePass,
    TypFilter,
    Workspace,
)
from . import html, naming, pdf, sources, tools, typ  # noqa: F401
from .cli import main, run  # noqa: F401

__all__ = [
    "API_VERSION",
    "BuildError",
    "Page",
    "Site",
    "SourcePass",
    "TypFilter",
    "Workspace",
    "html",
    "naming",
    "pdf",
    "sources",
    "tools",
    "typ",
    "main",
    "run",
]
