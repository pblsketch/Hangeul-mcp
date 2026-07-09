"""US-035: DELEGATE build a filled table from 2D data (skips without python-hwpx)."""

import pytest

pytest.importorskip("hwpx")

from hangeul_core.delegate import create_table_from_rows  # noqa: E402
from hangeul_core.owpml import HwpxPackage  # noqa: E402
from hangeul_core.read import get_document_outline  # noqa: E402
from hangeul_core.validate import validate_hwpx  # noqa: E402
from hangeul_mcp import server  # noqa: E402


def _all_text(hwpx) -> str:
    pkg = HwpxPackage.open(hwpx)
    return "".join(
        pkg.read(n).decode("utf-8")
        for n in pkg.names()
        if n.startswith("Contents/section") and n.endswith(".xml")
    )


def test_create_table_valid_and_content(tmp_path):
    out = tmp_path / "t.hwpx"
    rows = [["이름", "부서", "직급"], ["홍길동", "교육팀", "선임"], ["김철수", "연구팀", "책임"]]
    res = create_table_from_rows(rows, out)
    assert res["ok"] is True and res["validation"]["valid"] is True
    assert res["rows"] == 3 and res["cols"] == 3
    text = _all_text(out)
    for v in ("이름", "홍길동", "교육팀", "책임"):
        assert v in text
    # a 3x3 table exists in the outline
    tables = get_document_outline(out)["tables"]
    assert any(t["rows"] == 3 and t["cols"] == 3 for t in tables)


def test_ragged_rows_padded(tmp_path):
    out = tmp_path / "t.hwpx"
    res = create_table_from_rows([["a", "b", "c"], ["x"]], out)  # 2nd row short
    assert res["ok"] is True and res["cols"] == 3
    assert validate_hwpx(out)["valid"] is True


def test_empty_rows_rejected(tmp_path):
    out = tmp_path / "t.hwpx"
    res = create_table_from_rows([], out)
    assert res.get("ok") is False and not out.exists()


def test_server_create_table_tool(tmp_path):
    out = tmp_path / "t.hwpx"
    res = server.create_hwpx_table([["h1", "h2"], ["v1", "v2"]], str(out))
    assert res["available"] is True and res["ok"] is True
    assert "v1" in _all_text(out)
