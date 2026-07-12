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

import ntpath
import sys
from pathlib import Path
from typing import Dict, List, Sequence


def normalize_live_path(path: str | Path) -> str:
    """Normalize a live-attach path for exact Windows-style FullName matching."""
    raw = str(path or "").strip()
    if not raw:
        return ""
    return ntpath.normcase(ntpath.normpath(ntpath.abspath(raw.replace("/", "\\"))))


def same_doc(active_fullname: str, path: str | Path) -> bool:
    """True when an attached instance's active document IS the requested file."""
    normalized_active = normalize_live_path(active_fullname)
    return bool(normalized_active) and normalized_active == normalize_live_path(path)


def _document_fullname(doc) -> str:
    try:
        return str(doc.FullName or "")
    except Exception:
        return ""


def _document_index_base(docs, count: int) -> int:
    if count <= 0:
        return 0
    try:
        docs.Item(0)
        return 0
    except Exception:
        return 1


def inspect_open_documents(docs) -> List[dict]:
    """Read XHwpDocuments metadata without opening, attaching, or switching docs."""
    try:
        count = int(docs.Count)
    except Exception:
        return []
    active_path = _document_fullname(getattr(docs, "Active_XHwpDocument", None))
    active_normalized = normalize_live_path(active_path)
    base = _document_index_base(docs, count)
    documents: List[dict] = []
    for slot in range(count):
        entry: dict = {"slot": slot}
        try:
            fullname = _document_fullname(docs.Item(slot + base))
            entry["path"] = fullname
            entry["normalized_path"] = normalize_live_path(fullname)
            entry["is_active"] = bool(
                active_normalized and entry["normalized_path"] == active_normalized
            )
        except Exception as exc:
            entry["inspect_error"] = str(exc)
        documents.append(entry)
    if active_path and not any(doc.get("is_active") for doc in documents):
        documents.insert(
            0,
            {
                "slot": None,
                "path": active_path,
                "normalized_path": active_normalized,
                "is_active": True,
                "source": "Active_XHwpDocument",
            },
        )
    return documents


def inspect_attached_documents(hwp) -> List[dict]:
    """Read document metadata from an already-attached automation instance."""
    try:
        docs = hwp.XHwpDocuments
    except Exception:
        return []
    return inspect_open_documents(docs)


def active_attached_document_path(hwp) -> str:
    for doc in inspect_attached_documents(hwp):
        if doc.get("is_active"):
            return str(doc.get("path") or "")
    return ""


def find_attached_exact_path_documents(hwp, path: str | Path) -> List[dict]:
    """Return automation-visible attached documents whose FullName exactly matches *path*."""
    requested = normalize_live_path(path)
    if not requested:
        return []
    return [
        doc
        for doc in inspect_attached_documents(hwp)
        if str(doc.get("normalized_path") or "") == requested
    ]


def find_rot_exact_path_candidates(
    path: str | Path, instances: Sequence[dict] | None = None
) -> List[dict]:
    """Return ROT documents whose FullName exactly matches *path* after normalization."""
    requested = normalize_live_path(path)
    if not requested:
        return []
    if instances is None:
        instances = list_rot_instances()
    candidates: List[dict] = []
    for instance in instances:
        moniker = str(instance.get("moniker") or "")
        documents = instance.get("documents") or []
        matched = False
        for doc in documents:
            doc_path = str((doc or {}).get("path") or "")
            if not doc_path or normalize_live_path(doc_path) != requested:
                continue
            candidates.append(
                {
                    "state": "attached_existing",
                    "path": doc_path,
                    "source": "rot_exact_path",
                    "moniker": moniker,
                    "is_active": bool(doc.get("is_active")),
                }
            )
            matched = True
        if matched or documents:
            continue
        active_document = str(instance.get("active_document") or "")
        if same_doc(active_document, path):
            candidates.append(
                {
                    "state": "attached_existing",
                    "path": active_document,
                    "source": "rot_exact_path",
                    "moniker": moniker,
                    "is_active": True,
                }
            )
    return candidates


def pick_rot_exact_path_candidate(
    path: str | Path, instances: Sequence[dict] | None = None
) -> dict | None:
    """Return the unique exact-path ROT match, else None."""
    candidates = find_rot_exact_path_candidates(path, instances)
    return candidates[0] if len(candidates) == 1 else None
def normalize_field_values(values: Dict[str, str]) -> Dict[str, str]:
    """Light preprocessing before PutFieldText.

    Field (누름틀) text uses CRLF for line breaks; normalize newlines so
    multi-line values render correctly inside a field.
    """
    return {k: (v.replace("\r\n", "\n").replace("\n", "\r\n")) for k, v in values.items()}


def load_pyhwpx():
    """Guarded pyhwpx access shared by the live entry points.

    Returns ``(Hwp, None)`` when live COM is possible here, else
    ``(None, structured_error)`` — one source of truth for the fallback shape.
    """
    if sys.platform != "win32":
        return None, {"available": False, "error": "live COM needs Windows + Hangul"}
    try:
        from pyhwpx import Hwp  # optional; pulls pywin32/numpy/pandas
    except Exception as exc:  # ImportError or dependency error
        return None, {"available": False, "error": f"pyhwpx not installed (extra 'live'): {exc}"}
    return Hwp, None


# Hangul modal auto-answer while a live call runs: OK-only notices get OK,
# yes/no prompts (e.g. "already open — open read-only?") get NO so the call
# returns a structured error instead of hanging on an invisible dialog.
# Same mask pyhwpx uses around its own open/save paths.
_DIALOG_GUARD_MODE = 0x2FFF1


def suppress_dialogs(hwp):
    """Enable auto-answer for modal dialogs; returns the previous mode (or None)."""
    try:
        return hwp.SetMessageBoxMode(_DIALOG_GUARD_MODE)
    except Exception:
        return None


def restore_dialogs(hwp, previous_mode) -> None:
    if previous_mode is None:
        return
    try:
        hwp.SetMessageBoxMode(previous_mode)
    except Exception:
        pass


def list_rot_instances() -> List[dict]:
    """Enumerate running HwpObject automation instances (side-effect-free).

    Reads the COM Running Object Table and inspects only objects Hangul already
    registered there — it never creates an instance. Returned metadata is limited
    to the moniker plus observed XHwpDocuments/FullName values so callers can do
    exact-path attach resolution without claiming more than the ROT revealed.
    Returns [] off-Windows or without pywin32.
    """
    if sys.platform != "win32":
        return []
    try:
        import pythoncom
        import win32com.client as win32
    except Exception:
        return []
    instances: List[dict] = []
    try:
        pythoncom.CoInitialize()
        context = pythoncom.CreateBindCtx(0)
        rot = pythoncom.GetRunningObjectTable()
        for moniker in rot.EnumRunning():
            try:
                name = moniker.GetDisplayName(context, moniker)
            except Exception:
                continue
            if "HwpObject" not in name:
                continue
            entry: dict = {"moniker": name}
            try:
                obj = rot.GetObject(moniker)
                hwp = win32.Dispatch(obj.QueryInterface(pythoncom.IID_IDispatch))
                docs = hwp.XHwpDocuments
                entry["open_documents"] = int(docs.Count)
                entry["documents"] = inspect_open_documents(docs)
                active_document = next(
                    (doc.get("path", "") for doc in entry["documents"] if doc.get("is_active")),
                    "",
                )
                entry["active_document"] = active_document
                entry["normalized_active_document"] = normalize_live_path(active_document)
            except Exception as exc:
                entry["inspect_error"] = str(exc)
            instances.append(entry)
    except Exception:
        pass  # ROT unavailable -> report what was gathered so far
    return instances


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
