"""US-063: open_in_hwp + active-document verification (headless-testable parts).

Live COM behavior is desktop-only (docs/live-qa-runbook.md); these tests cover
the pure comparator, the structured non-COM fallbacks, and (via a fake COM
object) the CRITICAL-1 guard that refuses to edit when an auto-``open`` did not
actually make the requested file the active document.
"""

from hangeul_core.hwp.live import _apply_cells_connected, _same_doc, open_in_hwp
from hangeul_mcp import server


class _Active:
    def __init__(self, fullname):
        self.FullName = fullname


class _Docs:
    def __init__(self, hwp):
        self.Active_XHwpDocument = _Active(hwp._active)


class _HAction:
    def __init__(self, hwp):
        self.hwp = hwp

    def Run(self, action):
        self.hwp.actions.append(action)


class FakeHwp:
    """Fake COM instance for the auto-open active-document guard (CRITICAL-1)."""

    def __init__(self, active, *, open_result=True, open_sets_active=None):
        self._active = active
        self.open_result = open_result
        self.open_sets_active = open_sets_active
        self.opened = []
        self.actions = []
        self.tables = []
        self.inserted = []
        self.HAction = _HAction(self)

    @property
    def XHwpDocuments(self):
        return _Docs(self)

    def open(self, p):
        self.opened.append(p)
        if self.open_sets_active is not None:
            self._active = self.open_sets_active
        return self.open_result

    def get_into_nth_table(self, idx):
        self.tables.append(idx)
        return True

    def goto_addr(self, row, col, select_cell=True):
        return True

    def insert_text(self, value):
        self.inserted.append(value)


_CELL = {"table": 1, "row": 0, "col": 0, "value": "홍길동", "label": "성명", "field_id": "t1.r0.c0"}


def _apply(hwp, path):
    return _apply_cells_connected(
        hwp, path, [dict(_CELL)], [], [], [], clear=True,
        open_if_needed=True, cold_start=False, started=0.0,
    )


def test_open_true_but_active_unchanged_refuses_without_editing(tmp_path):
    # open() returns True yet the active document never switches to *path*.
    hwp = FakeHwp("C:/other/unrelated.hwpx", open_result=True, open_sets_active=None)
    res = _apply(hwp, tmp_path / "form.hwpx")
    assert res["ok"] is False
    assert "active document" in res["error"]
    assert hwp.tables == [] and hwp.inserted == [] and "Delete" not in hwp.actions


def test_open_switches_active_then_edits(tmp_path):
    src = tmp_path / "form.hwpx"
    hwp = FakeHwp("C:/other/unrelated.hwpx", open_result=True, open_sets_active=str(src))
    res = _apply(hwp, src)
    assert res.get("ok") is not False  # proceeded
    assert hwp.tables == [0] and hwp.inserted == ["홍길동"] and "Delete" in hwp.actions
    assert len(res["applied"]) == 1


def test_already_active_does_not_reopen(tmp_path):
    src = tmp_path / "form.hwpx"
    hwp = FakeHwp(str(src))
    res = _apply(hwp, src)
    assert hwp.opened == []  # already active -> no open
    assert len(res["applied"]) == 1


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
