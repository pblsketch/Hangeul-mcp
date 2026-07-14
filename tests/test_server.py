"""US-007: MCP server exposes the engine as tools (FastMCP)."""

import asyncio
from pathlib import Path

from hangeul_mcp import server
import hangeul_mcp.tools_file_edit as file_edit_tools

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
        "complete_addressed_template",
        "apply_edit_session",
        "restore_edit_session",
        "extract_hwp_text",
        "describe_capabilities",
        "preview_small_live_label_cells",
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

def test_complete_addressed_template_requires_distinct_out_path():
    res = server.complete_addressed_template(str(FIXTURE), [], str(FIXTURE))
    assert res["available"] is True
    assert res["ok"] is False
    assert res["state"] == "invalid_output_path"
def test_complete_addressed_template_rejects_resolved_same_path(tmp_path):
    fixture = tmp_path / "sample_form.hwpx"
    fixture.write_bytes(FIXTURE.read_bytes())

    res = server.complete_addressed_template(
        str(fixture),
        [{"target": "t1.r1.c1", "kind": "cell", "operation": "replace_text", "value": "홍길동", "expected_text": ""}],
        str(fixture.parent / "." / fixture.name),
    )

    assert res["available"] is True
    assert res["ok"] is False
    assert res["state"] == "invalid_output_path"
def test_apply_addressed_edits_requires_out_path():
    import inspect

    assert inspect.signature(server.apply_addressed_edits).parameters["out_path"].default is inspect._empty

def test_apply_addressed_edits_delegates_same_path_rejection(monkeypatch):
    monkeypatch.setattr(file_edit_tools, "_apply_addressed_edits", lambda session_id, out_path=None: {"ok": False, "state": "invalid_output_path"})
    res = server.apply_addressed_edits("sid", "same.hwpx")
    assert res == {"available": True, "ok": False, "state": "invalid_output_path"}
def test_apply_addressed_edits_rejects_hardlink_alias(tmp_path):
    fixture = Path(__file__).parent / "fixtures" / "lesson_plan_addressed.hwpx"
    source = tmp_path / "source.hwpx"
    alias = tmp_path / "alias.hwpx"
    source.write_bytes(fixture.read_bytes())
    alias.unlink(missing_ok=True)
    alias.hardlink_to(source)

    preview = server.preview_addressed_edits(
        str(source),
        [{"target": "b1", "kind": "body_para", "operation": "preserve_marker_replace_tail", "value": "빛의 반사", "expected_text": "▶ 수업 제목"}],
    )
    res = server.apply_addressed_edits(preview["session_id"], str(alias))
    assert res["available"] is True
    assert res["ok"] is False
    assert res["state"] == "invalid_output_path"


def test_complete_addressed_template_delegates_to_core(monkeypatch, tmp_path):
    out = tmp_path / "completed.hwpx"

    def _complete(path, edits, out_path, verify=True):
        assert path == str(FIXTURE)
        assert edits == [
            {
                "target": "t1.r1.c1",
                "value": "홍길동",
                "kind": "cell",
                "operation": "replace_text",
            }
        ]
        assert out_path == str(out)
        assert verify is False
        return {"ok": True, "state": "applied", "target_path": out_path, "counts": {"verified": 0}}

    monkeypatch.setattr(file_edit_tools._addressed, "complete_addressed_template", _complete, raising=False)

    res = server.complete_addressed_template(
        str(FIXTURE),
        [{"target": "t1.r1.c1", "value": "홍길동"}],
        str(out),
        verify=False,
    )

    assert res == {
        "available": True,
        "ok": True,
        "state": "applied",
        "target_path": str(out),
        "counts": {"verified": 0},
    }


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
