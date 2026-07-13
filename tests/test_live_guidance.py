"""US-061: BYO-AI clients must not misread live status/boundaries.

A real Claude Desktop session interpreted ``hwp_status``'s ``connected:false``
as "the open document is unreachable" and gave up on the live path. The
guidance has to live in the server responses and tool descriptions themselves —
BYO-AI clients only see those, never our docs.
"""

import asyncio

from hangeul_mcp import server


def _tool_descriptions():
    return {t.name: (t.description or "") for t in asyncio.run(server.mcp.list_tools())}


def test_hwp_status_idle_carries_guidance():
    st = server.hwp_status()
    assert st.get("connected") is False  # side-effect-free probe never attaches
    note = st.get("note", "")
    assert "side-effect" in note or "attach" in note, "idle status must explain itself"
    nxt = st.get("next", "")
    assert "preview_cells_to_open_hwp" in nxt, "idle status must name the next tool"
    assert "open_in_hwp" in nxt and "exact path" in nxt.lower(), (
        "idle guidance must tell clients to attach by exact path before live apply"
    )


def test_live_tool_descriptions_state_value_only_boundary():
    tools = _tool_descriptions()
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
    assert "open_in_hwp" in boundary and "exact path" in boundary.lower(), (
        "status boundary must explain exact-path attach-first guidance"
    )
    assert "cannot be attached" not in boundary.lower() and "never register" not in boundary.lower(), (
        "status boundary must not claim hand-opened docs are categorically unattainable"
    )


def test_open_in_hwp_description_states_attach_boundary():
    tools = _tool_descriptions()
    desc = tools["open_in_hwp"].lower()
    assert "hand-opened" in desc and "exact path" in desc and "attach" in desc
    assert "cannot be attached" not in desc and "never register" not in desc
    apply_cells = tools["apply_cells_to_open_hwp"].lower()
    assert "open_if_needed" in apply_cells or "opens it" in apply_cells


def test_live_tools_state_cold_start_and_inline_boundary():
    tools = _tool_descriptions()
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

def test_hwp_status_exposes_runtime_observability_fields():
    caps = server.describe_capabilities()
    st = server.hwp_status()
    assert st["server_instance_id"] == caps["runtime"]["server_instance_id"]
    assert st["pid"] == caps["runtime"]["pid"]
    assert st["started_at"] == caps["runtime"]["started_at"]
    assert st["tool_schema_version"] == 1
    assert st["session_scope"] == "this stdio process"
    assert st["survives_restart"] is False
    assert st["feature_flags"]["raw_cell_editing"] is True
    assert st["feature_flags"]["live_addressed_editing"] is False
    ladder = st["attach_ladder"]
    assert {"window_detected", "rot_visible", "com_object_acquired", "document_identity_proven"} <= set(ladder)
