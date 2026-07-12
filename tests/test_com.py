"""US-009/010: COM bridge (env-guarded) + apply tool graceful behavior.

Live COM tests only run when ``HANGEUL_MCP_LIVE=1`` (and Hangul is reachable),
so the suite never spawns a Hangul window by accident.
"""

import os

import pytest

from hangeul_core.hwp import HwpBridge, find_rot_exact_path_candidates, normalize_field_values, pick_rot_exact_path_candidate
from hangeul_mcp import server


def test_available_returns_bool():
    assert isinstance(HwpBridge.available(), bool)


def test_status_unconnected_is_side_effect_free():
    st = HwpBridge().status()
    assert st["connected"] is False
    assert "available" in st


def test_normalize_field_values_newlines():
    out = normalize_field_values({"a": "x\ny", "b": "p\r\nq"})
    assert out["a"] == "x\r\ny"
    assert out["b"] == "p\r\nq"


def test_hwp_status_tool_does_not_dispatch():
    st = server.hwp_status()
    assert "available" in st
    assert st.get("connected") is False


def test_apply_tool_graceful_when_unavailable(monkeypatch):
    monkeypatch.setattr(HwpBridge, "available", staticmethod(lambda: False))
    res = server.apply_to_open_hwp({"성명": "홍길동"})
    assert res["available"] is False
    assert res["state"] == "unavailable"
    assert res["state"] != "attached_existing"
    assert "error" in res


def test_apply_tool_pathless_freezes_legacy_connected_state(monkeypatch):
    monkeypatch.setattr(HwpBridge, "available", staticmethod(lambda: True))
    monkeypatch.setattr(HwpBridge, "connect", lambda self, visible=True: self)
    monkeypatch.setattr(HwpBridge, "get_field_list", lambda self: ["성명"])
    monkeypatch.setattr(
        HwpBridge,
        "put_field_text",
        lambda self, values: {"applied": list(values), "skipped": []},
    )

    res = server.apply_to_open_hwp({"성명": "홍길동"})

    assert res["state"] == "legacy_connected"
    assert res["state"] != "attached_existing"
    assert res["connected"] is True
    assert res["field_count"] == 1
    assert res["applied"] == ["성명"]



def test_apply_tool_pathless_freezes_legacy_registration_state(monkeypatch):
    monkeypatch.setattr(HwpBridge, "available", staticmethod(lambda: True))
    monkeypatch.setattr(HwpBridge, "connect", lambda self, visible=True: self)
    monkeypatch.setattr(HwpBridge, "get_field_list", lambda self: [])

    res = server.apply_to_open_hwp({"성명": "홍길동"})

    assert res["state"] == "legacy_needs_field_registration"
    assert res["state"] != "attached_existing"
    assert res["needs_field_registration"] is True
    assert res["connected"] is True



def test_apply_tool_pathful_missing_file_uses_exact_path_state(monkeypatch, tmp_path):
    monkeypatch.setattr(HwpBridge, "available", staticmethod(lambda: True))

    def boom(self, *args, **kwargs):
        raise AssertionError("pathful apply_to_open_hwp must not use generic reconnect")

    monkeypatch.setattr(HwpBridge, "connect", boom)
    missing = tmp_path / "missing.hwpx"

    res = server.apply_to_open_hwp({"성명": "홍길동"}, path=str(missing))

    assert res["state"] == "not_found"
    assert res["requested_path"] == str(missing)
    assert res["available"] is True


def test_find_rot_exact_path_candidates_preserve_ambiguity(tmp_path):
    src = tmp_path / "form.hwpx"
    src.write_bytes(b"x")
    instances = [
        {
            "moniker": "rot://1",
            "documents": [{"path": str(src), "is_active": True}],
            "active_document": str(src),
        },
        {
            "moniker": "rot://2",
            "documents": [{"path": str(src), "is_active": False}],
            "active_document": str(src),
        },
    ]

    candidates = find_rot_exact_path_candidates(src, instances)

    assert len(candidates) == 2
    assert {c["moniker"] for c in candidates} == {"rot://1", "rot://2"}
    assert all(c["state"] == "attached_existing" for c in candidates)
    assert all(c["source"] == "rot_exact_path" for c in candidates)
    assert pick_rot_exact_path_candidate(src, instances) is None


def test_apply_tool_pathful_exact_path_candidates_still_refuses_generic_reconnect(monkeypatch, tmp_path):
    monkeypatch.setattr(HwpBridge, "available", staticmethod(lambda: True))

    def boom(self, *args, **kwargs):
        raise AssertionError("pathful apply_to_open_hwp must not use generic reconnect")

    monkeypatch.setattr(HwpBridge, "connect", boom)
    src = tmp_path / "form.hwpx"
    src.write_bytes(b"x")

    import hangeul_mcp.tools_live as live_tools

    monkeypatch.setattr(
        live_tools,
        "_exact_attach_candidates",
        lambda path: [
            {"state": "attached_existing", "path": str(src), "source": "rot_exact_path"},
            {"state": "attached_existing", "path": str(src), "source": "rot_exact_path"},
        ],
    )

    res = server.apply_to_open_hwp({"성명": "홍길동"}, path=str(src))

    assert res["ok"] is False
    assert res["state"] == "legacy_active_document"
    assert res["requested_path"] == str(src)
    assert res["attach_candidates"] == [
        {"state": "attached_existing", "path": str(src), "source": "rot_exact_path"},
        {"state": "attached_existing", "path": str(src), "source": "rot_exact_path"},
    ]
    assert "use open_in_hwp(path)" in res["note"]


def test_com_tools_registered():
    import asyncio

    tools = asyncio.run(server.mcp.list_tools())
    names = {t.name for t in tools}
    assert {"hwp_status", "apply_to_open_hwp"} <= names


@pytest.mark.skipif(
    os.environ.get("HANGEUL_MCP_LIVE") != "1",
    reason="live Hangul COM test; set HANGEUL_MCP_LIVE=1 on a desktop with Hangul open",
)
def test_live_connect_and_status():  # pragma: no cover - requires live Hangul
    bridge = HwpBridge()
    if not bridge.available():
        pytest.skip("pywin32/Hangul not available")
    bridge.connect()
    assert bridge.status()["connected"] is True
