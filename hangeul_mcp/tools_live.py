from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from hangeul_core.convert import ensure_hwpx
from hangeul_core.hwp import HwpBridge, normalize_field_values
from hangeul_core.hwp.com import list_rot_instances
from hangeul_core.hwp.live import apply_cells_to_open as _apply_cells_to_open
from hangeul_core.hwp.live import open_in_hwp as _open_in_hwp
from hangeul_core.hwp.live import preview_cells_to_open as _preview_cells_to_open


def register_live_tools(mcp) -> Dict[str, Any]:
    @mcp.tool()
    def hwp_status() -> Dict[str, Any]:
        """Live COM availability probe — side-effect-free, never launches Hangul.

        connected:false is the NORMAL idle state (no attach is attempted here).
        `instances` lists automation-created Hangul instances already in the COM
        ROT (inspect-only). Hand-opened windows never appear there and cannot be
        attached — open documents via open_in_hwp for live fill.
        """
        st = HwpBridge().status()
        st["instances"] = list_rot_instances()
        st["attach_boundary"] = (
            "live tools attach only to automation-created Hangul instances (COM ROT); "
            "windows the user opened by hand never register there and cannot be attached — "
            "use open_in_hwp(path) to open the document in a controllable window first"
        )
        st["first_call_hint"] = (
            "if instances is empty, the first open_in_hwp/apply call LAUNCHES Hangul — "
            "cold start can take tens of seconds (responses carry cold_start/elapsed_seconds); "
            "later calls take a few seconds"
        )
        if not st.get("connected"):
            st["note"] = (
                "connected:false is the normal idle state: hwp_status is side-effect-free "
                "and never attaches to Hangul. It does NOT mean live fill is unreachable."
            )
            st["next"] = (
                "file mode works with any absolute path (analyze_form / extract_text / fill_form); "
                "live cell fill: open_in_hwp (controllable window), "
                "preview_cells_to_open_hwp (pure preview), then "
                "apply_cells_to_open_hwp (attaches on call; auto-opens the file if not active)"
            )
        return st

    @mcp.tool()
    def open_in_hwp(path: str, visible: bool = True) -> Dict[str, Any]:
        """Open a .hwp/.hwpx file in a CONTROLLABLE Hangul window — the live-edit entry point.

        Hand-opened Hangul windows cannot be attached (they never register in the
        COM ROT), so open the document with this tool instead, then fill it live
        with apply_cells_to_open_hwp / apply_to_open_hwp. Leaves the window open;
        saves and closes nothing. If Hangul is not running, this call launches it
        — cold start can take tens of seconds (see cold_start/elapsed_seconds in
        the response); later calls take a few seconds. Modal dialogs are
        auto-answered during the call so it cannot hang on an invisible prompt.
        """
        p = Path(path)
        if p.suffix.lower() not in (".hwp", ".hwpx"):
            return {"available": True, "ok": False, "error": "open_in_hwp accepts .hwp or .hwpx files"}
        return _open_in_hwp(p, visible=visible)

    @mcp.tool()
    def apply_to_open_hwp(values: Dict[str, str], visible: bool = True) -> Dict[str, Any]:
        """One-shot VALUE fill of named form fields (누름틀) in the OPEN Hangul window.

        Value insertion only — formatting/styling edits are not supported live;
        use the file-mode delegate tools (set_header, emphasize_text, ...) and
        produce a new file instead. Attaches to the running automation instance
        on call; hand-opened windows are not attachable — open the document via
        open_in_hwp first.
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
    def apply_cells_to_open_hwp(
        path: str,
        values: Dict[str, str],
        visible: bool = True,
        clear: bool = True,
        open_if_needed: bool = True,
    ) -> Dict[str, Any]:
        """Fill label:value CELLS of the OPEN Hangul window live (no 누름틀 required).

        Handles empty label:value cells AND inline blanks (colon "은행명:",
        marker "∘ 프로그램명", checkboxes) — inline values are mirrored through
        the file fill engine and applied as a full-cell text replacement, which
        flattens intra-cell rich formatting (file mode stays the byte-preserving
        gold path). Value insertion only — no formatting/styling. Attaches to
        the running automation instance on call (optional 'live' extra: pyhwpx)
        and verifies its active document is *path*; if not, opens it there
        (open_if_needed, default) — hand-opened windows are not attachable.
        Cold start (Hangul not running) can take tens of seconds. Preview first
        with preview_cells_to_open_hwp.
        """
        try:
            path = ensure_hwpx(path)
        except RuntimeError as exc:
            return {"available": True, "error": str(exc)}
        return _apply_cells_to_open(
            path, values, visible=visible, clear=clear, open_if_needed=open_if_needed
        )

    return {
        "hwp_status": hwp_status,
        "open_in_hwp": open_in_hwp,
        "apply_to_open_hwp": apply_to_open_hwp,
        "preview_cells_to_open_hwp": preview_cells_to_open_hwp,
        "apply_cells_to_open_hwp": apply_cells_to_open_hwp,
    }
