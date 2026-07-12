"""US-009/010: COM bridge (env-guarded) + apply tool graceful behavior.

Live COM tests only run when ``HANGEUL_MCP_LIVE=1`` (and Hangul is reachable),
so the suite never spawns a Hangul window by accident.
"""

import os

import pytest

from hangeul_core.hwp import (
    HwpBridge,
    find_broker_exact_path_candidates,
    normalize_field_values,
    pick_broker_exact_path_candidate,
    revalidate_broker_exact_path_candidate,
)
from hangeul_core.hwp.com import inspect_open_documents
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


class _Doc:
    def __init__(self, fullname):
        self.FullName = fullname


class _Docs:
    def __init__(self, docs, active_doc):
        self._docs = list(docs)
        self.Active_XHwpDocument = active_doc
        self.Count = len(self._docs)

    def Item(self, idx):
        if idx < 1 or idx > self.Count:
            raise IndexError(idx)
        return self._docs[idx - 1]


def test_inspect_open_documents_reports_active_provenance(tmp_path):
    src = tmp_path / "form.hwpx"
    other = tmp_path / "other.hwpx"
    docs = [_Doc(str(other)), _Doc(str(src))]

    rows = inspect_open_documents(_Docs(docs, docs[1]))

    assert rows[1]["is_active"] is True
    assert rows[1]["active_source"] == "identity"
    assert rows[1]["active_slot"] == 1
    assert rows[1]["active_path_empty"] is False
    assert rows[1]["active_identity_proven"] is True


def test_inspect_open_documents_reports_unprovable_active_empty_path():
    docs = [_Doc("C:/docs/one.hwpx")]

    rows = inspect_open_documents(_Docs(docs, _Doc("")))

    assert rows[0]["source"] == "Active_XHwpDocument"
    assert rows[0]["is_active"] is True
    assert rows[0]["active_source"] == "active_only"
    assert rows[0]["active_slot"] is None
    assert rows[0]["active_path_empty"] is True
    assert rows[0]["active_identity_proven"] is False




def test_find_broker_exact_path_candidates_preserve_ambiguity(tmp_path):
    src = tmp_path / "form.hwpx"
    src.write_bytes(b"x")
    instances = [
        {
            "moniker": "rot://1",
            "documents": [
                {
                    "path": str(src),
                    "slot": 0,
                    "is_active": True,
                    "active_source": "identity",
                    "active_slot": 0,
                    "active_path_empty": False,
                    "active_identity_proven": True,
                }
            ],
            "active_document": str(src),
        },
        {
            "moniker": "rot://2",
            "documents": [
                {
                    "path": str(src),
                    "slot": 0,
                    "is_active": False,
                    "active_source": "path",
                    "active_slot": 1,
                    "active_path_empty": False,
                    "active_identity_proven": False,
                }
            ],
            "active_document": str(src),
        },
    ]

    candidates = find_broker_exact_path_candidates(src, instances)

    assert len(candidates) == 2
    assert {c["moniker"] for c in candidates} == {"rot://1", "rot://2"}
    assert all(c["state"] == "attached_existing" for c in candidates)
    assert all(c["source"] == "rot_exact_path" for c in candidates)
    assert pick_broker_exact_path_candidate(src, instances) is None


def test_revalidate_broker_exact_path_candidate_rechecks_moniker_and_slot(tmp_path):
    src = tmp_path / "form.hwpx"
    src.write_bytes(b"x")
    candidate = {
        "moniker": "rot://1",
        "path": str(src),
        "slot": 1,
    }
    instances = [
        {
            "moniker": "rot://1",
            "documents": [
                {"path": str(src), "slot": 0, "is_active": False},
                {"path": str(src), "slot": 1, "is_active": True},
            ],
        },
        {
            "moniker": "rot://2",
            "documents": [{"path": str(src), "slot": 1, "is_active": True}],
        },
    ]

    matched = revalidate_broker_exact_path_candidate(src, candidate, instances)

    assert matched is not None
    assert matched["moniker"] == "rot://1"
    assert matched["slot"] == 1


def test_apply_tool_pathful_exact_path_delegates_to_exact_path_helper(monkeypatch, tmp_path):
    src = tmp_path / "form.hwpx"
    src.write_bytes(b"x")

    import hangeul_mcp.tools_live as live_tools

    monkeypatch.setattr(
        live_tools,
        "_apply_named_fields_exact_path",
        lambda path, values, visible=True: {
            "available": True,
            "connected": True,
            "ok": True,
            "state": "attached_existing",
            "requested_path": str(path),
            "applied": ["성명"],
            "skipped": [],
        },
    )

    res = server.apply_to_open_hwp({"성명": "홍길동"}, path=str(src))

    assert res["ok"] is True
    assert res["state"] == "attached_existing"
    assert res["requested_path"] == str(src)
    assert res["applied"] == ["성명"]


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
