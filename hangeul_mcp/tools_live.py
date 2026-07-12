from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from hangeul_core.convert import ensure_hwpx
from hangeul_core.hwp import HwpBridge, normalize_field_values
from hangeul_core.hwp.com import find_rot_exact_path_candidates, list_rot_instances
from hangeul_core.hwp.live import apply_cells_to_open as _apply_cells_to_open
from hangeul_core.hwp.live import open_in_hwp as _open_in_hwp
from hangeul_core.hwp.live import preview_cells_to_open as _preview_cells_to_open



def _exact_attach_candidates(path: Path) -> List[Dict[str, Any]]:
    return [dict(item) for item in find_rot_exact_path_candidates(path)]


def register_live_tools(mcp) -> Dict[str, Any]:
    @mcp.tool()
    def hwp_status() -> Dict[str, Any]:
        """Live COM availability probe — side-effect-free, never launches Hangul.

        connected:false is the NORMAL idle state (no attach is attempted here).
        `instances` lists automation-visible Hangul instances already in the COM
        ROT. For live edits, attach by exact path: use open_in_hwp(path) to make
        the requested document active in that automation window before apply.
        """
        st = HwpBridge().status()
        st["instances"] = list_rot_instances()
        st["attach_boundary"] = (
            "live tools use exact-path attach against automation-visible COM ROT instances; "
            "use open_in_hwp(path) first so the requested exact path is active before live apply"
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
                "live cell fill: open_in_hwp(path) for the exact path, preview_cells_to_open_hwp "
                "(pure preview), then apply_cells_to_open_hwp"
            )
        return st

    @mcp.tool()
    def open_in_hwp(path: str, visible: bool = True) -> Dict[str, Any]:
        """Open a .hwp/.hwpx file in a CONTROLLABLE Hangul window.

        Hand-opened windows are not a safe exact-path live-attach anchor on their
        own. Use this tool to attach by exact path in the automation-visible
        window first, then apply_to_open_hwp / apply_cells_to_open_hwp. Leaves the
        window open; saves and closes nothing. If Hangul is not running, this
        launches it — cold start can take tens of seconds
        (see cold_start/elapsed_seconds in the response). Modal dialogs are
        auto-answered during the call so it cannot hang on an invisible prompt.
        """
        p = Path(path)
        if p.suffix.lower() not in (".hwp", ".hwpx"):
            return {"available": True, "ok": False, "error": "open_in_hwp accepts .hwp or .hwpx files"}
        return _open_in_hwp(p, visible=visible)

    @mcp.tool()
    def apply_to_open_hwp(
        values: Dict[str, str],
        path: str | None = None,
        visible: bool = True,
    ) -> Dict[str, Any]:
        """One-shot VALUE fill of named form fields (누름틀) in the OPEN Hangul window.

        Value insertion only — formatting/styling edits are not supported live;
        use the file-mode delegate tools and produce a new file instead. Legacy
        mode is pathless and writes to the active automation document. Optional
        path=... is exact-path guidance only in this slice: it reports safe attach
        state without doing a generic reconnect or guessing the target broker.
        """
        if path is not None:
            p = Path(path)
            if not p.exists():
                return {
                    "available": True,
                    "ok": False,
                    "state": "not_found",
                    "requested_path": str(p),
                    "error": f"file not found: {p}",
                }
            return {
                "available": True,
                "ok": False,
                "state": "legacy_active_document",
                "requested_path": str(p),
                "attach_candidates": _exact_attach_candidates(p),
                "note": (
                    "exact-path named-field apply is not safely available here without a generic reconnect; "
                    "use open_in_hwp(path) to make that exact path active, then call apply_to_open_hwp(values) without path"
                ),
            }

        bridge = HwpBridge()
        if not bridge.available():
            return {
                "available": False,
                "connected": False,
                "state": "unavailable",
                "error": "COM bridge needs Windows + pywin32 + Hangul",
            }
        try:
            bridge.connect(visible=visible)
        except Exception as exc:
            return {
                "available": True,
                "connected": False,
                "state": "legacy_connect_failed",
                "error": str(exc),
            }
        fields = bridge.get_field_list()
        if not fields:
            return {
                "available": True,
                "connected": True,
                "state": "legacy_needs_field_registration",
                "needs_field_registration": True,
                "note": "no named fields; use apply_cells_to_open_hwp for cell-based forms",
            }
        result = bridge.put_field_text(normalize_field_values(values))
        return {
            "available": True,
            "connected": True,
            "state": "legacy_connected",
            "field_count": len(fields),
            **result,
        }

    @mcp.tool()
    def preview_cells_to_open_hwp(path: str, values: Dict[str, str]) -> Dict[str, Any]:
        """Compute live cell-fill targets WITHOUT COM (pure, side-effect-free preview).

        Run this before apply_cells_to_open_hwp to confirm which table/row/col
        each value would land in and whether an exact-path attach candidate is
        already visible.
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
        result = dict(_preview_cells_to_open(p, values))
        candidates = _exact_attach_candidates(p)
        result.update(
            {
                "ok": result.get("ok", True),
                "resolver": {
                    "side_effect_free": True,
                    "exact_path": str(p),
                    "apply_to_open_hwp_state": "legacy_active_document",
                    "apply_cells_to_open_hwp_state": "pathful_exact_path",
                },
                "attach_candidates": candidates,
            }
        )
        return result

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
        marker "∘ 프로그램명", checkboxes). Value insertion only — no
        formatting/styling. Attaches to the automation-visible instance on call
        and verifies the requested exact path is active; if not, it opens it there
        when open_if_needed=true. Cold start can take tens of seconds. Preview
        first with preview_cells_to_open_hwp.
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
