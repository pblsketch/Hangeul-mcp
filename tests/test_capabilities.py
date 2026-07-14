import asyncio
import tomllib
from pathlib import Path

from hangeul_core.capabilities import describe_capabilities
from hangeul_mcp import server


def test_manifest_matches_registered_tools_exactly():
    """Equality parity guard (not a subset): catches silent drift in BOTH directions.

    Every registered MCP tool must be listed in exactly one manifest bucket,
    modulo the explicit meta allowlist.
    """
    caps = server.describe_capabilities()
    manifest: set[str] = set()
    for cap in caps["capabilities"]:
        manifest |= set(cap["tools"])
    registered = {tool.name for tool in asyncio.run(server.mcp.list_tools())}
    meta_allowlist = {"describe_capabilities"}
    expected = registered - meta_allowlist
    assert manifest == expected, (
        f"manifest-only: {sorted(manifest - expected)}; unlisted: {sorted(expected - manifest)}"
    )
    counts: dict[str, int] = {}
    for cap in caps["capabilities"]:
        for name in cap["tools"]:
            counts[name] = counts.get(name, 0) + 1
    duplicated = sorted(name for name, n in counts.items() if n > 1)
    assert duplicated == [], f"tools listed in more than one bucket: {duplicated}"


def test_every_tool_has_nonempty_description():
    """LLM clients route by tool descriptions; an empty one is a routing dead end."""
    tools = asyncio.run(server.mcp.list_tools())
    missing = sorted(tool.name for tool in tools if not (tool.description or "").strip())
    assert missing == [], f"tools without descriptions: {missing}"


def test_own_engine_mail_merge_sits_in_file_bucket():
    file_cap = next(cap for cap in describe_capabilities()["capabilities"] if cap["mode"] == "file_hwpx")
    assert {"mail_merge", "analyze_formfit", "list_styles"} <= set(file_cap["tools"])
    delegate_cap = next(cap for cap in describe_capabilities()["capabilities"] if cap["mode"] == "delegate_hwpx")
    assert "mail_merge" not in delegate_cap["tools"], "mail_merge runs on the OWN engine, not python-hwpx"
    assert {
        "set_header",
        "set_footer",
        "split_merged_cell",
        "set_page_size",
        "set_page_margins",
        "set_columns",
        "set_page_number",
    } <= set(delegate_cap["tools"])


def test_describe_capabilities_no_server_side_llm():
    res = describe_capabilities()
    assert res["mode"] == "byo_ai_local_harness"
    assert res["server_side_llm"] is False
    assert res["privacy"]["server_side_llm"] is False
    names = {cap["name"] for cap in res["capabilities"]}
    modes = {cap["mode"] for cap in res["capabilities"]}
    expected = {"file_hwpx", "delegate_hwpx", "render", "live_hwp", "hwp_headless"}
    assert expected <= names
    assert expected <= modes
    hwp_headless = next(cap for cap in res["capabilities"] if cap["mode"] == "hwp_headless")
    assert hwp_headless["available"] is False


def test_server_describe_capabilities_tool_registered():
    res = server.describe_capabilities()
    assert res["product"] == "Hangeul-mcp"
    assert any("fill_form" in cap["tools"] for cap in res["capabilities"])


def test_delegate_capability_lists_document_spec_tool():
    delegate = next(cap for cap in describe_capabilities()["capabilities"] if cap["mode"] == "delegate_hwpx")
    assert "create_document_from_spec" in delegate["tools"]


def test_file_capability_lists_edit_session_tools():
    file_cap = next(cap for cap in server.describe_capabilities()["capabilities"] if cap["mode"] == "file_hwpx")
    assert {
        "search_and_replace",
        "batch_replace",
        "preview_search_and_replace",
        "preview_batch_replace",
        "preview_addressed_edits",
        "apply_addressed_edits",
        "complete_addressed_template",
        "apply_edit_session",
        "restore_edit_session",
    } <= set(file_cap["tools"])


def test_live_capability_lists_current_document_tools():
    live = next(cap for cap in describe_capabilities()["capabilities"] if cap["mode"] == "live_hwp")
    assert {
        "hwp_status",
        "open_in_hwp",
        "apply_to_open_hwp",
        "preview_small_live_label_cells",
        "apply_small_live_label_cells",
        "resolve_current_hwp_document",
        "preview_current_hwp_document",
        "apply_to_current_hwp_document",
    } <= set(live["tools"])

def test_runtime_observability_fields_present():
    res = server.describe_capabilities()
    runtime = res["runtime"]
    assert runtime["version"]
    assert runtime["build_identifier"]
    assert runtime["server_instance_id"]
    assert isinstance(runtime["pid"], int) and runtime["pid"] > 0
    assert runtime["started_at"].endswith("Z")
    assert runtime["tool_schema_version"] == 1
    assert runtime["session_scope"] == "this stdio process"
    assert runtime["survives_restart"] is False
    flags = res["feature_flags"]
    assert flags["body_paragraph"] is True
    assert flags["raw_cell_editing"] is True
    assert flags["occurrence_editing"] is False
    # promoted 2026-07-15 with the P0-C desktop QA gate (8/8 checks,
    # docs/evidence/live-addressed-desktop-capture.json); pin the promoted value
    assert flags["live_addressed_editing"] is True


def test_project_does_not_depend_on_llm_api_sdks():
    data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    project_deps = data["project"].get("dependencies", [])
    optional = data["project"].get("optional-dependencies", {})
    deps = list(project_deps)
    for values in optional.values():
        deps.extend(values)
    banned = ("openai", "anthropic", "google-generativeai", "pydantic-ai")
    normalized = [dep.split("[", 1)[0].split(">=", 1)[0].lower() for dep in deps]
    assert not (set(normalized) & set(banned))
