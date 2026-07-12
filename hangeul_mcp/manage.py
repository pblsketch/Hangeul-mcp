from __future__ import annotations

import argparse
import json
from typing import Any

from hangeul_mcp import __version__
from hangeul_mcp.client_config import determine_launcher, setup_client_config, uninstall_client_config
from hangeul_mcp.doctor import format_doctor_text, gather_doctor_report
from hangeul_mcp.managed import (
    ManagedPaths,
    UpdateLock,
    check_for_updates as managed_check_for_updates,
    install_managed_version,
    load_config,
    load_current_state,
    rollback_current_version,
    save_config,
    switch_current_version,
)


CLIENT_CHOICES = ("claude", "codex", "antigravity", "all")
AUTO_CHOICES = ("notify", "daily", "off")
CHANNEL_CHOICES = ("stable", "beta")


def _managed_paths() -> ManagedPaths:
    return ManagedPaths.discover()


def _selected_clients(client: str) -> list[str]:
    if client == "all":
        return ["claude", "codex", "antigravity"]
    return [client]

def current_reported_version() -> str:
    from hangeul_mcp.managed import get_managed_runtime_command

    paths = _managed_paths()
    current = load_current_state(paths)
    managed_command = get_managed_runtime_command(paths)
    if managed_command is not None and current.get("install_source") in {"pypi", "bootstrap"} and current.get("current_version"):
        return str(current["current_version"])
    return __version__


def run_setup(*, client: str, features: list[str], dry_run: bool, yes: bool) -> dict[str, Any]:
    launcher = determine_launcher()
    results = [
        setup_client_config(name, launcher=launcher, dry_run=dry_run)
        for name in _selected_clients(client)
    ]
    manual_needed = any(item.get("status") not in {"configured", "unchanged"} for item in results)
    return {
        "status": "dry_run" if dry_run else ("needs_manual_steps" if manual_needed else "ok"),
        "client": client,
        "requested_features": list(features),
        "launcher": launcher.to_mapping(),
        "managed": launcher.managed,
        "non_interactive": yes,
        "results": results,
        "changes": [item["client"] for item in results if item.get("changed")],
        "needs_manual_clients": [item["client"] for item in results if item.get("status") not in {"configured", "unchanged"}],
    }


def run_uninstall_config(*, client: str, dry_run: bool) -> dict[str, Any]:
    results = [uninstall_client_config(name, dry_run=dry_run) for name in _selected_clients(client)]
    return {
        "client": client,
        "dry_run": dry_run,
        "results": results,
        "removed": any(item.get("changed") for item in results),
    }


def show_config() -> dict[str, Any]:
    paths = _managed_paths()
    config = load_config(paths)
    current = load_current_state(paths)
    return {
        "managed_root": str(paths.root_dir),
        "config_path": str(paths.config_file),
        "current_path": str(paths.current_file),
        "update_policy": config.get("auto", "notify"),
        "channel": config.get("channel", "stable"),
        "current": current,
    }


def run_update_config(*, auto: str, channel: str) -> dict[str, Any]:
    paths = _managed_paths()
    data = load_config(paths)
    data["auto"] = auto
    data["channel"] = channel
    save_config(paths, data)
    return {
        "config_path": str(paths.config_file),
        "auto": auto,
        "channel": channel,
    }


def run_rollback(*, target_version: str | None) -> dict[str, Any]:
    paths = _managed_paths()
    current = load_current_state(paths)
    if not current.get("current_version"):
        return {
            "status": "unavailable",
            "reason": "managed_install_not_found",
        }
    try:
        state = (
            switch_current_version(paths, target_version)
            if target_version is not None
            else rollback_current_version(paths)
        )
    except FileNotFoundError:
        return {
            "status": "error",
            "reason": "version_not_found",
            "requested_version": target_version or current.get("previous_version"),
        }
    except RuntimeError:
        return {
            "status": "unavailable",
            "reason": "no_previous_version",
        }
    return {
        "status": "ok",
        "rolled_back_to": state.get("current_version"),
        "previous_version": state.get("previous_version"),
        "current_path": str(paths.current_file),
    }


def _record_update_result(paths: ManagedPaths, result: dict[str, Any]) -> dict[str, Any]:
    config = load_config(paths)
    config["last_checked_at"] = result.get("checked_at") or config.get("last_checked_at")
    config["last_status"] = result.get("status")
    config["last_error"] = result.get("error") if result.get("status") == "error" else None
    if result.get("latest_version"):
        config["latest_version"] = result.get("latest_version")
    save_config(paths, config)
    return result


def run_update_check() -> dict[str, Any]:
    paths = _managed_paths()
    config = load_config(paths)
    current = load_current_state(paths)
    channel = config.get("channel", "stable")
    include_prerelease = channel == "beta"
    managed_source = current.get("install_source") in {"pypi", "bootstrap"}
    installed_version = current.get("current_version") if managed_source and current.get("current_version") else __version__
    result = managed_check_for_updates(installed_version, include_prerelease=include_prerelease)
    result["channel"] = channel
    result["installed_version"] = installed_version
    result["install_source"] = current.get("install_source")
    return _record_update_result(paths, result)


def run_update_apply() -> dict[str, Any]:
    paths = _managed_paths()
    current = load_current_state(paths)
    install_source = current.get("install_source")
    if install_source != "pypi":
        return {
            "status": "unavailable",
            "reason": "unsupported_install_source",
            "install_source": install_source,
        }
    try:
        with UpdateLock(paths.lock_file):
            check = run_update_check()
            if check.get("status") != "update_available":
                return check
            latest_version = check.get("latest_version")
            outcome = install_managed_version(paths, latest_version)
    except TimeoutError:
        return _record_update_result(
            paths,
            {
                "status": "error",
                "reason": "update_lock_timeout",
            },
        )
    if not outcome.get("ok"):
        return _record_update_result(
            paths,
            {
                "status": "error",
                "reason": outcome.get("stage"),
                "error": outcome.get("error"),
                "requested_version": latest_version,
                "checked_at": check.get("checked_at"),
            },
        )
    return _record_update_result(
        paths,
        {
            "status": "updated",
            "from_version": check.get("installed_version"),
            "to_version": latest_version,
            "previous_version": outcome["state"].get("previous_version"),
            "current_path": str(paths.current_file),
            "checked_at": check.get("checked_at"),
            "latest_version": latest_version,
        },
    )


def run_doctor(as_json: bool) -> dict[str, Any] | str:
    report = gather_doctor_report()
    if as_json:
        return report
    return format_doctor_text(report)


def _print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hangeul-mcp-manage")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor")
    doctor.add_argument("--json", action="store_true")

    setup = subparsers.add_parser("setup")
    setup.add_argument("--client", choices=CLIENT_CHOICES, required=True)
    setup.add_argument("--features", nargs="*", default=[])
    setup.add_argument("--dry-run", action="store_true")
    setup.add_argument("--yes", action="store_true")

    config = subparsers.add_parser("config")
    config_subparsers = config.add_subparsers(dest="config_command", required=True)
    config_subparsers.add_parser("show")

    subparsers.add_parser("version")

    update = subparsers.add_parser("update")
    update.add_argument("--check", action="store_true")
    update.add_argument("--json", action="store_true")

    update_config = subparsers.add_parser("update-config")
    update_config.add_argument("--auto", choices=AUTO_CHOICES, required=True)
    update_config.add_argument("--channel", choices=CHANNEL_CHOICES, required=True)

    rollback = subparsers.add_parser("rollback")
    rollback.add_argument("--to")

    uninstall = subparsers.add_parser("uninstall-config")
    uninstall.add_argument("--client", choices=CLIENT_CHOICES, required=True)
    uninstall.add_argument("--dry-run", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "version":
        print(current_reported_version())
        return 0
    if args.command == "doctor":
        result = run_doctor(args.json)
        if args.json:
            _print_json(result)
        else:
            print(result)
        return 0
    if args.command == "setup":
        _print_json(
            run_setup(
                client=args.client,
                features=list(args.features),
                dry_run=args.dry_run,
                yes=args.yes,
            )
        )
        return 0
    if args.command == "config" and args.config_command == "show":
        _print_json(show_config())
        return 0
    if args.command == "update":
        result = run_update_check() if args.check else run_update_apply()
        _print_json(result)
        return 0
    if args.command == "update-config":
        _print_json(run_update_config(auto=args.auto, channel=args.channel))
        return 0
    if args.command == "rollback":
        _print_json(run_rollback(target_version=args.to))
        return 0
    if args.command == "uninstall-config":
        _print_json(run_uninstall_config(client=args.client, dry_run=args.dry_run))
        return 0
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
