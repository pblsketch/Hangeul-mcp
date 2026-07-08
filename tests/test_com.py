"""US-009/010: COM bridge (env-guarded) + apply tool graceful behavior.

Live COM tests only run when ``HANGEUL_MCP_LIVE=1`` (and Hangul is reachable),
so the suite never spawns a Hangul window by accident.
"""

import os

import pytest

from hangeul_core.hwp import HwpBridge, normalize_field_values
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
    assert "error" in res


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
