from __future__ import annotations

import asyncio
import zipfile
from pathlib import Path

from hangeul_core.owpml import HwpxPackage
from hangeul_mcp import server

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


def test_server_edit_session_preview_apply_restore_contract(tmp_path):
    src = tmp_path / "source.hwpx"
    out = tmp_path / "out.hwpx"
    _build(src)

    preview = server.preview_search_and_replace(str(src), "2025", "2026")

    assert preview["available"] is True
    assert preview["ok"] is True
    assert preview["kind"] == "search_and_replace"
    assert preview["substrate"] == "own.byte_preserving_text"
    assert preview["counts"] == {"2025": 2}
    assert preview["total"] == 2
    assert preview["changed_entries"] == ["Contents/section0.xml"]
    assert not out.exists()

    applied = server.apply_edit_session(preview["session_id"], str(out))
    assert applied["available"] is True
    assert applied["ok"] is True
    assert applied["target_path"] == str(out)
    assert Path(applied["journal_path"]).exists()
    assert Path(applied["snapshot_path"]).exists()
    assert "2026년 계획 (2026 기준)" in _section(out)

    second = server.apply_edit_session(preview["session_id"], str(out))
    assert second["available"] is True
    assert second["ok"] is False
    assert "already applied" in second["error"]

    restored = server.restore_edit_session(applied["journal_path"])
    assert restored["available"] is True
    assert restored["ok"] is True
    assert restored["restored"] is True
    assert restored["target_exists"] is False
    assert not out.exists()


def test_server_registers_edit_session_tools():
    tools = asyncio.run(server.mcp.list_tools())
    names = {tool.name for tool in tools}
    assert {
        "preview_search_and_replace",
        "preview_batch_replace",
        "apply_edit_session",
        "restore_edit_session",
    } <= names
