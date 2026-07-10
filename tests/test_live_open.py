"""US-063: open_in_hwp + active-document verification (headless-testable parts).

Live COM behavior is desktop-only (docs/live-qa-runbook.md); these tests cover
the pure comparator and the structured non-COM fallbacks.
"""

from hangeul_core.hwp.live import _same_doc, open_in_hwp
from hangeul_mcp import server


def test_same_doc_normalizes_separators_and_relative_segments(tmp_path):
    f = tmp_path / "form.hwpx"
    f.write_bytes(b"x")
    assert _same_doc(str(f), f)
    assert _same_doc(str(f), tmp_path / "." / "form.hwpx")
    assert not _same_doc("", f)
    assert not _same_doc(str(tmp_path / "other.hwpx"), f)


def test_open_in_hwp_missing_file_is_structured():
    res = open_in_hwp("no/such/file.hwpx")
    assert res["ok"] is False
    assert "not found" in res["error"]


def test_open_in_hwp_tool_rejects_non_hwp_extensions(tmp_path):
    f = tmp_path / "note.txt"
    f.write_text("x", encoding="utf-8")
    res = server.open_in_hwp(str(f))
    assert res["ok"] is False
    assert ".hwp" in res["error"]
