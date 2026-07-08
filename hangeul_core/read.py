"""Low-cost read-only helpers: text search, document outline, style listing.

These build on the existing ``analyze`` / ``extract`` engine and never mutate the
document. They round out the "reading" side of the tool surface (find where text
lives, get a structural overview, list the header's styles) without pulling in a
full editor.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Dict, List

from hangeul_core.analyze import analyze
from hangeul_core.checkbox import detect_checkbox
from hangeul_core.extract import extract_text
from hangeul_core.formfield import detect_form_fields
from hangeul_core.inline import detect_inline
from hangeul_core.locate import detect_placeholders
from hangeul_core.markpen import detect_markpen
from hangeul_core.owpml import HwpxPackage
from hangeul_core.understand import understand


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _snippet(text: str, query: str, pad: int = 12) -> str:
    i = text.find(query)
    if i < 0:
        return text[: pad * 2]
    s = max(0, i - pad)
    e = min(len(text), i + len(query) + pad)
    return ("…" if s > 0 else "") + text[s:e] + ("…" if e < len(text) else "")


def find_text(path: str | Path, query: str) -> Dict:
    """Find *query* in the document.

    Returns a document-wide ``count`` plus addressed ``cell_occurrences``
    (section + field_id + snippet) for matches that live in table cells.
    """
    if not query:
        return {"query": query, "count": 0, "cell_occurrences": []}
    result = analyze(path)
    occ: List[dict] = []
    for c in result.all_cells():
        if query in c.text:
            occ.append({"section": c.section, "field_id": c.field_id, "snippet": _snippet(c.text, query)})
    count = extract_text(path).count(query)
    return {"query": query, "count": count, "cell_occurrences": occ}


def _all_fields(path: str | Path):
    return (
        understand(path).fields
        + detect_inline(path)
        + detect_placeholders(path)
        + detect_markpen(path)
        + detect_checkbox(path)
        + detect_form_fields(path)
    )


def get_document_outline(path: str | Path) -> Dict:
    """Structural overview: sections, tables, cell counts, and field-kind tally."""
    pkg = HwpxPackage.open(path)
    sections = [n for n in pkg.names() if n.startswith("Contents/section") and n.endswith(".xml")]
    result = analyze(path)
    tables = [
        {"index": t.index, "rows": t.rows, "cols": t.cols, "cells": len(t.cells)}
        for t in result.tables
    ]
    cells = result.all_cells()
    kinds = Counter(f.kind for f in _all_fields(path))
    return {
        "sections": len(sections),
        "tables": tables,
        "cell_count": len(cells),
        "empty_cells": sum(1 for c in cells if c.is_empty),
        "fields_by_kind": dict(kinds),
    }


def list_styles(path: str | Path) -> Dict:
    """List header charPr (font height / hangul spacing) and paraPr (bullet)."""
    header = HwpxPackage.open(path).read("Contents/header.xml")
    root = ET.fromstring(header)
    char: List[dict] = []
    para: List[dict] = []
    for el in root.iter():
        ln = _local(el.tag)
        if ln == "charPr":
            cid = el.get("id")
            if cid is None:
                continue
            spacing = None
            for ch in el:
                if _local(ch.tag) == "spacing":
                    spacing = ch.get("hangul")
                    break
            height = el.get("height")
            char.append(
                {
                    "id": cid,
                    "height": int(height) if height and height.isdigit() else None,
                    "spacing_hangul": int(spacing) if spacing and spacing.lstrip("-").isdigit() else None,
                }
            )
        elif ln == "paraPr":
            pid = el.get("id")
            if pid is None:
                continue
            bullet = any(
                _local(c.tag) == "heading" and c.get("type") == "BULLET" for c in el.iter()
            )
            para.append({"id": pid, "bullet": bullet})
    return {"charPr": char, "paraPr": para}
