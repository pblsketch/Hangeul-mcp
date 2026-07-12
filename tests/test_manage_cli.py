import json

from hangeul_mcp import __version__
from hangeul_mcp import manage
from hangeul_mcp.managed import ManagedPaths, save_current_state


def test_version_command_prints_package_version(capsys):
    assert manage.main(["version"]) == 0
    out = capsys.readouterr().out.strip()
    assert out == __version__


def test_setup_cli_forwards_options(monkeypatch, capsys):
    captured = {}

    def fake_run_setup(*, client, features, dry_run, yes):
        captured.update(
            client=client,
            features=features,
            dry_run=dry_run,
            yes=yes,
        )
        return {
            "status": "dry_run",
            "client": client,
            "changes": ["claude"],
        }

    monkeypatch.setattr(manage, "run_setup", fake_run_setup)

    assert (
        manage.main(
            [
                "setup",
                "--client",
                "claude",
                "--features",
                "com",
                "live",
                "--dry-run",
                "--yes",
            ]
        )
        == 0
    )
    assert captured == {
        "client": "claude",
        "features": ["com", "live"],
        "dry_run": True,
        "yes": True,
    }
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "dry_run"


def test_run_setup_persists_requested_features(tmp_path, monkeypatch):
    paths = ManagedPaths.from_root(tmp_path)
    monkeypatch.setattr(manage, "_managed_paths", lambda: paths)

    class FakeLauncher:
        managed = False

        def to_mapping(self):
            return {"command": "python", "args": []}

    monkeypatch.setattr(manage, "determine_launcher", lambda: FakeLauncher())
    monkeypatch.setattr(
        manage,
        "setup_client_config",
        lambda name, launcher, dry_run: {"client": name, "status": "configured", "changed": False},
    )

    result = manage.run_setup(client="codex", features=["live", "com"], dry_run=False, yes=False)

    assert result["requested_features"] == ["live", "com"]
    assert manage.load_config(paths)["features"] == ["live", "com"]

def test_update_check_json_uses_structured_output(monkeypatch, capsys):
    monkeypatch.setattr(
        manage,
        "run_update_check",
        lambda: {
            "status": "not_published",
            "channel": "stable",
            "installed_version": __version__,
        },
    )

    assert manage.main(["update", "--check", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "status": "not_published",
        "channel": "stable",
        "installed_version": __version__,
    }


def test_update_apply_json_uses_structured_output(monkeypatch, capsys):
    monkeypatch.setattr(
        manage,
        "run_update_apply",
        lambda: {
            "status": "updated",
            "from_version": "0.1.0",
            "to_version": "0.1.1",
        },
    )

    assert manage.main(["update"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "status": "updated",
        "from_version": "0.1.0",
        "to_version": "0.1.1",
    }

def test_update_config_cli_forwards_values(monkeypatch, capsys):
    captured = {}

    def fake_update_config(*, auto, channel):
        captured.update(auto=auto, channel=channel)
        return {"auto": auto, "channel": channel}

    monkeypatch.setattr(manage, "run_update_config", fake_update_config)

    assert (
        manage.main(["update-config", "--auto", "daily", "--channel", "beta"])
        == 0
    )
    assert captured == {"auto": "daily", "channel": "beta"}
    assert json.loads(capsys.readouterr().out) == captured


def test_rollback_cli_forwards_optional_target(monkeypatch, capsys):
    captured = {}

    def fake_rollback(*, target_version):
        captured["target_version"] = target_version
        return {"rolled_back_to": target_version or "previous"}

    monkeypatch.setattr(manage, "run_rollback", fake_rollback)

    assert manage.main(["rollback", "--to", "0.0.9"]) == 0
    assert captured == {"target_version": "0.0.9"}
    assert json.loads(capsys.readouterr().out) == {"rolled_back_to": "0.0.9"}


def test_uninstall_config_cli_forwards_client(monkeypatch, capsys):
    captured = {}

    def fake_uninstall(*, client, dry_run):
        captured.update(client=client, dry_run=dry_run)
        return {"client": client, "removed": True}

    monkeypatch.setattr(manage, "run_uninstall_config", fake_uninstall)

    assert manage.main(["uninstall-config", "--client", "codex"]) == 0
    assert captured == {"client": "codex", "dry_run": False}
    assert json.loads(capsys.readouterr().out) == {"client": "codex", "removed": True}


def test_run_update_apply_rejects_local_checkout_sources(tmp_path, monkeypatch):
    paths = ManagedPaths.from_root(tmp_path)
    paths.root_dir.mkdir(parents=True, exist_ok=True)
    save_current_state(
        paths,
        {"current_version": "source-current", "previous_version": None, "install_source": "local_checkout"},
    )
    monkeypatch.setattr(manage, "_managed_paths", lambda: paths)

    result = manage.run_update_apply()

    assert result == {
        "status": "unavailable",
        "reason": "unsupported_install_source",
        "install_source": "local_checkout",
    }


def test_run_update_apply_installs_latest_version(tmp_path, monkeypatch):
    paths = ManagedPaths.from_root(tmp_path)
    paths.root_dir.mkdir(parents=True, exist_ok=True)
    save_current_state(
        paths,
        {"current_version": "1.0.0", "previous_version": None, "install_source": "pypi"},
    )
    monkeypatch.setattr(manage, "_managed_paths", lambda: paths)
    monkeypatch.setattr(
        manage,
        "run_update_check",
        lambda: {
            "status": "update_available",
            "installed_version": "1.0.0",
            "latest_version": "1.1.0",
        },
    )
    monkeypatch.setattr(
        manage,
        "install_managed_version",
        lambda managed_paths, version, features=None: {
            "ok": True,
            "state": {"previous_version": "1.0.0"},
        },
    )

    result = manage.run_update_apply()

    assert result == {
        "status": "updated",
        "from_version": "1.0.0",
        "to_version": "1.1.0",
        "previous_version": "1.0.0",
        "current_path": str(paths.current_file),
        "checked_at": None,
        "latest_version": "1.1.0",
    }

def test_run_update_apply_preserves_configured_features(tmp_path, monkeypatch):
    paths = ManagedPaths.from_root(tmp_path)
    paths.root_dir.mkdir(parents=True, exist_ok=True)
    save_current_state(
        paths,
        {"current_version": "1.0.0", "previous_version": None, "install_source": "pypi"},
    )
    manage.save_config(paths, {"features": ["delegate", "render"]})
    monkeypatch.setattr(manage, "_managed_paths", lambda: paths)
    monkeypatch.setattr(
        manage,
        "run_update_check",
        lambda: {
            "status": "update_available",
            "installed_version": "1.0.0",
            "latest_version": "1.1.0",
        },
    )
    seen = {}

    def fake_install(managed_paths, version, features=None):
        seen["features"] = features
        return {"ok": True, "state": {"previous_version": "1.0.0"}}

    monkeypatch.setattr(manage, "install_managed_version", fake_install)

    manage.run_update_apply()

    assert seen["features"] == ["delegate", "render"]


def test_config_show_prints_structured_state(monkeypatch, capsys):
    monkeypatch.setattr(
        manage,
        "show_config",
        lambda: {"managed_root": "/tmp/hangeul", "update_policy": "notify"},
    )

    assert manage.main(["config", "show"]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "managed_root": "/tmp/hangeul",
        "update_policy": "notify",
    }