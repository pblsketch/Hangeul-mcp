"""form-fit / 쪽수 드리프트 가드 — overflow estimation + opt-in auto-fit.

HWPX carries no layout engine, so whether filled text overflows a cell (and
pushes the page count) can only be *estimated*. This module provides a documented
heuristic:

* cell capacity  = ``cellSz`` width (HWPUNIT) minus an inner margin,
* text width     = Σ per-char advance, where a char's advance ≈ its font height
  (``charPr@height``, HWPUNIT) times a class factor: full-width/Hangul ≈ 1.0,
  latin/digit/punct/space ≈ 0.5.

``analyze_formfit`` reports fields whose widest line is estimated to exceed the
cell (pure measurement — no mutation). ``clone_charpr_scaled`` supports the
opt-in auto-fit in :func:`hangeul_core.fill.fill` (``auto_fit=True``), which
shrinks *only the filled run's* font via a cloned charPr down to a floor.

Explicit non-goal: pixel-perfect layout or true line wrapping. Visual truth is
deferred to Phase B ``render_preview``. Treat ratios as estimates.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from hangeul_core.analyze import analyze
from hangeul_core.checkbox import detect_checkbox
from hangeul_core.schema import label_key
from hangeul_core.understand import understand

DEFAULT_FONT_HEIGHT = 1000  # 10pt in HWPUNIT (100 HWPUNIT per point)
DEFAULT_INNER_MARGIN = 280  # left+right cell inner margin (≈140+140)


def _char_factor(ch: str) -> float:
    if ch.isspace():
        return 0.5
    o = ord(ch)
    if (
        0xAC00 <= o <= 0xD7A3  # Hangul syllables
        or 0x1100 <= o <= 0x11FF  # Hangul jamo
        or 0x3130 <= o <= 0x318F  # compatibility jamo
        or 0x4E00 <= o <= 0x9FFF  # CJK ideographs
        or 0xFF00 <= o <= 0xFFEF  # full-width forms
    ):
        return 1.0
    return 0.5  # latin / digit / punctuation


def estimate_width(text: str, font_height: int) -> float:
    """Estimated rendered width (HWPUNIT) of a single line of *text*."""
    return sum(font_height * _char_factor(c) for c in text)


def font_height(header: str, char_pr: Optional[str]) -> int:
    """Font height (HWPUNIT) for a charPr id, from header; default 10pt."""
    if not char_pr:
        return DEFAULT_FONT_HEIGHT
    m = re.search(r'<hh:charPr id="' + re.escape(char_pr) + r'"[^>]*?height="(\d+)"', header)
    return int(m.group(1)) if m else DEFAULT_FONT_HEIGHT


def _resolve_cell_fields(path: str | Path):
    """label/field_id -> Field for the cell-based kinds (empty_cell, checkbox)."""
    fields = understand(path).fields + detect_checkbox(path)
    by_id = {f.field_id: f for f in fields}
    by_label: Dict[str, object] = {}
    for f in fields:
        by_label.setdefault(label_key(f.label), f)
    return by_id, by_label


def analyze_formfit(
    path: str | Path,
    values: Dict[str, str],
    *,
    inner_margin: int = DEFAULT_INNER_MARGIN,
) -> Dict[str, object]:
    """Estimate whether each provided value overflows its target cell.

    Returns ``{"warnings": [...], "checked": N}``. Each warning carries
    ``field_id``, ``label``, ``estimated_width``, ``available_width`` and
    ``ratio`` (>1.0 means likely overflow). Only cell-addressable fields
    (empty_cell / checkbox) are evaluated; section-wide kinds are skipped.
    """
    from hangeul_core.owpml import HwpxPackage

    result = analyze(path)
    cells = {c.field_id: c for c in result.all_cells()}
    by_id, by_label = _resolve_cell_fields(path)
    header = HwpxPackage.open(path).read("Contents/header.xml").decode("utf-8")

    warnings: List[dict] = []
    checked = 0
    for key, value in values.items():
        fld = by_id.get(key) or by_label.get(label_key(key))
        if fld is None:
            continue
        cell = cells.get(fld.field_id.split("#")[0])
        if cell is None or not cell.width:
            continue
        checked += 1
        avail = cell.width - inner_margin
        fh = font_height(header, cell.char_pr)
        widest = max((estimate_width(ln, fh) for ln in value.split("\n")), default=0.0)
        ratio = (widest / avail) if avail > 0 else float("inf")
        if ratio > 1.0:
            warnings.append(
                {
                    "field_id": cell.field_id,
                    "label": fld.label,
                    "estimated_width": round(widest),
                    "available_width": avail,
                    "ratio": round(ratio, 2),
                    "overflow": True,
                }
            )
    return {"warnings": warnings, "checked": checked}


def overflow_scale(
    value: str,
    cell,
    header: str,
    *,
    inner_margin: int = DEFAULT_INNER_MARGIN,
    floor: float = 0.6,
) -> Optional[float]:
    """Shrink factor needed to fit *value* in *cell*, or None if it already fits.

    Bounded below by *floor* (never shrink past it). Returns a value in
    ``[floor, 1.0)`` when the estimate overflows.
    """
    if not cell.width:
        return None
    avail = cell.width - inner_margin
    if avail <= 0:
        return None
    fh = font_height(header, cell.char_pr)
    widest = max((estimate_width(ln, fh) for ln in value.split("\n")), default=0.0)
    if widest <= avail:
        return None
    return max(floor, avail / widest)


def clone_charpr_scaled(header: str, char_pr: str, scale: float) -> Tuple[str, Optional[str]]:
    """Append a height-scaled clone of *char_pr* to header; return (header, id)."""
    m = re.search(
        r'<hh:charPr id="' + re.escape(char_pr) + r'"(?:(?!</hh:charPr>).)*</hh:charPr>',
        header,
        re.S,
    )
    if not m:
        return header, None
    ids = [int(x) for x in re.findall(r'<hh:charPr id="(\d+)"', header)]
    new_id = (max(ids) + 1) if ids else 1
    block = re.sub(r'id="' + re.escape(char_pr) + r'"', 'id="%d"' % new_id, m.group(0), count=1)
    block = re.sub(
        r'height="(\d+)"',
        lambda x: 'height="%d"' % max(1, int(int(x.group(1)) * scale)),
        block,
        count=1,
    )
    if "</hh:charProperties>" not in header:
        return header, None
    header = header.replace("</hh:charProperties>", block + "</hh:charProperties>", 1)
    header = re.sub(
        r'<hh:charProperties itemCnt="(\d+)">',
        lambda x: '<hh:charProperties itemCnt="%d">' % (int(x.group(1)) + 1),
        header,
        count=1,
    )
    return header, str(new_id)
