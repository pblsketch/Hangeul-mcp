"""python-hwpx delegation layer (commodity breadth: export/edit/generate).

Per DECISIONS D1 and the ROADMAP own-vs-delegate split, our differentiators
(form recognition + byte-preserving fill) stay in the OWN engine; commodity
breadth (general editing, document generation, rich export) is *delegated* to the
mature `python-hwpx` substrate and merely exposed as Hangeul-mcp tools — no
re-invention.

`python-hwpx` is a **soft/optional dependency** (extra ``delegate``): the core
stays dependency-light and cross-platform, and every function here degrades
gracefully with a clear message when it is not installed. Delegated *edits*
re-serialize XML (they are not byte-identical the way our fill is); the integrity
contract for delegated output is our ``validate_hwpx`` gate, not byte-preservation.

Note: python-hwpx logs fallback notices to **stderr**, which is safe for the
stdio MCP server (stdout stays protocol-clean).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path


def hwpx_available() -> bool:
    """True if the optional python-hwpx substrate is importable."""
    return importlib.util.find_spec("hwpx") is not None


def _doc(path: str | Path):
    if not hwpx_available():
        raise RuntimeError(
            "python-hwpx not installed; run `pip install python-hwpx` "
            "(or `pip install -e \".[delegate]\"`) to enable delegated editing/export"
        )
    import hwpx  # local import: keep the core import-light

    return hwpx.HwpxDocument.open(str(path))


# -- export / preview (read-only) --------------------------------------------
def to_html(path: str | Path) -> str:
    """Render an HWPX document to HTML (structural preview)."""
    return _doc(path).export_html()


def to_markdown(path: str | Path) -> str:
    """Render an HWPX document to Markdown."""
    return _doc(path).export_markdown()


def to_text_rich(path: str | Path) -> str:
    """Extract rich text (python-hwpx's export_text) from an HWPX document."""
    return _doc(path).export_text()
