from hangeul_core import hwp_headless
from hangeul_mcp import server


def test_hwp_headless_missing_substrate(monkeypatch, tmp_path):
    monkeypatch.setattr(hwp_headless, "CANDIDATES", ("definitely_missing_hwp_reader",))
    fake = tmp_path / "sample.hwp"
    fake.write_bytes(b"HWP binary placeholder")
    res = hwp_headless.extract_hwp_text(fake)
    assert res["available"] is False
    assert res["ok"] is False
    assert res["checked"] == {"definitely_missing_hwp_reader": False}


def test_server_extract_hwp_text_non_hwp(tmp_path):
    fake = tmp_path / "sample.txt"
    fake.write_text("x", encoding="utf-8")
    res = server.extract_hwp_text(str(fake))
    assert res["ok"] is False
    assert ".hwp" in res["error"]
