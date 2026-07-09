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
import re
from pathlib import Path
from typing import Dict, Optional

from hangeul_core.validate import validate_hwpx

_MD_MARKER = re.compile(r"^\s{0,3}(#{1,6}\s+|[-*+]\s+|>\s+|\d+\.\s+)")


def hwpx_available() -> bool:
    """True if the optional python-hwpx substrate is importable."""
    return importlib.util.find_spec("hwpx") is not None


def _module():
    if not hwpx_available():
        raise RuntimeError(
            "python-hwpx not installed; run `pip install python-hwpx` "
            "(or `pip install -e \".[delegate]\"`) to enable delegated editing/export"
        )
    import hwpx  # local import: keep the core import-light

    return hwpx


def _doc(path: str | Path):
    return _module().HwpxDocument.open(str(path))


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


def emphasize_text(
    path: str | Path,
    find: str,
    out_path: str | Path,
    *,
    bold: bool = False,
    italic: bool = False,
    underline: bool = False,
    color: Optional[str] = None,
    size: Optional[float] = None,
) -> Dict:
    """Apply formatting to every run whose text contains *find*, then validate.

    Scope is whole-run: a run is styled when its text contains *find* (sub-run
    substring splitting is not attempted). Styling is applied via a single
    ensured charPr, so all requested attributes land together. Returns the
    validation report plus ``matched_runs``.
    """
    doc = _doc(path)
    cid = doc.ensure_run_style(
        bold=bold, italic=italic, underline=underline, color=color, size=size
    )
    matched = 0
    for run in doc.iter_runs():
        if find and find in (run.text or ""):
            run.char_pr_id_ref = cid
            matched += 1
    _save(doc, out_path)
    result = _edit_result(out_path)
    result["matched_runs"] = matched
    return result


def add_picture(
    path: str | Path,
    image_path: str | Path,
    out_path: str | Path,
    *,
    width_mm: Optional[float] = None,
    height_mm: Optional[float] = None,
) -> Dict:
    """Insert an image (도장/서명/그림) from *image_path*, save, and validate."""
    img = Path(image_path)
    data = img.read_bytes()
    fmt = (img.suffix.lstrip(".").lower() or "png")
    doc = _doc(path)
    kwargs: Dict = {}
    if width_mm is not None:
        kwargs["width_mm"] = width_mm
    if height_mm is not None:
        kwargs["height_mm"] = height_mm
    doc.add_picture(data, fmt, **kwargs)
    _save(doc, out_path)
    return _edit_result(out_path)


# -- generation (delegated assembly; content is client-provided) -------------
def create_table_from_rows(rows, out_path: str | Path) -> Dict:
    """Build a new HWPX containing one table filled from *rows* (2D data).

    ``rows`` is a list of lists of cell strings (ragged rows are padded). The
    content is client-provided (brain/hand separation); this only assembles the
    table structure. Output is validated via our gate.
    """
    rows = [list(r) for r in rows]
    nrows = len(rows)
    ncols = max((len(r) for r in rows), default=0)
    if nrows == 0 or ncols == 0:
        return {"error": "rows must be a non-empty 2D list", "ok": False}
    doc = _module().HwpxDocument.new()
    table = doc.add_table(nrows, ncols)
    for r, row in enumerate(rows):
        for c in range(ncols):
            val = row[c] if c < len(row) else ""
            table.set_cell_text(r, c, "" if val is None else str(val))
    _save(doc, out_path)
    result = _edit_result(out_path)
    result["rows"] = nrows
    result["cols"] = ncols
    return result


def _official_lines(fields: Dict[str, str]) -> list:
    """Lay out a standard Korean 공문(official letter) skeleton from *fields*."""
    def g(key: str) -> str:
        return (fields.get(key) or "").strip()

    lines: list = []
    if g("기관명"):
        lines.append(g("기관명"))
        lines.append("")
    for key in ("수신", "참조"):
        if g(key):
            lines.append(f"{key}  {g(key)}")
    if g("수신") or g("참조"):
        lines.append("")
    if g("제목"):
        lines.append(f"제목  {g('제목')}")
        lines.append("")
    for para in g("본문").split("\n"):
        lines.append(para)
    lines.append("")
    if g("날짜"):
        lines.append(g("날짜"))
    if g("발신명의"):
        lines.append(g("발신명의"))
    if g("담당자"):
        lines.append(f"담당자: {g('담당자')}")
    return lines


def create_official_document(fields: Dict[str, str], out_path: str | Path) -> Dict:
    """Assemble a 공문-style official document from client-provided *fields*.

    Recognized keys: 기관명, 수신, 참조, 제목, 본문(줄바꿈=문단), 날짜, 발신명의, 담당자.
    Content is client-authored (brain/hand separation); this only lays out the
    standard skeleton and validates the output. Unknown keys are ignored.
    """
    lines = _official_lines(fields)
    doc = _module().HwpxDocument.new()
    for text in lines:
        doc.add_paragraph(text)
    _save(doc, out_path)
    result = _edit_result(out_path)
    result["lines"] = len(lines)
    return result


def create_from_markdown(markdown: str, out_path: str | Path) -> Dict:
    """Build a new HWPX from client-provided markdown/text (one paragraph per line).

    Assembly only — the *content* is authored by the client LLM (brain/hand
    separation). Leading markdown markers (``#``, ``-``, ``>`` , ``1.``) are
    stripped to plain paragraph text; rich markdown structure mapping is a
    follow-up. Output is validated via our gate.
    """
    doc = _module().HwpxDocument.new()
    lines = markdown.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    added = 0
    for line in lines:
        text = _MD_MARKER.sub("", line.rstrip())
        doc.add_paragraph(text)
        added += 1
    _save(doc, out_path)
    result = _edit_result(out_path)
    result["paragraphs"] = added
    return result
