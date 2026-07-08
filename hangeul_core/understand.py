"""Form understanding: map labels to their value cells (merged-cell aware).

Korean forms place a value either to the *right* of its label or *below* it
(header-above-value layout), and cells are frequently merged (colSpan/rowSpan).
This module accounts for spans when locating the value cell so that, e.g., the
value for '성명' is the empty cell below it, not the adjacent '주민등록번호' label.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, Tuple

from hangeul_core.analyze import analyze
from hangeul_core.schema import (
    KIND_EMPTY_CELL,
    Cell,
    Field,
    FormSchema,
    normalize_label,
)


def _looks_like_label(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    # Labels are short-ish headers; skip obvious sentence/paragraph content.
    return len(stripped) <= 24


def _value_cell(label: Cell, index: Dict[Tuple[int, int], Cell]) -> Optional[Cell]:
    """Find the empty value cell for *label*: right first, then below."""
    right = index.get((label.row, label.col + label.col_span))
    if right is not None and right.is_empty:
        return right
    below = index.get((label.row + label.row_span, label.col))
    if below is not None and below.is_empty:
        return below
    return None


def understand(path: str | Path) -> FormSchema:
    """Produce a FormSchema of label -> value-cell fields (empty_cell kind)."""
    result = analyze(path)
    fields = []
    claimed = set()  # value cell field_ids already mapped

    for table in result.tables:
        index = {(c.row, c.col): c for c in table.cells}
        for cell in table.cells:
            if cell.is_empty or not _looks_like_label(cell.text):
                continue
            value = _value_cell(cell, index)
            if value is None or value.field_id in claimed:
                continue
            claimed.add(value.field_id)
            fields.append(
                Field(
                    field_id=value.field_id,
                    label=normalize_label(cell.text),
                    label_id=cell.field_id,
                    kind=KIND_EMPTY_CELL,
                    para_bullet=value.para_bullet,
                    char_spacing=value.char_spacing,
                )
            )
    return FormSchema(fmt=result.fmt, fields=fields)
