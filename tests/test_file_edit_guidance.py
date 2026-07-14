import asyncio

from hangeul_mcp import server


def _tool_descriptions():
    return {tool.name: (tool.description or "") for tool in asyncio.run(server.mcp.list_tools())}


def test_addressed_preview_description_routes_to_structural_scope():
    desc = _tool_descriptions()["preview_addressed_edits"].lower()
    assert "do not require" in desc and "named fields" in desc
    assert "structural addresses" in desc
    assert "▶" in desc and "○○○" in desc
    assert "ordinary table cells" in desc and "paragraphs" in desc
    assert "global replace" in desc and "explicit scope" in desc
    assert "one edits array" in desc and "one tool call per cell" in desc
    assert "start in file mode" in desc
    assert "does not mutate" in desc and "already-open same hangul window" in desc
    assert "open the verified output" in desc
    assert "apply_addressed_edits(session_id, out_path)" in desc


def test_addressed_apply_description_keeps_file_mode_boundary():
    desc = _tool_descriptions()["apply_addressed_edits"].lower()
    assert "named" in desc and "fields" in desc
    assert "▶" in desc and "○○○" in desc
    assert "ordinary table cells" in desc and "paragraphs" in desc
    assert "one tool call per cell" in desc
    assert "file mode" in desc and "live field writes" in desc
    assert "does not mutate" in desc and "already-open same hangul window" in desc
    assert "structural" in desc and "global replacement" in desc
    assert "open the verified output" in desc
    assert "preview_addressed_edits" in desc and "out_path" in desc and "session_id" in desc


def test_complete_addressed_template_description_routes_one_shot_completion():
    desc = _tool_descriptions()["complete_addressed_template"].lower()
    assert "one `edits` array" in desc or "one edits array" in desc
    assert "not one call per cell" in desc
    assert "do not require" in desc and "named fields" in desc
    assert "▶" in desc and "○○○" in desc
    assert "ordinary table" in desc and "paragraphs" in desc
    assert "start in file mode" in desc
    assert "mixing live field writes" in desc and "falling back to file mode" in desc
    assert "does not" in desc and "mutate" in desc and "already-open same hangul window" in desc
    assert "open the verified output" in desc and "afterward" in desc
