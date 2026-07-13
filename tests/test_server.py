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
        "create_document_from_spec",
        "render_preview",
        "preview_search_and_replace",
        "preview_batch_replace",
        "preview_addressed_edits",
        "apply_addressed_edits",
        "apply_edit_session",
        "restore_edit_session",
        "extract_hwp_text",
        "describe_capabilities",
        "preview_cells_to_open_hwp",
        "resolve_current_hwp_document",
        "preview_current_hwp_document",
        "apply_to_current_hwp_document",
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


def test_current_document_tools_delegate_to_live_module(monkeypatch):
    import hangeul_mcp.tools_live as live_tools

    monkeypatch.setattr(live_tools, "_resolve_current_hwp_document", lambda: {"state": "selection_required", "candidates": []})
    monkeypatch.setattr(
        live_tools,
        "_preview_current_hwp_document",
        lambda values, candidate_id=None, mode="auto": {
            "state": "preview_ready",
            "preview_token": "tok",
            "candidate": {"candidate_id": candidate_id, "picker_label": "sample.hwpx — fixtures"},
            "candidates": [{"candidate_id": candidate_id, "picker_label": "sample.hwpx — fixtures"}],
            "mode": mode,
        },
    )
    monkeypatch.setattr(
        live_tools,
        "_apply_to_current_hwp_document",
        lambda preview_token: {"state": "applied_cells", "preview_token": preview_token},
    )

    assert server.resolve_current_hwp_document()["state"] == "selection_required"
    preview = server.preview_current_hwp_document({"성명": "홍길동"}, candidate_id="cand-1", mode="strict")
    assert preview["state"] == "preview_ready"
    assert preview["candidate"]["candidate_id"] == "cand-1"
    assert preview["candidate"]["picker_label"] == "sample.hwpx — fixtures"
    assert preview["mode"] == "strict"
    assert server.apply_to_current_hwp_document("tok")["preview_token"] == "tok"
