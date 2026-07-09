from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

from hangeul_core.delegate_base import doc, edit_result, save


def add_paragraph(
    path: str | Path,
    text: str,
    out_path: str | Path,
    section_index: Optional[int] = None,
) -> Dict:
    doc_obj = doc(path)
    kwargs = {} if section_index is None else {"section_index": section_index}
    doc_obj.add_paragraph(text, **kwargs)
    save(doc_obj, out_path)
    return edit_result(out_path)


def add_table(path: str | Path, rows: int, cols: int, out_path: str | Path) -> Dict:
    doc_obj = doc(path)
    doc_obj.add_table(rows, cols)
    save(doc_obj, out_path)
    return edit_result(out_path)


def _tables(doc_obj) -> list:
    tables = []
    for section in doc_obj.oxml.sections:
        for paragraph in section.paragraphs:
            tables.extend(paragraph.tables)
    return tables


def _table_at(doc_obj, table_index: int):
    if table_index < 0:
        raise ValueError("table_index must be >= 0")
    tables = _tables(doc_obj)
    if table_index >= len(tables):
        raise ValueError(f"table_index {table_index} out of range; table_count={len(tables)}")
    return tables[table_index]


def merge_table_cells(
    path: str | Path,
    table_index: int,
    cell_range: str,
    out_path: str | Path,
) -> Dict:
    if not cell_range or ":" not in cell_range:
        return {"ok": False, "error": "cell_range must be spreadsheet range like A1:B2"}
    doc_obj = doc(path)
    table = _table_at(doc_obj, int(table_index))
    table.merge_cells(cell_range)
    save(doc_obj, out_path)
    result = edit_result(out_path)
    result["table_index"] = table_index
    result["cell_range"] = cell_range
    return result


def set_cell_shading(
    path: str | Path,
    table_index: int,
    row: int,
    col: int,
    fill_color: str,
    out_path: str | Path,
) -> Dict:
    if not fill_color.startswith("#") or len(fill_color) != 7:
        return {"ok": False, "error": "fill_color must be a hex color like #FFF2CC"}
    doc_obj = doc(path)
    table = _table_at(doc_obj, int(table_index))
    table.set_cell_shading(int(row), int(col), fill_color)
    save(doc_obj, out_path)
    result = edit_result(out_path)
    result["table_index"] = table_index
    result["row"] = row
    result["col"] = col
    result["fill_color"] = fill_color
    return result


def emphasize_text(
    path: str | Path,
    find: str,
    out_path: str | Path,
    *,
    bold: bool = False,
    italic: bool = False,
    underline: bool = False,
    color: Optional[str] = None,
    size: Optional[float] = None,
) -> Dict:
    doc_obj = doc(path)
    cid = doc_obj.ensure_run_style(
        bold=bold, italic=italic, underline=underline, color=color, size=size
    )
    matched = 0
    for run in doc_obj.iter_runs():
        if find and find in (run.text or ""):
            run.char_pr_id_ref = cid
            matched += 1
    save(doc_obj, out_path)
    result = edit_result(out_path)
    result["matched_runs"] = matched
    return result


def add_picture(
    path: str | Path,
    image_path: str | Path,
    out_path: str | Path,
    *,
    width_mm: Optional[float] = None,
    height_mm: Optional[float] = None,
) -> Dict:
    img = Path(image_path)
    data = img.read_bytes()
    fmt = img.suffix.lstrip(".").lower() or "png"
    doc_obj = doc(path)
    kwargs: Dict = {}
    if width_mm is not None:
        kwargs["width_mm"] = width_mm
    if height_mm is not None:
        kwargs["height_mm"] = height_mm
    doc_obj.add_picture(data, fmt, **kwargs)
    save(doc_obj, out_path)
    return edit_result(out_path)
