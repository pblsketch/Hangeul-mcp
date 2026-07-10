"""US-061: BYO-AI clients must not misread live status/boundaries.

A real Claude Desktop session interpreted ``hwp_status``'s ``connected:false``
as "the open document is unreachable" and gave up on the live path. The
guidance has to live in the server responses and tool descriptions themselves —
BYO-AI clients only see those, never our docs.
"""

import asyncio

from hangeul_mcp import server


def test_hwp_status_idle_carries_guidance():
    st = server.hwp_status()
    assert st.get("connected") is False  # side-effect-free probe never attaches
    note = st.get("note", "")
    assert "side-effect" in note or "attach" in note, "idle status must explain itself"
    assert "preview_cells_to_open_hwp" in st.get("next", ""), "idle status must name the next tool"


def test_live_tool_descriptions_state_value_only_boundary():
    tools = {t.name: (t.description or "") for t in asyncio.run(server.mcp.list_tools())}
    apply_named = tools["apply_to_open_hwp"].lower()
    assert "value" in apply_named and "format" in apply_named, (
        "apply_to_open_hwp description must state the value-only / no-formatting boundary"
    )
    assert "value" in tools["apply_cells_to_open_hwp"].lower()
    status_desc = tools["hwp_status"]
    assert "connected:false" in status_desc or "side-effect" in status_desc.lower()


def test_hwp_status_exposes_rot_instances_and_attach_boundary():
    st = server.hwp_status()
    assert isinstance(st.get("instances"), list), "instances must always be a list (empty off-Windows)"
    boundary = st.get("attach_boundary", "")
    assert "open_in_hwp" in boundary and "attach" in boundary, (
        "status must explain that hand-opened windows are not attachable and name open_in_hwp"
    )


def test_open_in_hwp_description_states_attach_boundary():
    tools = {t.name: (t.description or "") for t in asyncio.run(server.mcp.list_tools())}
    desc = tools["open_in_hwp"].lower()
    assert "hand-opened" in desc and "attach" in desc
    apply_cells = tools["apply_cells_to_open_hwp"].lower()
    assert "open_if_needed" in apply_cells or "opens it" in apply_cells


def test_live_tools_state_cold_start_and_inline_boundary():
    tools = {t.name: (t.description or "") for t in asyncio.run(server.mcp.list_tools())}
    assert "cold start" in tools["open_in_hwp"].lower()
    apply_cells = tools["apply_cells_to_open_hwp"].lower()
    assert "cold start" in apply_cells and "inline" in apply_cells
    st = server.hwp_status()
    assert "cold start" in st.get("first_call_hint", ""), (
        "status must warn that the first live call may launch Hangul"
    )


def test_capabilities_live_note_states_boundaries():
    caps = server.describe_capabilities()
    live = next(c for c in caps["capabilities"] if c["name"] == "live_hwp")
    note = live["note"].lower()
    assert "value" in note and ("format" in note or "styling" in note)
    assert "connected:false" in note or "side-effect" in note
