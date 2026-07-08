"""COM bridge to a running Hangul (한글) instance (v2 live apply).

Uses the Hancom automation API (``HWPFrame.HwpObject``) via pywin32 to read the
document's named fields (누름틀 / cell fields) and fill them in one shot with
``PutFieldText``. This is the only path that fills the *already-open* window.

Everything here is guarded: importing this module never fails off-Windows, and
``HwpBridge.available()`` only checks import-ability — it does NOT dispatch, so
merely inspecting status can never spawn a Hangul window. A real connection
happens only when :meth:`connect` is called explicitly.
"""

from __future__ import annotations

import sys
from typing import Dict, List


def normalize_field_values(values: Dict[str, str]) -> Dict[str, str]:
    """Light preprocessing before PutFieldText.

    Field (누름틀) text uses CRLF for line breaks; normalize newlines so
    multi-line values render correctly inside a field.
    """
    return {k: (v.replace("\r\n", "\n").replace("\n", "\r\n")) for k, v in values.items()}


class HwpBridge:
    """Thin wrapper over the Hancom HwpObject automation interface."""

    def __init__(self) -> None:
        self._hwp = None

    @staticmethod
    def available() -> bool:
        """True if the COM stack *could* work here (Windows + pywin32 importable).

        Does not dispatch Hangul, so it is side-effect free.
        """
        if sys.platform != "win32":
            return False
        import importlib.util

        return importlib.util.find_spec("win32com") is not None

    def connect(self, visible: bool = True, register_security: bool = True) -> "HwpBridge":
        """Dispatch/attach to a Hangul instance. Spawns Hangul if none is running."""
        if not self.available():
            raise RuntimeError(
                "COM bridge unavailable (needs Windows + pywin32 + Hangul installed)"
            )
        import win32com.client

        hwp = win32com.client.gencache.EnsureDispatch("HWPFrame.HwpObject")
        if register_security:
            try:
                hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
            except Exception:
                pass  # security-prompt DLL not registered; user may see prompts
        try:
            hwp.XHwpWindows.Item(0).Visible = visible
        except Exception:
            pass
        self._hwp = hwp
        return self

    def status(self) -> Dict[str, object]:
        """Report availability and, if connected, version + open-document count."""
        if self._hwp is None:
            return {"available": self.available(), "connected": False}
        version = None
        docs = None
        try:
            version = str(self._hwp.Version)
        except Exception:
            pass
        try:
            docs = int(self._hwp.XHwpDocuments.Count)
        except Exception:
            pass
        return {"available": True, "connected": True, "version": version, "open_documents": docs}

    def get_field_list(self) -> List[str]:
        if self._hwp is None:
            raise RuntimeError("not connected")
        raw = self._hwp.GetFieldList(0, 0) or ""
        return [x for x in raw.split("\x02") if x]

    def put_field_text(self, values: Dict[str, str]) -> Dict[str, object]:
        """Fill named fields; skip names absent from the document."""
        if self._hwp is None:
            raise RuntimeError("not connected")
        existing = set(self.get_field_list())
        bases = {name.split("{{")[0] for name in existing}
        applied: List[str] = []
        skipped: List[dict] = []
        for name, value in values.items():
            if existing and name not in existing and name not in bases:
                skipped.append({"field": name, "reason": "no such field in document"})
                continue
            try:
                self._hwp.PutFieldText(name, value)
                applied.append(name)
            except Exception as exc:  # pragma: no cover - depends on live Hangul
                skipped.append({"field": name, "reason": str(exc)})
        return {"applied": applied, "skipped": skipped}
