import pytest

pytest.importorskip("hwpx")

from hangeul_core.markdown import markdown_to_blocks
from hangeul_core.delegate import create_from_markdown
from hangeul_core.owpml import HwpxPackage
from hangeul_core.read import get_document_outline
from hangeul_core.validate import validate_hwpx
from hangeul_mcp import server


def _xml(hwpx):
    pkg = HwpxPackage.open(hwpx)
    return "".join(
        pkg.read(n).decode("utf-8")
        for n in pkg.names()
        if n.startswith("Contents/section") and n.endswith(".xml")
    )


def test_markdown_to_blocks_supported_subset():
    md = "# 제목\n\n본문입니다.\n- 항목 하나\n- 항목 둘\n\n| 단계 | 내용 |\n| --- | --- |\n| 도입 | 질문 |"
    blocks = markdown_to_blocks(md)
    assert [b["type"] for b in blocks] == ["heading", "paragraph", "bullet_list", "table"]
    assert blocks[0]["text"] == "제목"
    assert blocks[-1]["rows"][1] == ["도입", "질문"]


def test_create_from_markdown_preserves_basic_structure(tmp_path):
    out = tmp_path / "md.hwpx"
    md = "# 보고서 제목\n\n첫 문단입니다.\n- 항목 하나\n- 항목 둘\n\n| 이름 | 역할 |\n| --- | --- |\n| 홍길동 | 발표 |"
    res = create_from_markdown(md, out)
    assert res["ok"] is True and res["tables"] == 1
    text = _xml(out)
    for expected in ("보고서 제목", "첫 문단입니다.", "항목 하나", "홍길동"):
        assert expected in text
    assert "# 보고서" not in text and "- 항목" not in text
    assert any(t["rows"] == 2 and t["cols"] == 2 for t in get_document_outline(out)["tables"])
    assert validate_hwpx(out)["valid"] is True


def test_server_markdown_tool(tmp_path):
    out = tmp_path / "server.hwpx"
    res = server.create_hwpx_from_markdown("# 서버 제목\n\n내용", str(out))
    assert res["available"] is True and res["ok"] is True
    assert "서버 제목" in _xml(out)
