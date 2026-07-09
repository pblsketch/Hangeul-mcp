from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from hangeul_core.convert import ensure_hwpx
from hangeul_core.hwp import HwpBridge, normalize_field_values
from hangeul_core.hwp.live import apply_cells_to_open as _apply_cells_to_open
from hangeul_core.hwp.live import preview_cells_to_open as _preview_cells_to_open


def register_live_tools(mcp) -> Dict[str, Any]:
    @mcp.tool()
    def hwp_status() -> Dict[str, Any]:
        return HwpBridge().status()

    @mcp.tool()
    def apply_to_open_hwp(values: Dict[str, str], visible: bool = True) -> Dict[str, Any]:
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
                "note": "no named fields; use apply_cells_to_open_hwp for cell-based forms",
            }
        result = bridge.put_field_text(normalize_field_values(values))
        return {"available": True, "connected": True, "field_count": len(fields), **result}

    @mcp.tool()
    def preview_cells_to_open_hwp(path: str, values: Dict[str, str]) -> Dict[str, Any]:
        p = Path(path)
        if p.suffix.lower() == ".hwp":
            return {
                "available": True,
                "ok": False,
                "error": "preview_cells_to_open_hwp is side-effect free and only accepts .hwpx; save/convert .hwp to .hwpx first",
            }
        if p.suffix.lower() != ".hwpx":
            return {"available": True, "ok": False, "error": "preview_cells_to_open_hwp only accepts .hwpx files"}
        return _preview_cells_to_open(p, values)

    @mcp.tool()
    def apply_cells_to_open_hwp(path: str, values: Dict[str, str], visible: bool = True, clear: bool = True) -> Dict[str, Any]:
        try:
            path = ensure_hwpx(path)
        except RuntimeError as exc:
            return {"available": True, "error": str(exc)}
        return _apply_cells_to_open(path, values, visible=visible, clear=clear)

    return {
        "hwp_status": hwp_status,
        "apply_to_open_hwp": apply_to_open_hwp,
        "preview_cells_to_open_hwp": preview_cells_to_open_hwp,
        "apply_cells_to_open_hwp": apply_cells_to_open_hwp,
    }
