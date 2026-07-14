"""US-012: .hwp -> .hwpx conversion policy (D3)."""

import pytest

from hangeul_core.convert import ensure_hwpx, hwp_to_hwpx
from hangeul_core.hwp import HwpBridge
from hangeul_mcp import server


def test_ensure_hwpx_passthrough():
    assert ensure_hwpx("some/form.hwpx").endswith(".hwpx")


def test_hwp_conversion_requires_hangul(monkeypatch, tmp_path):
    monkeypatch.setattr(HwpBridge, "available", staticmethod(lambda: False))
    existing = tmp_path / "form.hwp"
    existing.write_bytes(b"HWP binary placeholder")
    with pytest.raises(RuntimeError, match="requires Windows"):
        hwp_to_hwpx(str(existing))


def test_analyze_form_hwp_graceful_without_hangul(monkeypatch, tmp_path):
    monkeypatch.setattr(HwpBridge, "available", staticmethod(lambda: False))
    fake = tmp_path / "form.hwp"
    fake.write_bytes(b"HWP binary placeholder")
    res = server.analyze_form(str(fake))
    assert "error" in res


def test_fill_form_hwp_graceful_without_hangul(monkeypatch, tmp_path):
    monkeypatch.setattr(HwpBridge, "available", staticmethod(lambda: False))
    fake = tmp_path / "form.hwp"
    fake.write_bytes(b"HWP binary placeholder")
    res = server.fill_form(str(fake), {"성명": "홍길동"}, str(tmp_path / "o.hwpx"))
    assert "error" in res
    assert res["filled"] == []
