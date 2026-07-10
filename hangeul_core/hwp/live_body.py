"""Live fill of BODY paragraphs (outside tables) in the open Hangul window.

Body paragraphs have no cell address, so the cell-navigation path can't reach
them. Instead we align our document-order body ordinals to the open document's
root-list (list 0) paragraphs and drive the caret there.

Alignment (verified 2026-07-11): our body fields and HWP's list-0 paragraphs are
both in document order, so a sequential text match assigns each body field its
paragraph index. Wrapper paragraphs (that embed a table) read as multi-line COM
text and never match a single-line body template, so they are skipped for free —
no fragile index arithmetic. The fill then places the caret just past the marker
prefix and replaces to the paragraph end, preserving the marker and formatting.
"""

from __future__ import annotations

from typing import Dict, List

from hangeul_core.body import detect_body_fields


def _norm(s: str) -> str:
    return "".join(s.split())


def _align_paras(hwp, fields) -> Dict[str, int]:
    """Map each body field_id -> list-0 paragraph index in the open document."""
    ordered: List[tuple] = []
    para = 0
    misses = 0
    while misses < 6 and para < 3000:
        if hwp.set_pos(0, para, 0):
            misses = 0
            hwp.set_pos(0, para, 0)
            hwp.HAction.Run("MoveSelParaEnd")
            txt = hwp.get_selected_text()
            hwp.HAction.Run("Cancel")
            if txt.strip():
                ordered.append((para, txt))
        else:
            misses += 1
        para += 1

    para_for_field: Dict[str, int] = {}
    ti = 0
    for idx, txt in ordered:
        if ti >= len(fields):
            break
        if _norm(txt) == _norm(fields[ti].template):
            para_for_field[fields[ti].field_id] = idx
            ti += 1
    return para_for_field


def apply_body_targets(hwp, path, body_targets: List[dict], applied: List[dict], skipped: List[dict]) -> None:
    """Replace each requested body paragraph's text in the OPEN window (COM)."""
    if not body_targets:
        return
    para_for_field = _align_paras(hwp, detect_body_fields(path))
    for t in body_targets:
        fid = t["field_id"]
        para = para_for_field.get(fid)
        if para is None:
            skipped.append({"key": fid, "reason": "body paragraph not found live"})
            continue
        try:
            hwp.set_pos(0, para, len(t["marker"]))  # caret just past the marker
            hwp.HAction.Run("MoveSelParaEnd")
            hwp.HAction.Run("Delete")
            if t["value"]:
                hwp.insert_text(t["value"])
            applied.append({"label": fid, "field_id": fid, "mode": "body_para"})
        except Exception as exc:  # pragma: no cover - live COM only
            skipped.append({"key": fid, "reason": f"live error: {exc}"})
