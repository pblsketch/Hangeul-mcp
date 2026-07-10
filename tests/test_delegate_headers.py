"""US-057: header/footer delegate tools (python-hwpx set_header_text/set_footer_text).

BC2: "the text exists in the output" is verified by RE-OPENING the saved
package and searching its XML entries — never by validate_hwpx alone.
"""

import pytest

pytest.importorskip("hwpx")

from pathlib import Path

from hangeul_core.delegate_edit import set_footer, set_header
from hangeul_core.owpml import HwpxPackage
from hangeul_mcp import server

FIXTURE = Path(__file__).parent / "fixtures" / "sample_form.hwpx"


def _xml_contains(path, needle: str) -> bool:
    pkg = HwpxPackage.open(path)
    blob = needle.encode("utf-8")
    return any(blob in pkg.read(n) for n in pkg.names() if n.endswith(".xml"))


def test_set_header_text_lands_in_saved_package(tmp_path):
    out = tmp_path / "h.hwpx"
    res = set_header(FIXTURE, "머리말-검증-문자열", out)
    assert res["ok"] is True
    assert _xml_contains(out, "머리말-검증-문자열")


def test_set_footer_text_lands_in_saved_package(tmp_path):
    out = tmp_path / "f.hwpx"
    res = set_footer(FIXTURE, "꼬리말-검증-문자열", out)
    assert res["ok"] is True
    assert _xml_contains(out, "꼬리말-검증-문자열")


def test_old_hwpx_yields_actionable_version_message(monkeypatch, tmp_path):
    """Feature-detect: a pre-2.24 hwpx must not hide behind a bare AttributeError."""
    import hangeul_core.delegate_edit as de

    class OldDoc:  # no set_header_text
        pass

    monkeypatch.setattr(de, "doc", lambda p: OldDoc())
    res = server.set_header(str(FIXTURE), "x", str(tmp_path / "o.hwpx"))
    assert res["ok"] is False
    assert "requires python-hwpx>=2.24" in res["error"]


def test_header_footer_tools_registered():
    import asyncio

    tools = asyncio.run(server.mcp.list_tools())
    names = {t.name for t in tools}
    assert {"set_header", "set_footer"} <= names
