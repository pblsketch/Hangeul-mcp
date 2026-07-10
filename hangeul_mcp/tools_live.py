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
        """Live COM availability probe — side-effect-free, never launches or attaches to Hangul.

        connected:false is the NORMAL idle state (no attach is attempted here);
        it does NOT mean the open document is unreachable. Live fill tools
        attach on call.
        """
        st = HwpBridge().status()
        if not st.get("connected"):
            st["note"] = (
                "connected:false is the normal idle state: hwp_status is side-effect-free "
                "and never attaches to Hangul. It does NOT mean the open document is unreachable."
            )
            st["next"] = (
                "file mode works with any absolute path (analyze_form / extract_text / fill_form); "
                "live cell fill: preview_cells_to_open_hwp (pure preview), then "
                "apply_cells_to_open_hwp (attaches to the running Hangul on call)"
            )
        return st

    @mcp.tool()
    def apply_to_open_hwp(values: Dict[str, str], visible: bool = True) -> Dict[str, Any]:
        """One-shot VALUE fill of named form fields (누름틀) in the OPEN Hangul window.

        Value insertion only — formatting/styling edits are not supported live;
        use the file-mode delegate tools (set_header, emphasize_text, ...) and
        produce a new file instead. Attaches to the running Hangul on call.
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
                "note": "no named fields; use apply_cells_to_open_hwp for cell-based forms",
            }
        result = bridge.put_field_text(normalize_field_values(values))
        return {"available": True, "connected": True, "field_count": len(fields), **result}

    @mcp.tool()
    def preview_cells_to_open_hwp(path: str, values: Dict[str, str]) -> Dict[str, Any]:
        """Compute live cell-fill targets WITHOUT COM (pure, side-effect-free preview).

        Run this before apply_cells_to_open_hwp to confirm which table/row/col
        each value would land in.
        """
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
        """Fill label:value CELLS of the OPEN Hangul window live (no 누름틀 required).

        Value insertion only — no formatting/styling. Attaches to the running
        Hangul on call (optional 'live' extra: pyhwpx). Preview first with
        preview_cells_to_open_hwp.
        """
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
