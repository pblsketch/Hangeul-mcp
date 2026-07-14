"""P1-2: core/read/mail_merge responses converge on the common envelope keys.

Non-destructive contract: `available`/`ok` are ADDED; every legacy key stays.
Error paths are triggered deterministically by stubbing the module-level
`ensure_hwpx` conversion hook (no COM, no environment dependence).
"""

from __future__ import annotations

from pathlib import Path

import hangeul_mcp.tools_core as tools_core
import hangeul_mcp.tools_delegate as tools_delegate
import hangeul_mcp.tools_read as tools_read
from hangeul_mcp import server

FIXTURE = str(Path(__file__).parent / "fixtures" / "sample_form.hwpx")


def _boom(path):
    raise RuntimeError("conversion unavailable in this test")


def test_read_conversion_errors_carry_envelope(monkeypatch):
    monkeypatch.setattr(tools_read, "ensure_hwpx", _boom)
    calls = (
        lambda: server.find_text(FIXTURE, "x"),
        lambda: server.get_document_outline(FIXTURE),
        lambda: server.get_table_map(FIXTURE),
        lambda: server.find_cell_by_label(FIXTURE, "라벨"),
        lambda: server.verify_fill(FIXTURE, {}),
        lambda: server.list_styles(FIXTURE),
        lambda: server.get_paragraph_map(FIXTURE),
        lambda: server.find_text_occurrences(FIXTURE, "x"),
        lambda: server.inspect_editable_regions(FIXTURE),
        lambda: server.plan_template_completion(FIXTURE),
        lambda: server.verify_targets(FIXTURE, []),
    )
    for call in calls:
        res = call()
        assert res["available"] is True, res
        assert res["ok"] is False, res
        assert "error" in res, res


def test_core_conversion_errors_carry_envelope(monkeypatch, tmp_path):
    monkeypatch.setattr(tools_core, "ensure_hwpx", _boom)
    calls = (
        lambda: server.analyze_form(FIXTURE),
        lambda: server.fill_form(FIXTURE, {}, str(tmp_path / "out.hwpx")),
        lambda: server.scan_pii(FIXTURE),
        lambda: server.analyze_formfit(FIXTURE, {}),
    )
    for call in calls:
        res = call()
        assert res["available"] is True, res
        assert res["ok"] is False, res
        assert "error" in res, res


def test_core_legacy_error_keys_preserved(monkeypatch):
    monkeypatch.setattr(tools_core, "ensure_hwpx", _boom)
    res = server.analyze_form(FIXTURE)
    assert res["fields"] == [] and res["format"] == "hwp", "legacy keys must survive the envelope"


def test_mail_merge_error_carries_envelope(monkeypatch, tmp_path):
    monkeypatch.setattr(tools_delegate, "ensure_hwpx", _boom)
    res = server.mail_merge(FIXTURE, [], str(tmp_path))
    assert res["available"] is True
    assert res["ok"] is False
    assert "error" in res and res["count"] == 0, "legacy count key must survive"


def test_success_responses_carry_envelope():
    res = server.analyze_form(FIXTURE)
    assert res["available"] is True and res["ok"] is True and res["format"] == "hwpx"
    outline = server.get_document_outline(FIXTURE)
    assert outline["available"] is True and outline["ok"] is True
    styles = server.list_styles(FIXTURE)
    assert styles["available"] is True and styles["ok"] is True


def test_detect_format_keeps_existing_ok_and_reason(tmp_path):
    good = server.detect_format(FIXTURE)
    assert good["available"] is True and good["ok"] is True
    missing = server.detect_format(str(tmp_path / "nope.hwpx"))
    assert missing["available"] is True
    assert missing["ok"] is False, "pre-existing ok value must not be clobbered"
    assert missing["reason"] == "file not found"


def test_semantic_verification_failures_report_ok_false(tmp_path):
    bad = tmp_path / "bad.hwpx"
    bad.write_bytes(b"definitely not a zip")
    res = server.validate_hwpx(str(bad))
    assert res["available"] is True
    assert res["valid"] is False
    assert res["ok"] is False, "invalid package must not read as ok"

    res2 = server.verify_fill(FIXTURE, {"존재하지않는라벨": "이값은없다"})
    assert res2["verified"] is False and res2["ok"] is False

    res3 = server.verify_targets(FIXTURE, [{"target": "t1.r0.c0.p1", "expected_text": "절대일치안함"}])
    assert res3["verified"] is False and res3["ok"] is False


def test_unavailable_headless_reader_never_reports_ok(tmp_path):
    hwp = tmp_path / "legacy.hwp"
    hwp.write_bytes(b"\x00binary hwp placeholder")
    res = server.extract_hwp_text(str(hwp))
    assert res["available"] is False
    assert res["ok"] is False, "available:false must imply ok:false"
