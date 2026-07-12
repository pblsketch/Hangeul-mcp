from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from hangeul_core.edit import apply_edit_session, preview_batch_replace, preview_search_and_replace, restore_edit_session
from hangeul_core.edit_session import OWN_TEXT_SUBSTRATE
from hangeul_core.owpml import HwpxPackage

_NS = (
    'xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
    'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"'
)


def _build(dst: Path) -> None:
    header = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
        b'<hh:head xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head"/>'
    )
    section0 = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?><hs:sec {_NS}>'
        '<hp:p id="1"><hp:run charPrIDRef="0"><hp:t>2025년 계획 (2025 기준)</hp:t></hp:run></hp:p>'
        '</hs:sec>'
    ).encode()
    with zipfile.ZipFile(dst, "w") as z:
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        z.writestr(zi, b"application/hwp+zip")
        z.writestr("Contents/header.xml", header)
        z.writestr("Contents/section0.xml", section0)


def _section(hwpx: Path) -> str:
    return HwpxPackage.open(hwpx).read("Contents/section0.xml").decode("utf-8")


def test_preview_search_and_replace_is_read_only_and_immutable(tmp_path):
    src = tmp_path / "source.hwpx"
    _build(src)

    plan = preview_search_and_replace(src, "2025", "2026")

    assert plan.kind == "search_and_replace"
    assert plan.substrate == OWN_TEXT_SUBSTRATE
    assert dict(plan.counts) == {"2025": 2}
    assert plan.total == 2
    assert list(plan.changed_entries) == ["Contents/section0.xml"]
    assert list(plan.audit) == ["Contents/section0.xml: 2 replacement(s) [2025×2]"]
    assert list(tmp_path.glob("*.journal.json")) == []
    assert "2025년 계획 (2025 기준)" in _section(src)

    with pytest.raises(TypeError):
        plan.counts["x"] = 1


def test_apply_edit_session_writes_journal_snapshot_and_restores_target(tmp_path):
    src = tmp_path / "source.hwpx"
    out = tmp_path / "out.hwpx"
    _build(src)
    _build(out)
    original_out = _section(out)

    plan = preview_batch_replace(src, {"2025": "2026"})
    session = apply_edit_session(plan.session_id, out)

    assert session.kind == "batch_replace"
    assert session.substrate == OWN_TEXT_SUBSTRATE
    assert dict(session.counts) == {"2025": 2}
    assert session.total == 2
    assert "2026년 계획 (2026 기준)" in _section(out)

    journal_path = Path(session.journal_path)
    snapshot_path = Path(session.snapshot_path)
    assert journal_path.exists()
    assert snapshot_path.exists()

    journal = json.loads(journal_path.read_text(encoding="utf-8"))
    assert journal["kind"] == "batch_replace"
    assert journal["substrate"] == OWN_TEXT_SUBSTRATE
    assert journal["target_existed_before_apply"] is True
    assert journal["snapshot_role"] == "target_before_apply"
    assert journal["counts"] == {"2025": 2}
    assert journal["audit"] == ["Contents/section0.xml: 2 replacement(s) [2025×2]"]

    with pytest.raises(RuntimeError):
        apply_edit_session(plan.session_id, out)

    restored = restore_edit_session(session.journal_path)
    assert restored.restored is True
    assert restored.target_exists is True
    assert _section(out) == original_out


def test_restore_edit_session_removes_new_target_when_unmodified(tmp_path):
    src = tmp_path / "source.hwpx"
    out = tmp_path / "out.hwpx"
    _build(src)

    plan = preview_batch_replace(src, {"2025": "2026"})
    session = apply_edit_session(plan.session_id, out)
    assert out.exists()

    restored = restore_edit_session(session.journal_path)
    assert restored.restored is True
    assert restored.target_exists is False
    assert not out.exists()


def test_restore_edit_session_refuses_to_clobber_modified_target(tmp_path):
    src = tmp_path / "source.hwpx"
    out = tmp_path / "out.hwpx"
    _build(src)
    _build(out)

    plan = preview_batch_replace(src, {"2025": "2026"})
    session = apply_edit_session(plan.session_id, out)
    out.write_bytes(b"user-modified")

    with pytest.raises(RuntimeError, match="target changed after apply"):
        restore_edit_session(session.journal_path)


def test_restore_edit_session_refuses_deleted_new_target(tmp_path):
    src = tmp_path / "source.hwpx"
    out = tmp_path / "out.hwpx"
    _build(src)

    plan = preview_batch_replace(src, {"2025": "2026"})
    session = apply_edit_session(plan.session_id, out)
    out.unlink()

    with pytest.raises(RuntimeError, match="target changed after apply"):
        restore_edit_session(session.journal_path)
