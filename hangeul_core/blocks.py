from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Dict

from hangeul_core.validate import validate_hwpx


def _module():
    if importlib.util.find_spec("hwpx") is None:
        raise RuntimeError("python-hwpx not installed (extra 'delegate')")
    import hwpx

    return hwpx


def _save(doc, out_path: str | Path) -> None:
    saver = getattr(doc, "save_to_path", None)
    if callable(saver):
        saver(str(out_path))
    else:
        doc.save(str(out_path))


def _result(out_path: str | Path) -> Dict:
    report = validate_hwpx(out_path)
    xsd_ok = report.get("xsd", {}).get("valid", True) is not False
    return {"ok": bool(report["valid"]) and xsd_ok, "out_path": str(out_path), "validation": report}


def _text(value) -> str:
    return "" if value is None else str(value)


def _add_text_paragraph(doc, text: str):
    doc.add_paragraph(text)
    return len(doc.paragraphs) - 1


def _add_table(doc, rows) -> tuple[int, int]:
    rows = [list(r) for r in rows]
    nrows = len(rows)
    ncols = max((len(r) for r in rows), default=0)
    if nrows == 0 or ncols == 0:
        raise ValueError("table block rows must be a non-empty 2D list")
    table = doc.add_table(nrows, ncols)
    for r, row in enumerate(rows):
        for c in range(ncols):
            table.set_cell_text(r, c, _text(row[c] if c < len(row) else ""))
    return nrows, ncols


def _add_image(doc, block: dict) -> None:
    image_path = block.get("image_path")
    if not image_path:
        raise ValueError("image block requires image_path")
    img = Path(image_path)
    data = img.read_bytes()
    fmt = img.suffix.lstrip(".").lower() or "png"
    kwargs = {}
    if block.get("width_mm") is not None:
        kwargs["width_mm"] = block["width_mm"]
    if block.get("height_mm") is not None:
        kwargs["height_mm"] = block["height_mm"]
    doc.add_picture(data, fmt, **kwargs)


def create_document_from_blocks(blocks: list, out_path: str | Path) -> Dict:
    if not isinstance(blocks, list) or not blocks:
        return {"ok": False, "error": "blocks must be a non-empty list"}
    doc = _module().HwpxDocument.new()
    stats = {"blocks": 0, "paragraphs": 0, "tables": 0, "images": 0}
    try:
        for block in blocks:
            if not isinstance(block, dict):
                raise ValueError("each block must be an object")
            kind = block.get("type")
            if kind == "heading":
                level = int(block.get("level", 1))
                idx = _add_text_paragraph(doc, _text(block.get("text")))
                doc.set_paragraph_format(paragraph_index=idx, outline_level=max(1, min(level, 6)))
                stats["paragraphs"] += 1
            elif kind == "paragraph":
                _add_text_paragraph(doc, _text(block.get("text")))
                stats["paragraphs"] += 1
            elif kind == "bullet_list":
                for item in block.get("items") or []:
                    idx = _add_text_paragraph(doc, _text(item))
                    doc.set_list_format(paragraph_index=idx, kind="bullet", level=1)
                    stats["paragraphs"] += 1
            elif kind == "numbered_list":
                for item in block.get("items") or []:
                    idx = _add_text_paragraph(doc, _text(item))
                    doc.set_list_format(paragraph_index=idx, kind="number", level=1)
                    stats["paragraphs"] += 1
            elif kind == "table":
                _add_table(doc, block.get("rows") or [])
                stats["tables"] += 1
            elif kind == "image":
                _add_image(doc, block)
                stats["images"] += 1
            elif kind == "page_break":
                idx = _add_text_paragraph(doc, "")
                doc.set_paragraph_format(paragraph_index=idx, page_break_before=True)
                stats["paragraphs"] += 1
            else:
                raise ValueError(f"unsupported block type: {kind}")
            stats["blocks"] += 1
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    _save(doc, out_path)
    result = _result(out_path)
    result.update(stats)
    return result
