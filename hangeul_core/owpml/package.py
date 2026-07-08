"""Byte-preserving HWPX package I/O.

An HWPX file is an OPC/ODF-style ZIP whose first entry ``mimetype`` must be
stored uncompressed. This module reads all entries into memory, lets callers
stage byte replacements for specific entries, and repacks while preserving:

* original entry order,
* per-entry compression method,
* the ``mimetype`` entry as the first, STORED entry,
* every unmodified entry's payload byte-for-byte.

Only entries explicitly replaced via :meth:`HwpxPackage.replace` change; all
others are re-emitted with identical content bytes. (The archive is rewritten,
so raw ZIP local-header framing may differ; each entry's *payload* is identical.)
This is the substrate that makes "fill only the fields, touch nothing else" possible.
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Dict, List

MIMETYPE_ENTRY = "mimetype"
HWPX_MIMETYPE = b"application/hwp+zip"


class HwpxPackage:
    """In-memory, byte-preserving view of an HWPX package."""

    def __init__(self, path: str | Path):
        self._path = Path(path)
        self._infos: List[zipfile.ZipInfo] = []
        self._data: Dict[str, bytes] = {}
        self._replacements: Dict[str, bytes] = {}
        with zipfile.ZipFile(self._path, "r") as z:
            for info in z.infolist():
                self._infos.append(info)
                self._data[info.filename] = z.read(info.filename)

    @classmethod
    def open(cls, path: str | Path) -> "HwpxPackage":
        return cls(path)

    # -- introspection -------------------------------------------------
    def names(self) -> List[str]:
        """Entry names in original order."""
        return [i.filename for i in self._infos]

    def read(self, name: str) -> bytes:
        """Current bytes for *name* (staged replacement if any)."""
        if name in self._replacements:
            return self._replacements[name]
        return self._data[name]

    def has(self, name: str) -> bool:
        return name in self._data

    def is_mimetype_ok(self) -> bool:
        """True if the first entry is a STORED ``mimetype`` == HWPX mimetype."""
        if not self._infos:
            return False
        first = self._infos[0]
        return (
            first.filename == MIMETYPE_ENTRY
            and first.compress_type == zipfile.ZIP_STORED
            and self._data.get(MIMETYPE_ENTRY, b"").strip() == HWPX_MIMETYPE
        )

    # -- mutation ------------------------------------------------------
    def replace(self, name: str, data: bytes) -> None:
        """Stage a byte replacement for an existing entry."""
        if name not in self._data:
            raise KeyError(f"entry not in package: {name!r}")
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError("replacement data must be bytes")
        self._replacements[name] = bytes(data)

    # -- output --------------------------------------------------------
    def save(self, out_path: str | Path) -> Path:
        """Repack to *out_path* preserving order, compression and mimetype."""
        out_path = Path(out_path)
        with zipfile.ZipFile(out_path, "w") as zout:
            for info in self._infos:
                data = self._replacements.get(info.filename, self._data[info.filename])
                zi = zipfile.ZipInfo(info.filename, date_time=info.date_time)
                zi.compress_type = info.compress_type
                zi.external_attr = info.external_attr
                zi.internal_attr = info.internal_attr
                zi.create_system = info.create_system
                zout.writestr(zi, data)
        return out_path
