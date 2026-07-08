"""형광펜(markpen) placeholder detection + fill.

Real 평가 운영 계획 templates mark an *example value* with a yellow highlight
(``<hp:markpenBegin/>2학년<hp:markpenEnd/>``) to signal "replace me". The
highlighted text is carried between the two self-closing markpen tags, usually
inside a single ``<hp:t>`` node. We detect each highlighted region as a field
and, on fill, replace **only the highlighted text** while leaving the
``markpenBegin``/``markpenEnd`` tags in place so the highlight is preserved.

Note: this deliberately keeps ``analyze._cell_content``'s itertext reading intact
(a highlighted cell must not look empty — see tests/test_markpen.py).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Tuple

from hangeul_core.analyze import _section_names
from hangeul_core.owpml import HwpxPackage
from hangeul_core.schema import KIND_MARKPEN, Field, normalize_label

# capture (begin tag)(highlighted text)(end tag) so fill can swap only the middle
_MARKPEN3 = re.compile(
    r"(<hp:markpenBegin\b[^>]*/>)(.*?)(<hp:markpenEnd\s*/>)", re.S
)
_TAGS = re.compile(r"<[^>]+>")
_T = re.compile(r"<hp:t>(.*?)</hp:t>", re.S)


def _nearby_label(section: str, pos: int, sample: str) -> str | None:
    """Nearest preceding short text (a label) before the highlight at *pos*.

    Prefers text sitting in the *same* ``<hp:t>`` before the highlight (e.g.
    "학교명 [예시]"), then falls back to the previous complete ``<hp:t>`` (e.g.
    a label cell to the left of the highlighted value cell).
    """
    topen = section.rfind("<hp:t>", 0, pos)
    if topen != -1:
        prefix = normalize_label(_TAGS.sub("", section[topen + len("<hp:t>"):pos]))
        if prefix and prefix != sample and len(prefix) <= 24:
            return prefix
    window = section[max(0, pos - 400):pos]
    for raw in reversed(_T.findall(window)):
        clean = normalize_label(_TAGS.sub("", raw))
        if clean and clean != sample and len(clean) <= 24:
            return clean
    return None


def markpen_regions(path: str | Path) -> List[Dict]:
    """Per-region records: field_id, label, sample, section, occ (in-section idx)."""
    pkg = HwpxPackage.open(path)
    out: List[Dict] = []
    n = 0
    for sname in _section_names(pkg):
        section = pkg.read(sname).decode("utf-8")
        for occ, m in enumerate(_MARKPEN3.finditer(section)):
            n += 1
            sample = normalize_label(_TAGS.sub("", m.group(2)))
            label = _nearby_label(section, m.start(), sample) or sample or f"강조{n}"
            out.append(
                {
                    "field_id": f"mk:{n}",
                    "label": label,
                    "sample": sample,
                    "section": sname,
                    "occ": occ,
                }
            )
    return out


def detect_markpen(path: str | Path) -> List[Field]:
    """Highlighted example values as KIND_MARKPEN fields."""
    return [
        Field(
            field_id=r["field_id"],
            label=r["label"],
            kind=KIND_MARKPEN,
            template=r["sample"],
            insert_after=r["sample"],
        )
        for r in markpen_regions(path)
    ]


def replace_markpen(section: str, occ_values: Dict[int, str], esc) -> Tuple[str, List[int]]:
    """Replace the highlighted text of the given in-section occurrences.

    ``occ_values`` maps an occurrence index (0-based, in document order within
    this section) to its new value. Regions whose highlighted content spans
    inline markup (contains ``<``) are left untouched (reported as not applied).
    """
    state = {"i": -1}
    applied: List[int] = []

    def repl(m: "re.Match") -> str:
        state["i"] += 1
        i = state["i"]
        if i in occ_values and "<" not in m.group(2):
            applied.append(i)
            return m.group(1) + esc(occ_values[i]) + m.group(3)
        return m.group(0)

    return _MARKPEN3.sub(repl, section), applied
