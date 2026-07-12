"""US-063: open_in_hwp + active-document verification (headless-testable parts).

Live COM behavior is desktop-only (docs/live-qa-runbook.md); these tests cover
the pure comparator, the structured non-COM fallbacks, and (via a fake COM
object) the CRITICAL-1 guard that refuses to edit when an auto-``open`` did not
actually make the requested file the active document.
"""

from hangeul_core.hwp import pick_broker_exact_path_candidate
from hangeul_core.hwp.live import _apply_cells_connected, _same_doc, open_in_hwp
from hangeul_mcp import server
import hangeul_core.hwp.live_attach as live_attach_mod


class _Active:
    def __init__(self, fullname):
        self.FullName = fullname


class _Docs:
    def __init__(self, hwp):
        self.Active_XHwpDocument = _Active(hwp._active)
        self._docs = [_Active(path) for path in hwp._attached_paths]
        self.Count = len(self._docs)

    def Item(self, idx):
        if idx < 1 or idx > self.Count:
            raise IndexError(idx)
        return self._docs[idx - 1]


class _HAction:
    def __init__(self, hwp):
        self.hwp = hwp

    def Run(self, action):
        self.hwp.actions.append(action)


class FakeHwp:
    """Fake COM instance for the auto-open active-document guard (CRITICAL-1)."""

    def __init__(self, active, *, open_result=True, open_sets_active=None, attached_paths=None):
        self._active = active
        self._attached_paths = list(attached_paths or [])
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


def test_has_exact_path_supports_one_based_document_collections(tmp_path):
    src = tmp_path / "form.hwpx"
    other = tmp_path / "other.hwpx"
    src.write_bytes(b"x")
    other.write_bytes(b"y")
    hwp = FakeHwp(str(other), attached_paths=[str(other), str(src)])

    assert live_attach_mod._has_exact_path(hwp, src) is True


def test_open_in_hwp_missing_file_is_structured():
    res = open_in_hwp("no/such/file.hwpx")
    assert res["ok"] is False
    assert "not found" in res["error"]


def test_pick_broker_exact_path_candidate_supports_open_in_hwp_attach_substrate(tmp_path):
    src = tmp_path / "form.hwpx"
    src.write_bytes(b"x")

    candidate = pick_broker_exact_path_candidate(
        src,
        [
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
            }
        ],
    )

    assert candidate is not None
    assert candidate["moniker"] == "rot://1"
    assert candidate["slot"] == 0
    assert candidate["active_source"] == "identity"


def test_open_in_hwp_attaches_unique_exact_path_candidate_without_reopen(monkeypatch, tmp_path):
    src = tmp_path / "form.hwpx"
    src.write_bytes(b"x")
    hwp = FakeHwp(str(src))

    monkeypatch.setattr(live_attach_mod, "load_pyhwpx", lambda: (lambda **kwargs: hwp, None))
    monkeypatch.setattr(
        live_attach_mod,
        "list_rot_instances",
        lambda: [{"moniker": "rot://1", "active_document": str(src), "open_documents": 1}],
    )
    monkeypatch.setattr(live_attach_mod, "suppress_dialogs", lambda hwp: None)
    monkeypatch.setattr(live_attach_mod, "restore_dialogs", lambda hwp, previous_mode: None)

    res = open_in_hwp(src)
    assert res["ok"] is True
    assert res["attached_existing"] is True
    assert res["opened"] is False
    assert hwp.opened == []


def test_open_in_hwp_keeps_structured_fallback_when_no_exact_path_attach(monkeypatch, tmp_path):
    src = tmp_path / "form.hwpx"
    src.write_bytes(b"x")
    hwp = FakeHwp("C:/other/unrelated.hwpx", open_result=True, open_sets_active=str(src))

    monkeypatch.setattr(live_attach_mod, "load_pyhwpx", lambda: (lambda **kwargs: hwp, None))
    monkeypatch.setattr(
        live_attach_mod,
        "list_rot_instances",
        lambda: [{"moniker": "rot://1", "active_document": "C:/other/unrelated.hwpx", "open_documents": 1}],
    )
    monkeypatch.setattr(live_attach_mod, "suppress_dialogs", lambda hwp: None)
    monkeypatch.setattr(live_attach_mod, "restore_dialogs", lambda hwp, previous_mode: None)

    res = open_in_hwp(src)
    assert res["ok"] is True
    assert res["attached_existing"] is False
    assert res["opened"] is True
    assert res["resolution"] == "opened_in_automation_window"
    assert hwp.opened == [str(src)]


def test_open_in_hwp_tool_rejects_non_hwp_extensions(tmp_path):
    f = tmp_path / "note.txt"
    f.write_text("x", encoding="utf-8")
    res = server.open_in_hwp(str(f))
    assert res["ok"] is False
    assert ".hwp" in res["error"]
