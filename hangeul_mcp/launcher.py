from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Callable

from hangeul_mcp.managed import (
    ManagedPaths,
    get_base_runtime_command,
    get_managed_runtime_command,
    is_update_check_stale,
    load_config,
    load_current_state,
)

Execv = Callable[[str, list[str]], None]
Popen = Callable[..., object]


def maybe_schedule_daily_update(
    paths: ManagedPaths,
    *,
    popen: Popen = subprocess.Popen,
) -> dict[str, object]:
    config = load_config(paths)
    if config.get("auto", "notify") != "daily":
        return {"status": "skipped", "reason": "policy_disabled"}

    current = load_current_state(paths)
    if current.get("install_source") != "pypi":
        return {"status": "skipped", "reason": "unsupported_install_source"}

    last_checked_at = config.get("last_checked_at")
    if not is_update_check_stale(last_checked_at):
        return {"status": "skipped", "reason": "fresh_ttl"}

    paths.logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = paths.logs_dir / "auto-update.log"

    with log_path.open("ab") as handle:
        popen(
            [os.fspath(Path(get_base_runtime_command()[0])), "-m", "hangeul_mcp.manage", "update"],
            cwd=os.fspath(paths.root_dir),
            stdout=handle,
            stderr=handle,
            close_fds=True,
        )
    return {"status": "scheduled", "log_path": str(log_path)}
    return {"status": "scheduled", "log_path": str(log_path)}



def resolve_launcher_command(*, data_dir: Path | str | None = None) -> list[str]:
    paths = ManagedPaths.from_root(data_dir) if data_dir is not None else ManagedPaths.discover()
    return get_managed_runtime_command(paths) or get_base_runtime_command()


def main(
    *,
    data_dir: Path | str | None = None,
    execv: Execv = os.execv,
    popen: Popen = subprocess.Popen,
) -> None:
    paths = ManagedPaths.from_root(data_dir) if data_dir is not None else ManagedPaths.discover()
    try:
        maybe_schedule_daily_update(paths, popen=popen)
    except Exception:
        pass
    command = get_managed_runtime_command(paths) or get_base_runtime_command()
    execv(command[0], command)
