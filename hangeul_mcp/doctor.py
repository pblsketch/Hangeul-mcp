from __future__ import annotations

import asyncio
import importlib
import importlib.util
import platform
import sys
from pathlib import Path
from typing import Any

from hangeul_core.hwp_headless import headless_status
from hangeul_mcp import __version__
from hangeul_mcp.client_config import (
    command_exists,
    default_antigravity_workspace_path,
    default_client_path,
    default_codex_project_path,
    determine_launcher,
    load_registered_client_command,
)

REQUIRED_TOOLS = [
    "detect_format",
    "analyze_form",
    "fill_form",
    "resolve_current_hwp_document",
]

OPTIONAL_EXTRA_MODULES = {
    "com": ["win32com.client"],
    "delegate": ["hwpx"],
    "render": ["playwright"],
    "live": ["pyhwpx"],
    "hwp-headless": [],
}



def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False

def collect_optional_extras_status() -> dict[str, Any]:
    status: dict[str, Any] = {}
    for extra, modules in OPTIONAL_EXTRA_MODULES.items():
        if extra == "hwp-headless":
            gate = headless_status()
            status[extra] = {
                "available": False,
                "status": "unsupported",
                "checked": gate["checked"],
                "modules": {},
                "note": "headless .hwp extraction adapter is not selected yet",
            }
            continue
        if not modules:
            status[extra] = {"available": True, "modules": {}}
            continue
        module_status = {
            module: {"available": _module_available(module)}
            for module in modules
        }
        status[extra] = {
            "available": all(item["available"] for item in module_status.values()),
            "modules": module_status,
        }
    return status


def collect_windows_live_status() -> dict[str, Any]:
    if sys.platform != "win32":
        return {"status": "not_applicable", "reason": "non_windows"}
    com_available = _module_available("win32com.client")
    pyhwpx_available = _module_available("pyhwpx")
    return {
        "status": "ok" if com_available and pyhwpx_available else "degraded",
        "com": {"available": com_available},
        "pyhwpx": {"available": pyhwpx_available},
    }


def _surface_command(client: str, path: Path) -> dict[str, Any] | None:
    registered = load_registered_client_command(client, path=path)
    if registered is None:
        return None
    command = registered.get("command")
    args = list(registered.get("args") or [])
    return {
        "command": command,
        "args": args,
        "exists": command_exists(command),
        "managed": args == ["-m", "hangeul_mcp.launcher"],
    }



def _surface_status(*, client: str, name: str, path: Path, mode: str) -> dict[str, Any]:
    command = _surface_command(client, path) if path.exists() else None
    return {
        "name": name,
        "mode": mode,
        "path": str(path),
        "exists": path.exists(),
        "registered": command is not None,
        "command": command,
    }



def _primary_command(surfaces: list[dict[str, Any]]) -> dict[str, Any]:
    for surface in surfaces:
        if surface.get("registered") and surface.get("command"):
            return dict(surface["command"])
    return {"exists": False, "managed": False}



def collect_client_statuses() -> dict[str, Any]:
    statuses: dict[str, Any] = {}

    claude_surfaces: list[dict[str, Any]] = []
    claude_path = default_client_path("claude")
    if claude_path is not None:
        claude_surfaces.append(
            _surface_status(client="claude", name="desktop", path=claude_path, mode="auto_managed")
        )
    statuses["claude"] = {
        "support": "auto_managed" if claude_surfaces else "unsupported",
        "detected": any(surface["exists"] for surface in claude_surfaces),
        "path": claude_surfaces[0]["path"] if claude_surfaces else None,
        "candidate_count": len(claude_surfaces),
        "registered": any(surface["registered"] for surface in claude_surfaces),
        "command": _primary_command(claude_surfaces),
        "surfaces": claude_surfaces,
        "restart_required": True,
        "manual_commands": ["Restart Claude Desktop after editing the config."],
    }

    codex_global = default_client_path("codex")
    codex_project = default_codex_project_path()
    codex_project_exists = codex_project.exists()
    codex_surfaces = [
        _surface_status(client="codex", name="global", path=codex_global, mode="auto_managed"),
        _surface_status(client="codex", name="project", path=codex_project, mode="manual_only"),
    ]
    statuses["codex"] = {
        "support": "auto_and_manual",
        "status": "needs_manual_scope" if codex_project_exists else "auto_ready",
        "detected": any(surface["exists"] for surface in codex_surfaces),
        "path": None if codex_project_exists else str(codex_global),
        "candidate_count": len(codex_surfaces),
        "registered": any(surface["registered"] for surface in codex_surfaces),
        "command": _primary_command(codex_surfaces),
        "surfaces": codex_surfaces,
        "manual_commands": [
            "codex mcp list",
            "codex mcp get hangeul-mcp",
            "codex mcp add hangeul-mcp -- <command> [args...]",
            "codex mcp remove hangeul-mcp",
        ],
    }

    antigravity_global = default_client_path("antigravity")
    antigravity_workspace = default_antigravity_workspace_path()
    antigravity_workspace_exists = antigravity_workspace.exists()
    antigravity_surfaces = [
        _surface_status(client="antigravity", name="global", path=antigravity_global, mode="auto_managed"),
        _surface_status(client="antigravity", name="workspace", path=antigravity_workspace, mode="manual_only"),
    ]
    statuses["antigravity"] = {
        "support": "auto_and_manual",
        "status": "needs_manual_scope" if antigravity_workspace_exists else "auto_ready",
        "detected": any(surface["exists"] for surface in antigravity_surfaces),
        "path": None if antigravity_workspace_exists else str(antigravity_global),
        "candidate_count": len(antigravity_surfaces),
        "registered": any(surface["registered"] for surface in antigravity_surfaces),
        "command": _primary_command(antigravity_surfaces),
        "surfaces": antigravity_surfaces,
        "manual_commands": [
            "Use Settings > Customizations > Installed MCP Servers in Antigravity 2.0.",
            "Use /mcp in Antigravity CLI.",
        ],
    }
    return statuses


def _check_required_tools(tool_names: set[str]) -> dict[str, bool]:
    return {name: name in tool_names for name in REQUIRED_TOOLS}



def selected_runtime() -> dict[str, Any]:
    try:
        from hangeul_mcp.managed import ManagedPaths, get_base_runtime_command, get_managed_runtime_command, load_current_state

        paths = ManagedPaths.discover()
        state = load_current_state(paths)
        managed_command = get_managed_runtime_command(paths)
        command = managed_command or get_base_runtime_command()
        install_source = state.get("install_source") if managed_command is not None else None
        managed_source = install_source in {"pypi", "bootstrap"}
        package_version = state.get("current_version") if managed_source and state.get("current_version") else __version__
        return {
            "command": command,
            "python_executable": command[0],
            "package_version": package_version,
            "install_source": install_source,
            "current_version": state.get("current_version") if managed_command is not None else None,
        }
    except Exception:
        return {
            "command": [sys.executable, "-m", "hangeul_mcp.server"],
            "python_executable": sys.executable,
            "package_version": __version__,
            "install_source": None,
            "current_version": None,
        }



def run_mcp_smoke_test(timeout: float = 10.0) -> dict[str, Any]:
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except Exception as exc:
        return {
            "status": "error",
            "initialized": False,
            "tool_count": 0,
            "required_tools": _check_required_tools(set()),
            "error": {"kind": "import", "message": str(exc)},
        }

    launcher = determine_launcher()

    async def run() -> dict[str, Any]:
        params = StdioServerParameters(command=launcher.command, args=launcher.args)
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                listed = await session.list_tools()
                names = {tool.name for tool in listed.tools}
                return {
                    "status": "ok",
                    "initialized": True,
                    "tool_count": len(names),
                    "required_tools": _check_required_tools(names),
                }

    try:
        return asyncio.run(asyncio.wait_for(run(), timeout=timeout))
    except asyncio.TimeoutError:
        return {
            "status": "error",
            "initialized": False,
            "tool_count": 0,
            "required_tools": _check_required_tools(set()),
            "error": {"kind": "timeout", "message": "MCP smoke test timed out"},
        }
    except Exception as exc:
        return {
            "status": "error",
            "initialized": False,
            "tool_count": 0,
            "required_tools": _check_required_tools(set()),
            "error": {"kind": "runtime", "message": str(exc)},
        }


def _parse_version(value: str) -> tuple[tuple[int, ...], int, int]:
    base = value
    prerelease_rank = 3
    prerelease_number = 0
    for marker, rank in (("a", 0), ("b", 1), ("rc", 2)):
        if marker in value:
            base, suffix = value.split(marker, 1)
            prerelease_rank = rank
            digits = "".join(ch for ch in suffix if ch.isdigit())
            prerelease_number = int(digits or "0")
            break
    parts = tuple(int(part) for part in base.split(".") if part.isdigit())
    return parts, prerelease_rank, prerelease_number


def _select_latest_release(releases: list[str], channel: str) -> str | None:
    allowed = []
    for release in releases:
        lowered = release.lower()
        prerelease = any(token in lowered for token in ("a", "b", "rc"))
        if prerelease and channel != "beta":
            continue
        allowed.append(release)
    if not allowed:
        return None
    return sorted(allowed, key=_parse_version)[-1]


def check_for_updates(channel: str = "stable", timeout: float = 3.0) -> dict[str, Any]:
    from hangeul_mcp.managed import check_for_updates as managed_check_for_updates

    runtime = selected_runtime()
    installed_version = runtime["package_version"]
    result = managed_check_for_updates(
        installed_version,
        include_prerelease=(channel == "beta"),
    )
    result["channel"] = channel
    result["installed_version"] = installed_version
    result["install_source"] = runtime["install_source"]
    if "ok" in result:
        error_kind = result.pop("error", "network")
        status_code = result.pop("status", None)
        result.pop("ok", None)
        result["status"] = "error"
        result["error"] = {
            "kind": error_kind,
            "message": str(status_code) if status_code is not None else "update check failed",
        }
    return result


def gather_doctor_report() -> dict[str, Any]:
    try:
        importlib.import_module("hangeul_core")
        core_import = {"ok": True}
    except Exception as exc:
        core_import = {"ok": False, "error": str(exc)}
    try:
        from hangeul_mcp.managed import ManagedPaths, load_config

        update_channel = load_config(ManagedPaths.discover()).get("channel", "stable")
    except Exception:
        update_channel = "stable"
    runtime = selected_runtime()
    return {
        "package": {
            "name": "hangeul-mcp",
            "version": runtime["package_version"],
        },
        "python": {
            "version": sys.version.split()[0],
            "executable": runtime["python_executable"],
            "host_executable": sys.executable,
        },
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
        },
        "managed_runtime": {
            "install_source": runtime["install_source"],
            "current_version": runtime["current_version"],
            "command": runtime["command"],
        },
        "core_import": core_import,
        "optional_extras": collect_optional_extras_status(),
        "windows_live": collect_windows_live_status(),
        "clients": collect_client_statuses(),
        "mcp_smoke": run_mcp_smoke_test(),
        "updates": check_for_updates(channel=update_channel),
    }


def format_doctor_text(report: dict[str, Any]) -> str:
    lines = [
        f"package: {report['package']['name']} {report['package']['version']}",
        f"python: {report['python']['version']} ({report['python']['executable']})",
        f"platform: {report['platform']['system']} {report['platform']['release']}",
        f"core import: {'ok' if report['core_import'].get('ok') else 'error'}",
        f"updates: {report['updates'].get('status')}",
        f"mcp smoke: {report['mcp_smoke'].get('status')} ({report['mcp_smoke'].get('tool_count', 0)} tools)",
    ]
    for client, data in report["clients"].items():
        support = data.get("support", "unknown")
        state = "registered" if data.get("registered") else "unregistered"
        lines.append(f"client:{client}: {state} ({support})")
    return "\n".join(lines)
