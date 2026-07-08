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
from hangeul_core.convert import ensure_hwpx
from hangeul_core.formfield import detect_form_fields
from hangeul_core.formfit import analyze_formfit as _analyze_formfit
from hangeul_core.extract import extract_text as _extract_text
from hangeul_core.fill import fill as _fill
from hangeul_core.hwp import HwpBridge, normalize_field_values
from hangeul_core.inline import detect_inline
from hangeul_core.locate import detect_placeholders
from hangeul_core.markpen import detect_markpen
from hangeul_core.owpml import HwpxPackage
from hangeul_core.pii import scan_text as _scan_pii
from hangeul_core.understand import understand

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
            "note": "no named fields (누름틀) in the open document; register fields first",
        }
    result = bridge.put_field_text(normalize_field_values(values))
    return {"available": True, "connected": True, "field_count": len(fields), **result}


def main() -> None:
    """Console entrypoint: run the stdio MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
