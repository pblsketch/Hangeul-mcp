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

from hangeul_core.extract import extract_text as _extract_text
from hangeul_core.fill import fill as _fill
from hangeul_core.inline import detect_inline
from hangeul_core.owpml import HwpxPackage
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
    fields = understand(path).fields + detect_inline(path)
    return {"format": "hwpx", "fields": [_field_dict(f) for f in fields]}


@mcp.tool()
def fill_form(
    path: str,
    values: Dict[str, str],
    out_path: str,
    normalize_spacing: bool = False,
    respect_bullets: bool = True,
) -> Dict[str, Any]:
    """Fill values into an HWPX form, preserving all original formatting.

    ``values`` is a map of field_id or label -> value. Multi-line values become
    real paragraphs; bullet cells are not double-marked. Returns the filled and
    skipped fields and the output path. Unmodified regions stay byte-identical.
    """
    result = _fill(
        path,
        values,
        out_path,
        normalize_spacing=normalize_spacing,
        respect_bullets=respect_bullets,
    )
    return {"filled": result.filled, "skipped": result.skipped, "out_path": result.out_path}


@mcp.tool()
def extract_text(path: str) -> str:
    """Extract plain text from an HWPX document (one line per text node)."""
    return _extract_text(path)


def main() -> None:
    """Console entrypoint: run the stdio MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
