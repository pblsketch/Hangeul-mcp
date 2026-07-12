from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

try:
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback
    tomllib = None


SERVER_NAME = "hangeul-mcp"


@dataclass(frozen=True)
class LauncherSpec:
    command: str
    args: list[str]
    managed: bool

    def to_mapping(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "args": list(self.args),
        }


class ConfigError(RuntimeError):
    pass


Validator = Callable[[Path], None]


def get_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def get_managed_root() -> Path:
    override = os.environ.get("HANGEUL_MCP_MANAGED_ROOT")
    if override:
        return Path(override).expanduser()
    try:
        from hangeul_mcp.managed import ManagedPaths
    except ImportError:
        if sys.platform == "win32":
            base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
            return base / "hangeul-mcp"
        if sys.platform == "darwin":
            return Path.home() / "Library" / "Application Support" / "hangeul-mcp"
        return Path(os.environ.get("XDG_STATE_HOME") or (Path.home() / ".local" / "state")) / "hangeul-mcp"
    return ManagedPaths.discover().root_dir


def managed_install_available() -> bool:
    launcher_spec = importlib.util.find_spec("hangeul_mcp.launcher")
    current_file = get_managed_root() / "current.json"
    return launcher_spec is not None and current_file.exists()


def determine_launcher() -> LauncherSpec:
    if managed_install_available():
        return LauncherSpec(
            command=sys.executable,
            args=["-m", "hangeul_mcp.launcher"],
            managed=True,
        )
    return LauncherSpec(
        command=sys.executable,
        args=["-m", "hangeul_mcp.server"],
        managed=False,
    )


def default_client_path(client: str) -> Path | None:
    if client == "claude":
        if sys.platform == "win32":
            base = os.environ.get("APPDATA")
            if not base:
                return None
            return Path(base) / "Claude" / "claude_desktop_config.json"
        if sys.platform == "darwin":
            return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
        return None
    if client == "codex":
        return Path.home() / ".codex" / "config.toml"
    if client == "antigravity":
        return Path.home() / ".gemini" / "config" / "mcp_config.json"
    raise ValueError(f"unsupported client: {client}")


def default_codex_project_path(*, cwd: Path | None = None) -> Path:
    base = cwd or Path.cwd()
    return base / ".codex" / "config.toml"


def default_antigravity_workspace_path(*, cwd: Path | None = None) -> Path:
    base = cwd or Path.cwd()
    return base / ".agents" / "mcp_config.json"


def default_antigravity_candidates(*, cwd: Path | None = None, include_missing_global: bool = False) -> list[Path]:
    candidates: list[Path] = []
    global_path = default_client_path("antigravity")
    if global_path is not None and (include_missing_global or global_path.exists()):
        candidates.append(global_path)
    workspace_path = default_antigravity_workspace_path(cwd=cwd)
    if workspace_path.exists():
        candidates.append(workspace_path)
    return candidates


def backup_path_for(path: Path) -> Path:
    return path.with_name(f"{path.name}.bak.{get_timestamp()}")


def best_effort_restrict_backup_permissions(path: Path) -> None:
    try:
        os.chmod(path, 0o600)
    except OSError:
        return


def create_backup(path: Path) -> Path | None:
    if not path.exists():
        return None
    backup = backup_path_for(path)
    shutil.copy2(path, backup)
    best_effort_restrict_backup_permissions(backup)
    return backup


def atomic_write_text(path: Path, content: str, validator: Validator) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    original_text = path.read_text(encoding="utf-8") if path.exists() else None
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(content, encoding="utf-8")
    os.replace(tmp_path, path)
    try:
        validator(path)
    except Exception:
        if original_text is None:
            if path.exists():
                path.unlink()
        else:
            restore = path.with_name(f".{path.name}.restore")
            restore.write_text(original_text, encoding="utf-8")
            os.replace(restore, path)
        raise
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def validate_json_config(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ConfigError("JSON config must contain an object")


def _json_root_for(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {}
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ConfigError("JSON config must contain an object")
    return data


def render_json_client_config(existing: dict[str, Any], launcher: LauncherSpec) -> dict[str, Any]:
    data = dict(existing)
    servers = data.get("mcpServers")
    if servers is None:
        servers = {}
    if not isinstance(servers, dict):
        raise ConfigError("mcpServers must be an object")
    servers = dict(servers)
    servers[SERVER_NAME] = launcher.to_mapping()
    data["mcpServers"] = servers
    return data


def render_json_client_uninstall(existing: dict[str, Any]) -> dict[str, Any]:
    data = dict(existing)
    servers = data.get("mcpServers")
    if not isinstance(servers, dict):
        return data
    if SERVER_NAME not in servers:
        return data
    servers = dict(servers)
    servers.pop(SERVER_NAME, None)
    data["mcpServers"] = servers
    return data


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _toml_array(values: Iterable[str]) -> str:
    return "[" + ", ".join(_toml_string(value) for value in values) + "]"


TARGET_CODEX_SECTION = f"mcp_servers.{SERVER_NAME}"


def _section_name(line: str) -> str | None:
    stripped = line.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        return stripped[1:-1].strip()
    return None


def _remove_toml_sections(text: str, section_name: str) -> tuple[str, int]:
    lines = text.splitlines()
    kept: list[str] = []
    removed = 0
    index = 0
    while index < len(lines):
        current_section = _section_name(lines[index])
        if current_section != section_name:
            kept.append(lines[index])
            index += 1
            continue
        removed += 1
        index += 1
        while index < len(lines) and _section_name(lines[index]) is None:
            index += 1
        while kept and kept[-1] == "" and index < len(lines) and lines[index] == "":
            kept.pop()
    rendered = "\n".join(kept)
    if text.endswith("\n"):
        rendered += "\n"
    return rendered, removed


def render_codex_config_text(existing: str, launcher: LauncherSpec) -> str:
    trimmed, _ = _remove_toml_sections(existing, TARGET_CODEX_SECTION)
    parts: list[str] = []
    prefix = trimmed.rstrip("\n")
    block = "\n".join(
        [
            f"[{TARGET_CODEX_SECTION}]",
            f"command = {_toml_string(launcher.command)}",
            f"args = {_toml_array(launcher.args)}",
        ]
    )
    if prefix.strip():
        parts.extend([prefix, "", block])
    else:
        parts.append(block)
    return "\n".join(parts).rstrip() + "\n"


def render_codex_uninstall_text(existing: str) -> str:
    trimmed, _ = _remove_toml_sections(existing, TARGET_CODEX_SECTION)
    return trimmed.rstrip() + ("\n" if trimmed.strip() else "")


def validate_codex_config(path: Path) -> None:
    if tomllib is None:
        return
    tomllib.loads(path.read_text(encoding="utf-8"))


def _load_codex_command_fallback(text: str) -> dict[str, Any] | None:
    in_target = False
    values: dict[str, Any] = {}
    for line in text.splitlines():
        section = _section_name(line)
        if section is not None:
            in_target = section == TARGET_CODEX_SECTION
            continue
        if not in_target or "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        key = key.strip()
        raw_value = raw_value.strip()
        if key == "command":
            values["command"] = json.loads(raw_value)
        elif key == "args":
            values["args"] = list(json.loads(raw_value))
    if "command" not in values:
        return None
    values.setdefault("args", [])
    return values


def _json_changed(before: dict[str, Any], after: dict[str, Any]) -> bool:
    return json.dumps(before, sort_keys=True, ensure_ascii=False) != json.dumps(
        after,
        sort_keys=True,
        ensure_ascii=False,
    )


def _write_json_config(path: Path, before: dict[str, Any], after: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    changed = _json_changed(before, after)
    result = {
        "path": str(path),
        "changed": changed,
        "dry_run": dry_run,
        "backup": None,
    }
    if not changed or dry_run:
        return result
    backup = create_backup(path)
    atomic_write_text(
        path,
        json.dumps(after, ensure_ascii=False, indent=2) + "\n",
        validator=validate_json_config,
    )
    result["backup"] = str(backup) if backup else None
    return result


def _write_codex_config(path: Path, rendered: str, dry_run: bool, changed: bool) -> dict[str, Any]:
    result = {
        "path": str(path),
        "changed": changed,
        "dry_run": dry_run,
        "backup": None,
    }
    if not changed or dry_run:
        return result
    backup = create_backup(path)
    atomic_write_text(path, rendered, validator=validate_codex_config)
    result["backup"] = str(backup) if backup else None
    return result


def _antigravity_snippet(launcher: LauncherSpec) -> dict[str, Any]:
    return {
        "mcpServers": {
            SERVER_NAME: launcher.to_mapping(),
        }
    }


def _manual_client_result(
    client: str,
    *,
    dry_run: bool,
    reason: str,
    launcher: LauncherSpec | None = None,
    status: str = "needs_manual_path",
    paths: list[Path] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "client": client,
        "status": status,
        "reason": reason,
        "changed": False,
        "dry_run": dry_run,
    }
    if launcher is not None:
        if client == "antigravity":
            result["snippet"] = _antigravity_snippet(launcher)
        elif client == "codex":
            result["snippet_toml"] = render_codex_config_text("", launcher)
        else:
            result["snippet"] = launcher.to_mapping()
    if paths is not None:
        result["paths"] = [str(item) for item in paths]
    return result


def _resolve_antigravity_target(
    *,
    launcher: LauncherSpec,
    dry_run: bool,
    path: Path | None,
    candidate_paths: list[Path] | None,
) -> tuple[Path | None, dict[str, Any] | None]:
    global_path = default_client_path("antigravity")
    workspace_path = default_antigravity_workspace_path()
    if global_path is None:
        return None, _manual_client_result(
            "antigravity",
            dry_run=dry_run,
            reason="unsupported_platform",
            launcher=launcher,
            status="unsupported_platform",
        )
    if path is not None:
        if path == global_path and not workspace_path.exists():
            return path, None
        return None, _manual_client_result(
            "antigravity",
            dry_run=dry_run,
            reason="unsupported_path_override",
            launcher=launcher,
            status="needs_manual_scope",
            paths=[global_path, workspace_path],
        )
    if candidate_paths is not None:
        if len(candidate_paths) != 1:
            reason = "missing" if not candidate_paths else "ambiguous"
            return None, _manual_client_result(
                "antigravity",
                dry_run=dry_run,
                reason=reason,
                launcher=launcher,
                paths=list(candidate_paths),
            )
        if candidate_paths[0] == global_path and not workspace_path.exists():
            return candidate_paths[0], None
        return None, _manual_client_result(
            "antigravity",
            dry_run=dry_run,
            reason="unsupported_path_override",
            launcher=launcher,
            status="needs_manual_scope",
            paths=[global_path, workspace_path],
        )
    if workspace_path.exists():
        return None, _manual_client_result(
            "antigravity",
            dry_run=dry_run,
            reason="workspace_scope_present",
            launcher=launcher,
            status="needs_manual_scope",
            paths=[global_path, workspace_path],
        )
    return global_path, None

def _resolve_codex_target(
    *,
    launcher: LauncherSpec,
    dry_run: bool,
    path: Path | None,
) -> tuple[Path | None, dict[str, Any] | None]:
    if path is not None:
        return path, None
    global_path = default_client_path("codex")
    if global_path is None:
        return None, _manual_client_result(
            "codex",
            dry_run=dry_run,
            reason="missing_global_config_path",
            launcher=launcher,
        )
    project_path = default_codex_project_path()
    if project_path.exists():
        return None, _manual_client_result(
            "codex",
            dry_run=dry_run,
            reason="project_scope_present",
            launcher=launcher,
            status="needs_manual_scope",
            paths=[global_path, project_path],
        )
    return global_path, None


def _setup_client_config_with_targets(
    client: str,
    *,
    launcher: LauncherSpec | None = None,
    dry_run: bool = False,
    path: Path | None = None,
    candidate_paths: list[Path] | None = None,
) -> dict[str, Any]:
    launcher = launcher or determine_launcher()
    if client == "claude":
        target = path or default_client_path(client)
        if target is None:
            return _manual_client_result(
                client,
                dry_run=dry_run,
                reason="unsupported_platform",
                status="unsupported_platform",
            )
        before = _json_root_for(target)
        after = render_json_client_config(before, launcher)
        result = _write_json_config(target, before, after, dry_run)
        result["client"] = client
        result["status"] = "configured" if result["changed"] else "unchanged"
        return result
    if client == "codex":
        target, manual = _resolve_codex_target(
            launcher=launcher,
            dry_run=dry_run,
            path=path,
        )
        if manual is not None:
            return manual
        before = target.read_text(encoding="utf-8") if target.exists() else ""
        after = render_codex_config_text(before, launcher)
        result = _write_codex_config(target, after, dry_run, before != after)
        result["client"] = client
        result["status"] = "configured" if result["changed"] else "unchanged"
        return result
    if client == "antigravity":
        target, manual = _resolve_antigravity_target(
            launcher=launcher,
            dry_run=dry_run,
            path=path,
            candidate_paths=candidate_paths,
        )
        if manual is not None:
            return manual
        before = _json_root_for(target)
        after = render_json_client_config(before, launcher)
        result = _write_json_config(target, before, after, dry_run)
        result["client"] = client
        result["status"] = "configured" if result["changed"] else "unchanged"
        return result
    raise ValueError(f"unsupported client: {client}")


def setup_client_config(
    client: str,
    *,
    launcher: LauncherSpec | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    return _setup_client_config_with_targets(
        client,
        launcher=launcher,
        dry_run=dry_run,
    )


def _uninstall_client_config_with_targets(
    client: str,
    *,
    dry_run: bool = False,
    path: Path | None = None,
    candidate_paths: list[Path] | None = None,
) -> dict[str, Any]:
    if client == "claude":
        target = path or default_client_path(client)
        if target is None:
            return _manual_client_result(
                client,
                dry_run=dry_run,
                reason="unsupported_platform",
                status="unsupported_platform",
            )
        before = _json_root_for(target)
        after = render_json_client_uninstall(before)
        result = _write_json_config(target, before, after, dry_run)
        result["client"] = client
        result["status"] = "removed" if result["changed"] else "unchanged"
        return result
    if client == "codex":
        target, manual = _resolve_codex_target(
            launcher=determine_launcher(),
            dry_run=dry_run,
            path=path,
        )
        if manual is not None:
            return manual
        before = target.read_text(encoding="utf-8") if target.exists() else ""
        after = render_codex_uninstall_text(before)
        result = _write_codex_config(target, after, dry_run, before != after)
        result["client"] = client
        result["status"] = "removed" if result["changed"] else "unchanged"
        return result
    if client == "antigravity":
        target, manual = _resolve_antigravity_target(
            launcher=determine_launcher(),
            dry_run=dry_run,
            path=path,
            candidate_paths=candidate_paths,
        )
        if manual is not None:
            return manual
        before = _json_root_for(target)
        after = render_json_client_uninstall(before)
        result = _write_json_config(target, before, after, dry_run)
        result["client"] = client
        result["status"] = "removed" if result["changed"] else "unchanged"
        return result
    raise ValueError(f"unsupported client: {client}")


def uninstall_client_config(
    client: str,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    return _uninstall_client_config_with_targets(
        client,
        dry_run=dry_run,
    )


def load_registered_client_command(client: str, path: Path | None = None) -> dict[str, Any] | None:
    if client == "codex":
        target = path or default_client_path(client)
        if target is None or not target.exists():
            return None
        text = target.read_text(encoding="utf-8")
        if tomllib is not None:
            try:
                data = tomllib.loads(text)
            except Exception:
                return _load_codex_command_fallback(text)
            servers = data.get("mcp_servers")
            if not isinstance(servers, dict):
                return None
            server = servers.get(SERVER_NAME)
            if not isinstance(server, dict):
                return None
            return {
                "command": server.get("command"),
                "args": list(server.get("args") or []),
            }
        return _load_codex_command_fallback(text)
    target = path or default_client_path(client)
    if target is None or not target.exists():
        return None
    try:
        data = _json_root_for(target)
    except Exception:
        return None
    servers = data.get("mcpServers")
    if not isinstance(servers, dict):
        return None
    server = servers.get(SERVER_NAME)
    if not isinstance(server, dict):
        return None
    return {
        "command": server.get("command"),
        "args": list(server.get("args") or []),
    }


def command_exists(command: str | None) -> bool:
    if not command:
        return False
    if os.path.isabs(command):
        return Path(command).exists()
    return shutil.which(command) is not None
