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
from typing import Dict, Optional

from hangeul_core.validate import validate_hwpx


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


# -- structural editing (delegated; validated via our gate) ------------------
def _save(doc, out_path: str | Path) -> None:
    """Save via the current API (save_to_path), falling back to legacy save()."""
    saver = getattr(doc, "save_to_path", None)
    if callable(saver):
        saver(str(out_path))
    else:  # pragma: no cover - older python-hwpx
        doc.save(str(out_path))


def _edit_result(out_path: str | Path) -> Dict:
    """Run our validate_hwpx gate on delegated output and shape a result."""
    report = validate_hwpx(out_path)
    return {"ok": bool(report["valid"]), "out_path": str(out_path), "validation": report}


def add_paragraph(
    path: str | Path,
    text: str,
    out_path: str | Path,
    section_index: Optional[int] = None,
) -> Dict:
    """Append a paragraph, save, and validate the output (delegated)."""
    doc = _doc(path)
    kwargs = {} if section_index is None else {"section_index": section_index}
    doc.add_paragraph(text, **kwargs)
    _save(doc, out_path)
    return _edit_result(out_path)


def add_table(
    path: str | Path,
    rows: int,
    cols: int,
    out_path: str | Path,
) -> Dict:
    """Append an (rows x cols) table, save, and validate the output (delegated)."""
    doc = _doc(path)
    doc.add_table(rows, cols)
    _save(doc, out_path)
    return _edit_result(out_path)
