import pytest

pytest.importorskip("hwpx")

from hangeul_core.blocks import create_document_from_blocks
from hangeul_core.owpml import HwpxPackage
from hangeul_core.validate import validate_hwpx
from hangeul_mcp import server


def _xml(hwpx):
    pkg = HwpxPackage.open(hwpx)
    return "".join(
        pkg.read(n).decode("utf-8")
        for n in pkg.names()
        if n.startswith("Contents/section") and n.endswith(".xml")
    )


def test_create_document_from_blocks_order_and_content(tmp_path):
    out = tmp_path / "blocks.hwpx"
    blocks = [
        {"type": "heading", "level": 1, "text": "수업 계획"},
        {"type": "paragraph", "text": "도입 문단"},
        {"type": "bullet_list", "items": ["활동 하나", "활동 둘"]},
        {"type": "numbered_list", "items": ["첫째", "둘째"]},
        {"type": "table", "rows": [["단계", "내용"], ["도입", "질문"]]},
    ]
    res = create_document_from_blocks(blocks, out)
    assert res["ok"] is True and res["blocks"] == 5 and res["tables"] == 1
    text = _xml(out)
    for expected in ("수업 계획", "도입 문단", "활동 하나", "둘째", "질문"):
        assert expected in text
    assert validate_hwpx(out)["valid"] is True


def test_blocks_invalid_inputs(tmp_path):
    out = tmp_path / "bad.hwpx"
    assert create_document_from_blocks([], out)["ok"] is False
    assert create_document_from_blocks([{"type": "unknown"}], out)["ok"] is False
    assert create_document_from_blocks([{"type": "table", "rows": []}], out)["ok"] is False


def test_server_create_document_from_blocks(tmp_path):
    out = tmp_path / "server.hwpx"
    res = server.create_document_from_blocks(
        [{"type": "paragraph", "text": "서버 블록"}, {"type": "table", "rows": [["A", "B"]]}],
        str(out),
    )
    assert res["available"] is True and res["ok"] is True
    assert "서버 블록" in _xml(out)
