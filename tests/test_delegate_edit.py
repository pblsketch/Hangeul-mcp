"""US-024: DELEGATE structural edit (add_paragraph/add_table) + validate gate.

Delegated edits re-serialize the XML (not byte-identical); the contract is that
the output passes our own validate_hwpx gate. Skips when python-hwpx is absent.
"""

from pathlib import Path

import pytest

pytest.importorskip("hwpx")

from hangeul_core.delegate import add_paragraph, add_table  # noqa: E402
from hangeul_core.owpml import HwpxPackage  # noqa: E402
from hangeul_core.read import get_document_outline  # noqa: E402
from hangeul_mcp import server  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "sample_form.hwpx"


def _all_text(hwpx) -> str:
    pkg = HwpxPackage.open(hwpx)
    return "".join(
        pkg.read(n).decode("utf-8")
        for n in pkg.names()
        if n.startswith("Contents/section") and n.endswith(".xml")
    )


def test_add_paragraph_valid_and_present(tmp_path):
    out = tmp_path / "o.hwpx"
    res = add_paragraph(FIXTURE, "델리게이트 추가 문단", out)
    assert res["ok"] is True and res["validation"]["valid"] is True
    assert "델리게이트 추가 문단" in _all_text(out)


def test_add_table_valid_and_table_count_increased(tmp_path):
    before = len(get_document_outline(FIXTURE)["tables"])
    out = tmp_path / "o.hwpx"
    res = add_table(FIXTURE, 2, 3, out)
    assert res["ok"] is True and res["validation"]["valid"] is True
    after = len(get_document_outline(out)["tables"])
    assert after == before + 1


def test_server_add_paragraph_tool(tmp_path):
    out = tmp_path / "o.hwpx"
    res = server.add_paragraph(str(FIXTURE), "서버 경유 문단", str(out))
    assert res["available"] is True and res["ok"] is True
    assert "서버 경유 문단" in _all_text(out)


def test_server_add_table_tool(tmp_path):
    out = tmp_path / "o.hwpx"
    res = server.add_table(str(FIXTURE), 3, 2, str(out))
    assert res["available"] is True and res["ok"] is True
    assert res["validation"]["valid"] is True
