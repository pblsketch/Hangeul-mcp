from __future__ import annotations

import re


_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_UL = re.compile(r"^\s{0,3}[-*+]\s+(.+?)\s*$")
_OL = re.compile(r"^\s{0,3}\d+\.\s+(.+?)\s*$")


def _is_pipe_table_start(lines: list[str], index: int) -> bool:
    if index + 1 >= len(lines):
        return False
    first = lines[index].strip()
    second = lines[index + 1].strip()
    if "|" not in first or "|" not in second:
        return False
    cells = [c.strip() for c in second.strip("|").split("|")]
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", c or "") for c in cells)


def _split_table_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def markdown_to_blocks(markdown: str) -> list[dict]:
    lines = markdown.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks: list[dict] = []
    paragraph: list[str] = []
    i = 0

    def flush_paragraph() -> None:
        if paragraph:
            blocks.append({"type": "paragraph", "text": " ".join(paragraph).strip()})
            paragraph.clear()

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            i += 1
            continue
        if _is_pipe_table_start(lines, i):
            flush_paragraph()
            rows = [_split_table_row(lines[i])]
            i += 2
            while i < len(lines) and "|" in lines[i].strip():
                rows.append(_split_table_row(lines[i]))
                i += 1
            blocks.append({"type": "table", "rows": rows})
            continue
        heading = _HEADING.match(line)
        if heading:
            flush_paragraph()
            blocks.append({"type": "heading", "level": len(heading.group(1)), "text": heading.group(2)})
            i += 1
            continue
        ul = _UL.match(line)
        if ul:
            flush_paragraph()
            items = []
            while i < len(lines):
                m = _UL.match(lines[i])
                if not m:
                    break
                items.append(m.group(1))
                i += 1
            blocks.append({"type": "bullet_list", "items": items})
            continue
        ol = _OL.match(line)
        if ol:
            flush_paragraph()
            items = []
            while i < len(lines):
                m = _OL.match(lines[i])
                if not m:
                    break
                items.append(m.group(1))
                i += 1
            blocks.append({"type": "numbered_list", "items": items})
            continue
        paragraph.append(stripped)
        i += 1
    flush_paragraph()
    return blocks
