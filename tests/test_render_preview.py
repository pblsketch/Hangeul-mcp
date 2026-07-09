from pathlib import Path

from hangeul_core import render
from hangeul_mcp import server

FIXTURE = Path(__file__).parent / "fixtures" / "sample_form.hwpx"


def test_render_preview_missing_playwright(monkeypatch, tmp_path):
    monkeypatch.setattr(render.delegate, "hwpx_available", lambda: True)
    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "playwright.sync_api":
            raise ImportError("no playwright")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)
    out = tmp_path / "preview.png"
    res = render.render_preview(FIXTURE, out)
    assert res["available"] is False
    assert res["ok"] is False
    assert not out.exists()


def test_render_preview_rejects_non_png(tmp_path):
    out = tmp_path / "preview.pdf"
    res = server.render_preview(str(FIXTURE), str(out), format="pdf")
    assert res["ok"] is False
    assert "png" in res["error"]
