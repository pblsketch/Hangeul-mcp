"""Live fill for INLINE blanks — mirrors the file-mode fill engine (US-065).

Inline blanks (colon ``은행명:``, marker ``∘ 프로그램명``) live INSIDE a cell's
text, so a live fill cannot clear-and-insert like empty_cell targets without
destroying the labels around the blank. Instead of re-implementing insertion
rules live, we run the byte-preserving FILE fill against a temp output, diff
each cell's final text, and replace those cells' text in the open window —
insertion semantics stay exactly file-mode's (one source of truth).

Boundary (stated in tool docs): the live replacement flattens intra-cell rich
formatting to the caret format and only reaches table-cell content — body-text
placeholders outside tables stay file-mode-only. File mode remains the
byte-preserving gold path.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Dict, List, Tuple

from hangeul_core.analyze import analyze
from hangeul_core.fill import fill


def compute_cell_text_replacements(
    path: str | Path, values: Dict[str, str]
) -> Tuple[List[dict], List[dict]]:
    """Map values the empty_cell resolver could not place to full-cell text
    replacements (PURE — no COM).

    Returns ``(text_targets, skipped)``. Each target: ``{table, row, col,
    field_id, lines, labels, mode:"cell_text"}`` — ``lines`` is the cell's
    FINAL text split per paragraph. Values the file engine could not place are
    passed through in ``skipped``; values it placed outside a table cell are
    skipped with an explicit file-mode-only reason.
    """
    if not values:
        return [], []
    before = {c.field_id: (c.text or "") for c in analyze(path).all_cells()}
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / "live_mirror.hwpx"
        res = fill(str(path), values, str(tmp))
        if not res.filled:
            return [], list(res.skipped)
        after_cells = analyze(tmp).all_cells()

    labels_by_cell: Dict[str, List[str]] = {}
    for f in res.filled:
        labels_by_cell.setdefault(f["field_id"].split("#")[0], []).append(f["label"])

    targets: List[dict] = []
    for c in after_cells:
        new_text = c.text or ""
        if before.get(c.field_id, "") == new_text:
            continue
        targets.append(
            {
                "table": c.table,
                "row": c.row,
                "col": c.col,
                "field_id": c.field_id,
                "lines": new_text.split("\n"),
                "labels": labels_by_cell.get(c.field_id, []),
                "mode": "cell_text",
            }
        )

    skipped = list(res.skipped)
    target_cells = {t["field_id"] for t in targets}
    for f in res.filled:
        if f["field_id"].split("#")[0] not in target_cells:
            skipped.append(
                {"key": f["label"], "reason": "filled outside a table cell — file mode only"}
            )
    return targets, skipped


def apply_text_targets(hwp, text_targets: List[dict], applied: List[dict], skipped: List[dict]) -> None:
    """Replace each target cell's full text in the OPEN window (COM — desktop only).

    Navigates like the direct value path, then selects the cell's whole content
    LIST (``MoveListBegin`` → ``MoveSelListEnd``) and deletes it — a cell-object
    block Delete leaves the old paragraphs behind (verified 2026-07-11), a text
    selection does not. The replacement text already carries the labels around
    the blank, so the cell is rebuilt line by line.
    """
    for t in text_targets:
        key = ", ".join(t["labels"]) or t["field_id"]
        try:
            if not hwp.get_into_nth_table(t["table"] - 1):
                skipped.append({"key": key, "reason": "table not found live"})
                continue
            if not hwp.goto_addr(t["row"] + 1, t["col"] + 1, select_cell=False):
                skipped.append({"key": key, "reason": "cell address not reachable"})
                continue
            hwp.HAction.Run("Cancel")          # drop any block selection -> caret in cell
            hwp.HAction.Run("MoveListBegin")   # start of the cell's content list
            hwp.HAction.Run("MoveSelListEnd")  # select all cell text (not the cell object)
            hwp.HAction.Run("Delete")
            for i, line in enumerate(t["lines"]):
                if i:
                    hwp.HAction.Run("BreakPara")  # keep the cell's paragraph structure
                if line:
                    hwp.insert_text(line)
            applied.append({"label": key, "field_id": t["field_id"], "mode": "cell_text"})
        except Exception as exc:  # pragma: no cover - live COM only
            skipped.append({"key": key, "reason": f"live error: {exc}"})
