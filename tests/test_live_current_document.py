from __future__ import annotations

import zipfile
from pathlib import Path

import hangeul_mcp.live_current as live_current
from hangeul_core.hwp import HwpBridge
from hangeul_core.hwp.current_document import classify_live_write_blocker



_NS = (
    'xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
    'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"'
)

SAMPLE_FIXTURE = Path(__file__).parent / "fixtures" / "sample_form.hwpx"
BODY_FIXTURE = Path(__file__).parent / "fixtures" / "공공기관 보고서 양식.hwpx"



def _field(begin: str, text_run: str, end: str) -> str:
    return (
        '<hp:run><hp:ctrl>' + begin + '</hp:ctrl></hp:run>'
        + text_run
        + '<hp:run><hp:ctrl>' + end + '</hp:ctrl></hp:run>'
    )


def _build_named_field(dst: Path, *, name: str = "성명") -> None:
    header = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
        b'<hh:head xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head"/>'
    )
    field = _field(
        f'<hp:fieldBegin id="1" type="CLICKHERE" name="{name}"/>',
        '<hp:run charPrIDRef="0"><hp:t>이름입력</hp:t></hp:run>',
        '<hp:fieldEnd id="1"/>',
    )
    section0 = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?><hs:sec {_NS}>'
        f'<hp:p id="1">{field}</hp:p></hs:sec>'
    ).encode()
    with zipfile.ZipFile(dst, "w") as z:
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        z.writestr(zi, b"application/hwp+zip")
        z.writestr("Contents/header.xml", header)
        z.writestr("Contents/section0.xml", section0)


def _doc(path: Path, **extra):
    return {
        "path": str(path),
        "normalized_path": str(path),
        "slot": 0,
        "is_active": True,
        "active_source": "identity",
        "active_slot": 0,
        "active_path_empty": False,
        "active_identity_proven": True,
        **extra,
    }


def _instance(moniker: str, *documents: dict):
    return [{"moniker": moniker, "documents": list(documents)}]


def test_resolve_current_reports_no_open_documents(monkeypatch):
    monkeypatch.setattr(HwpBridge, "available", staticmethod(lambda: True))
    monkeypatch.setattr(live_current, "list_rot_instances", lambda: [])
    res = live_current.resolve_current_hwp_document()
    assert res["state"] == "no_open_documents"
    assert res["candidates"] == []



def test_resolve_current_auto_selects_single_saved_active_hwpx(monkeypatch, tmp_path):
    src = tmp_path / "active.hwpx"
    other = tmp_path / "background.hwp"
    src.write_bytes(b"x")
    other.write_bytes(b"y")
    monkeypatch.setattr(
        live_current,
        "list_rot_instances",
        lambda: _instance("rot://1", _doc(src), _doc(other, slot=1, is_active=False)),
    )
    res = live_current.resolve_current_hwp_document()
    assert res["state"] == "auto_selected"
    assert res["selection_basis"] == "single_saved_active_hwpx"
    assert res["candidate"]["write_state"] == "writable"



def test_resolve_current_reports_unavailable_without_com_or_inventory(monkeypatch):
    monkeypatch.setattr(HwpBridge, "available", staticmethod(lambda: False))
    monkeypatch.setattr(live_current, "list_rot_instances", lambda: [])
    res = live_current.resolve_current_hwp_document()
    assert res["state"] == "unavailable"
    assert res["available"] is False


def test_resolve_current_auto_selects_single_saved_hwpx_total(monkeypatch, tmp_path):
    src = tmp_path / "only.hwpx"
    src.write_bytes(b"x")
    monkeypatch.setattr(live_current, "list_rot_instances", lambda: _instance("rot://1", _doc(src)))
    res = live_current.resolve_current_hwp_document()
    assert res["state"] == "auto_selected"
    assert res["selection_basis"] == "single_saved_hwpx_total"







def test_resolve_current_requires_selection_with_multiple_saved_hwpx(monkeypatch, tmp_path):
    active = tmp_path / "active.hwpx"
    other = tmp_path / "other.hwpx"
    active.write_bytes(b"x")
    other.write_bytes(b"y")
    monkeypatch.setattr(
        live_current,
        "list_rot_instances",
        lambda: _instance("rot://1", _doc(active), _doc(other, slot=1, is_active=False)),
    )
    res = live_current.resolve_current_hwp_document()
    assert res["state"] == "selection_required"
    assert len(res["candidates"]) == 2


def test_resolve_current_blocks_unsaved_active_document(monkeypatch):
    monkeypatch.setattr(
        live_current,
        "list_rot_instances",
        lambda: _instance(
            "rot://1",
            {
                "path": "",
                "normalized_path": "",
                "slot": 0,
                "is_active": True,
                "active_source": "identity",
                "active_slot": 0,
                "active_path_empty": True,
                "active_identity_proven": True,
            },
        ),
    )
    res = live_current.resolve_current_hwp_document()
    assert res["state"] == "current_document_unsaved"


def test_resolve_current_blocks_unprovable_active_document(monkeypatch, tmp_path):
    src = tmp_path / "form.hwpx"
    src.write_bytes(b"x")
    monkeypatch.setattr(
        live_current,
        "list_rot_instances",
        lambda: _instance("rot://1", _doc(src, active_identity_proven=False)),
    )
    res = live_current.resolve_current_hwp_document()
    assert res["state"] == "current_document_unprovable"


def test_preview_current_requires_hwpx_for_saved_hwp(monkeypatch, tmp_path):
    src = tmp_path / "form.hwp"
    src.write_bytes(b"x")
    monkeypatch.setattr(live_current, "list_rot_instances", lambda: _instance("rot://1", _doc(src)))
    res = live_current.preview_current_hwp_document({"성명": "홍길동"})
    assert res["state"] == "preview_requires_hwpx"
    assert res["ok"] is False
    assert "preview_token" not in res

def test_resolve_current_marks_saved_hwp_current_document_unsupported(monkeypatch, tmp_path):
    src = tmp_path / "legacy.hwp"
    src.write_bytes(b"x")
    monkeypatch.setattr(live_current, "list_rot_instances", lambda: _instance("rot://1", _doc(src)))
    res = live_current.resolve_current_hwp_document()
    assert res["state"] == "current_document_unsupported"


def test_preview_current_uses_real_cell_fixture(monkeypatch):
    monkeypatch.setattr(live_current, "list_rot_instances", lambda: _instance("rot://1", _doc(SAMPLE_FIXTURE)))
    res = live_current.preview_current_hwp_document({"성명": "홍길동", "직위": "교사"}, candidate_id=None)
    assert res["state"] == "preview_ready"
    assert res["route"] == "cells"
    assert res["selection_basis"] == "single_saved_hwpx_total"

    assert res["preview"]["count"] >= 2
    assert res["preview"]["targets"]


def test_preview_current_allows_explicit_candidate_selection(monkeypatch, tmp_path):
    first = tmp_path / "first.hwpx"
    second = tmp_path / "second.hwpx"
    _build_named_field(first)
    _build_named_field(second)
    monkeypatch.setattr(
        live_current,
        "list_rot_instances",
        lambda: _instance("rot://1", _doc(first), _doc(second, slot=1, is_active=False)),
    )
    selection = live_current.resolve_current_hwp_document()
    candidate_id = next(c["candidate_id"] for c in selection["candidates"] if c["path"] == str(second))
    monkeypatch.setattr(
        live_current,
        "preview_cells_to_open",
        lambda path, values: {
            "available": True,
            "ok": True,
            "targets": [{"label": "직위", "field_id": "t1.r0.c0", "value": "교사"}],
            "text_targets": [],
            "body_targets": [],
            "skipped": [],
        },
    )
    res = live_current.preview_current_hwp_document({"직위": "교사"}, candidate_id=candidate_id)
    assert res["state"] == "preview_ready"
    assert res["candidate"]["path"] == str(second)





def test_preview_current_mints_token_for_named_field(monkeypatch, tmp_path):
    src = tmp_path / "named.hwpx"
    _build_named_field(src)
    monkeypatch.setattr(live_current, "list_rot_instances", lambda: _instance("rot://1", _doc(src)))
    res = live_current.preview_current_hwp_document({"성명": "홍길동"})
    assert res["state"] == "preview_ready"
    assert res["route"] == "named_field"
    assert isinstance(res["preview_token"], str) and res["preview_token"]
    assert res["preview"]["named_field_keys"] == ["성명"]


def test_preview_current_reports_route_conflict(monkeypatch, tmp_path):
    src = tmp_path / "named.hwpx"
    _build_named_field(src)
    monkeypatch.setattr(live_current, "list_rot_instances", lambda: _instance("rot://1", _doc(src)))
    monkeypatch.setattr(
        live_current,
        "preview_cells_to_open",
        lambda path, values: {
            "available": True,
            "ok": True,
            "targets": [{"label": "성명", "field_id": "t1.r0.c0", "value": "홍길동"}],
            "text_targets": [],
            "body_targets": [],
            "skipped": [],
        },
    )
    res = live_current.preview_current_hwp_document({"성명": "홍길동"})
    assert res["state"] == "route_conflict"
    assert res["conflict_keys"] == ["성명"]

def test_preview_current_uses_real_body_fixture(monkeypatch):
    monkeypatch.setattr(live_current, "list_rot_instances", lambda: _instance("rot://1", _doc(BODY_FIXTURE)))
    res = live_current.preview_current_hwp_document({"b2": "새 본문"})
    assert res["state"] == "preview_ready"
    assert res["route"] == "cells"
    assert any(t["field_id"] == "b2" for t in res["preview"]["body_targets"])




def test_apply_current_rejects_stale_preview_token():
    res = live_current.apply_to_current_hwp_document("missing-token")
    assert res["state"] == "stale_preview_token"


def test_apply_current_detects_active_race(monkeypatch, tmp_path):
    src = tmp_path / "named.hwpx"
    _build_named_field(src)
    monkeypatch.setattr(live_current, "list_rot_instances", lambda: _instance("rot://1", _doc(src)))
    preview = live_current.preview_current_hwp_document({"성명": "홍길동"})
    monkeypatch.setattr(
        live_current,
        "list_rot_instances",
        lambda: _instance("rot://1", _doc(src, active_identity_proven=False)),
    )
    res = live_current.apply_to_current_hwp_document(preview["preview_token"])
    assert res["state"] == "active_race"


def test_apply_current_named_field_uses_exact_path_helper(monkeypatch, tmp_path):
    src = tmp_path / "named.hwpx"
    _build_named_field(src)
    monkeypatch.setattr(live_current, "list_rot_instances", lambda: _instance("rot://1", _doc(src)))
    preview = live_current.preview_current_hwp_document({"성명": "홍길동"})
    monkeypatch.setattr(
        live_current,
        "apply_named_fields_exact_path",
        lambda path, values: {
            "available": True,
            "connected": True,
            "ok": True,
            "state": "attached_existing",
            "applied": ["성명"],
            "skipped": [],
            "count": 1,
            "active_document": str(path),
        },
    )
    res = live_current.apply_to_current_hwp_document(preview["preview_token"])
    assert res["state"] == "applied_named_field"
    assert res["applied"] == ["성명"]

def test_preview_current_supports_mixed_route(monkeypatch, tmp_path):
    src = tmp_path / "named.hwpx"
    _build_named_field(src)
    monkeypatch.setattr(live_current, "list_rot_instances", lambda: _instance("rot://1", _doc(src)))
    monkeypatch.setattr(
        live_current,
        "preview_cells_to_open",
        lambda path, values: {
            "available": True,
            "ok": True,
            "targets": [{"label": "직위", "field_id": "t1.r0.c1", "value": "교사"}],
            "text_targets": [],
            "body_targets": [],
            "skipped": [],
        },
    )
    res = live_current.preview_current_hwp_document({"성명": "홍길동", "직위": "교사"})
    assert res["state"] == "preview_ready"
    assert res["route"] == "mixed"
    assert res["preview"]["named_field_keys"] == ["성명"]


def test_apply_current_reports_stale_candidate(monkeypatch, tmp_path):
    src = tmp_path / "named.hwpx"
    _build_named_field(src)
    monkeypatch.setattr(live_current, "list_rot_instances", lambda: _instance("rot://1", _doc(src)))
    preview = live_current.preview_current_hwp_document({"성명": "홍길동"})
    monkeypatch.setattr(
        live_current,
        "list_rot_instances",
        lambda: _instance("rot://1", _doc(src, slot=1, active_slot=1)),
    )
    res = live_current.apply_to_current_hwp_document(preview["preview_token"])
    assert res["state"] == "stale_candidate"


def test_apply_current_reports_closed_document(monkeypatch, tmp_path):
    src = tmp_path / "named.hwpx"
    _build_named_field(src)
    monkeypatch.setattr(HwpBridge, "available", staticmethod(lambda: True))
    monkeypatch.setattr(live_current, "list_rot_instances", lambda: _instance("rot://1", _doc(src)))
    preview = live_current.preview_current_hwp_document({"성명": "홍길동"})
    monkeypatch.setattr(live_current, "list_rot_instances", lambda: [])
    res = live_current.apply_to_current_hwp_document(preview["preview_token"])
    assert res["state"] == "closed_document"


def test_preview_current_refuses_read_only_candidate(monkeypatch, tmp_path):
    src = tmp_path / "named.hwpx"
    _build_named_field(src)
    monkeypatch.setattr(live_current, "candidate_write_state", lambda path: "read_only")
    monkeypatch.setattr(live_current, "list_rot_instances", lambda: _instance("rot://1", _doc(src)))
    res = live_current.preview_current_hwp_document({"성명": "홍길동"})
    assert res["state"] == "read_only"
    assert "preview_token" not in res


def test_apply_current_upgrades_unknown_to_read_only(monkeypatch, tmp_path):
    src = tmp_path / "named.hwpx"
    _build_named_field(src)
    monkeypatch.setattr(live_current, "candidate_write_state", lambda path: "unknown")
    monkeypatch.setattr(live_current, "list_rot_instances", lambda: _instance("rot://1", _doc(src)))
    preview = live_current.preview_current_hwp_document({"성명": "홍길동"})
    monkeypatch.setattr(live_current, "candidate_write_state", lambda path: "read_only")
    res = live_current.apply_to_current_hwp_document(preview["preview_token"])
    assert res["state"] == "read_only"


def test_apply_current_preserves_reload_blocked_existing(monkeypatch):
    monkeypatch.setattr(live_current, "list_rot_instances", lambda: _instance("rot://1", _doc(SAMPLE_FIXTURE)))
    preview = live_current.preview_current_hwp_document({"성명": "홍길동"})
    monkeypatch.setattr(
        live_current,
        "apply_cells_to_open",
        lambda path, values: {
            "available": True,
            "ok": False,
            "state": "reload_blocked_existing",
            "warning": "reload blocked",
        },
    )
    res = live_current.apply_to_current_hwp_document(preview["preview_token"])
    assert res["state"] == "reload_blocked_existing"


def test_apply_current_cells_success(monkeypatch):
    monkeypatch.setattr(HwpBridge, "available", staticmethod(lambda: True))
    monkeypatch.setattr(live_current, "list_rot_instances", lambda: _instance("rot://1", _doc(SAMPLE_FIXTURE)))
    preview = live_current.preview_current_hwp_document({"성명": "홍길동"})
    monkeypatch.setattr(
        live_current,
        "apply_cells_to_open",
        lambda path, values: {
            "available": True,
            "ok": True,
            "state": "attached_existing",
            "applied": [{"label": "성명", "field_id": "t1.r0.c0", "value": "홍길동"}],
            "skipped": [],
            "count": 1,
            "active_document": str(path),
        },
    )
    res = live_current.apply_to_current_hwp_document(preview["preview_token"])
    assert res["state"] == "applied_cells"
    assert res["count"] == 1



def test_apply_current_consumes_successful_preview_token(monkeypatch, tmp_path):
    src = tmp_path / "named.hwpx"
    _build_named_field(src)
    monkeypatch.setattr(live_current, "list_rot_instances", lambda: _instance("rot://1", _doc(src)))
    preview = live_current.preview_current_hwp_document({"성명": "홍길동"})
    monkeypatch.setattr(
        live_current,
        "apply_named_fields_exact_path",
        lambda path, values: {
            "available": True,
            "connected": True,
            "ok": True,
            "state": "attached_existing",
            "applied": ["성명"],
            "skipped": [],
            "count": 1,
            "active_document": str(path),
        },
    )
    first = live_current.apply_to_current_hwp_document(preview["preview_token"])
    second = live_current.apply_to_current_hwp_document(preview["preview_token"])
    assert first["state"] == "applied_named_field"
    assert second["state"] == "stale_preview_token"


def test_apply_current_mixed_success(monkeypatch, tmp_path):
    src = tmp_path / "named.hwpx"
    _build_named_field(src)
    monkeypatch.setattr(HwpBridge, "available", staticmethod(lambda: True))
    monkeypatch.setattr(live_current, "list_rot_instances", lambda: _instance("rot://1", _doc(src)))
    monkeypatch.setattr(
        live_current,
        "preview_cells_to_open",
        lambda path, values: {
            "available": True,
            "ok": True,
            "targets": [{"label": "직위", "field_id": "t1.r0.c1", "value": "교사"}],
            "text_targets": [],
            "body_targets": [],
            "skipped": [],
        },
    )
    preview = live_current.preview_current_hwp_document({"성명": "홍길동", "직위": "교사"})
    monkeypatch.setattr(
        live_current,
        "apply_named_fields_exact_path",
        lambda path, values: {
            "available": True,
            "connected": True,
            "ok": True,
            "state": "attached_existing",
            "applied": ["성명"],
            "skipped": [],
            "count": 1,
            "active_document": str(path),
        },
    )
    monkeypatch.setattr(
        live_current,
        "apply_cells_to_open",
        lambda path, values: {
            "available": True,
            "ok": True,
            "state": "attached_existing",
            "applied": [{"label": "직위", "field_id": "t1.r0.c1", "value": "교사"}],
            "skipped": [],
            "count": 1,
            "active_document": str(path),
        },
    )
    res = live_current.apply_to_current_hwp_document(preview["preview_token"])
    assert res["state"] == "applied_mixed"
    assert res["count"] == 2


def test_apply_current_invalidates_token_after_partial_mixed_failure(monkeypatch, tmp_path):
    src = tmp_path / "named.hwpx"
    _build_named_field(src)
    monkeypatch.setattr(HwpBridge, "available", staticmethod(lambda: True))
    monkeypatch.setattr(live_current, "list_rot_instances", lambda: _instance("rot://1", _doc(src)))
    monkeypatch.setattr(
        live_current,
        "preview_cells_to_open",
        lambda path, values: {
            "available": True,
            "ok": True,
            "targets": [{"label": "직위", "field_id": "t1.r0.c1", "value": "교사"}],
            "text_targets": [],
            "body_targets": [],
            "skipped": [],
        },
    )
    preview = live_current.preview_current_hwp_document({"성명": "홍길동", "직위": "교사"})
    monkeypatch.setattr(
        live_current,
        "apply_named_fields_exact_path",
        lambda path, values: {
            "available": True,
            "connected": True,
            "ok": True,
            "state": "attached_existing",
            "applied": ["성명"],
            "skipped": [],
            "count": 1,
            "active_document": str(path),
        },
    )
    monkeypatch.setattr(
        live_current,
        "apply_cells_to_open",
        lambda path, values: {
            "available": True,
            "ok": False,
            "state": "error",
            "error": "cell apply failed",
        },
    )
    first = live_current.apply_to_current_hwp_document(preview["preview_token"])
    second = live_current.apply_to_current_hwp_document(preview["preview_token"])
    assert first["state"] == "error"
    assert second["state"] == "stale_preview_token"


def test_classify_live_write_blocker_detects_read_only():
    out = classify_live_write_blocker(
        write_state="unknown",
        route="named_field",
        exc_text="Document is read-only",
        dialog_hint=None,
    )
    assert out == "read_only"
