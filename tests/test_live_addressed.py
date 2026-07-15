"""P0-C in-place live addressed editing — PURE plan + fake-COM apply.

The flag ``live_addressed_editing`` was promoted True with the desktop QA gate
(docs/evidence/live-addressed-desktop-capture.json, 8/8 checks); the gating
mechanism itself is still exercised here by patching the gate helper off.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import hangeul_core.hwp.live_addressed as la
import hangeul_mcp.live_current as live_current
from hangeul_core.hwp.live_addressed import apply_live_addressed, plan_live_addressed_edits

_NS = (
    'xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
    'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"'
)


def _run(text: str) -> str:
    return f'<hp:run charPrIDRef="0"><hp:t>{text}</hp:t></hp:run>'


def _write_hwpx(dst: Path, section0: str) -> None:
    header = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
        b'<hh:head xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head"/>'
    )
    with zipfile.ZipFile(dst, "w") as z:
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        z.writestr(zi, b"application/hwp+zip")
        z.writestr("Contents/header.xml", header)
        z.writestr("Contents/section0.xml", section0.encode("utf-8"))


def _build_form(dst: Path) -> None:
    """2x2 table: r0=(성명, {성명}) r1=(직위, empty)."""
    section0 = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?><hs:sec {_NS}>'
        '<hp:tbl rowCnt="2" colCnt="2"><hp:tr>'
        '<hp:tc><hp:cellAddr rowAddr="0" colAddr="0"/><hp:subList><hp:p id="1">' + _run("성명") + '</hp:p></hp:subList></hp:tc>'
        '<hp:tc><hp:cellAddr rowAddr="0" colAddr="1"/><hp:subList><hp:p id="2">' + _run("{성명}") + '</hp:p></hp:subList></hp:tc>'
        '</hp:tr><hp:tr>'
        '<hp:tc><hp:cellAddr rowAddr="1" colAddr="0"/><hp:subList><hp:p id="3">' + _run("직위") + '</hp:p></hp:subList></hp:tc>'
        '<hp:tc><hp:cellAddr rowAddr="1" colAddr="1"/><hp:subList><hp:p id="4">' + _run("") + '</hp:p></hp:subList></hp:tc>'
        '</hp:tr></hp:tbl>'
        '</hs:sec>'
    )
    _write_hwpx(dst, section0)


def _build_multi_para_cell(dst: Path) -> None:
    section0 = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?><hs:sec {_NS}>'
        '<hp:tbl rowCnt="1" colCnt="1"><hp:tr>'
        '<hp:tc><hp:cellAddr rowAddr="0" colAddr="0"/><hp:subList>'
        '<hp:p id="11">' + _run("자료") + '</hp:p>'
        '<hp:p id="12">' + _run("추가") + '</hp:p>'
        '</hp:subList></hp:tc>'
        '</hp:tr></hp:tbl>'
        '</hs:sec>'
    )
    _write_hwpx(dst, section0)


def _build_marker_cell(dst: Path) -> None:
    """1x1 table, cell holds a single ▶ marker paragraph."""
    section0 = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?><hs:sec {_NS}>'
        '<hp:tbl rowCnt="1" colCnt="1"><hp:tr>'
        '<hp:tc><hp:cellAddr rowAddr="0" colAddr="0"/><hp:subList>'
        '<hp:p id="40">' + _run("▶") + '</hp:p>'
        '</hp:subList></hp:tc>'
        '</hp:tr></hp:tbl>'
        '</hs:sec>'
    )
    _write_hwpx(dst, section0)


def _inline_timeout(func, *args, timeout_seconds, **kwargs):
    """Run the apply inline (no subprocess) so fake-COM monkeypatches apply."""
    return {"ok": True, "result": func(*args, **kwargs)}


def _build_wide_form(dst: Path, n: int) -> None:
    """1 x n table, each cell a distinct {vN} placeholder (for batch-size routing)."""
    cells = "".join(
        f'<hp:tc><hp:cellAddr rowAddr="0" colAddr="{i}"/><hp:subList>'
        f'<hp:p id="{100 + i}">' + _run("{v%d}" % i) + '</hp:p></hp:subList></hp:tc>'
        for i in range(n)
    )
    section0 = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?><hs:sec {_NS}>'
        f'<hp:tbl rowCnt="1" colCnt="{n}"><hp:tr>{cells}</hp:tr></hp:tbl>'
        '</hs:sec>'
    )
    _write_hwpx(dst, section0)


def _build_nested_table(dst: Path) -> None:
    section0 = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?><hs:sec {_NS}>'
        '<hp:tbl rowCnt="1" colCnt="1"><hp:tr>'
        '<hp:tc><hp:cellAddr rowAddr="0" colAddr="0"/><hp:subList>'
        '<hp:p id="30">' + _run("외부") + '</hp:p>'
        '<hp:tbl rowCnt="1" colCnt="1"><hp:tr>'
        '<hp:tc><hp:cellAddr rowAddr="0" colAddr="0"/><hp:subList><hp:p id="31">' + _run("내부") + '</hp:p></hp:subList></hp:tc>'
        '</hp:tr></hp:tbl>'
        '</hp:subList></hp:tc>'
        '</hp:tr></hp:tbl>'
        '</hs:sec>'
    )
    _write_hwpx(dst, section0)


def _edit(target: str, value: str, expected: str, kind: str = "cell") -> dict:
    return {"target": target, "kind": kind, "operation": "replace_text", "value": value, "expected_text": expected}


# ---------- PURE plan ----------


def test_plan_requires_expected_text_on_every_edit(tmp_path):
    src = tmp_path / "form.hwpx"
    _build_form(src)
    edits = [{"target": "t1.r0.c1", "kind": "cell", "operation": "replace_text", "value": "홍길동"}]
    plan = plan_live_addressed_edits(src, edits)
    assert plan["ok"] is False
    assert plan["state"] == "live_targets_unresolved"
    assert plan["unresolved"][0]["reason"] == "expected_text_required"


def test_plan_fails_closed_on_nested_tables(tmp_path):
    src = tmp_path / "nested.hwpx"
    _build_nested_table(src)
    plan = plan_live_addressed_edits(src, [_edit("t1.r0.c0", "값", "외부")])
    assert plan["ok"] is False
    assert plan["state"] == "nested_tables_unsupported"
    assert "complete_and_load" in plan["next"]


def test_plan_resolves_cell_targets_with_coordinates(tmp_path):
    src = tmp_path / "form.hwpx"
    _build_form(src)
    plan = plan_live_addressed_edits(src, [_edit("t1.r0.c1", "홍길동", "{성명}"), _edit("t1.r1.c1", "교사", "")])
    assert plan["ok"] is True and plan["state"] == "planned"
    assert plan["counts"] == {"requested": 2, "planned": 2}
    assert plan["source_sha256"]
    first = plan["targets"][0]
    assert (first["table"], first["row"], first["col"]) == (1, 0, 1)
    assert first["expected_text"] == "{성명}"


def test_plan_surfaces_expected_text_mismatch_from_file(tmp_path):
    src = tmp_path / "form.hwpx"
    _build_form(src)
    plan = plan_live_addressed_edits(src, [_edit("t1.r0.c1", "홍길동", "다른텍스트")])
    assert plan["ok"] is False
    assert any(u["reason"] == "expected_text_mismatch" for u in plan["unresolved"])


def test_plan_paragraph_targets_only_single_paragraph_cells(tmp_path):
    single = tmp_path / "form.hwpx"
    _build_form(single)
    plan = plan_live_addressed_edits(single, [_edit("t1.r0.c1.p1", "홍길동", "{성명}", kind="paragraph")])
    assert plan["ok"] is True
    assert plan["targets"][0]["cell"] == "t1.r0.c1"

    multi = tmp_path / "multi.hwpx"
    _build_multi_para_cell(multi)
    plan2 = plan_live_addressed_edits(multi, [_edit("t1.r0.c0.p1", "값", "자료", kind="paragraph")])
    assert plan2["ok"] is False
    assert plan2["unresolved"][0]["reason"] == "multi_paragraph_cell_unsupported"

    plan3 = plan_live_addressed_edits(multi, [_edit("t1.r0.c0.p2", "값", "추가", kind="paragraph")])
    assert plan3["ok"] is False
    assert plan3["unresolved"][0]["reason"] == "paragraph_ordinal_unsupported"


def test_plan_rejects_body_paragraph_targets(tmp_path):
    src = tmp_path / "form.hwpx"
    _build_form(src)
    plan = plan_live_addressed_edits(src, [_edit("b1", "값", "본문", kind="body_para")])
    assert plan["ok"] is False
    assert plan["unresolved"][0]["reason"] == "body_targets_file_mode_only"


# ---------- fake-COM apply ----------


class _FakeHAction:
    def __init__(self, owner):
        self._owner = owner

    def Run(self, command):
        self._owner._action(command)


class FakeHwp:
    """Shared class-level document state so writer + fresh reader see one window."""

    cells: dict = {}
    tables: set = set()
    raise_on_insert_targets: set = set()

    def __init__(self, new=False, visible=True, on_quit=False):
        self._pos = None
        self._selected = False
        self.HAction = _FakeHAction(self)

    def get_into_nth_table(self, index):
        self._table = index + 1
        return (index + 1) in type(self).tables

    def goto_addr(self, row, col, select_cell=False):
        pos = (self._table, row - 1, col - 1)
        if pos not in type(self).cells:
            return False
        self._pos = pos
        return True

    def _action(self, command):
        if command == "Cancel":
            self._selected = False
        elif command == "MoveSelListEnd":
            self._selected = True
        elif command == "Delete" and self._selected and self._pos:
            type(self).cells[self._pos] = ""
            self._selected = False
        elif command == "BreakPara" and self._pos:
            type(self).cells[self._pos] += "\n"

    def get_selected_text(self):
        # real hardware drops the selection after the read (desktop capture
        # 2026-07-15): a Delete right after this call must be a no-op
        text = type(self).cells.get(self._pos, "") if self._selected else ""
        self._selected = False
        return text

    def insert_text(self, text):
        if self._pos in type(self).raise_on_insert_targets:
            raise RuntimeError("COM write failed")
        type(self).cells[self._pos] += text


def _fake_com(monkeypatch, cells, tables=None, raise_on=None):
    FakeHwp.cells = dict(cells)
    FakeHwp.tables = set(tables or {t for (t, _r, _c) in cells})
    FakeHwp.raise_on_insert_targets = set(raise_on or ())
    monkeypatch.setattr(la, "load_pyhwpx", lambda: (FakeHwp, None))
    monkeypatch.setattr(la, "list_rot_instances", lambda: [{"moniker": "rot://fake"}])
    monkeypatch.setattr(la, "suppress_dialogs", lambda hwp: None)
    monkeypatch.setattr(la, "restore_dialogs", lambda hwp, mode: None)
    monkeypatch.setattr(la, "_ensure_active_document", lambda hwp, path, open_if_needed: (str(path), False, None))


def _target(target, table, row, col, value, expected):
    return {"target": target, "cell": target, "table": table, "row": row, "col": col, "value": value, "expected_text": expected}


def test_apply_full_success_with_fresh_readback(monkeypatch, tmp_path):
    _fake_com(monkeypatch, {(1, 0, 1): "{성명}", (1, 1, 1): ""})
    res = apply_live_addressed(tmp_path / "form.hwpx", [
        _target("t1.r0.c1", 1, 0, 1, "홍길동", "{성명}"),
        _target("t1.r1.c1", 1, 1, 1, "교사", ""),
    ])
    assert res["ok"] is True and res["state"] == "applied_live_addressed"
    assert [a["target"] for a in res["applied"]] == ["t1.r0.c1", "t1.r1.c1"]
    assert res["remaining"] == [] and res["skipped"] == []
    assert res["readback"] == {"verified": True, "failed": [], "checked": 2}
    assert FakeHwp.cells[(1, 0, 1)] == "홍길동"


def test_apply_skips_mismatched_cell_without_touching_it(monkeypatch, tmp_path):
    _fake_com(monkeypatch, {(1, 0, 1): "이미변경됨", (1, 1, 1): ""})
    res = apply_live_addressed(tmp_path / "form.hwpx", [
        _target("t1.r0.c1", 1, 0, 1, "홍길동", "{성명}"),
        _target("t1.r1.c1", 1, 1, 1, "교사", ""),
    ])
    assert res["ok"] is False and res["state"] == "live_addressed_partial"
    skip = res["skipped"][0]
    assert skip["reason"] == "expected_text_mismatch" and skip["actual_text"] == "이미변경됨"
    assert FakeHwp.cells[(1, 0, 1)] == "이미변경됨"  # fail-closed: never edited
    assert [a["target"] for a in res["applied"]] == ["t1.r1.c1"]
    assert "Ctrl-Z" in res["recovery"]["instruction"]
    assert "complete_and_load" in res["next"]


def test_apply_skips_missing_table_and_unreachable_cell(monkeypatch, tmp_path):
    _fake_com(monkeypatch, {(1, 0, 1): "{성명}"})
    res = apply_live_addressed(tmp_path / "form.hwpx", [
        _target("t2.r0.c0", 2, 0, 0, "값", "x"),
        _target("t1.r5.c5", 1, 5, 5, "값", "x"),
    ])
    assert res["ok"] is False
    reasons = {s["reason"] for s in res["skipped"]}
    assert reasons == {"table_not_found_live", "cell_unreachable"}
    assert res["applied"] == []
    assert FakeHwp.cells[(1, 0, 1)] == "{성명}"


def test_apply_aborts_with_applied_and_remaining_on_live_error(monkeypatch, tmp_path):
    _fake_com(
        monkeypatch,
        {(1, 0, 1): "{성명}", (1, 1, 1): "", (1, 1, 0): "직위"},
        raise_on={(1, 1, 1)},
    )
    res = apply_live_addressed(tmp_path / "form.hwpx", [
        _target("t1.r0.c1", 1, 0, 1, "홍길동", "{성명}"),
        _target("t1.r1.c1", 1, 1, 1, "교사", ""),
        _target("t1.r1.c0", 1, 1, 0, "부장", "직위"),
    ])
    assert res["ok"] is False and res["state"] == "live_addressed_partial"
    assert [a["target"] for a in res["applied"]] == ["t1.r0.c1"]
    assert [r["target"] for r in res["remaining"]] == ["t1.r1.c0"]
    assert res["skipped"][0]["reason"].startswith("live_error")
    assert res["recovery"]["undo_actions_per_cell"] == 2


# ---------- current-document route ----------


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


def _rot(path: Path):
    return [{"moniker": "rot://1", "documents": [_doc(path)]}]


def test_preview_live_addressed_route_enabled_by_promoted_flag(monkeypatch, tmp_path):
    src = tmp_path / "form.hwpx"
    _build_form(src)
    monkeypatch.setattr(live_current, "list_rot_instances", lambda: _rot(src))
    res = live_current.preview_current_hwp_document({}, edits=[_edit("t1.r0.c1", "홍길동", "{성명}")], mode="live_addressed")
    assert res["state"] == "preview_ready" and res["route"] == "live_addressed"


def test_preview_live_addressed_route_gates_when_flag_disabled(monkeypatch, tmp_path):
    src = tmp_path / "form.hwpx"
    _build_form(src)
    monkeypatch.setattr(live_current, "list_rot_instances", lambda: _rot(src))
    monkeypatch.setattr(live_current, "live_addressed_enabled", lambda: False)
    res = live_current.preview_current_hwp_document({}, edits=[_edit("t1.r0.c1", "홍길동", "{성명}")], mode="live_addressed")
    assert res["state"] == "live_addressed_gated"
    assert "preview_token" not in res
    assert "complete_and_load" in res["next"]


def test_preview_and_apply_live_addressed_when_enabled(monkeypatch, tmp_path):
    src = tmp_path / "form.hwpx"
    _build_form(src)
    monkeypatch.setattr(live_current, "list_rot_instances", lambda: _rot(src))
    monkeypatch.setattr(live_current, "live_addressed_enabled", lambda: True)
    preview = live_current.preview_current_hwp_document({}, edits=[_edit("t1.r0.c1", "홍길동", "{성명}")], mode="live_addressed")
    assert preview["state"] == "preview_ready" and preview["route"] == "live_addressed"
    assert preview["preview"]["counts"] == {"requested": 1, "planned": 1}
    monkeypatch.setattr(live_current, "run_with_timeout", _inline_timeout)
    monkeypatch.setattr(
        live_current,
        "apply_live_addressed",
        lambda path, targets, **kw: {
            "available": True,
            "connected": True,
            "ok": True,
            "state": "applied_live_addressed",
            "applied": [{"target": t["target"], "value": t["value"]} for t in targets],
            "skipped": [],
            "remaining": [],
            "readback": {"verified": True, "failed": [], "checked": len(targets)},
        },
    )
    first = live_current.apply_to_current_hwp_document(preview["preview_token"])
    assert first["state"] == "applied_live_addressed" and first["route"] == "live_addressed"
    second = live_current.apply_to_current_hwp_document(preview["preview_token"])
    assert second["state"] == "stale_preview_token"  # single-use even on success


def test_apply_live_addressed_rejects_stale_source_file(monkeypatch, tmp_path):
    src = tmp_path / "form.hwpx"
    _build_form(src)
    monkeypatch.setattr(live_current, "list_rot_instances", lambda: _rot(src))
    monkeypatch.setattr(live_current, "live_addressed_enabled", lambda: True)
    preview = live_current.preview_current_hwp_document({}, edits=[_edit("t1.r0.c1", "홍길동", "{성명}")], mode="live_addressed")
    assert preview["state"] == "preview_ready"
    _build_multi_para_cell(src)  # the saved file changed after preview
    res = live_current.apply_to_current_hwp_document(preview["preview_token"])
    assert res["state"] == "stale_preview"
    again = live_current.apply_to_current_hwp_document(preview["preview_token"])
    assert again["state"] == "stale_preview_token"  # consumed fail-closed


def test_apply_live_addressed_route_stays_gated_without_flag(monkeypatch, tmp_path):
    src = tmp_path / "form.hwpx"
    _build_form(src)
    monkeypatch.setattr(live_current, "list_rot_instances", lambda: _rot(src))
    enabled = iter([True])
    monkeypatch.setattr(live_current, "live_addressed_enabled", lambda: next(enabled, False))
    preview = live_current.preview_current_hwp_document({}, edits=[_edit("t1.r0.c1", "홍길동", "{성명}")], mode="live_addressed")
    assert preview["state"] == "preview_ready"
    res = live_current.apply_to_current_hwp_document(preview["preview_token"])
    assert res["state"] == "live_addressed_gated"


def test_preview_live_addressed_blocks_read_only_candidate(monkeypatch, tmp_path):
    src = tmp_path / "form.hwpx"
    _build_form(src)
    monkeypatch.setattr(live_current, "list_rot_instances", lambda: _rot(src))
    monkeypatch.setattr(live_current, "live_addressed_enabled", lambda: True)
    monkeypatch.setattr(live_current, "candidate_write_state", lambda path: "read_only")
    res = live_current.preview_current_hwp_document({}, edits=[_edit("t1.r0.c1", "홍길동", "{성명}")], mode="live_addressed")
    assert res["state"] == "read_only"
    assert "preview_token" not in res


def test_preview_live_addressed_passes_nested_fail_closed_through(monkeypatch, tmp_path):
    src = tmp_path / "nested.hwpx"
    _build_nested_table(src)
    monkeypatch.setattr(live_current, "list_rot_instances", lambda: _rot(src))
    monkeypatch.setattr(live_current, "live_addressed_enabled", lambda: True)
    res = live_current.preview_current_hwp_document({}, edits=[_edit("t1.r0.c0", "값", "외부")], mode="live_addressed")
    assert res["state"] == "nested_tables_unsupported"
    assert "preview_token" not in res


# ---------- v0.5.2: marker preservation + multiline + timeout isolation ----------


def test_plan_preserves_marker_via_after_text_then_applies(monkeypatch, tmp_path):
    src = tmp_path / "marker.hwpx"
    _build_marker_cell(src)
    plan = plan_live_addressed_edits(
        src,
        [{"target": "t1.r0.c0.p1", "kind": "paragraph", "operation": "preserve_marker_replace_tail",
          "value": "핵심 개념 정리", "expected_text": "▶"}],
    )
    assert plan["ok"] is True
    # the live target carries the RESOLVED text (marker kept), not the raw '핵심 개념 정리'
    assert plan["targets"][0]["value"] == "▶ 핵심 개념 정리"

    _fake_com(monkeypatch, {(1, 0, 0): "▶"})
    res = apply_live_addressed(src, plan["targets"])
    assert res["ok"] is True
    assert FakeHwp.cells[(1, 0, 0)] == "▶ 핵심 개념 정리"  # ▶ survived the live replace


def test_whole_cell_multiline_value_splits_into_paragraphs(monkeypatch, tmp_path):
    src = tmp_path / "form.hwpx"
    _build_form(src)
    plan = plan_live_addressed_edits(src, [_edit("t1.r1.c1", "1. 목표 하나\n2. 목표 둘", "")])
    assert plan["ok"] is True
    assert plan["targets"][0]["value"] == "1. 목표 하나\n2. 목표 둘"

    _fake_com(monkeypatch, {(1, 1, 1): ""})
    res = apply_live_addressed(src, plan["targets"])
    assert res["ok"] is True
    assert FakeHwp.cells[(1, 1, 1)] == "1. 목표 하나\n2. 목표 둘"  # BreakPara between lines
    assert res["readback"]["verified"] is True  # \r\n vs \n normalized


def test_apply_matches_multipara_expected_ignoring_paragraph_breaks(monkeypatch, tmp_path):
    # a live COM read of a multi-paragraph cell carries \r\n separators the
    # inspection expected_text ("▶-▶-") lacks; the contrast must still match
    _fake_com(monkeypatch, {(1, 0, 0): "▶\r\n-\r\n\r\n▶\r\n-"})
    res = apply_live_addressed(tmp_path / "f.hwpx", [
        _target("t1.r0.c0", 1, 0, 0, "▶ 활동 하나\n- 세부 하나", "▶-▶-"),
    ])
    assert res["ok"] is True  # not skipped as expected_text_mismatch
    assert FakeHwp.cells[(1, 0, 0)] == "▶ 활동 하나\n- 세부 하나"


def test_apply_verify_false_skips_readback(monkeypatch, tmp_path):
    _fake_com(monkeypatch, {(1, 0, 1): "{성명}"})
    res = apply_live_addressed(tmp_path / "f.hwpx", [_target("t1.r0.c1", 1, 0, 1, "홍길동", "{성명}")], verify=False)
    assert res["ok"] is True  # trusts the per-cell expected_text pre-check
    assert res["readback"]["skipped"] is True and res["readback"]["checked"] == 0
    assert FakeHwp.cells[(1, 0, 1)] == "홍길동"  # write still happened


def test_route_skips_readback_and_notes_for_large_batch(monkeypatch, tmp_path):
    src = tmp_path / "wide.hwpx"
    _build_wide_form(src, 13)
    monkeypatch.setattr(live_current, "list_rot_instances", lambda: _rot(src))
    monkeypatch.setattr(live_current, "live_addressed_enabled", lambda: True)
    edits = [_edit(f"t1.r0.c{i}", f"값{i}", "{v%d}" % i) for i in range(13)]
    preview = live_current.preview_current_hwp_document({}, edits=edits, mode="live_addressed")
    assert preview["state"] == "preview_ready"
    captured = {}

    def capture(path, targets, **kw):
        captured["verify"] = kw.get("verify")
        return {"available": True, "connected": True, "ok": True, "state": "applied_live_addressed",
                "applied": [{"target": t["target"], "value": t["value"]} for t in targets],
                "skipped": [], "remaining": [], "readback": {"verified": False, "failed": [], "checked": 0, "skipped": True}}

    monkeypatch.setattr(live_current, "run_with_timeout", _inline_timeout)
    monkeypatch.setattr(live_current, "apply_live_addressed", capture)
    res = live_current.apply_to_current_hwp_document(preview["preview_token"])
    assert captured["verify"] is False  # >12 cells -> read-back skipped for speed
    assert "skipped for speed" in res["note"]


def test_route_keeps_readback_for_small_batch(monkeypatch, tmp_path):
    src = tmp_path / "form.hwpx"
    _build_form(src)
    monkeypatch.setattr(live_current, "list_rot_instances", lambda: _rot(src))
    monkeypatch.setattr(live_current, "live_addressed_enabled", lambda: True)
    preview = live_current.preview_current_hwp_document({}, edits=[_edit("t1.r0.c1", "홍길동", "{성명}")], mode="live_addressed")
    captured = {}

    def capture(path, targets, **kw):
        captured["verify"] = kw.get("verify")
        return {"available": True, "connected": True, "ok": True, "state": "applied_live_addressed",
                "applied": [{"target": t["target"], "value": t["value"]} for t in targets],
                "skipped": [], "remaining": [], "readback": {"verified": True, "failed": [], "checked": len(targets)}}

    monkeypatch.setattr(live_current, "run_with_timeout", _inline_timeout)
    monkeypatch.setattr(live_current, "apply_live_addressed", capture)
    res = live_current.apply_to_current_hwp_document(preview["preview_token"])
    assert captured["verify"] is True  # small batch stays verified
    assert "note" not in res


def test_multipara_rejection_guides_to_whole_cell_multiline(tmp_path):
    multi = tmp_path / "multi.hwpx"
    _build_multi_para_cell(multi)
    plan = plan_live_addressed_edits(multi, [_edit("t1.r0.c0.p1", "값", "자료", kind="paragraph")])
    assert plan["ok"] is False
    u = plan["unresolved"][0]
    assert u["reason"] == "multi_paragraph_cell_unsupported"
    assert "kind=cell" in u["next"] and "\\n" in u["next"]  # tells the client how to fill it live


def test_apply_route_isolates_hang_as_structured_timeout(monkeypatch, tmp_path):
    src = tmp_path / "form.hwpx"
    _build_form(src)
    monkeypatch.setattr(live_current, "list_rot_instances", lambda: _rot(src))
    monkeypatch.setattr(live_current, "live_addressed_enabled", lambda: True)
    preview = live_current.preview_current_hwp_document({}, edits=[_edit("t1.r0.c1", "홍길동", "{성명}")], mode="live_addressed")
    assert preview["state"] == "preview_ready"

    def _hang(func, *args, timeout_seconds, **kwargs):
        return {
            "ok": False, "timed_out": True, "state": "timeout_outcome_unknown",
            "may_have_partially_applied": True, "timeout_seconds": timeout_seconds,
            "elapsed_seconds": 180.0, "error": "operation timed out in isolated worker",
        }

    monkeypatch.setattr(live_current, "run_with_timeout", _hang)
    res = live_current.apply_to_current_hwp_document(preview["preview_token"])
    assert res["ok"] is False
    assert res["state"] == "timeout_outcome_unknown"
    assert res["may_have_partially_applied"] is True
    assert "without saving" in res["recovery"]["instruction"].lower()
    assert "complete_and_load" in res["next"]
    # single-use token consumed even on a hang, so no accidental replay
    again = live_current.apply_to_current_hwp_document(preview["preview_token"])
    assert again["state"] == "stale_preview_token"


def test_apply_route_unwraps_worker_result_on_success(monkeypatch, tmp_path):
    src = tmp_path / "form.hwpx"
    _build_form(src)
    monkeypatch.setattr(live_current, "list_rot_instances", lambda: _rot(src))
    monkeypatch.setattr(live_current, "live_addressed_enabled", lambda: True)
    preview = live_current.preview_current_hwp_document({}, edits=[_edit("t1.r0.c1", "홍길동", "{성명}")], mode="live_addressed")
    monkeypatch.setattr(live_current, "run_with_timeout", _inline_timeout)
    monkeypatch.setattr(live_current, "apply_live_addressed", lambda path, targets, **kw: {
        "available": True, "connected": True, "ok": True, "state": "applied_live_addressed",
        "applied": [{"target": t["target"], "value": t["value"]} for t in targets],
        "skipped": [], "remaining": [], "readback": {"verified": True, "failed": [], "checked": len(targets)},
    })
    res = live_current.apply_to_current_hwp_document(preview["preview_token"])
    assert res["ok"] is True and res["state"] == "applied_live_addressed" and res["route"] == "live_addressed"
