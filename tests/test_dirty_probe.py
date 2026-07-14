"""Track B prerequisite: COM dirty-probe fail-closed semantics (ADR D19)."""

from __future__ import annotations

import hangeul_core.hwp.dirty_probe as dp
from hangeul_core.hwp.dirty_probe import probe_document_dirty


class _FakeDoc:
    def __init__(self, full_name, modified):
        self.FullName = full_name
        self.Modified = modified


class _FakeDocs:
    def __init__(self, docs):
        self._docs = docs
        self.Count = len(docs)

    def Item(self, index):
        return self._docs[index]


def _fake_hwp_factory(docs):
    class _FakeHwp:
        XHwpDocuments = _FakeDocs(docs)

        def __init__(self, new=False, visible=True, on_quit=False):
            pass

    return _FakeHwp


def test_probe_reports_clean_document(monkeypatch, tmp_path):
    src = tmp_path / "doc.hwpx"
    monkeypatch.setattr(dp, "load_pyhwpx", lambda: (_fake_hwp_factory([_FakeDoc(str(src), 0)]), None))
    res = probe_document_dirty(src)
    assert res["state"] == "probed" and res["ok"] is True
    assert res["dirty"] is False


def test_probe_reports_dirty_document(monkeypatch, tmp_path):
    src = tmp_path / "doc.hwpx"
    monkeypatch.setattr(dp, "load_pyhwpx", lambda: (_fake_hwp_factory([_FakeDoc(str(src), 1)]), None))
    res = probe_document_dirty(src)
    assert res["state"] == "probed" and res["dirty"] is True


def test_probe_any_dirty_slot_wins(monkeypatch, tmp_path):
    src = tmp_path / "doc.hwpx"
    docs = [_FakeDoc(str(src), 0), _FakeDoc(str(src), 1), _FakeDoc(str(tmp_path / "other.hwpx"), 0)]
    monkeypatch.setattr(dp, "load_pyhwpx", lambda: (_fake_hwp_factory(docs), None))
    res = probe_document_dirty(src)
    assert res["dirty"] is True and res["modified_flags"] == [0, 1]


def test_probe_treats_unreadable_modified_flag_as_dirty(monkeypatch, tmp_path):
    src = tmp_path / "doc.hwpx"
    monkeypatch.setattr(dp, "load_pyhwpx", lambda: (_fake_hwp_factory([_FakeDoc(str(src), None)]), None))
    res = probe_document_dirty(src)
    assert res["state"] == "probed"
    assert res["dirty"] is True  # None/unreadable flag must never read as clean


def test_probe_fails_closed_when_not_attached(monkeypatch, tmp_path):
    monkeypatch.setattr(dp, "load_pyhwpx", lambda: (_fake_hwp_factory([]), None))
    res = probe_document_dirty(tmp_path / "doc.hwpx")
    assert res["state"] == "document_not_attached"
    assert res["ok"] is False and res["dirty"] is None


def test_probe_fails_closed_on_com_error(monkeypatch, tmp_path):
    class _Broken:
        def __init__(self, new=False, visible=True, on_quit=False):
            pass

        @property
        def XHwpDocuments(self):
            raise RuntimeError("RPC unavailable")

    monkeypatch.setattr(dp, "load_pyhwpx", lambda: (_Broken, None))
    res = probe_document_dirty(tmp_path / "doc.hwpx")
    assert res["state"] == "probe_error"
    assert res["ok"] is False and res["dirty"] is None


def test_probe_fails_closed_when_substrate_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(dp, "load_pyhwpx", lambda: (None, {"available": False, "ok": False, "state": "unavailable"}))
    res = probe_document_dirty(tmp_path / "doc.hwpx")
    assert res["available"] is False and res["dirty"] is None
