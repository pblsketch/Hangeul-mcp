from __future__ import annotations
import ctypes
import errno
import os
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Iterable, Protocol
RENAME_NOREPLACE: Final = 1
_AT_FDCWD: Final = -100
_COLLISION_ERRORS: Final = frozenset({errno.EEXIST, errno.ENOTEMPTY, 80, 183})
_UNAVAILABLE_ERRORS: Final = frozenset(
    {errno.ENOSYS, errno.EINVAL, getattr(errno, "EOPNOTSUPP", errno.ENOTSUP), 1, 50, 120}
)
class MovePrimitive(Protocol):
    def __call__(self, source: Path, destination: Path, flags: int) -> None: ...
class DeviceId(Protocol):
    def __call__(self, path: Path) -> int: ...
@dataclass(frozen=True, slots=True)
class PublishError(RuntimeError):
    code: str
    def __str__(self) -> str:
        return self.code
@dataclass(frozen=True, slots=True)
class AtomicPublishProbeResult:
    available: bool
@dataclass(frozen=True, slots=True)
class PublishedRecovery:
    code: str
@dataclass(frozen=True, slots=True, init=False)
class SafeOutputRootRegistry:
    roots: tuple[Path, ...]
    def __init__(self, roots: Iterable[str | Path]) -> None:
        canonical = tuple(_registered_root(root) for root in roots)
        object.__setattr__(self, "roots", tuple(dict.fromkeys(canonical)))
    def require_exact(self, output_dir: str | Path) -> Path:
        candidate = Path(output_dir)
        raw_absolute = candidate if candidate.is_absolute() else Path.cwd() / candidate
        try:
            resolved = candidate.resolve(strict=True)
        except OSError:
            raise PublishError("unregistered_output_root") from None
        registered = {_path_key(root) for root in self.roots}
        if (
            not resolved.is_dir()
            or _raw_path_key(raw_absolute) != _raw_path_key(resolved)
            or _path_key(resolved) not in registered
        ):
            raise PublishError("unregistered_output_root")
        return resolved
class AtomicPublishAdapter:
    """Mutable counter records use of the single production publish seam."""
    __slots__ = ("_device_id", "_flags", "_move", "publish_count")
    def __init__(
        self,
        move: MovePrimitive | None,
        flags: int,
        device_id: DeviceId,
    ) -> None:
        self._move = move
        self._flags = flags
        self._device_id = device_id
        self.publish_count = 0
    @classmethod
    def windows(cls, move: MovePrimitive, device_id: DeviceId) -> AtomicPublishAdapter:
        return cls(move, 0, device_id)
    @classmethod
    def linux(cls, move: MovePrimitive, device_id: DeviceId) -> AtomicPublishAdapter:
        return cls(move, RENAME_NOREPLACE, device_id)
    @classmethod
    def unavailable(cls) -> AtomicPublishAdapter:
        return cls(None, RENAME_NOREPLACE, _stat_device_id)
    def publish(self, staging: str | Path, final: str | Path) -> None:
        source = Path(staging)
        destination = Path(final)
        self.publish_count += 1
        if self._move is None:
            raise PublishError("atomic_publish_unavailable")
        try:
            source_device = self._device_id(source)
            parent_device = self._device_id(destination.parent)
        except OSError:
            raise PublishError("publish_io_error") from None
        if source_device != parent_device:
            raise PublishError("cross_device_publish")
        try:
            self._move(source, destination, self._flags)
        except OSError as exc:
            _raise_mapped_os_error(exc.errno)
def _stat_device_id(path: Path) -> int:
    return os.stat(path, follow_symlinks=False).st_dev
def _registered_root(root: str | Path) -> Path:
    try:
        resolved = Path(root).resolve(strict=True)
    except OSError:
        raise PublishError("unregistered_output_root") from None
    if not resolved.is_dir():
        raise PublishError("unregistered_output_root")
    return resolved
def _path_key(path: Path) -> str:
    return os.path.normcase(os.path.normpath(str(path)))
def _raw_path_key(path: Path) -> str:
    return os.path.normcase(str(path))
def _raise_mapped_os_error(error_number: int | None) -> None:
    if error_number in _COLLISION_ERRORS:
        raise PublishError("output_collision")
    if error_number in {errno.EXDEV, 17}:
        raise PublishError("cross_device_publish")
    if error_number in _UNAVAILABLE_ERRORS:
        raise PublishError("atomic_publish_unavailable")
    raise PublishError("publish_io_error")
def _windows_move(source: Path, destination: Path, flags: int) -> None:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    move_file = kernel32.MoveFileExW
    move_file.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32)
    move_file.restype = ctypes.c_int
    if not move_file(str(source), str(destination), flags):
        error_number = ctypes.get_last_error()
        raise OSError(error_number, "publish failed")
def _linux_rename(source: Path, destination: Path, flags: int) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    try:
        renameat2 = libc.renameat2
    except AttributeError:
        raise OSError(errno.ENOSYS, "publish unavailable") from None
    renameat2.argtypes = (
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    )
    renameat2.restype = ctypes.c_int
    result = renameat2(
        _AT_FDCWD,
        os.fsencode(source),
        _AT_FDCWD,
        os.fsencode(destination),
        flags,
    )
    if result != 0:
        error_number = ctypes.get_errno()
        raise OSError(error_number, "publish failed")
def platform_atomic_publish_adapter() -> AtomicPublishAdapter:
    match sys.platform:
        case "win32":
            return AtomicPublishAdapter.windows(_windows_move, _stat_device_id)
        case "linux":
            return AtomicPublishAdapter.linux(_linux_rename, _stat_device_id)
        case _:
            return AtomicPublishAdapter.unavailable()
def _publish_directory_no_replace(
    staging: str | Path,
    final: str | Path,
    adapter: AtomicPublishAdapter | None = None,
) -> None:
    (adapter or platform_atomic_publish_adapter()).publish(staging, final)
def run_atomic_publish_probe(
    safe_root: str | Path,
    adapter: AtomicPublishAdapter | None = None,
) -> AtomicPublishProbeResult:
    from hangeul_core.assessment_cleanup import (
        CleanupError,
        OwnershipRegistry,
        StagingOwner,
        cleanup_owned_staging,
        create_owned_staging,
        staging_directory_name,
    )
    root = Path(safe_root).resolve(strict=True)
    publisher = adapter or platform_atomic_publish_adapter()
    nonce = uuid.uuid4().hex
    registry = OwnershipRegistry(f"probe-{nonce}")
    first_owner = StagingOwner("probe-first", f"{nonce}-first")
    second_owner = StagingOwner("probe-second", f"{nonce}-second")
    first = create_owned_staging(root, first_owner, registry)
    second = create_owned_staging(root, second_owner, registry)
    final = root / staging_directory_name("probe-final", nonce)
    expected_marker = (first / ".hangeul-assessment-owner.json").read_bytes()
    available = False
    try:
        _publish_directory_no_replace(first, final, publisher)
        registry.register(final, first_owner.ownership_nonce, first_owner.session_id)
        try:
            _publish_directory_no_replace(second, final, publisher)
        except PublishError as exc:
            available = exc.code == "output_collision"
        marker_after = final / ".hangeul-assessment-owner.json"
        available = available and marker_after.read_bytes() == expected_marker
    except (OSError, PublishError):
        available = False
    finally:
        cleanup_ok = True
        for path in (first, second, final):
            if path.exists():
                try:
                    cleanup_owned_staging(path, registry, root)
                except CleanupError:
                    cleanup_ok = False
        available = available and cleanup_ok
    return AtomicPublishProbeResult(available=available)
def recover_published_session(
    final: str | Path,
    adapter: AtomicPublishAdapter,
) -> PublishedRecovery:
    del adapter
    if not Path(final).is_dir():
        raise PublishError("publish_io_error")
    return PublishedRecovery(code="already_applied")
__all__ = [
    "RENAME_NOREPLACE",
    "AtomicPublishAdapter",
    "AtomicPublishProbeResult",
    "PublishError", "PublishedRecovery", "SafeOutputRootRegistry",
    "_publish_directory_no_replace",
    "platform_atomic_publish_adapter",
    "recover_published_session",
    "run_atomic_publish_probe",
]
