"""US-007: MCP server exposes the engine as tools (FastMCP)."""

import asyncio
from pathlib import Path

from hangeul_mcp import server

FIXTURE = Path(__file__).parent / "fixtures" / "sample_form.hwpx"


def test_four_tools_registered():
    tools = asyncio.run(server.mcp.list_tools())
    names = {t.name for t in tools}
    assert {
        "detect_format",
        "analyze_form",
        "fill_form",
        "extract_text",
        "merge_table_cells",
        "set_cell_shading",
        "create_document_from_blocks",
        "render_preview",
        "extract_hwp_text",
        "describe_capabilities",
        "preview_cells_to_open_hwp",
    } <= names


def test_detect_format_tool():
    res = server.detect_format(str(FIXTURE))
    assert res["format"] == "hwpx" and res["ok"] is True


def test_analyze_form_tool():
    res = server.analyze_form(str(FIXTURE))
    assert res["fields"]
    labels = {f["label"].replace(" ", "") for f in res["fields"]}
    assert "성명" in labels


def test_fill_form_tool_end_to_end(tmp_path):
    out = tmp_path / "o.hwpx"
    res = server.fill_form(str(FIXTURE), {"성명": "홍길동"}, str(out))
    assert any(f["label"].replace(" ", "") == "성명" for f in res["filled"])
    assert out.exists()
    assert "홍길동" in server.extract_text(str(out))


def test_extract_text_tool():
    txt = server.extract_text(str(FIXTURE))
    assert "강사카드" in txt.replace(" ", "")
