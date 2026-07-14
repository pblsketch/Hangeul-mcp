"""P0-B1: complete_and_load route — verified file-mode completion auto-opened as a NEW document.

The original window/document is never saved, closed, or reloaded (0-touch);
the verified completion is written to a NEW file and opened as a new tab.
Fake-COM only: the open step is monkeypatched; real-device evidence is the
desktop-capture story in the live QA runbook.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import hangeul_mcp.live_current as live_current
from hangeul_core.hwp.current_document import plan_preview_route

LESSON_PLAN = Path(__file__).parent / "fixtures" / "lesson_plan_addressed.hwpx"

EDITS = [
    {"target": "t1.r0.c0.p1", "kind": "paragraph", "operation": "replace_text", "value": "거울", "expected_text": "자료"},
    {"target": "t1.r0.c1.p1", "kind": "paragraph", "operation": "replace_text", "value": "도입 활동", "expected_text": "▶"},
]


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


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _setup_current(monkeypatch, tmp_path: Path) -> Path:
    src = tmp_path / "lesson.hwpx"
    shutil.copyfile(LESSON_PLAN, src)
    monkeypatch.setattr(live_current, "list_rot_instances", lambda: _instance("rot://1", _doc(src)))
    return src


def test_plan_preview_route_edits_yield_complete_and_load():
    plan = plan_preview_route({}, field_names=[], cell_preview={}, edits=[{"target": "t0.r0.c0", "value": "x"}])
    assert plan["route"] == "complete_and_load"
    assert plan["edit_count"] == 1


def test_plan_preview_route_values_plus_edits_conflict():
    plan = plan_preview_route(
        {"성명": "홍길동"}, field_names=[], cell_preview={}, edits=[{"target": "t0.r0.c0", "value": "x"}]
    )
    assert plan["route"] == "route_conflict"
    assert plan["input_conflict"] == "values_and_edits"


def test_plan_preview_route_without_edits_is_unchanged():
    plan = plan_preview_route({"성명": "홍길동"}, field_names=["성명"], cell_preview={})
    assert plan["route"] == "named_field"
    assert plan["named_field_keys"] == ["성명"]


def test_preview_complete_and_load_issues_token_and_output_path(monkeypatch, tmp_path):
    src = _setup_current(monkeypatch, tmp_path)
    res = live_current.preview_current_hwp_document(values={}, edits=EDITS)
    assert res["available"] is True and res["ok"] is True
    assert res["state"] == "preview_ready"
    assert res["route"] == "complete_and_load"
    out = Path(res["preview"]["output_path"])
    assert out != src and out.parent == src.parent and out.suffix == ".hwpx"
    assert not out.exists(), "preview must not write anything"
    assert res["preview"]["counts"]["resolved"] == len(EDITS)
    assert res["preview_token"].startswith(res["server_instance_id"])


def test_preview_rejects_values_and_edits_together(monkeypatch, tmp_path):
    _setup_current(monkeypatch, tmp_path)
    res = live_current.preview_current_hwp_document(values={"성명": "홍길동"}, edits=EDITS)
    assert res["ok"] is False
    assert res["state"] == "route_conflict"
    assert res["input_conflict"] == "values_and_edits"


def test_preview_rejects_output_overwriting_original(monkeypatch, tmp_path):
    src = _setup_current(monkeypatch, tmp_path)
    res = live_current.preview_current_hwp_document(values={}, edits=EDITS, output_path=str(src))
    assert res["ok"] is False
    assert res["state"] == "output_overwrites_original"


def test_preview_rejects_existing_output(monkeypatch, tmp_path):
    src = _setup_current(monkeypatch, tmp_path)
    existing = src.parent / "already.hwpx"
    existing.write_bytes(b"x")
    res = live_current.preview_current_hwp_document(values={}, edits=EDITS, output_path=str(existing))
    assert res["ok"] is False
    assert res["state"] == "output_exists"


def test_preview_requires_hwpx_output_suffix(monkeypatch, tmp_path):
    src = _setup_current(monkeypatch, tmp_path)
    res = live_current.preview_current_hwp_document(
        values={}, edits=EDITS, output_path=str(src.parent / "done.hwp")
    )
    assert res["ok"] is False
    assert res["state"] == "output_requires_hwpx"


def test_preview_fails_closed_on_unresolvable_edits(monkeypatch, tmp_path):
    _setup_current(monkeypatch, tmp_path)
    bad = [{"target": "t9.r9.c9.p9", "kind": "paragraph", "operation": "replace_text", "value": "x"}]
    res = live_current.preview_current_hwp_document(values={}, edits=bad)
    assert res["ok"] is False
    assert res["state"] == "addressed_preview_failed"
    assert res["unresolved"], "must surface the unresolved targets"


def test_apply_completes_and_loads_without_touching_original(monkeypatch, tmp_path):
    src = _setup_current(monkeypatch, tmp_path)
    before = _sha(src)
    res = live_current.preview_current_hwp_document(values={}, edits=EDITS)
    token = res["preview_token"]
    opened: dict = {}

    def fake_open(path, *, visible=True):
        opened["path"] = str(path)
        return {
            "available": True,
            "connected": True,
            "ok": True,
            "state": "opened_new",
            "active_document": str(path),
        }

    monkeypatch.setattr(live_current, "_open_completed_in_window", fake_open)
    applied = live_current.apply_to_current_hwp_document(token)
    assert applied["ok"] is True
    assert applied["state"] == "completed_and_loaded"
    out = Path(applied["output_path"])
    assert out.exists() and opened["path"] == str(out)
    assert applied["original_untouched"] is True
    assert _sha(src) == before, "original file must be byte-identical (0-touch)"
    note = str(applied["note"]).lower()
    assert "untouched" in note and "new tab" in note and "new" in note
    assert applied["completion"]["counts"]["verified"] == len(EDITS)
    replay = live_current.apply_to_current_hwp_document(token)
    assert replay["state"] == "stale_preview_token", "token must be single-use"


def test_apply_reports_partial_success_when_open_fails(monkeypatch, tmp_path):
    src = _setup_current(monkeypatch, tmp_path)
    before = _sha(src)
    res = live_current.preview_current_hwp_document(values={}, edits=EDITS)
    token = res["preview_token"]
    monkeypatch.setattr(
        live_current,
        "_open_completed_in_window",
        lambda path, *, visible=True: {"available": True, "ok": False, "state": "open_failed", "error": "boom"},
    )
    applied = live_current.apply_to_current_hwp_document(token)
    assert applied["ok"] is False
    assert applied["state"] == "completed_open_failed"
    out = Path(applied["output_path"])
    assert out.exists(), "the verified file must survive the failed open"
    assert applied["original_untouched"] is True
    assert "manually" in str(applied["next"]).lower()
    assert _sha(src) == before, "original must stay byte-identical even on open failure"
    replay = live_current.apply_to_current_hwp_document(token)
    assert replay["state"] == "stale_preview_token", "file was created; token must not be replayable"


def test_apply_keeps_token_when_completion_fails(monkeypatch, tmp_path):
    src = _setup_current(monkeypatch, tmp_path)
    before = _sha(src)
    res = live_current.preview_current_hwp_document(values={}, edits=EDITS)
    token = res["preview_token"]

    def boom(path, edits, out_path, verify=True):
        return {"ok": False, "state": "ambiguous_target", "unresolved": [{"target": "t1.r0.c0.p1"}]}

    monkeypatch.setattr(live_current, "_complete_addressed_template", boom)
    applied = live_current.apply_to_current_hwp_document(token)
    assert applied["ok"] is False
    assert applied["state"] == "complete_failed"
    assert _sha(src) == before
    retry = live_current.apply_to_current_hwp_document(token)
    assert retry["state"] == "complete_failed", "no mutation happened; token stays usable for retry"


def test_apply_rejects_stale_original_after_preview(monkeypatch, tmp_path):
    src = _setup_current(monkeypatch, tmp_path)
    res = live_current.preview_current_hwp_document(values={}, edits=EDITS)
    token = res["preview_token"]
    src.write_bytes(src.read_bytes() + b"#changed-after-preview")
    applied = live_current.apply_to_current_hwp_document(token)
    assert applied["ok"] is False
    assert applied["state"] == "stale_preview"
    assert not Path(applied["output_path"]).exists(), "must not publish against a changed original"
    assert "preview" in str(applied["next"]).lower()
    replay = live_current.apply_to_current_hwp_document(token)
    assert replay["state"] == "stale_preview_token", "a stale preview must consume the token"


def test_apply_cleans_partial_output_when_verification_fails(monkeypatch, tmp_path):
    src = _setup_current(monkeypatch, tmp_path)
    before = _sha(src)
    res = live_current.preview_current_hwp_document(values={}, edits=EDITS)
    token = res["preview_token"]

    def write_then_fail(path, edits, out_path, verify=True):
        Path(out_path).write_bytes(b"partial garbage")
        return {"ok": False, "state": "partial", "failures": [{"reason": "verification_mismatch"}]}

    monkeypatch.setattr(live_current, "_complete_addressed_template", write_then_fail)
    applied = live_current.apply_to_current_hwp_document(token)
    assert applied["state"] == "complete_failed"
    assert applied["partial_output_removed"] is True
    out = Path(applied["output_path"])
    assert not out.exists(), "failed verification must not leave the output file"
    assert not list(out.parent.glob("*.part")), "temp part files must not survive"
    assert _sha(src) == before
    retry = live_current.apply_to_current_hwp_document(token)
    assert retry["state"] == "complete_failed", "retry must not deadlock on output_exists"


def test_wrapper_rejects_empty_edits_and_orphan_output_path():
    from hangeul_mcp import server

    res = server.preview_current_hwp_document(values={}, edits=[])
    assert res["ok"] is False and res["state"] == "empty_edits"
    res2 = server.preview_current_hwp_document(values={"라벨": "값"}, output_path="x.hwpx")
    assert res2["ok"] is False and res2["state"] == "output_path_requires_edits"


def test_values_only_flow_unaffected_by_edits_param(monkeypatch, tmp_path):
    _setup_current(monkeypatch, tmp_path)
    res = live_current.preview_current_hwp_document(values={"미지정라벨": "값"})
    assert res["available"] is True
    assert res["state"] == "preview_ready"
    assert res["route"] in {"cells", "named_field"}, "value routing must be unchanged by the edits feature"


def test_read_only_original_still_allows_complete_and_load(monkeypatch, tmp_path):
    src = _setup_current(monkeypatch, tmp_path)
    monkeypatch.setattr(
        live_current,
        "list_rot_instances",
        lambda: _instance("rot://1", {**_doc(src), "write_state": "read_only"}),
    )
    monkeypatch.setattr(
        "hangeul_mcp.live_current.candidate_write_state", lambda path: "read_only", raising=False
    )
    res = live_current.preview_current_hwp_document(values={}, edits=EDITS)
    assert res["state"] == "preview_ready", "completion only READS the original; read-only must not block"
