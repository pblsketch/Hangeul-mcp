from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

from hangeul_core.delegate_base import doc, edit_result, require_method, save


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


def set_header(
    path: str | Path,
    text: str,
    out_path: str | Path,
    *,
    page_type: str = "BOTH",
) -> Dict:
    """Set header text (text comes from the client — D10 brain/hand split)."""
    doc_obj = doc(path)
    require_method(doc_obj, "set_header_text")(text, page_type=page_type)
    save(doc_obj, out_path)
    return edit_result(out_path)


def set_footer(
    path: str | Path,
    text: str,
    out_path: str | Path,
    *,
    page_type: str = "BOTH",
) -> Dict:
    doc_obj = doc(path)
    require_method(doc_obj, "set_footer_text")(text, page_type=page_type)
    save(doc_obj, out_path)
    return edit_result(out_path)


def split_merged_cell(
    path: str | Path,
    table_index: int,
    row: int,
    col: int,
    out_path: str | Path,
) -> Dict:
    """Un-merge a previously merged cell (python-hwpx split_merged_cell).

    Only merged cells can be split — arbitrary cell splitting is NOT exposed by
    python-hwpx 2.24 and stays a documented non-goal (ADR D13). A non-merged
    target surfaces as ok:false with the upstream error.
    """
    doc_obj = doc(path)
    table = _table_at(doc_obj, int(table_index))
    grid = require_method(table, "get_cell_map")()
    if not (0 <= int(row) < len(grid)) or not (0 <= int(col) < len(grid[int(row)])):
        return {"ok": False, "error": f"cell ({row},{col}) out of range for table {table_index}"}
    pos = grid[int(row)][int(col)]
    # upstream split_merged_cell is a silent no-op on non-merged cells — reject
    # explicitly so callers never get a vacuous ok:true (G1 spirit).
    if pos.row_span <= 1 and pos.col_span <= 1:
        return {"ok": False, "error": f"cell ({row},{col}) is not merged; only merged cells can be split (ADR D13)"}
    require_method(table, "split_merged_cell")(int(row), int(col))
    save(doc_obj, out_path)
    result = edit_result(out_path)
    result["table_index"] = table_index
    result["row"] = row
    result["col"] = col
    return result


def set_page_size(
    path: str | Path,
    out_path: str | Path,
    *,
    width: Optional[int] = None,
    height: Optional[int] = None,
    orientation: Optional[str] = None,
) -> Dict:
    """Page size in HWPUNITs (1/7200 inch); observable in section <hp:pagePr>."""
    if (width is not None and width <= 0) or (height is not None and height <= 0):
        return {"ok": False, "error": "width/height must be positive HWPUNITs (1/7200 inch)"}
    if width is None and height is None and orientation is None:
        return {"ok": False, "error": "nothing to change: pass width/height/orientation"}
    doc_obj = doc(path)
    require_method(doc_obj, "set_page_size")(width=width, height=height, orientation=orientation)
    save(doc_obj, out_path)
    return edit_result(out_path)


def set_page_margins(
    path: str | Path,
    out_path: str | Path,
    *,
    left: Optional[int] = None,
    right: Optional[int] = None,
    top: Optional[int] = None,
    bottom: Optional[int] = None,
    header: Optional[int] = None,
    footer: Optional[int] = None,
    gutter: Optional[int] = None,
) -> Dict:
    """Margins in HWPUNITs; observable in section <hp:margin> attributes."""
    values = {"left": left, "right": right, "top": top, "bottom": bottom,
              "header": header, "footer": footer, "gutter": gutter}
    if all(v is None for v in values.values()):
        return {"ok": False, "error": "nothing to change: pass at least one margin"}
    negative = [k for k, v in values.items() if v is not None and v < 0]
    if negative:
        return {"ok": False, "error": f"margins must be >= 0 HWPUNITs: {negative}"}
    doc_obj = doc(path)
    require_method(doc_obj, "set_page_margins")(**values)
    save(doc_obj, out_path)
    return edit_result(out_path)


def set_columns(path: str | Path, out_path: str | Path, col_count: int = 2) -> Dict:
    """Multi-column layout; observable as <hp:colPr colCount="N">."""
    if int(col_count) < 1:
        return {"ok": False, "error": "col_count must be >= 1"}
    doc_obj = doc(path)
    require_method(doc_obj, "set_columns")(int(col_count))
    save(doc_obj, out_path)
    return edit_result(out_path)


def set_page_number(
    path: str | Path,
    out_path: str | Path,
    *,
    position: str = "BOTTOM_CENTER",
) -> Dict:
    """Page-number field; observable as <hp:pageNum pos="...">."""
    doc_obj = doc(path)
    require_method(doc_obj, "set_page_number")(position=position)
    save(doc_obj, out_path)
    return edit_result(out_path)


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
