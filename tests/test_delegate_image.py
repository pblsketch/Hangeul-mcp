"""US-027: DELEGATE image insertion via python-hwpx (skips without the substrate)."""

import base64
from pathlib import Path

import pytest

hwpx = pytest.importorskip("hwpx")

from hangeul_core.delegate import add_picture  # noqa: E402
from hangeul_core.validate import validate_hwpx  # noqa: E402
from hangeul_mcp import server  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "sample_form.hwpx"

# 1x1 transparent PNG (synthetic)
_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def _img_count(hwpx_path) -> int:
    return len(hwpx.HwpxDocument.open(str(hwpx_path)).list_images())


def test_add_picture_valid_and_image_count_increases(tmp_path):
    img = tmp_path / "seal.png"
    img.write_bytes(_PNG)
    before = _img_count(FIXTURE)
    out = tmp_path / "o.hwpx"
    res = add_picture(FIXTURE, img, out)
    assert res["ok"] is True and res["validation"]["valid"] is True
    assert _img_count(out) == before + 1


def test_server_add_image_bad_path_returns_structured_error(tmp_path):
    # a delegated op failure (missing image) must be a structured result, not a crash
    out = tmp_path / "o.hwpx"
    res = server.add_image(str(FIXTURE), str(tmp_path / "nope.png"), str(out))
    assert res["available"] is True and res.get("ok") is False and "error" in res


def test_server_add_image_tool(tmp_path):
    img = tmp_path / "sign.png"
    img.write_bytes(_PNG)
    out = tmp_path / "o.hwpx"
    res = server.add_image(str(FIXTURE), str(img), str(out))
    assert res["available"] is True and res["ok"] is True
    assert validate_hwpx(out)["valid"] is True
