from __future__ import annotations

from pathlib import Path
from typing import Dict

from hangeul_core.delegate_base import edit_result, module, save


def create_table_from_rows(rows, out_path: str | Path) -> Dict:
    rows = [list(r) for r in rows]
    nrows = len(rows)
    ncols = max((len(r) for r in rows), default=0)
    if nrows == 0 or ncols == 0:
        return {"error": "rows must be a non-empty 2D list", "ok": False}
    doc_obj = module().HwpxDocument.new()
    table = doc_obj.add_table(nrows, ncols)
    for r, row in enumerate(rows):
        for c in range(ncols):
            val = row[c] if c < len(row) else ""
            table.set_cell_text(r, c, "" if val is None else str(val))
    save(doc_obj, out_path)
    result = edit_result(out_path)
    result["rows"] = nrows
    result["cols"] = ncols
    return result


def _official_lines(fields: Dict[str, str]) -> list:
    def g(key: str) -> str:
        return (fields.get(key) or "").strip()

    lines: list = []
    if g("기관명"):
        lines.append(g("기관명"))
        lines.append("")
    for key in ("수신", "참조"):
        if g(key):
            lines.append(f"{key}  {g(key)}")
    if g("수신") or g("참조"):
        lines.append("")
    if g("제목"):
        lines.append(f"제목  {g('제목')}")
        lines.append("")
    for para in g("본문").split("\n"):
        lines.append(para)
    lines.append("")
    if g("날짜"):
        lines.append(g("날짜"))
    if g("발신명의"):
        lines.append(g("발신명의"))
    if g("담당자"):
        lines.append(f"담당자  {g('담당자')}")
    return lines


def _press_lines(fields: Dict[str, str]) -> list:
    def g(key: str) -> str:
        return (fields.get(key) or "").strip()

    lines: list = []
    if g("기관명"):
        lines.append(g("기관명"))
    lines.append("보도자료")
    if g("배포일"):
        lines.append(f"배포일  {g('배포일')}")
    if g("담당"):
        contact = f" ({g('연락처')})" if g("연락처") else ""
        lines.append(f"담당  {g('담당')}{contact}")
    lines.append("")
    if g("제목"):
        lines.append(g("제목"))
    if g("부제"):
        lines.append(g("부제"))
    lines.append("")
    for para in g("본문").split("\n"):
        lines.append(para)
    lines.append("")
    if g("문의"):
        lines.append(f"문의  {g('문의')}")
    return lines


def _draft_lines(fields: Dict[str, str]) -> list:
    def g(key: str) -> str:
        return (fields.get(key) or "").strip()

    lines: list = []
    if g("제목"):
        lines.append(f"제목  {g('제목')}")
    lines.append("")
    for key in ("기안자", "기안일", "시행일", "수신"):
        if g(key):
            lines.append(f"{key}  {g(key)}")
    lines.append("")
    if g("목적"):
        lines.append("1. 목적")
        lines.append(f"   {g('목적')}")
    if g("내용"):
        lines.append("2. 내용")
        for para in g("내용").split("\n"):
            lines.append(f"   {para}")
    if g("붙임"):
        lines.append("")
        lines.append(f"붙임  {g('붙임')}")
    return lines


_RECIPE_BUILDERS = {
    "공문": _official_lines,
    "보도자료": _press_lines,
    "기안문": _draft_lines,
}


def create_official_document(
    fields: Dict[str, str], out_path: str | Path, doc_type: str = "공문"
) -> Dict:
    builder = _RECIPE_BUILDERS.get(doc_type, _official_lines)
    lines = builder(fields)
    doc_obj = module().HwpxDocument.new()
    for text in lines:
        doc_obj.add_paragraph(text)
    save(doc_obj, out_path)
    result = edit_result(out_path)
    result["doc_type"] = doc_type if doc_type in _RECIPE_BUILDERS else "공문"
    result["lines"] = len(lines)
    return result


def create_from_markdown(markdown: str, out_path: str | Path) -> Dict:
    from hangeul_core.markdown import markdown_to_blocks

    return create_document_from_blocks(markdown_to_blocks(markdown), out_path)


def create_document_from_blocks(blocks: list, out_path: str | Path) -> Dict:
    from hangeul_core.blocks import create_document_from_blocks as create

    return create(blocks, out_path)
