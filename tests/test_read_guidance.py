import asyncio

from hangeul_mcp import server


TARGETS = {
    "inspect_editable_regions": [
        "not required",
        "repeated `▶`",
        "repeated `○○○`",
        "ordinary table cells",
        "paragraphs",
        "global-replace",
        "preview_addressed_edits",
        "apply_addressed_edits(session_id, out_path)",
        "completed copy",
        "does not mutate the already-open same Hangul window",
    ],
    "find_text_occurrences": [
        "not required",
        "repeated `▶`",
        "repeated `○○○`",
        "ordinary table",
        "paragraphs",
        "globally replaced without",
        "preview_addressed_edits",
        "apply_addressed_edits(session_id, out_path)",
        "complete_addressed_template",
        "completed copy",
        "does not mutate the already-open same Hangul window",
    ],
    "plan_template_completion": [
        "not required",
        "repeated `▶`",
        "repeated `○○○`",
        "ordinary table cells",
        "paragraphs",
        "repeated text without explicit scope",
        "all values first",
        "one complete addressed edits array",
        "instead of one tool call per cell",
        "mixing live field writes",
        "completed copy",
        "does not mutate the already-open same Hangul window",
    ],
}


def _tool_descriptions():
    return {tool.name: (tool.description or "") for tool in asyncio.run(server.mcp.list_tools())}


def test_read_tool_descriptions_pin_template_routing_guidance():
    descriptions = _tool_descriptions()
    for tool_name, required_snippets in TARGETS.items():
        desc = descriptions[tool_name]
        missing = [snippet for snippet in required_snippets if snippet.lower() not in desc.lower()]
        assert not missing, f"{tool_name} description lost routing guidance: {missing}"


def test_plan_template_completion_description_pins_file_mode_handoff():
    desc = _tool_descriptions()["plan_template_completion"].lower()
    assert "file mode" in desc
    assert "complete_addressed_template" in desc
    assert "one tool call per cell" in desc
    assert "already-open same hangul window" in desc
def test_read_tool_descriptions_pin_preview_then_session_apply_contract():
    descriptions = _tool_descriptions()
    for tool_name in ("inspect_editable_regions", "find_text_occurrences"):
        desc = descriptions[tool_name].lower()
        assert "preview_addressed_edits" in desc
        assert "apply_addressed_edits(session_id, out_path)" in desc
        assert "one addressed edits array" in desc
