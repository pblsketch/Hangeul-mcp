"""US-034: DELEGATE rich formatting (emphasize_text) — skips without python-hwpx."""

from pathlib import Path

import pytest

hwpx = pytest.importorskip("hwpx")

from hangeul_core.delegate import emphasize_text  # noqa: E402
from hangeul_core.validate import validate_hwpx  # noqa: E402
from hangeul_mcp import server  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "sample_form.hwpx"


def _a_run_substring() -> str:
    doc = hwpx.HwpxDocument.open(str(FIXTURE))
    for r in doc.iter_runs():
        t = (r.text or "").strip()
        if len(t) >= 2:
            return t[:2]
    return ""


def test_emphasize_bold_matches_and_applies(tmp_path):
    find = _a_run_substring()
    assert find  # fixture has some run text
    out = tmp_path / "o.hwpx"
    res = emphasize_text(FIXTURE, find, out, bold=True)
    assert res["ok"] is True and res["validation"]["valid"] is True
    assert res["matched_runs"] >= 1
    # reopen and confirm a matching run is now bold
    doc = hwpx.HwpxDocument.open(str(out))
    assert any((r.text and find in r.text and r.bold) for r in doc.iter_runs())


def test_emphasize_color_size_stays_valid(tmp_path):
    find = _a_run_substring()
    out = tmp_path / "o.hwpx"
    res = emphasize_text(FIXTURE, find, out, color="#FF0000", size=14)
    assert res["matched_runs"] >= 1
    assert validate_hwpx(out)["valid"] is True


def test_emphasize_no_match_is_noop_but_valid(tmp_path):
    out = tmp_path / "o.hwpx"
    res = emphasize_text(FIXTURE, "존재하지않는문자열ZZZ", out, bold=True)
    assert res["matched_runs"] == 0 and res["validation"]["valid"] is True


def test_server_emphasize_tool(tmp_path):
    find = _a_run_substring()
    out = tmp_path / "o.hwpx"
    res = server.emphasize_text(str(FIXTURE), find, str(out), bold=True)
    assert res["available"] is True and res["ok"] is True
