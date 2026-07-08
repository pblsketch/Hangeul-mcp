"""Inline-blank detection.

Korean forms often place fillable gaps *inside* a cell's running text rather
than in a dedicated empty cell:

* marker gaps    — a cell that is just a bullet marker ('∘'), with the sentence
                   tail in an adjacent cell ("∘ ___ 을 졸업하시고").
* colon gaps     — "은행명: ___ 계좌번호: ___" (multiple blanks in one cell).

These are the differentiating cases that whole-cell fillers cannot handle. Each
detected blank becomes a Field(kind=inline_blank) with an ``insert_after`` anchor
so the fill engine knows exactly where to splice the value.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List

from hangeul_core.analyze import analyze
from hangeul_core.schema import KIND_INLINE_BLANK, Field, normalize_label

MARKERS = "∘○•·"
_MARKER_ONLY = re.compile(rf"^[{re.escape(MARKERS)}]\s*$")
# A label right before a colon that is followed by a real gap (2+ spaces or end).
_COLON_BLANK = re.compile(r"([0-9A-Za-z가-힣][^:()\[\]]{0,15}?)\s*:(?=\s{2,}|\s*$)")


def detect_inline(path: str | Path) -> List[Field]:
    """Detect inline blanks (marker and colon gaps) across all tables."""
    result = analyze(path)
    fields: List[Field] = []

    for table in result.tables:
        rows = {}
        for c in table.cells:
            rows.setdefault(c.row, []).append(c)
        for r in rows.values():
            r.sort(key=lambda c: c.col)

        for cell in table.cells:
            text = cell.text
            if not text.strip():
                continue

            # 1) marker-only cell -> fill after the marker
            if _MARKER_ONLY.match(text.strip()):
                marker = text.strip()[0]
                same = rows.get(cell.row, [])
                left = [c for c in same if c.col < cell.col and c.text.strip()]
                right = [c for c in same if c.col > cell.col and c.text.strip()]
                label = normalize_label(left[-1].text) if left else ""
                tail = normalize_label(right[0].text) if right else ""
                template = f"{marker} {{}}" + (f" {tail}" if tail else "")
                fields.append(
                    Field(
                        field_id=f"{cell.field_id}#0",
                        label=label or "항목",
                        kind=KIND_INLINE_BLANK,
                        insert_after=marker,
                        template=template,
                        para_bullet=cell.para_bullet,
                        char_spacing=cell.char_spacing,
                    )
                )
                continue

            # 2) colon gaps within a single cell
            for m in _COLON_BLANK.finditer(text):
                lab = m.group(1).strip()
                fields.append(
                    Field(
                        field_id=f"{cell.field_id}#{lab}",
                        label=lab,
                        kind=KIND_INLINE_BLANK,
                        insert_after=m.group(0).strip(),  # e.g. "은행명:"
                        template=text,
                        char_spacing=cell.char_spacing,
                    )
                )

    return fields
