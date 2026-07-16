from __future__ import annotations
import json
import os
import shutil
import stat
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final
from hangeul_core.assessment_publish import PublishError
from hangeul_core.assessment_publish import SafeOutputRootRegistry as _PublishRootRegistry
MARKER_NAME: Final = ".hangeul-assessment-owner.json"
STAGING_PREFIX: Final = ".hangeul-assessment-staging-"
_MARKER_VERSION: Final = 1
_REPARSE_POINT: Final = 0x400
@dataclass(frozen=True, slots=True)
class CleanupError(RuntimeError):
    code: str
    def __str__(self) -> str:
        return self.code
@dataclass(frozen=True, slots=True)
class OwnershipMarker:
    marker_version: int
    session_id: str
    owner_instance_id: str
    ownership_nonce: str
    created_at_epoch: int
@dataclass(frozen=True, slots=True)
class CleanupResult:
    removed: int = 0
    cleanup_skipped_unowned: int = 0
    foreign_staging_detected: int = 0
@dataclass(frozen=True, slots=True)
class StagingOwner:
    session_id: str
    ownership_nonce: str
class SafeOutputRootRegistry:
    __slots__ = ("_registry",)
    def __init__(self, roots: tuple[str | Path, ...]) -> None:
        try:
            self._registry = _PublishRootRegistry(roots)
        except PublishError as exc:
            raise CleanupError(exc.code) from None
    def require_exact(self, output_dir: str | Path) -> Path:
        try:
            return self._registry.require_exact(output_dir)
        except PublishError as exc:
            raise CleanupError(exc.code) from None
class OwnershipRegistry:
    """Mutable registry intentionally tracks current-process staging ownership."""
    __slots__ = ("instance_id", "_active_sessions", "_owned")
    def __init__(self, instance_id: str) -> None:
        self.instance_id = instance_id
        self._active_sessions: set[str] = set()
        self._owned: dict[Path, tuple[str, str]] = {}
    def register(
        self,
        staging: str | Path,
        ownership_nonce: str,
        session_id: str,
    ) -> None:
        self._owned[Path(staging).resolve(strict=False)] = (session_id, ownership_nonce)
    def unregister(self, staging: str | Path) -> None:
        self._owned.pop(Path(staging).resolve(strict=False), None)
    def ownership(self, staging: str | Path) -> tuple[str, str] | None:
        return self._owned.get(Path(staging).resolve(strict=False))
    def activate(self, session_id: str) -> None:
        self._active_sessions.add(session_id)
    def deactivate(self, session_id: str) -> None:
        self._active_sessions.discard(session_id)
    def is_active(self, session_id: str) -> bool:
        return session_id in self._active_sessions
    def forget(self, session_id: str, ownership_nonce: str) -> None:
        for path, owner in tuple(self._owned.items()):
            if owner == (session_id, ownership_nonce):
                self._owned.pop(path)
def staging_directory_name(session_id: str, ownership_nonce: str) -> str:
    return f"{STAGING_PREFIX}{session_id}-{ownership_nonce}"
def write_staging_marker(
    staging: str | Path,
    instance_id: str,
    ownership_nonce: str,
    session_id: str,
    created_at_epoch: int | None = None,
) -> Path:
    marker = OwnershipMarker(
        marker_version=_MARKER_VERSION,
        session_id=session_id,
        owner_instance_id=instance_id,
        ownership_nonce=ownership_nonce,
        created_at_epoch=created_at_epoch or int(time.time()),
    )
    marker_path = Path(staging) / MARKER_NAME
    marker_path.write_text(
        json.dumps(asdict(marker), sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return marker_path
def create_owned_staging(
    safe_root: str | Path,
    owner: StagingOwner,
    registry: OwnershipRegistry,
) -> Path:
    root = Path(safe_root).resolve(strict=True)
    staging = root / staging_directory_name(owner.session_id, owner.ownership_nonce)
    staging.mkdir()
    registry.register(staging, owner.ownership_nonce, owner.session_id)
    write_staging_marker(
        staging,
        registry.instance_id,
        owner.ownership_nonce,
        owner.session_id,
    )
    return staging
def cleanup_staging(
    safe_root: str | Path,
    safe_roots: SafeOutputRootRegistry,
    ownership: OwnershipRegistry,
    *,
    active_sessions: frozenset[str],
) -> CleanupResult:
    root = safe_roots.require_exact(safe_root)
    removed = skipped = foreign = 0
    for path in root.iterdir():
        if not path.name.startswith(STAGING_PREFIX):
            continue
        marker = _read_marker(path / MARKER_NAME)
        if marker is not None and marker.session_id in active_sessions:
            skipped += 1
            continue
        result = cleanup_owned_staging(path, ownership, root)
        removed += result.removed
        skipped += result.cleanup_skipped_unowned
        foreign += result.foreign_staging_detected
    return CleanupResult(removed, skipped, foreign)
def cleanup_owned_staging(
    staging: str | Path,
    registry: OwnershipRegistry,
    safe_root: str | Path,
) -> CleanupResult:
    path = Path(staging)
    root = Path(safe_root).resolve(strict=True)
    if not _is_direct_child(path, root) or not path.name.startswith(STAGING_PREFIX):
        return CleanupResult(cleanup_skipped_unowned=1)
    if _unsafe_entry(path):
        raise CleanupError("cleanup_unsafe_descendant")
    marker = _read_marker(path / MARKER_NAME)
    if marker is None:
        return CleanupResult(cleanup_skipped_unowned=1)
    if marker.owner_instance_id != registry.instance_id:
        return CleanupResult(foreign_staging_detected=1)
    ownership = registry.ownership(path)
    if ownership != (marker.session_id, marker.ownership_nonce):
        return CleanupResult(cleanup_skipped_unowned=1)
    if registry.is_active(marker.session_id):
        return CleanupResult(cleanup_skipped_unowned=1)
    _preflight_descendants(path)
    try:
        shutil.rmtree(path)
    except OSError:
        raise CleanupError("cleanup_unsafe_descendant") from None
    registry.unregister(path)
    return CleanupResult(removed=1)
def _is_direct_child(path: Path, root: Path) -> bool:
    try:
        raw_absolute = path if path.is_absolute() else Path.cwd() / path
        resolved = path.resolve(strict=True)
    except OSError:
        return False
    return (
        os.path.normcase(str(raw_absolute)) == os.path.normcase(str(resolved))
        and resolved.parent == root
    )
def _read_marker(marker_path: Path) -> OwnershipMarker | None:
    try:
        payload = json.loads(marker_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if set(payload) != set(OwnershipMarker.__dataclass_fields__):
        return None
    try:
        marker = OwnershipMarker(**payload)
    except TypeError:
        return None
    if marker.marker_version != _MARKER_VERSION:
        return None
    return marker
def _unsafe_entry(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError:
        return True
    attributes = getattr(info, "st_file_attributes", 0)
    return stat.S_ISLNK(info.st_mode) or bool(attributes & _REPARSE_POINT)
def _preflight_descendants(root: Path) -> None:
    pending = [root]
    while pending:
        current = pending.pop()
        try:
            entries = tuple(os.scandir(current))
        except OSError:
            raise CleanupError("cleanup_unsafe_descendant") from None
        for entry in entries:
            try:
                info = entry.stat(follow_symlinks=False)
            except OSError:
                raise CleanupError("cleanup_unsafe_descendant") from None
            attributes = getattr(info, "st_file_attributes", 0)
            if stat.S_ISLNK(info.st_mode) or attributes & _REPARSE_POINT:
                raise CleanupError("cleanup_unsafe_descendant")
            if stat.S_ISDIR(info.st_mode):
                pending.append(Path(entry.path))
__all__ = [
    "CleanupError",
    "CleanupResult",
    "OwnershipMarker",
    "OwnershipRegistry",
    "SafeOutputRootRegistry",
    "StagingOwner",
    "cleanup_staging",
    "cleanup_owned_staging",
    "create_owned_staging",
    "staging_directory_name",
    "write_staging_marker",
]
