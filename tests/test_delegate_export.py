"""US-023: DELEGATE export/preview via python-hwpx (soft dependency).

Skips cleanly when python-hwpx is not installed, so CI without the 'delegate'
extra stays green.
"""

from pathlib import Path

import pytest

pytest.importorskip("hwpx")  # python-hwpx (import name: hwpx)

from hangeul_core.delegate import hwpx_available, to_html, to_markdown, to_text_rich  # noqa: E402
from hangeul_mcp import server  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "sample_form.hwpx"


def test_available():
    assert hwpx_available() is True


def test_to_html_renders_markup_with_text():
    html = to_html(FIXTURE)
    assert "성명" in html and "<" in html  # contains HTML markup


def test_to_markdown_contains_text():
    assert "성명" in to_markdown(FIXTURE).replace(" ", "")


def test_to_text_rich_contains_text():
    assert "성명" in to_text_rich(FIXTURE).replace(" ", "")


def test_server_hwpx_to_html_tool():
    res = server.hwpx_to_html(str(FIXTURE))
    assert res["available"] is True and "성명" in res["html"]


def test_server_hwpx_to_markdown_tool():
    res = server.hwpx_to_markdown(str(FIXTURE))
    assert res["available"] is True and "성명" in res["markdown"].replace(" ", "")
