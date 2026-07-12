import tomllib
from pathlib import Path

from hangeul_core.capabilities import describe_capabilities
from hangeul_mcp import server


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


def test_live_capability_lists_current_document_tools():
    live = next(cap for cap in describe_capabilities()["capabilities"] if cap["mode"] == "live_hwp")
    assert {
        "resolve_current_hwp_document",
        "preview_current_hwp_document",
        "apply_to_current_hwp_document",
    } <= set(live["tools"])


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
