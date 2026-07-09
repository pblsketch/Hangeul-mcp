"""US-036: DELEGATE official-document recipe (skips without python-hwpx)."""

import pytest

pytest.importorskip("hwpx")

from hangeul_core.delegate import create_official_document  # noqa: E402
from hangeul_core.owpml import HwpxPackage  # noqa: E402
from hangeul_mcp import server  # noqa: E402


def _all_text(hwpx) -> str:
    pkg = HwpxPackage.open(hwpx)
    return "".join(
        pkg.read(n).decode("utf-8")
        for n in pkg.names()
        if n.startswith("Contents/section") and n.endswith(".xml")
    )


def test_official_document_content_and_order(tmp_path):
    out = tmp_path / "doc.hwpx"
    fields = {
        "기관명": "한국교육연구소",
        "수신": "각 학교장",
        "제목": "여름 독서토론 특강 안내",
        "본문": "아래와 같이 특강을 안내합니다.\n많은 참여 바랍니다.",
        "날짜": "2026. 8. 1.",
        "발신명의": "한국교육연구소장",
    }
    res = create_official_document(fields, out)
    assert res["ok"] is True and res["validation"]["valid"] is True
    text = _all_text(out)
    for v in ("한국교육연구소", "각 학교장", "여름 독서토론 특강 안내", "많은 참여 바랍니다.", "한국교육연구소장"):
        assert v in text
    # 수신 appears before 제목 which appears before the body
    assert text.index("각 학교장") < text.index("여름 독서토론 특강 안내") < text.index("많은 참여")


def test_official_document_ignores_unknown_and_stays_valid(tmp_path):
    out = tmp_path / "doc.hwpx"
    res = create_official_document({"제목": "제목만", "미지의키": "무시됨"}, out)
    assert res["ok"] is True
    assert "제목만" in _all_text(out) and "무시됨" not in _all_text(out)


def test_server_official_document_tool(tmp_path):
    out = tmp_path / "doc.hwpx"
    res = server.create_official_document({"제목": "테스트 공문", "본문": "본문 내용"}, str(out))
    assert res["available"] is True and res["ok"] is True
    assert "테스트 공문" in _all_text(out)
