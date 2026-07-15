"""MCP tool for live (COM) table-structure editing of the open Hangul window."""

from __future__ import annotations

from typing import Any, Dict

from hangeul_core.convert import ensure_hwpx
from hangeul_core.hwp.live_table import apply_live_row_deletes, plan_live_row_deletes


def register_live_table_tools(mcp) -> Dict[str, Any]:
    @mcp.tool()
    def live_delete_table_rows(path: str, rows: list[str], visible: bool = True) -> Dict[str, Any]:
        """Delete table ROWS in the OPEN Hangul window (live-only; Windows + Hangul).

        Offline row delete is unsafe (cellAddr/rowCnt/merge recompute), so this
        drives the open window — Hangul's TableSubtractRow recomputes merges.
        ``rows`` are ``tN.rN`` addresses (global table number, 0-based row), e.g.
        ["t2.r3"]. Plans purely first (fails closed on nested tables / unknown
        rows / duplicates), deletes bottom-up, and never opens/saves/closes the
        document. Cold start can take tens of seconds.
        """
        try:
            path = ensure_hwpx(path)
        except RuntimeError as exc:
            return {"available": True, "error": str(exc)}
        edits = [{"target": str(r), "operation": "delete_row"} for r in rows]
        plan = plan_live_row_deletes(path, edits)
        if not plan.get("ok"):
            return plan
        return apply_live_row_deletes(path, plan["targets"], visible=visible)

    return {"live_delete_table_rows": live_delete_table_rows}
