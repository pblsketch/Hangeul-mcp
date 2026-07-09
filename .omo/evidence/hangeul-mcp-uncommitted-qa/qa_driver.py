from __future__ import annotations

import json
import sys
import traceback
import zipfile
from pathlib import Path
from typing import Any

from hangeul_core.validate import validate_hwpx
from hangeul_mcp import server


ROOT = Path(__file__).resolve().parent
ARTIFACTS = ROOT / "artifacts"
ARTIFACTS.mkdir(parents=True, exist_ok=True)


def _jsonable(value: Any) -> Any:
    try:
        json.dumps(value, ensure_ascii=False)
        return value
    except TypeError:
        return repr(value)


def call(name: str, *args, **kwargs) -> dict:
    fn = getattr(server, name)
    record = {
        "surface": "public Python/MCP tool function via hangeul_mcp.server",
        "invocation": f"server.{name}({', '.join([repr(a) for a in args] + [f'{k}={v!r}' for k, v in kwargs.items()])})",
    }
    try:
        result = fn(*args, **kwargs)
        record["result"] = _jsonable(result)
    except Exception as exc:
        record["exception"] = f"{type(exc).__name__}: {exc}"
        record["traceback"] = traceback.format_exc()
    return record


def png_dimensions(path: Path) -> tuple[int | None, int | None]:
    data = path.read_bytes()[:24]
    if len(data) >= 24 and data[:8] == b"\x89PNG\r\n\x1a\n":
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    return None, None


def zip_contains(path: Path, needle: str) -> bool:
    encoded = needle.encode("utf-8")
    with zipfile.ZipFile(path) as zf:
        for name in zf.namelist():
            if name.endswith(".xml") and encoded in zf.read(name):
                return True
    return False


def main() -> int:
    evidence: dict[str, Any] = {"artifacts_dir": str(ARTIFACTS), "calls": {}, "checks": {}}

    table_src = ARTIFACTS / "table_src.hwpx"
    table_merged = ARTIFACTS / "table_merged.hwpx"
    table_shaded = ARTIFACTS / "table_shaded.hwpx"
    evidence["calls"]["create_table_from_rows_for_table_ops"] = call(
        "create_table_from_rows",
        [["Header A", "Header B"], ["Left", "Right"]],
        str(table_src),
    )
    evidence["calls"]["merge_table_cells"] = call(
        "merge_table_cells", str(table_src), 0, "A1:B1", str(table_merged)
    )
    evidence["calls"]["set_cell_shading"] = call(
        "set_cell_shading", str(table_merged), 0, 1, 0, "#FFF2CC", str(table_shaded)
    )
    evidence["calls"]["merge_invalid_range"] = call(
        "merge_table_cells", str(table_src), 0, "A1", str(ARTIFACTS / "bad_range.hwpx")
    )
    evidence["calls"]["shade_invalid_color"] = call(
        "set_cell_shading", str(table_src), 0, 0, 0, "FFF2CC", str(ARTIFACTS / "bad_color.hwpx")
    )
    evidence["calls"]["merge_bad_table_index"] = call(
        "merge_table_cells", str(table_src), 99, "A1:B1", str(ARTIFACTS / "bad_table.hwpx")
    )
    if table_shaded.exists():
        evidence["checks"]["table_shaded_validate"] = validate_hwpx(table_shaded)
        evidence["checks"]["table_shaded_contains_fill_color"] = zip_contains(table_shaded, "FFF2CC")
        evidence["calls"]["table_shaded_text"] = call("extract_text", str(table_shaded))
        evidence["calls"]["table_shaded_map"] = call("get_table_map", str(table_shaded))

    blocks_out = ARTIFACTS / "blocks_document.hwpx"
    blocks = [
        {"type": "heading", "level": 1, "text": "블록 문서 제목"},
        {"type": "paragraph", "text": "첫 문단"},
        {"type": "bullet_list", "items": ["불릿 하나", "불릿 둘"]},
        {"type": "numbered_list", "items": ["번호 하나", "번호 둘"]},
        {"type": "table", "rows": [["구분", "값"], ["A", "10"]]},
        {"type": "page_break"},
        {"type": "paragraph", "text": "마지막 문단"},
    ]
    evidence["calls"]["create_document_from_blocks"] = call(
        "create_document_from_blocks", blocks, str(blocks_out)
    )
    evidence["calls"]["create_document_from_blocks_empty"] = call(
        "create_document_from_blocks", [], str(ARTIFACTS / "empty_blocks.hwpx")
    )
    evidence["calls"]["create_document_from_blocks_unknown"] = call(
        "create_document_from_blocks", [{"type": "unknown"}], str(ARTIFACTS / "unknown_blocks.hwpx")
    )
    if blocks_out.exists():
        evidence["checks"]["blocks_validate"] = validate_hwpx(blocks_out)
        evidence["calls"]["blocks_text"] = call("extract_text", str(blocks_out))
        evidence["calls"]["blocks_table_map"] = call("get_table_map", str(blocks_out))

    markdown = (
        "# 마크다운 제목\n\n"
        "도입 문단입니다.\n\n"
        "- 불릿 A\n"
        "- 불릿 B\n\n"
        "1. 번호 A\n"
        "2. 번호 B\n\n"
        "| 항목 | 값 |\n"
        "| --- | --- |\n"
        "| 사과 | 3 |\n"
        "| 배 | 5 |\n"
    )
    md_out = ARTIFACTS / "markdown_document.hwpx"
    evidence["calls"]["create_hwpx_from_markdown"] = call(
        "create_hwpx_from_markdown", markdown, str(md_out)
    )
    if md_out.exists():
        evidence["checks"]["markdown_validate"] = validate_hwpx(md_out)
        evidence["calls"]["markdown_text"] = call("extract_text", str(md_out))
        evidence["calls"]["markdown_table_map"] = call("get_table_map", str(md_out))

    preview_out = ARTIFACTS / "markdown_preview.png"
    evidence["calls"]["render_preview"] = call(
        "render_preview", str(md_out), str(preview_out), "png", 900, 1300
    )
    if preview_out.exists():
        width, height = png_dimensions(preview_out)
        evidence["checks"]["render_preview_png"] = {
            "exists": True,
            "bytes": preview_out.stat().st_size,
            "width": width,
            "height": height,
        }
    else:
        evidence["checks"]["render_preview_png"] = {"exists": False}
    evidence["calls"]["render_preview_bad_format"] = call(
        "render_preview", str(md_out), str(ARTIFACTS / "bad_preview.jpg"), "jpg", 900, 1300
    )

    fake_hwp = ARTIFACTS / "fake_binary.hwp"
    fake_hwp.write_bytes(b"HWP Document File\x00non-real fixture")
    evidence["calls"]["extract_hwp_text_fake_hwp"] = call("extract_hwp_text", str(fake_hwp))
    evidence["calls"]["extract_hwp_text_missing"] = call(
        "extract_hwp_text", str(ARTIFACTS / "missing.hwp")
    )
    evidence["calls"]["extract_hwp_text_wrong_extension"] = call("extract_hwp_text", str(md_out))

    summary_path = ROOT / "qa_driver_results.json"
    summary_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "ok", "results": str(summary_path), "artifacts": str(ARTIFACTS)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
