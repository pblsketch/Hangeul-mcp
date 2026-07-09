from __future__ import annotations

import http.server
import socketserver
import tempfile
import threading
from pathlib import Path

from hangeul_core import delegate


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        return None


def _png_dimensions(path: str | Path) -> tuple[int | None, int | None]:
    data = Path(path).read_bytes()[:24]
    if len(data) >= 24 and data[:8] == b"\x89PNG\r\n\x1a\n":
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    return None, None


def render_available() -> tuple[bool, str | None]:
    if not delegate.hwpx_available():
        return False, "python-hwpx not installed (extra 'delegate')"
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False, "playwright not installed; run `pip install -e .[render]`"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            browser.close()
    except PlaywrightError as exc:
        return False, f"playwright browser unavailable; run `python -m playwright install chromium`: {exc}"
    return True, None


def render_preview(
    path: str | Path,
    out_path: str | Path,
    *,
    format: str = "png",
    width: int = 1280,
    height: int = 1800,
) -> dict:
    if format.lower() != "png":
        return {"available": True, "ok": False, "error": "only png preview is supported"}
    available, error = render_available()
    if not available:
        return {"available": False, "ok": False, "error": error}
    from playwright.sync_api import sync_playwright

    html = delegate.to_html(path)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        html_path = root / "index.html"
        html_path.write_text(html, encoding="utf-8")
        handler = lambda *args, **kwargs: _QuietHandler(*args, directory=str(root), **kwargs)
        with socketserver.TCPServer(("127.0.0.1", 0), handler) as httpd:
            port = httpd.server_address[1]
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch()
                    page = browser.new_page(viewport={"width": int(width), "height": int(height)})
                    page.goto(f"http://127.0.0.1:{port}/index.html", wait_until="networkidle")
                    page.screenshot(path=str(out), full_page=True)
                    browser.close()
            finally:
                httpd.shutdown()
                thread.join(timeout=5)
    w, h = _png_dimensions(out)
    return {
        "available": True,
        "ok": out.exists() and out.stat().st_size > 0,
        "out_path": str(out),
        "format": "png",
        "bytes": out.stat().st_size if out.exists() else 0,
        "width": w,
        "height": h,
    }
