"""Structural analysis of HWPX forms.

Walks every table in the document and produces addressed cells (rowAddr/colAddr
with colSpan/rowSpan), resolving each cell's first paragraph bullet style and
first run character spacing from the header definitions. This is the raw
structure that `understand` and `inline` build meaning on top of.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Optional, Tuple

from hangeul_core.owpml import HwpxPackage
from hangeul_core.schema import AnalyzeResult, Cell, Table


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _find_child(parent, local: str):
    for ch in parent:
        if _local(ch.tag) == local:
            return ch
    return None


def _parse_header(header_xml: bytes) -> Tuple[Dict[str, bool], Dict[str, Optional[int]]]:
    """Return (paraPr_id -> is_bullet, charPr_id -> hangul spacing)."""
    root = ET.fromstring(header_xml)
    para_bullet: Dict[str, bool] = {}
    char_spacing: Dict[str, Optional[int]] = {}
    for el in root.iter():
        ln = _local(el.tag)
        if ln == "paraPr":
            pid = el.get("id")
            if pid is None:
                continue
            bullet = any(
                _local(ch.tag) == "heading" and ch.get("type") == "BULLET"
                for ch in el.iter()
            )
            para_bullet[pid] = bullet
        elif ln == "charPr":
            cid = el.get("id")
            if cid is None:
                continue
            spacing: Optional[int] = None
            for ch in el:
                if _local(ch.tag) == "spacing":
                    raw = ch.get("hangul")
                    if raw is not None:
                        try:
                            spacing = int(raw)
                        except ValueError:
                            spacing = None
                    break
            char_spacing[cid] = spacing
    return para_bullet, char_spacing


def _cell_content(tc):
    """Own text (excluding nested tables) + nested flag + first paraPr/charPr/paraId."""
    parts = []
    state = {"nested": False, "para": None, "char": None, "pid": None}

    def rec(node):
        for ch in node:
            ln = _local(ch.tag)
            if ln == "tbl":
                state["nested"] = True
                continue  # do not descend into a nested table's own content
            if ln == "p":
                if state["para"] is None and ch.get("paraPrIDRef") is not None:
                    state["para"] = ch.get("paraPrIDRef")
                if state["pid"] is None and ch.get("id") is not None:
                    state["pid"] = ch.get("id")
            elif ln == "run" and state["char"] is None:
                cpr = ch.get("charPrIDRef")
                if cpr is not None:
                    state["char"] = cpr
            elif ln == "t":
                # Capture ALL text inside <hp:t>, including text carried as the
                # tail of inline children like <hp:markpenBegin> (highlight) —
                # otherwise highlighted cells look empty.
                txt = "".join(ch.itertext())
                if txt:
                    parts.append(txt)
                continue  # fully captured; don't re-descend into inline markup
            rec(ch)

    rec(tc)
    return "".join(parts), state["nested"], state["para"], state["char"], state["pid"]


def _section_names(pkg: HwpxPackage):
    names = [
        n
        for n in pkg.names()
        if n.startswith("Contents/section") and n.endswith(".xml")
    ]

    def order(n: str) -> int:
        digits = "".join(ch for ch in n if ch.isdigit())
        return int(digits) if digits else 0

    return sorted(names, key=order)


def analyze(path: str | Path) -> AnalyzeResult:
    """Analyze an HWPX file into addressed tables/cells with style flags."""
    pkg = HwpxPackage.open(path)
    para_bullet, char_spacing = _parse_header(pkg.read("Contents/header.xml"))

    tables = []
    ti = 0
    for sname in _section_names(pkg):
        root = ET.fromstring(pkg.read(sname))
        tis = 0  # table index within this section
        for tbl in root.iter():
            if _local(tbl.tag) != "tbl":
                continue
            ti += 1
            tis += 1
            trs = [tr for tr in tbl if _local(tr.tag) == "tr"]
            rowcnt = int(tbl.get("rowCnt") or len(trs) or 0)
            colcnt = int(tbl.get("colCnt") or 0)
            cells = []
            for tr in trs:
                for tc in tr:
                    if _local(tc.tag) != "tc":
                        continue
                    addr = _find_child(tc, "cellAddr")
                    span = _find_child(tc, "cellSpan")
                    row = int(addr.get("rowAddr")) if addr is not None else -1
                    col = int(addr.get("colAddr")) if addr is not None else -1
                    cs = int(span.get("colSpan")) if span is not None else 1
                    rs = int(span.get("rowSpan")) if span is not None else 1
                    text, nested, ppr, cpr, pid = _cell_content(tc)
                    cells.append(
                        Cell(
                            table=ti,
                            row=row,
                            col=col,
                            col_span=cs,
                            row_span=rs,
                            text=text,
                            is_empty=(text.strip() == "" and not nested),
                            has_nested_table=nested,
                            para_bullet=para_bullet.get(ppr, False) if ppr else False,
                            char_spacing=char_spacing.get(cpr) if cpr else None,
                            para_pr=ppr,
                            char_pr=cpr,
                            para_id=pid,
                            section=sname,
                            table_in_section=tis,
                        )
                    )
            tables.append(Table(index=ti, rows=rowcnt, cols=colcnt, cells=cells))
    return AnalyzeResult(fmt="hwpx", tables=tables)
