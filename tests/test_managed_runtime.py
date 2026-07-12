from __future__ import annotations

import stat
import sys
from pathlib import Path

import pytest

from hangeul_mcp import launcher, managed


@pytest.mark.parametrize(
    ("platform", "env", "expected_suffix"),
    [
        ("linux", {"XDG_DATA_HOME": "/tmp/xdg"}, Path("/tmp/xdg/hangeul-mcp")),
        (
            "darwin",
            {"HOME": "/Users/tester"},
            Path("/Users/tester/Library/Application Support/hangeul-mcp"),
        ),
        ("win32", {"APPDATA": "C:/Users/tester/AppData/Roaming"}, Path("C:/Users/tester/AppData/Roaming/hangeul-mcp")),
    ],
)
def test_user_data_dir_uses_platform_conventions(platform, env, expected_suffix):
    resolved = managed.get_user_data_dir(platform=platform, env=env)
    assert resolved == expected_suffix


def test_atomic_json_round_trip_and_permissions(tmp_path):
    target = tmp_path / "config.json"
    payload = {"channel": "stable", "enabled": True}

    managed.atomic_write_json(target, payload)

    assert managed.read_json_file(target) == payload
    mode = stat.S_IMODE(target.stat().st_mode)
    assert mode & 0o077 == 0


def test_update_lock_blocks_parallel_acquire(tmp_path):
    lock = managed.UpdateLock(tmp_path / "update.lock", poll_interval=0.01)
    second = managed.UpdateLock(tmp_path / "update.lock", poll_interval=0.01)

    with lock:
        with pytest.raises(TimeoutError):
            second.acquire(timeout=0.02)

    second.acquire(timeout=0.02)
    second.release()


def test_switch_and_rollback_restore_previous_version(tmp_path):
    paths = managed.ManagedPaths.from_root(tmp_path)
    managed.ensure_managed_dirs(paths)
    (paths.versions_dir / "1.0.0").mkdir(parents=True)
    (paths.versions_dir / "1.1.0").mkdir(parents=True)

    managed.switch_current_version(paths, "1.0.0")
    switched = managed.switch_current_version(paths, "1.1.0")

    assert switched["current_version"] == "1.1.0"
    assert switched["previous_version"] == "1.0.0"

    rolled_back = managed.rollback_current_version(paths)
    assert rolled_back["current_version"] == "1.0.0"
    assert rolled_back["previous_version"] == "1.1.0"


def test_current_state_preserves_install_source(tmp_path):
    paths = managed.ManagedPaths.from_root(tmp_path)
    managed.ensure_managed_dirs(paths)

    saved = managed.save_current_state(
        paths,
        {"current_version": "source-current", "previous_version": None, "install_source": "local_checkout"},
    )

    assert saved["install_source"] == "local_checkout"
    assert managed.load_current_state(paths)["install_source"] == "local_checkout"


def test_install_success_marks_pypi_install_source(tmp_path):
    paths = managed.ManagedPaths.from_root(tmp_path)
    managed.ensure_managed_dirs(paths)
    (paths.versions_dir / "1.0.0").mkdir(parents=True)
    managed.save_current_state(
        paths,
        {"current_version": "1.0.0", "previous_version": None, "install_source": "pypi"},
    )

    def fake_runner(argv, check, cwd=None, env=None, stdout=None, stderr=None):
        if argv[:3] == ["/usr/bin/python3", "-m", "venv"]:
            runtime_python = paths.version_python_path("1.1.0")
            runtime_python.parent.mkdir(parents=True, exist_ok=True)
            runtime_python.write_text("python", encoding="utf-8")
        return None

    outcome = managed.install_managed_version(
        paths,
        "1.1.0",
        runner=fake_runner,
        base_python="/usr/bin/python3",
        smoke_tester=lambda command: {"ok": True, "tool_count": 46},
    )

    assert outcome["ok"] is True
    state = managed.load_current_state(paths)
    assert state["current_version"] == "1.1.0"
    assert state["previous_version"] == "1.0.0"
    assert state["install_source"] == "pypi"

def test_install_success_runs_mcp_smoke_before_switch(tmp_path):
    paths = managed.ManagedPaths.from_root(tmp_path)
    managed.ensure_managed_dirs(paths)
    (paths.versions_dir / "1.0.0").mkdir(parents=True)
    managed.save_current_state(
        paths,
        {"current_version": "1.0.0", "previous_version": None, "install_source": "pypi"},
    )
    smoke_calls: list[list[str]] = []

    def fake_runner(argv, check, cwd=None, env=None, stdout=None, stderr=None):
        if argv[:3] == ["/usr/bin/python3", "-m", "venv"]:
            runtime_python = paths.version_python_path("1.1.0")
            runtime_python.parent.mkdir(parents=True, exist_ok=True)
            runtime_python.write_text("python", encoding="utf-8")
        return None

    def fake_smoke(command: list[str]) -> dict[str, object]:
        smoke_calls.append(list(command))
        return {"ok": True, "tool_count": 46}

    outcome = managed.install_managed_version(
        paths,
        "1.1.0",
        runner=fake_runner,
        base_python="/usr/bin/python3",
        smoke_tester=fake_smoke,
    )

    assert outcome["ok"] is True
    assert smoke_calls == [[str(paths.version_python_path("1.1.0")), "-m", "hangeul_mcp.server"]]

def test_install_failure_cleans_target_and_preserves_current(tmp_path):
    paths = managed.ManagedPaths.from_root(tmp_path)
    managed.ensure_managed_dirs(paths)
    current_dir = paths.versions_dir / "1.0.0"
    current_dir.mkdir(parents=True)
    managed.save_current_state(
        paths,
        {"current_version": "1.0.0", "previous_version": None},
    )

    calls: list[list[str]] = []

    def fake_runner(argv, check, cwd=None, env=None, stdout=None, stderr=None):
        calls.append(list(argv))
        runtime_python = paths.version_python_path("1.1.0")
        runtime_python.parent.mkdir(parents=True, exist_ok=True)
        runtime_python.write_text("python", encoding="utf-8")
        if argv[:4] == [str(runtime_python), "-m", "pip", "install"]:
            raise managed.RunnerError("install failed")
        return None

    outcome = managed.install_managed_version(
        paths,
        "1.1.0",
        runner=fake_runner,
        base_python="/usr/bin/python3",
    )

    assert outcome["ok"] is False
    assert outcome["stage"] == "install"
    assert managed.load_current_state(paths)["current_version"] == "1.0.0"
    assert not (paths.versions_dir / "1.1.0").exists()
    assert ["/usr/bin/python3", "-m", "venv", str(paths.versions_dir / "1.1.0")] in calls


def test_launcher_falls_back_to_base_server_when_no_managed_runtime(tmp_path, monkeypatch):
    paths = managed.ManagedPaths.from_root(tmp_path)
    managed.ensure_managed_dirs(paths)
    recorded: dict[str, object] = {}

    def fake_execv(executable, argv):
        recorded["executable"] = executable
        recorded["argv"] = list(argv)
        raise SystemExit(0)

    monkeypatch.setattr(sys, "executable", "/base/python")

    with pytest.raises(SystemExit):
        launcher.main(data_dir=paths.root_dir, execv=fake_execv)

    assert recorded == {
        "executable": "/base/python",
        "argv": ["/base/python", "-m", "hangeul_mcp.server"],
    }


def test_launcher_uses_managed_runtime_when_current_version_is_present(tmp_path):
    paths = managed.ManagedPaths.from_root(tmp_path)
    managed.ensure_managed_dirs(paths)
    managed_python = paths.version_python_path("1.2.0")
    managed_python.parent.mkdir(parents=True, exist_ok=True)
    managed_python.write_text("python", encoding="utf-8")
    managed.save_current_state(
        paths,
        {"current_version": "1.2.0", "previous_version": "1.1.0"},
    )
    recorded: dict[str, object] = {}

    def fake_execv(executable, argv):
        recorded["executable"] = executable
        recorded["argv"] = list(argv)
        raise SystemExit(0)

    with pytest.raises(SystemExit):
        launcher.main(data_dir=paths.root_dir, execv=fake_execv)

    assert recorded == {
        "executable": str(managed_python),
        "argv": [str(managed_python), "-m", "hangeul_mcp.server"],
    }

def test_launcher_schedules_daily_update_for_stale_pypi_install(tmp_path, monkeypatch):
    paths = managed.ManagedPaths.from_root(tmp_path)
    managed.ensure_managed_dirs(paths)
    managed.save_config(paths, {"auto": "daily", "channel": "stable", "last_checked_at": 1})
    managed.save_current_state(
        paths,
        {"current_version": "1.0.0", "previous_version": None, "install_source": "pypi"},
    )
    calls = {}

    def fake_popen(argv, cwd=None, stdout=None, stderr=None, close_fds=None):
        calls["argv"] = list(argv)
        calls["cwd"] = cwd
        return object()

    monkeypatch.setattr(launcher, "get_base_runtime_command", lambda: ["/base/python", "-m", "hangeul_mcp.server"])
    monkeypatch.setattr(launcher, "is_update_check_stale", lambda last_checked_at: True)

    result = launcher.maybe_schedule_daily_update(paths, popen=fake_popen)

    assert result["status"] == "scheduled"
    assert calls["argv"] == ["/base/python", "-m", "hangeul_mcp.manage", "update"]
    assert calls["cwd"] == str(paths.root_dir)


def test_launcher_schedules_notify_check_without_apply(tmp_path, monkeypatch):
    paths = managed.ManagedPaths.from_root(tmp_path)
    managed.ensure_managed_dirs(paths)
    managed.save_config(paths, {"auto": "notify", "channel": "stable", "last_checked_at": 1})
    managed.save_current_state(
        paths,
        {"current_version": "0.1.0", "previous_version": None, "install_source": "bootstrap"},
    )
    calls = {}

    def fake_popen(argv, cwd=None, stdout=None, stderr=None, close_fds=None):
        calls["argv"] = list(argv)
        return object()

    monkeypatch.setattr(launcher, "get_base_runtime_command", lambda: ["/base/python", "-m", "hangeul_mcp.server"])
    monkeypatch.setattr(launcher, "is_update_check_stale", lambda last_checked_at: True)

    result = launcher.maybe_schedule_daily_update(paths, popen=fake_popen)

    assert result["status"] == "scheduled"
    assert calls["argv"] == ["/base/python", "-m", "hangeul_mcp.manage", "update", "--check"]

def test_launcher_skips_daily_update_for_bootstrap_install(tmp_path, monkeypatch):
    paths = managed.ManagedPaths.from_root(tmp_path)
    managed.ensure_managed_dirs(paths)
    managed.save_config(paths, {"auto": "daily", "channel": "stable", "last_checked_at": 1})
    managed.save_current_state(
        paths,
        {"current_version": "0.1.0", "previous_version": None, "install_source": "bootstrap"},
    )
    calls = {}

    def fake_popen(argv, cwd=None, stdout=None, stderr=None, close_fds=None):
        calls["argv"] = list(argv)
        return object()

    monkeypatch.setattr(launcher, "get_base_runtime_command", lambda: ["/base/python", "-m", "hangeul_mcp.server"])
    monkeypatch.setattr(launcher, "is_update_check_stale", lambda last_checked_at: True)

    result = launcher.maybe_schedule_daily_update(paths, popen=fake_popen)

    assert result == {"status": "skipped", "reason": "unsupported_install_source"}
    assert calls == {}


def test_launcher_main_ignores_daily_update_failures(tmp_path):
    paths = managed.ManagedPaths.from_root(tmp_path)
    managed.ensure_managed_dirs(paths)
    managed.save_config(paths, {"auto": "daily", "channel": "stable", "last_checked_at": None})
    managed.save_current_state(
        paths,
        {"current_version": None, "previous_version": None, "install_source": "bootstrap"},
    )
    recorded = {}

    def fake_execv(executable, argv):
        recorded["executable"] = executable
        recorded["argv"] = list(argv)
        raise SystemExit(0)

    def bad_popen(*args, **kwargs):
        raise RuntimeError("spawn failed")

    with pytest.raises(SystemExit):
        launcher.main(data_dir=paths.root_dir, execv=fake_execv, popen=bad_popen)

    assert recorded["argv"][1:] == ["-m", "hangeul_mcp.server"]
def test_launcher_skips_daily_update_for_non_pypi_sources(tmp_path):
    paths = managed.ManagedPaths.from_root(tmp_path)
    managed.ensure_managed_dirs(paths)
    managed.save_config(paths, {"auto": "daily", "channel": "stable"})
    managed.save_current_state(
        paths,
        {"current_version": "source-current", "previous_version": None, "install_source": "local_checkout"},
    )

    result = launcher.maybe_schedule_daily_update(paths)

    assert result == {"status": "skipped", "reason": "unsupported_install_source"}
