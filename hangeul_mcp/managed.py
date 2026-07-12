from __future__ import annotations

import json
import os
import shutil
import socket
import ssl
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import urlopen as default_urlopen

PACKAGE_NAME = "hangeul-mcp"
MODULE_NAME = "hangeul_mcp.server"
UPDATE_TTL_SECONDS = 24 * 60 * 60


class RunnerError(RuntimeError):
    """Raised when an injected command runner fails."""


@dataclass(frozen=True)
class ManagedPaths:
    root_dir: Path
    config_file: Path
    current_file: Path
    versions_dir: Path
    logs_dir: Path
    lock_file: Path

    @classmethod
    def from_root(cls, root: Path | str) -> "ManagedPaths":
        root_dir = Path(root)
        return cls(
            root_dir=root_dir,
            config_file=root_dir / "config.json",
            current_file=root_dir / "current.json",
            versions_dir=root_dir / "versions",
            logs_dir=root_dir / "logs",
            lock_file=root_dir / "update.lock",
        )

    @classmethod
    def discover(
        cls,
        *,
        platform: str | None = None,
        env: dict[str, str] | None = None,
    ) -> "ManagedPaths":
        return cls.from_root(get_user_data_dir(platform=platform, env=env))

    def version_dir(self, version: str) -> Path:
        return self.versions_dir / version

    def version_python_path(self, version: str) -> Path:
        version_dir = self.version_dir(version)
        windows_python = version_dir / "Scripts" / "python.exe"
        if windows_python.exists() or sys.platform == "win32":
            return windows_python
        return version_dir / "bin" / "python"


def get_user_data_dir(*, platform: str | None = None, env: dict[str, str] | None = None) -> Path:
    platform_name = platform or sys.platform
    environ = dict(os.environ if env is None else env)

    if platform_name == "win32":
        base = environ.get("APPDATA") or environ.get("LOCALAPPDATA")
        if not base:
            home = environ.get("USERPROFILE") or str(Path.home())
            base = str(Path(home) / "AppData" / "Roaming")
        return Path(base) / PACKAGE_NAME

    if platform_name == "darwin":
        home = environ.get("HOME") or str(Path.home())
        return Path(home) / "Library" / "Application Support" / PACKAGE_NAME

    base = environ.get("XDG_DATA_HOME")
    if base:
        return Path(base) / PACKAGE_NAME

    home = environ.get("HOME") or str(Path.home())
    return Path(home) / ".local" / "share" / PACKAGE_NAME


def ensure_managed_dirs(paths: ManagedPaths) -> ManagedPaths:
    paths.root_dir.mkdir(parents=True, exist_ok=True)
    best_effort_restrict_permissions(paths.root_dir)
    paths.versions_dir.mkdir(parents=True, exist_ok=True)
    paths.logs_dir.mkdir(parents=True, exist_ok=True)
    best_effort_restrict_permissions(paths.versions_dir)
    best_effort_restrict_permissions(paths.logs_dir)
    if not paths.config_file.exists():
        atomic_write_json(paths.config_file, {})
    if not paths.current_file.exists():
        atomic_write_json(paths.current_file, {"current_version": None, "previous_version": None, "install_source": None})
    return paths


def best_effort_restrict_permissions(path: Path) -> None:
    try:
        os.chmod(path, 0o700 if path.is_dir() else 0o600)
    except OSError:
        return


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp-{os.getpid()}-{time.time_ns()}")
    temp_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    best_effort_restrict_permissions(temp_path)
    os.replace(temp_path, path)
    best_effort_restrict_permissions(path)


def read_json_file(path: Path, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return {} if default is None else dict(default)
    return json.loads(path.read_text(encoding="utf-8"))


def load_current_state(paths: ManagedPaths) -> dict[str, Any]:
    return read_json_file(
        paths.current_file,
        default={"current_version": None, "previous_version": None, "install_source": None},
    )


def save_current_state(paths: ManagedPaths, state: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "current_version": state.get("current_version"),
        "previous_version": state.get("previous_version"),
        "install_source": state.get("install_source"),
        "updated_at": state.get("updated_at", int(time.time())),
    }
    atomic_write_json(paths.current_file, payload)
    return payload


def load_config(paths: ManagedPaths) -> dict[str, Any]:
    return read_json_file(paths.config_file, default={})


def save_config(paths: ManagedPaths, config: dict[str, Any]) -> dict[str, Any]:
    atomic_write_json(paths.config_file, config)
    return dict(config)


def switch_current_version(paths: ManagedPaths, version: str) -> dict[str, Any]:
    ensure_managed_dirs(paths)
    version_dir = paths.version_dir(version)
    if not version_dir.exists():
        raise FileNotFoundError(f"Managed version is missing: {version}")
    current = load_current_state(paths)
    payload = {
        "current_version": version,
        "previous_version": current.get("current_version"),
        "install_source": current.get("install_source"),
        "updated_at": int(time.time()),
    }
    return save_current_state(paths, payload)


def rollback_current_version(paths: ManagedPaths) -> dict[str, Any]:
    current = load_current_state(paths)
    previous_version = current.get("previous_version")
    if not previous_version:
        raise RuntimeError("No previous managed version is available for rollback")
    if not paths.version_dir(previous_version).exists():
        raise FileNotFoundError(f"Managed version is missing: {previous_version}")
    payload = {
        "current_version": previous_version,
        "previous_version": current.get("current_version"),
        "install_source": current.get("install_source"),
        "updated_at": int(time.time()),
    }
    return save_current_state(paths, payload)


def get_base_runtime_command(*, python_executable: str | None = None) -> list[str]:
    executable = python_executable or sys.executable
    return [executable, "-m", MODULE_NAME]


def get_managed_runtime_command(paths: ManagedPaths) -> list[str] | None:
    state = load_current_state(paths)
    current_version = state.get("current_version")
    if not current_version:
        return None
    runtime_python = paths.version_python_path(current_version)
    if not runtime_python.exists():
        return None
    return [str(runtime_python), "-m", MODULE_NAME]


class UpdateLock:
    def __init__(self, path: Path, *, poll_interval: float = 0.1):
        self.path = Path(path)
        self.poll_interval = poll_interval
        self._fd: int | None = None

    def acquire(self, *, timeout: float = 30.0) -> None:
        deadline = time.monotonic() + timeout
        self.path.parent.mkdir(parents=True, exist_ok=True)
        while True:
            try:
                self._fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
                os.write(self._fd, str(os.getpid()).encode("utf-8"))
                return
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"Timed out waiting for update lock: {self.path}")
                time.sleep(self.poll_interval)

    def release(self) -> None:
        if self._fd is None:
            return
        os.close(self._fd)
        self._fd = None
        try:
            self.path.unlink()
        except FileNotFoundError:
            return

    def __enter__(self) -> "UpdateLock":
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()


def _coerce_runner_error(exc: Exception) -> RunnerError:
    if isinstance(exc, RunnerError):
        return exc
    if isinstance(exc, subprocess.CalledProcessError):
        return RunnerError(str(exc))
    return RunnerError(str(exc))

def smoke_mcp_command(command: list[str], *, timeout: float = 10.0) -> dict[str, Any]:
    try:
        import asyncio
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

    async def run() -> dict[str, Any]:
        params = StdioServerParameters(command=command[0], args=command[1:])
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                listed = await session.list_tools()
                return {"ok": True, "tool_count": len(listed.tools)}

    try:
        return asyncio.run(asyncio.wait_for(run(), timeout=timeout))
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def install_managed_version(
    paths: ManagedPaths,
    version: str,
    *,
    runner: Callable[..., Any] | None = None,
    base_python: str | None = None,
    smoke_tester: Callable[[list[str]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    current_file_existed = paths.current_file.exists()
    ensure_managed_dirs(paths)
    version_dir = paths.version_dir(version)
    current_before = load_current_state(paths)
    run = runner or subprocess.run
    smoke = smoke_tester or smoke_mcp_command

    if version_dir.exists():
        shutil.rmtree(version_dir)

    try:
        run([base_python or sys.executable, "-m", "venv", str(version_dir)], check=True, cwd=None, env=None, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        runtime_python = paths.version_python_path(version)
        run([str(runtime_python), "-m", "pip", "install", f"{PACKAGE_NAME}=={version}"], check=True, cwd=None, env=None, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        run([str(runtime_python), "-c", f"import {MODULE_NAME}"], check=True, cwd=None, env=None, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        smoke_result = smoke([str(runtime_python), "-m", MODULE_NAME])
        if not smoke_result.get("ok"):
            raise RunnerError(str(smoke_result.get("error") or "mcp smoke failed"))
    except Exception as exc:
        if version_dir.exists():
            shutil.rmtree(version_dir, ignore_errors=True)
        if current_file_existed:
            save_current_state(paths, current_before)
        elif paths.current_file.exists():
            paths.current_file.unlink()
        error = _coerce_runner_error(exc)
        stage = "create"
        message = str(error)
        if "pip" in message or "install" in message:
            stage = "install"
        if MODULE_NAME in message or "mcp smoke" in message:
            stage = "smoke"
        return {"ok": False, "stage": stage, "error": message, "version": version}

    switched = save_current_state(
        paths,
        {
            "current_version": version,
            "previous_version": current_before.get("current_version"),
            "install_source": "pypi",
            "updated_at": int(time.time()),
        },
    )
    return {"ok": True, "stage": "complete", "version": version, "state": switched}


@dataclass(order=True, frozen=True)
class ParsedVersion:
    release: tuple[int, ...]
    stability_rank: int
    prerelease_number: int
    original: str

    @property
    def is_prerelease(self) -> bool:
        return self.stability_rank < 3


def parse_version(value: str) -> ParsedVersion:
    normalized = value.strip()
    release_part = normalized
    stability_rank = 3
    prerelease_number = 0

    for marker, rank in (("a", 0), ("b", 1), ("rc", 2)):
        if marker in normalized:
            release_part, suffix = normalized.split(marker, 1)
            stability_rank = rank
            digits = "".join(ch for ch in suffix if ch.isdigit())
            prerelease_number = int(digits or "0")
            break

    release = tuple(int(part) for part in release_part.split(".") if part)
    return ParsedVersion(release, stability_rank, prerelease_number, normalized)


def select_latest_version(releases: dict[str, Any], *, include_prerelease: bool = False) -> str | None:
    parsed: list[ParsedVersion] = []
    for version, files in releases.items():
        if not files:
            continue
        try:
            candidate = parse_version(version)
        except ValueError:
            continue
        if candidate.is_prerelease and not include_prerelease:
            continue
        parsed.append(candidate)
    if not parsed:
        return None
    return max(parsed, key=lambda item: (item.release, item.stability_rank, item.prerelease_number)).original


def fetch_pypi_json(
    *,
    package_name: str = PACKAGE_NAME,
    timeout: float = 10.0,
    urlopen: Callable[..., Any] = default_urlopen,
) -> dict[str, Any]:
    url = f"https://pypi.org/pypi/{package_name}/json"
    try:
        with urlopen(url, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except socket.timeout as exc:
        return {"ok": False, "error": "timeout", "detail": str(exc)}
    except ssl.SSLError as exc:
        return {"ok": False, "error": "tls", "detail": repr(exc.args)}
    except HTTPError as exc:
        return {"ok": False, "error": "http", "status": exc.code, "detail": exc.reason}
    except URLError as exc:
        reason = exc.reason
        if isinstance(reason, ssl.SSLError):
            return {"ok": False, "error": "tls", "detail": repr(reason.args)}
        if isinstance(reason, socket.timeout):
            return {"ok": False, "error": "timeout", "detail": str(reason)}
        return {"ok": False, "error": "network", "detail": str(reason)}
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": "invalid_json", "detail": str(exc)}

    return {"ok": True, "payload": payload}


def is_update_check_stale(last_checked_at: int | None, *, now: int | None = None, ttl_seconds: int = UPDATE_TTL_SECONDS) -> bool:
    if last_checked_at is None:
        return True
    current_time = int(time.time() if now is None else now)
    return current_time - int(last_checked_at) >= ttl_seconds


def check_for_updates(
    current_version: str,
    *,
    include_prerelease: bool = False,
    fetcher: Callable[[], dict[str, Any]] | None = None,
    now: int | None = None,
) -> dict[str, Any]:
    checked_at = int(time.time() if now is None else now)
    metadata = (fetcher or fetch_pypi_json)()
    if not metadata.get("ok"):
        if metadata.get("error") == "http" and metadata.get("status") == 404:
            return {"status": "not_published", "checked_at": checked_at}
        outcome = {"status": "error", "checked_at": checked_at}
        outcome.update(metadata)
        return outcome

    latest_version = select_latest_version(
        metadata["payload"].get("releases", {}),
        include_prerelease=include_prerelease,
    )
    if latest_version is None:
        return {"status": "not_published", "checked_at": checked_at}

    if parse_version(latest_version) > parse_version(current_version):
        return {
            "status": "update_available",
            "checked_at": checked_at,
            "current_version": current_version,
            "latest_version": latest_version,
            "prerelease_included": include_prerelease,
        }

    return {
        "status": "up_to_date",
        "checked_at": checked_at,
        "current_version": current_version,
        "latest_version": latest_version,
        "prerelease_included": include_prerelease,
    }
