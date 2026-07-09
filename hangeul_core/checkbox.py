"""체크박스(☑/□) 필드 탐지 + 선택.

Korean 평가 계획 templates offer options as a checkbox run inside a cell, e.g.
``☑논술 □구술 □실기``. We detect each such cell as a KIND_CHECKBOX field whose
``options`` list carries every ``{label, checked}`` pair, and on fill we toggle
the chosen option(s) by swapping the box glyph — canonically ``□`` (unchecked)
and ``☑`` (checked) — editing only the glyph character inside its ``<hp:t>``.

Scope (P0): checkbox groups that live in a table cell (the observed real case).
Glyphs may still be split across runs within the cell — handled via the same
concatenated-text/segment mapping used for placeholders.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional, Tuple

from hangeul_core.analyze import analyze
from hangeul_core.locate import _concat_map, _segments
from hangeul_core.schema import KIND_CHECKBOX, Field, normalize_label

_UNCHECKED = "□☐"
_CHECKED = "☑☒■▣√"
_GLYPHS = _UNCHECKED + _CHECKED
_CHECK_CANON = "☑"
_UNCHECK_CANON = "□"

_OPT = re.compile(rf"([{_GLYPHS}])\s*([^{_GLYPHS}]{{0,40}})")
_HAS_GLYPH = re.compile(rf"[{_GLYPHS}]")
_YES_NO = ({"예", "아니요"}, {"예", "아니오"}, {"동의", "미동의"}, {"동의", "비동의"}, {"Y", "N"})


def _parse_options(text: str) -> List[Tuple[str, bool]]:
    """Return [(label, checked)] for each glyph+label pair in *text*."""
    out: List[Tuple[str, bool]] = []
    for m in _OPT.finditer(text):
        label = normalize_label(m.group(2))
        if not label:
            continue
        out.append((label, m.group(1) in _CHECKED))
    return out


def _leading_label(text: str) -> str:
    """Text before the first glyph (a question label), if short enough."""
    m = _HAS_GLYPH.search(text)
    if not m:
        return ""
    lead = normalize_label(text[: m.start()]).rstrip(":： ")
    return lead if 0 < len(lead) <= 24 else ""


def detect_checkbox(path: str | Path) -> List[Field]:
    """Detect checkbox option groups inside table cells as KIND_CHECKBOX fields."""
    result = analyze(path)
    fields: List[Field] = []
    n = 0
    for table in result.tables:
        rows: dict = {}
        for c in table.cells:
            rows.setdefault(c.row, []).append(c)
        for r in rows.values():
            r.sort(key=lambda c: c.col)
        for cell in table.cells:
            opts = _parse_options(cell.text)
            if not opts:
                continue
            n += 1
            label = _leading_label(cell.text)
            if not label:
                same = rows.get(cell.row, [])
                left = [c for c in same if c.col < cell.col and c.text.strip() and not _HAS_GLYPH.search(c.text)]
                if left:
                    label = normalize_label(left[-1].text)
            if not label:
                above = _cell_above(table, cell)  # header row above the checkbox
                if above is not None:
                    label = normalize_label(above.text)
            if not label:
                # descriptive fallback so a generic group is still identifiable
                preview = " / ".join(o[0] for o in opts)
                label = (preview[:40] + ("…" if len(preview) > 40 else "")) + " 중 선택"
            select_type = "yes_no" if {o[0] for o in opts} in _YES_NO else "select"
            fields.append(
                Field(
                    field_id=cell.field_id,
                    label=label,
                    kind=KIND_CHECKBOX,
                    template=select_type,  # "yes_no" | "select" (client hint)
                    options=[{"label": lab, "checked": chk} for lab, chk in opts],
                )
            )
    return fields


def _cell_above(table, cell):
    """Nearest non-empty, non-checkbox cell directly above *cell* (header label)."""
    candidates = [
        c
        for c in table.cells
        if c.col == cell.col and c.row < cell.row and c.text.strip() and not _HAS_GLYPH.search(c.text)
    ]
    return max(candidates, key=lambda c: c.row) if candidates else None


def toggle_checkbox(tc_xml: str, value: str, exclusive: bool = True) -> Optional[str]:
    """Toggle the option(s) named in *value* within a cell's ``<hp:tc>`` XML.

    *value* is one option label, or several comma-separated labels. Chosen
    options become ``☑``; with *exclusive* (default) the others become ``□``.
    Returns the new tc XML, or ``None`` if no option label matched (nothing
    changed). Only glyph characters inside ``<hp:t>`` are edited.
    """
    targets = {normalize_label(v) for v in value.split(",") if v.strip()}
    if not targets:
        return None

    segs = _segments(tc_xml)
    if not segs:
        return None
    concat, idxmap = _concat_map(tc_xml, segs)

    edits: dict = {}  # seg_index -> list of (start, end, replacement)
    matched = False
    for m in _OPT.finditer(concat):
        label = normalize_label(m.group(2))
        if not label:
            continue
        gi = m.start(1)  # glyph char index in concat
        glyph = m.group(1)
        want_checked: Optional[bool]
        if label in targets:
            want_checked = True
            matched = True
        elif exclusive:
            want_checked = False
        else:
            continue
        new_glyph = _CHECK_CANON if want_checked else _UNCHECK_CANON
        if glyph == new_glyph:
            continue  # already in desired state (idempotent)
        si, off = idxmap[gi]
        edits.setdefault(si, []).append((off, off + 1, new_glyph))

    if not matched:
        return None
    if not edits:
        return tc_xml  # matched but already in desired state

    out = tc_xml
    for si in sorted(edits.keys(), reverse=True):
        s, e = segs[si]
        inner = tc_xml[s:e]
        for start, end, repl in sorted(edits[si], reverse=True):
            inner = inner[:start] + repl + inner[end:]
        out = out[:s] + inner + out[e:]
    return out
