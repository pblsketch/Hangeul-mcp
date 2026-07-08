"""US-025: DELEGATE generation — markdown/text → HWPX (skips without python-hwpx)."""

import pytest

pytest.importorskip("hwpx")

from hangeul_core.delegate import create_from_markdown  # noqa: E402
from hangeul_core.owpml import HwpxPackage  # noqa: E402
from hangeul_core.validate import validate_hwpx  # noqa: E402
from hangeul_mcp import server  # noqa: E402


def _all_text(hwpx) -> str:
    pkg = HwpxPackage.open(hwpx)
    return "".join(
        pkg.read(n).decode("utf-8")
        for n in pkg.names()
        if n.startswith("Contents/section") and n.endswith(".xml")
    )


def test_create_from_markdown_valid_and_content(tmp_path):
    out = tmp_path / "new.hwpx"
    md = "# 보고서 제목\n\n첫 문단입니다.\n- 항목 하나\n- 항목 둘"
    res = create_from_markdown(md, out)
    assert res["ok"] is True and res["validation"]["valid"] is True
    text = _all_text(out)
    for expect in ("보고서 제목", "첫 문단입니다.", "항목 하나", "항목 둘"):
        assert expect in text
    # markdown markers stripped (no leading "# " / "- " in paragraph text)
    assert "# 보고서" not in text and "- 항목" not in text


def test_created_file_opens_and_validates(tmp_path):
    out = tmp_path / "new.hwpx"
    create_from_markdown("단일 문단", out)
    assert validate_hwpx(out)["valid"] is True


def test_server_create_tool(tmp_path):
    out = tmp_path / "new.hwpx"
    res = server.create_hwpx_from_markdown("서버 생성 테스트", str(out))
    assert res["available"] is True and res["ok"] is True
    assert "서버 생성 테스트" in _all_text(out)
