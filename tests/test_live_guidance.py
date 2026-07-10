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


def test_capabilities_live_note_states_boundaries():
    caps = server.describe_capabilities()
    live = next(c for c in caps["capabilities"] if c["name"] == "live_hwp")
    note = live["note"].lower()
    assert "value" in note and ("format" in note or "styling" in note)
    assert "connected:false" in note or "side-effect" in note
