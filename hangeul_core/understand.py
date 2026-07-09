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


def _occupancy(cells) -> Dict[Tuple[int, int], Cell]:
    """Map every covered (row, col) coordinate to its owning (top-left) cell.

    Merged cells occupy a rectangle; indexing only the top-left would miss value
    cells whose adjacency coordinate is a *covered* (non-origin) coordinate.
    """
    grid: Dict[Tuple[int, int], Cell] = {}
    for c in cells:
        for r in range(c.row, c.row + max(1, c.row_span)):
            for cc in range(c.col, c.col + max(1, c.col_span)):
                grid.setdefault((r, cc), c)
    return grid


def _value_cell(label: Cell, grid: Dict[Tuple[int, int], Cell]) -> Optional[Cell]:
    """Find the empty value cell for *label*: right of its span, else below it."""
    right = grid.get((label.row, label.col + label.col_span))
    if right is not None and right is not label and right.is_empty:
        return right
    below = grid.get((label.row + label.row_span, label.col))
    if below is not None and below is not label and below.is_empty:
        return below
    return None


def _capacity_hint(value, header: str) -> "int | None":
    """Approx max Korean characters that fit *value* cell at its font width."""
    if not value.width:
        return None
    from hangeul_core.formfit import DEFAULT_INNER_MARGIN, font_height  # lazy: avoid cycle

    avail = value.width - DEFAULT_INNER_MARGIN
    fh = font_height(header, value.char_pr)
    if avail <= 0 or fh <= 0:
        return 0 if avail <= 0 else None
    return int(avail / fh)  # Hangul is ~full-width, so this is a safe lower bound


def understand(path: str | Path) -> FormSchema:
    """Produce a FormSchema of label -> value-cell fields (empty_cell kind)."""
    result = analyze(path)
    from hangeul_core.owpml import HwpxPackage

    header = HwpxPackage.open(path).read("Contents/header.xml").decode("utf-8")
    fields = []
    claimed = set()  # value cell field_ids already mapped

    for table in result.tables:
        grid = _occupancy(table.cells)
        for cell in table.cells:
            if cell.is_empty or not _looks_like_label(cell.text):
                continue
            value = _value_cell(cell, grid)
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
                    capacity_hint=_capacity_hint(value, header),
                )
            )
    return FormSchema(fmt=result.fmt, fields=fields)
