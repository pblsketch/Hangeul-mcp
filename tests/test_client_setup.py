import json
import stat
import sys
from pathlib import Path


from hangeul_mcp import client_config


def test_claude_setup_dry_run_then_idempotent_apply(tmp_path, monkeypatch):
    config_path = tmp_path / "유저 Space" / "claude_desktop_config.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        json.dumps({"theme": "dark", "mcpServers": {"other": {"command": "x"}}}),
        encoding="utf-8",
    )
    launcher = client_config.LauncherSpec(
        command=str(tmp_path / "파이썬 Space" / "python.exe"),
        args=["-m", "hangeul_mcp.server"],
        managed=False,
    )
    monkeypatch.setattr(
        client_config,
        "get_timestamp",
        lambda: "20260712T123456Z",
    )

    preview = client_config._setup_client_config_with_targets(
        "claude",
        launcher=launcher,
        dry_run=True,
        path=config_path,
    )
    assert preview["changed"] is True
    assert preview["dry_run"] is True
    assert not list(config_path.parent.glob("*.bak.*"))

    applied = client_config._setup_client_config_with_targets(
        "claude",
        launcher=launcher,
        dry_run=False,
        path=config_path,
    )
    assert applied["changed"] is True
    backup = config_path.with_name("claude_desktop_config.json.bak.20260712T123456Z")
    assert backup.exists()
    assert stat.S_IMODE(backup.stat().st_mode) & 0o077 == 0

    data = json.loads(config_path.read_text(encoding="utf-8"))
    assert data["theme"] == "dark"
    assert data["mcpServers"]["other"] == {"command": "x"}
    assert data["mcpServers"]["hangeul-mcp"] == {
        "command": launcher.command,
        "args": launcher.args,
    }

    second = client_config._setup_client_config_with_targets(
        "claude",
        launcher=launcher,
        dry_run=False,
        path=config_path,
    )
    assert second["changed"] is False
    assert len(list(config_path.parent.glob("*.bak.*"))) == 1



def test_atomic_write_restores_original_on_validation_failure(tmp_path):
    path = tmp_path / "broken.json"
    original = '{"keep": true}\n'
    path.write_text(original, encoding="utf-8")

    def bad_validator(_: Path):
        raise ValueError("boom")

    try:
        client_config.atomic_write_text(path, '{"keep": false}\n', validator=bad_validator)
    except ValueError:
        pass
    else:
        raise AssertionError("expected validator failure")

    assert path.read_text(encoding="utf-8") == original


def test_codex_section_editor_replaces_duplicates_and_preserves_comments():
    original = """# leading comment
[mcp_servers.hangeul-mcp]
command = \"old\"
args = []

[mcp_servers.other]
command = \"keep\"

# trailing comment
[mcp_servers.hangeul-mcp]
command = \"stale\"
args = [\"-m\", \"old\"]
"""
    launcher = client_config.LauncherSpec(
        command="/tmp/Space Python/python",
        args=["-m", "hangeul_mcp.server"],
        managed=False,
    )

    updated = client_config.render_codex_config_text(original, launcher)

    assert updated.count("[mcp_servers.hangeul-mcp]") == 1
    assert "# leading comment" in updated
    assert "# trailing comment" in updated
    assert '[mcp_servers.other]\ncommand = "keep"' in updated
    assert 'command = "/tmp/Space Python/python"' in updated
    assert 'args = ["-m", "hangeul_mcp.server"]' in updated


def test_antigravity_returns_snippet_when_path_is_ambiguous(tmp_path):
    launcher = client_config.LauncherSpec(
        command=sys.executable,
        args=["-m", "hangeul_mcp.server"],
        managed=False,
    )
    first = tmp_path / "a.json"
    second = tmp_path / "b.json"
    first.write_text("{}", encoding="utf-8")
    second.write_text("{}", encoding="utf-8")

    result = client_config._setup_client_config_with_targets(
        "antigravity",
        launcher=launcher,
        dry_run=False,
        candidate_paths=[first, second],
    )

    assert result["status"] == "needs_manual_path"
    assert result["changed"] is False
    assert result["snippet"]["mcpServers"]["hangeul-mcp"] == {
        "command": sys.executable,
        "args": ["-m", "hangeul_mcp.server"],
    }
    assert result["reason"] == "ambiguous"



def test_uninstall_client_config_removes_only_hangeul_entry(tmp_path, monkeypatch):
    config_path = tmp_path / "claude_desktop_config.json"
    config_path.write_text(
        json.dumps(
            {
                "theme": "dark",
                "mcpServers": {
                    "hangeul-mcp": {"command": "python", "args": ["-m", "hangeul_mcp.server"]},
                    "other": {"command": "keep"},
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(client_config, "get_timestamp", lambda: "20260712T234500Z")

    result = client_config._uninstall_client_config_with_targets("claude", path=config_path)

    assert result["changed"] is True
    data = json.loads(config_path.read_text(encoding="utf-8"))
    assert data == {"theme": "dark", "mcpServers": {"other": {"command": "keep"}}}
    backup = config_path.with_name("claude_desktop_config.json.bak.20260712T234500Z")
    assert backup.exists()



def test_claude_default_path_is_unsupported_on_unverified_platform(monkeypatch):
    monkeypatch.setattr(client_config.sys, "platform", "linux")
    assert client_config.default_client_path("claude") is None


def test_antigravity_uses_official_global_config_when_workspace_is_absent(tmp_path, monkeypatch):
    home = tmp_path / "home"
    launcher = client_config.LauncherSpec(
        command=sys.executable,
        args=["-m", "hangeul_mcp.server"],
        managed=False,
    )
    monkeypatch.setattr(client_config.Path, "home", lambda: home)
    monkeypatch.chdir(tmp_path)

    result = client_config.setup_client_config("antigravity", launcher=launcher, dry_run=True)

    assert result["status"] == "configured"
    assert result["changed"] is True
    assert result["path"] == str(home / ".gemini" / "config" / "mcp_config.json")


def test_antigravity_fails_closed_when_workspace_scope_exists(tmp_path, monkeypatch):
    home = tmp_path / "home"
    launcher = client_config.LauncherSpec(
        command=sys.executable,
        args=["-m", "hangeul_mcp.server"],
        managed=False,
    )
    workspace = tmp_path / ".agents" / "mcp_config.json"
    workspace.parent.mkdir(parents=True)
    workspace.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(client_config.Path, "home", lambda: home)
    monkeypatch.chdir(tmp_path)

    result = client_config.setup_client_config("antigravity", launcher=launcher, dry_run=False)

    assert result["status"] == "needs_manual_scope"
    assert result["reason"] == "workspace_scope_present"
    assert result["changed"] is False
    assert result["paths"][0].endswith(".gemini/config/mcp_config.json")
    assert result["paths"][1].endswith(".agents/mcp_config.json")
    assert result["snippet"]["mcpServers"]["hangeul-mcp"] == {
        "command": sys.executable,
        "args": ["-m", "hangeul_mcp.server"],
    }


def test_antigravity_global_candidate_tracks_official_paths(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setattr(client_config.Path, "home", lambda: home)
    monkeypatch.chdir(tmp_path)

    candidates = client_config.default_antigravity_candidates(include_missing_global=True)

    assert len(candidates) == 1
    assert candidates[0] == home / ".gemini" / "config" / "mcp_config.json"

def test_codex_fails_closed_when_project_scope_exists(tmp_path, monkeypatch):
    home = tmp_path / "home"
    project = tmp_path / ".codex" / "config.toml"
    project.parent.mkdir(parents=True)
    project.write_text("[mcp_servers.other]\ncommand = \"keep\"\n", encoding="utf-8")
    launcher = client_config.LauncherSpec(
        command=sys.executable,
        args=["-m", "hangeul_mcp.server"],
        managed=False,
    )
    monkeypatch.setattr(client_config.Path, "home", lambda: home)
    monkeypatch.chdir(tmp_path)

    result = client_config.setup_client_config("codex", launcher=launcher, dry_run=False)

    assert result["status"] == "needs_manual_scope"
    assert result["reason"] == "project_scope_present"
    assert result["paths"][0] == str(home / ".codex" / "config.toml")
    assert result["paths"][1] == str(project)
    assert "[mcp_servers.hangeul-mcp]" in result["snippet_toml"]
    assert 'args = ["-m", "hangeul_mcp.server"]' in result["snippet_toml"]
def test_default_launcher_uses_absolute_module_command_when_unmanaged(monkeypatch):
    monkeypatch.setattr(client_config, "managed_install_available", lambda: False)
    launcher = client_config.determine_launcher()
    assert launcher.command == sys.executable
    assert launcher.args == ["-m", "hangeul_mcp.server"]
    assert launcher.managed is False

def test_managed_launcher_uses_managed_base_python(tmp_path, monkeypatch):
    managed_root = tmp_path / "managed"
    current = managed_root / "current.json"
    base_python = managed_root / "base" / "venv" / "bin" / "python"
    current.parent.mkdir(parents=True, exist_ok=True)
    current.write_text("{}", encoding="utf-8")
    base_python.parent.mkdir(parents=True, exist_ok=True)
    base_python.write_text("python", encoding="utf-8")
    monkeypatch.setenv("HANGEUL_MCP_MANAGED_ROOT", str(managed_root))
    monkeypatch.setattr(client_config.sys, "platform", "linux")

    launcher = client_config.determine_launcher()

    assert launcher.command == str(base_python)
    assert launcher.args == ["-m", "hangeul_mcp.launcher"]
    assert launcher.managed is True
