"""Hangeul-mcp MCP server (FastMCP, stdio transport).

Client-agnostic: works with any MCP client (Claude Desktop, Codex,
Antigravity 2.0, Cursor, ...). Exposes the hangeul_core engine as pure tools
(``params in -> JSON out``). Text/value generation is the client LLM's job;
these tools only understand and fill forms.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from mcp.server.fastmcp import FastMCP

from hangeul_core.checkbox import detect_checkbox
from hangeul_core import delegate as _delegate
from hangeul_core.convert import ensure_hwpx
from hangeul_core.edit import batch_replace as _batch_replace
from hangeul_core.edit import search_and_replace as _search_and_replace
from hangeul_core.formfield import detect_form_fields
from hangeul_core.formfit import analyze_formfit as _analyze_formfit
from hangeul_core.extract import extract_text as _extract_text
from hangeul_core.fill import fill as _fill
from hangeul_core.hwp import HwpBridge, normalize_field_values
from hangeul_core.hwp.live import apply_cells_to_open as _apply_cells_to_open
from hangeul_core.inline import detect_inline
from hangeul_core.locate import detect_placeholders
from hangeul_core.mailmerge import mail_merge as _mail_merge
from hangeul_core.markpen import detect_markpen
from hangeul_core.owpml import HwpxPackage
from hangeul_core.pii import scan_text as _scan_pii
from hangeul_core.read import find_cell_by_label as _find_cell_by_label
from hangeul_core.read import find_text as _find_text
from hangeul_core.read import get_document_outline as _get_document_outline
from hangeul_core.read import get_table_map as _get_table_map
from hangeul_core.read import list_styles as _list_styles
from hangeul_core.read import verify_fill as _verify_fill
from hangeul_core.understand import understand
from hangeul_core.validate import validate_hwpx as _validate_hwpx

mcp = FastMCP("hangeul-mcp")


def _field_dict(f) -> Dict[str, Any]:
    return {
        "field_id": f.field_id,
        "label": f.label,
        "kind": f.kind,
        "insert_after": f.insert_after,
        "template": f.template,
        "para_bullet": f.para_bullet,
        "char_spacing": f.char_spacing,
        "options": f.options,
    }


@mcp.tool()
def detect_format(path: str) -> Dict[str, Any]:
    """Detect a document's format. Returns {format: hwpx|hwp|unknown, ok, ...}."""
    p = Path(path)
    if not p.exists():
        return {"format": "unknown", "ok": False, "reason": "file not found"}
    try:
        pkg = HwpxPackage.open(p)
        if pkg.is_mimetype_ok():
            return {"format": "hwpx", "ok": True}
    except Exception:
        pass
    if p.suffix.lower() == ".hwp":
        return {
            "format": "hwp",
            "ok": False,
            "note": "binary HWP; v1 auto-convert to HWPX is planned",
        }
    return {"format": "unknown", "ok": False}


@mcp.tool()
def analyze_form(path: str) -> Dict[str, Any]:
    """Analyze a Korean HWPX form into fillable fields.

    Returns fields with field_id (authoritative address), label (alias), kind
    (empty_cell | inline_blank | ...), insert anchor, and style flags. Use the
    field_id or label as keys when calling fill_form.
    """
    try:
        path = ensure_hwpx(path)
    except RuntimeError as exc:
        return {"error": str(exc), "format": "hwp", "fields": []}
    fields = (
        understand(path).fields
        + detect_inline(path)
        + detect_placeholders(path)
        + detect_markpen(path)
        + detect_checkbox(path)
        + detect_form_fields(path)
    )
    return {"format": "hwpx", "fields": [_field_dict(f) for f in fields]}


@mcp.tool()
def fill_form(
    path: str,
    values: Dict[str, str],
    out_path: str,
    normalize_spacing: bool = False,
    respect_bullets: bool = True,
    checkbox_exclusive: bool = True,
    auto_fit: bool = False,
    mask_pii: bool = False,
    dry_run: bool = False,
    backup: bool = False,
) -> Dict[str, Any]:
    """Fill values into an HWPX form, preserving all original formatting.

    ``values`` is a map of field_id or label -> value. Handles empty cells,
    inline blanks, ``{placeholder}`` tokens, 형광펜(markpen) examples, checkbox
    groups (value = option label(s) to check; ``checkbox_exclusive`` unchecks the
    others), and 누름틀 named fields. Multi-line values become real paragraphs;
    bullet cells are not double-marked. With ``auto_fit``, cell text estimated to
    overflow is shrunk via a cloned charPr (bounded by a floor) and reported in
    ``shrunk``. Returns the filled/skipped/shrunk fields and the output path.
    Unmodified regions stay byte-identical.
    """
    try:
        path = ensure_hwpx(path)
    except RuntimeError as exc:
        return {"error": str(exc), "filled": [], "skipped": []}
    result = _fill(
        path,
        values,
        out_path,
        normalize_spacing=normalize_spacing,
        respect_bullets=respect_bullets,
        checkbox_exclusive=checkbox_exclusive,
        auto_fit=auto_fit,
        mask_pii=mask_pii,
        dry_run=dry_run,
        backup=backup,
    )
    return {
        "filled": result.filled,
        "skipped": result.skipped,
        "shrunk": result.shrunk,
        "masked": result.masked,
        "out_path": result.out_path,
        "dry_run": dry_run,
    }


@mcp.tool()
def scan_pii(path: str) -> Dict[str, Any]:
    """Audit a document's text for PII (주민번호/전화/카드/계좌/이메일).

    Read-only. Returns ``findings`` (type + masked preview, no raw value echoed
    beyond the match) and a ``count``. Use before sharing/committing a filled
    form, or pair with fill_form(mask_pii=True) to mask values on write.
    """
    try:
        path = ensure_hwpx(path)
    except RuntimeError as exc:
        return {"error": str(exc), "findings": [], "count": 0}
    findings = _scan_pii(_extract_text(path))
    return {
        "findings": [{"type": f["type"], "masked": f["masked"]} for f in findings],
        "count": len(findings),
    }


@mcp.tool()
def analyze_formfit(path: str, values: Dict[str, str]) -> Dict[str, Any]:
    """Estimate whether filled values would overflow their target cells.

    Heuristic (no renderer): compares each value's estimated width to the cell's
    capacity. Returns ``warnings`` (field_id, label, estimated_width,
    available_width, ratio>1.0 = likely overflow) and ``checked`` count. Use
    before fill_form(auto_fit=True) to preview page-drift risk. Estimates only.
    """
    try:
        path = ensure_hwpx(path)
    except RuntimeError as exc:
        return {"error": str(exc), "warnings": [], "checked": 0}
    return _analyze_formfit(path, values)


@mcp.tool()
def extract_text(path: str) -> str:
    """Extract plain text from an HWPX document (one line per text node)."""
    return _extract_text(path)


@mcp.tool()
def find_text(path: str, query: str) -> Dict[str, Any]:
    """Find text in an HWPX document (read-only).

    Returns a document-wide ``count`` and addressed ``cell_occurrences``
    (section, field_id, snippet) for matches located in table cells.
    """
    try:
        path = ensure_hwpx(path)
    except RuntimeError as exc:
        return {"error": str(exc), "query": query, "count": 0, "cell_occurrences": []}
    return _find_text(path, query)


@mcp.tool()
def get_document_outline(path: str) -> Dict[str, Any]:
    """Structural overview of an HWPX form (read-only).

    Returns section count, per-table geometry, cell/empty-cell counts, and a
    tally of fillable fields by kind (empty_cell/inline_blank/placeholder/
    markpen/checkbox/form_field).
    """
    try:
        path = ensure_hwpx(path)
    except RuntimeError as exc:
        return {"error": str(exc)}
    return _get_document_outline(path)


@mcp.tool()
def get_table_map(path: str) -> Dict[str, Any]:
    """Structured table/cell map (read-only): per table rows/cols, per cell
    field_id/row/col/spans/text/is_empty. Use to locate fill targets by address."""
    try:
        path = ensure_hwpx(path)
    except RuntimeError as exc:
        return {"error": str(exc), "tables": []}
    return _get_table_map(path)


@mcp.tool()
def find_cell_by_label(path: str, label: str) -> Dict[str, Any]:
    """Locate a label cell and its mapped value cell (read-only).

    Returns the label cell field_id(s) and the value-cell field_id that fill_form
    would target for this label.
    """
    try:
        path = ensure_hwpx(path)
    except RuntimeError as exc:
        return {"error": str(exc), "label": label}
    return _find_cell_by_label(path, label)


@mcp.tool()
def verify_fill(path: str, expected: Dict[str, str]) -> Dict[str, Any]:
    """Verify a filled document actually contains the expected values (read-only).

    Whitespace-insensitive. Returns verified + present[] + missing[]. Use after
    fill_form/apply_to_open_hwp to confirm the values landed.
    """
    try:
        path = ensure_hwpx(path)
    except RuntimeError as exc:
        return {"error": str(exc), "verified": False}
    return _verify_fill(path, expected)


@mcp.tool()
def list_styles(path: str) -> Dict[str, Any]:
    """List the header's charPr (font height / hangul spacing) and paraPr (bullet)."""
    try:
        path = ensure_hwpx(path)
    except RuntimeError as exc:
        return {"error": str(exc), "charPr": [], "paraPr": []}
    return _list_styles(path)


@mcp.tool()
def hwpx_to_html(path: str) -> Dict[str, Any]:
    """Render an HWPX document to HTML (read-only, delegated to python-hwpx).

    Structural preview (not pixel-perfect). Requires the optional python-hwpx
    substrate; returns available:false if it is not installed.
    """
    if not _delegate.hwpx_available():
        return {"available": False, "error": "python-hwpx not installed (extra 'delegate')"}
    try:
        path = ensure_hwpx(path)
    except RuntimeError as exc:
        return {"available": True, "error": str(exc)}
    return {"available": True, "html": _delegate.to_html(path)}


@mcp.tool()
def hwpx_to_markdown(path: str) -> Dict[str, Any]:
    """Render an HWPX document to Markdown (read-only, delegated to python-hwpx).

    Requires the optional python-hwpx substrate; returns available:false if it is
    not installed.
    """
    if not _delegate.hwpx_available():
        return {"available": False, "error": "python-hwpx not installed (extra 'delegate')"}
    try:
        path = ensure_hwpx(path)
    except RuntimeError as exc:
        return {"available": True, "error": str(exc)}
    return {"available": True, "markdown": _delegate.to_markdown(path)}


@mcp.tool()
def search_and_replace(path: str, find: str, replace: str, out_path: str) -> Dict[str, Any]:
    """Replace every occurrence of *find* with *replace* → new .hwpx (byte-preserving).

    Only ``<hp:t>`` text changes (tags/attributes untouched); matches may cross
    runs but never bridge a cell/paragraph/table boundary. Returns the match
    count and output path. For structural edits (paragraphs/tables/formatting),
    see the planned python-hwpx-backed tools.
    """
    try:
        path = ensure_hwpx(path)
    except RuntimeError as exc:
        return {"error": str(exc), "total": 0}
    res = _search_and_replace(path, find, replace, out_path)
    return {"counts": res.counts, "total": res.total, "out_path": res.out_path}


@mcp.tool()
def batch_replace(path: str, replacements: Dict[str, str], out_path: str) -> Dict[str, Any]:
    """Apply many find→replace pairs in one pass → new .hwpx (byte-preserving).

    ``replacements`` maps find-text to replacement. Longer finds win on overlap;
    each position is edited at most once (no chained re-replacement). Returns
    per-find counts and the output path.
    """
    try:
        path = ensure_hwpx(path)
    except RuntimeError as exc:
        return {"error": str(exc), "total": 0}
    res = _batch_replace(path, replacements, out_path)
    return {"counts": res.counts, "total": res.total, "out_path": res.out_path}


@mcp.tool()
def add_paragraph(path: str, text: str, out_path: str, section_index: int = -1) -> Dict[str, Any]:
    """Append a paragraph to an HWPX document → new .hwpx (delegated to python-hwpx).

    Structural edit (re-serialized, not byte-identical); the output is run through
    validate_hwpx and reported under ``validation`` (ok=true only when valid).
    Requires the optional python-hwpx substrate. Text is client-provided.
    """
    if not _delegate.hwpx_available():
        return {"available": False, "error": "python-hwpx not installed (extra 'delegate')"}
    try:
        path = ensure_hwpx(path)
    except RuntimeError as exc:
        return {"available": True, "error": str(exc)}
    idx = None if section_index < 0 else section_index
    return {"available": True, **_delegate.add_paragraph(path, text, out_path, section_index=idx)}


@mcp.tool()
def mail_merge(
    template_path: str,
    records: list,
    out_dir: str,
    mask_pii: bool = False,
) -> Dict[str, Any]:
    """Bulk-fill one template for many records → numbered .hwpx files (byte-preserving).

    ``records`` is a list of value maps (same keys as fill_form: field_id/label/
    placeholder/checkbox/markpen/누름틀). Each output keeps the template formatting
    exactly (only merged fields change). Records are client-provided. Returns a
    per-record summary and the output directory.
    """
    try:
        template_path = ensure_hwpx(template_path)
    except RuntimeError as exc:
        return {"error": str(exc), "count": 0}
    return _mail_merge(template_path, list(records), out_dir, mask_pii=mask_pii)


@mcp.tool()
def create_hwpx_from_markdown(markdown: str, out_path: str) -> Dict[str, Any]:
    """Build a new HWPX from client-provided markdown/text → new .hwpx (delegated).

    Assembly only: the content is authored by the client LLM (brain/hand
    separation); this maps each line to a paragraph and validates the output.
    Requires the optional python-hwpx substrate.
    """
    if not _delegate.hwpx_available():
        return {"available": False, "error": "python-hwpx not installed (extra 'delegate')"}
    return {"available": True, **_delegate.create_from_markdown(markdown, out_path)}


@mcp.tool()
def add_image(
    path: str,
    image_path: str,
    out_path: str,
    width_mm: float = 0.0,
    height_mm: float = 0.0,
) -> Dict[str, Any]:
    """Insert an image (도장/서명/그림) into an HWPX document → new .hwpx (delegated).

    Reads the image from ``image_path`` (png/jpg/…). Optional width_mm/height_mm
    (0 = keep intrinsic). Output validated via validate_hwpx. Requires the
    optional python-hwpx substrate.
    """
    if not _delegate.hwpx_available():
        return {"available": False, "error": "python-hwpx not installed (extra 'delegate')"}
    try:
        path = ensure_hwpx(path)
    except RuntimeError as exc:
        return {"available": True, "error": str(exc)}
    return {
        "available": True,
        **_delegate.add_picture(
            path,
            image_path,
            out_path,
            width_mm=(width_mm or None),
            height_mm=(height_mm or None),
        ),
    }


@mcp.tool()
def add_table(path: str, rows: int, cols: int, out_path: str) -> Dict[str, Any]:
    """Append a rows×cols table to an HWPX document → new .hwpx (delegated).

    Structural edit (re-serialized); output validated via validate_hwpx and
    reported under ``validation``. Requires the optional python-hwpx substrate.
    """
    if not _delegate.hwpx_available():
        return {"available": False, "error": "python-hwpx not installed (extra 'delegate')"}
    try:
        path = ensure_hwpx(path)
    except RuntimeError as exc:
        return {"available": True, "error": str(exc)}
    return {"available": True, **_delegate.add_table(path, rows, cols, out_path)}


@mcp.tool()
def validate_hwpx(path: str) -> Dict[str, Any]:
    """Validate an HWPX file's integrity (read-only, never raises).

    Checks every XML entry is well-formed, mimetype is the first STORED entry,
    and sections carry an XML declaration. If python-hwpx is installed, its XSD
    validation is folded in. Returns {valid, well_formed, mimetype_ok,
    declaration_ok, errors[], xsd}.
    """
    return _validate_hwpx(path)


@mcp.tool()
def hwp_status() -> Dict[str, Any]:
    """Report whether the COM live-apply bridge is available (Windows + Hangul).

    Side-effect free: never launches Hangul. Call this before apply_to_open_hwp.
    """
    return HwpBridge().status()


@mcp.tool()
def apply_to_open_hwp(values: Dict[str, str], visible: bool = True) -> Dict[str, Any]:
    """(v2) Fill values into the currently OPEN Hangul document in one shot (COM).

    Fills named fields (누름틀/cell fields) via PutFieldText. Requires Windows +
    Hangul + pywin32; otherwise returns ``available: false``. If the open
    document has no named fields, returns ``needs_field_registration: true``.
    """
    bridge = HwpBridge()
    if not bridge.available():
        return {"available": False, "error": "COM bridge needs Windows + pywin32 + Hangul"}
    try:
        bridge.connect(visible=visible)
    except Exception as exc:
        return {"available": True, "connected": False, "error": str(exc)}
    fields = bridge.get_field_list()
    if not fields:
        return {
            "available": True,
            "connected": True,
            "needs_field_registration": True,
            "note": "no named fields (누름틀); for a cell-based form call "
            "apply_cells_to_open_hwp(path, values) to fill the open document's cells live",
        }
    result = bridge.put_field_text(normalize_field_values(values))
    return {"available": True, "connected": True, "field_count": len(fields), **result}


@mcp.tool()
def apply_cells_to_open_hwp(
    path: str,
    values: Dict[str, str],
    visible: bool = True,
    clear: bool = True,
) -> Dict[str, Any]:
    """Fill the currently OPEN Hangul document's CELLS live — no 누름틀 needed.

    For cell-based forms (label:value tables like 강사카드) that have no named
    fields. ``path`` is the file that is open (used only to resolve cell
    addresses via analyze); the fill happens live in the running Hangul window,
    which is NOT closed. ``values`` keys are field_id or label. Requires Windows
    + Hangul + the optional pyhwpx substrate (extra 'live'); otherwise returns
    available:false. Returns applied[]/skipped[]/count.
    """
    try:
        path = ensure_hwpx(path)
    except RuntimeError as exc:
        return {"available": True, "error": str(exc)}
    return _apply_cells_to_open(path, values, visible=visible, clear=clear)


def main() -> None:
    """Console entrypoint: run the stdio MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
