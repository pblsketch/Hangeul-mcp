import json

from hangeul_mcp import doctor, manage


def test_doctor_report_json_shape_with_deterministic_fakes(monkeypatch):
    monkeypatch.setattr(doctor, "collect_optional_extras_status", lambda: {"delegate": {"available": True}})
    monkeypatch.setattr(
        doctor,
        "collect_windows_live_status",
        lambda: {"status": "not_applicable", "reason": "non_windows"},
    )
    monkeypatch.setattr(
        doctor,
        "collect_client_statuses",
        lambda: {
            "claude": {
                "detected": True,
                "registered": True,
                "command": {"exists": True, "managed": False},
            },
            "codex": {
                "detected": False,
                "registered": False,
                "command": {"exists": False, "managed": False},
            },
        },
    )
    monkeypatch.setattr(
        doctor,
        "run_mcp_smoke_test",
        lambda timeout=10.0: {
            "status": "ok",
            "initialized": True,
            "tool_count": 46,
            "required_tools": {
                "detect_format": True,
                "analyze_form": True,
                "fill_form": True,
                "resolve_current_hwp_document": True,
            },
        },
    )
    monkeypatch.setattr(
        doctor,
        "check_for_updates",
        lambda channel="stable", timeout=3.0: {
            "status": "not_published",
            "channel": channel,
        },
    )

    report = doctor.gather_doctor_report()

    assert report["package"]["name"] == "hangeul-mcp"
    assert report["package"]["version"]
    assert report["python"]["executable"]
    assert report["core_import"]["ok"] is True
    assert report["optional_extras"]["delegate"]["available"] is True
    assert report["windows_live"]["status"] == "not_applicable"
    assert report["clients"]["claude"]["registered"] is True
    assert report["clients"]["claude"]["command"]["exists"] is True
    assert report["mcp_smoke"]["tool_count"] == 46
    assert report["updates"]["status"] == "not_published"


def test_doctor_command_json_output(monkeypatch, capsys):
    monkeypatch.setattr(
        manage,
        "run_doctor",
        lambda as_json: {"package": {"version": "0.1.0"}, "updates": {"status": "ok"}},
    )

    assert manage.main(["doctor", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "package": {"version": "0.1.0"},
        "updates": {"status": "ok"},
    }


def test_update_check_reports_smoke_failure_without_crashing(monkeypatch):
    monkeypatch.setattr(
        doctor,
        "collect_optional_extras_status",
        lambda: {},
    )
    monkeypatch.setattr(
        doctor,
        "collect_windows_live_status",
        lambda: {"status": "not_applicable", "reason": "non_windows"},
    )
    monkeypatch.setattr(
        doctor,
        "collect_client_statuses",
        lambda: {},
    )
    monkeypatch.setattr(
        doctor,
        "run_mcp_smoke_test",
        lambda timeout=10.0: {
            "status": "error",
            "initialized": False,
            "error": {"kind": "timeout", "message": "tool list timed out"},
            "tool_count": 0,
            "required_tools": {},
        },
    )
    monkeypatch.setattr(
        doctor,
        "check_for_updates",
        lambda channel="stable", timeout=3.0: {
            "status": "error",
            "channel": channel,
            "error": {"kind": "http", "message": "503"},
        },
    )

    report = doctor.gather_doctor_report()

    assert report["mcp_smoke"]["status"] == "error"
    assert report["mcp_smoke"]["error"]["kind"] == "timeout"
    assert report["updates"]["status"] == "error"
    assert report["updates"]["error"]["kind"] == "http"

def test_collect_client_statuses_distinguishes_auto_and_manual_surfaces(tmp_path, monkeypatch):
    home = tmp_path / "home"
    claude_path = home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    codex_global = home / ".codex" / "config.toml"
    codex_project = tmp_path / ".codex" / "config.toml"
    antigravity_global = home / ".gemini" / "config" / "mcp_config.json"
    antigravity_workspace = tmp_path / ".agents" / "mcp_config.json"
    for path in (claude_path, codex_global, codex_project, antigravity_global, antigravity_workspace):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(doctor.Path, "home", lambda: home)
    monkeypatch.setattr(doctor.sys, "platform", "darwin")
    monkeypatch.chdir(tmp_path)

    def fake_load(client: str, path=None):
        if path == claude_path:
            return {"command": "python", "args": ["-m", "hangeul_mcp.server"]}
        if path == codex_global:
            return {"command": "python", "args": ["-m", "hangeul_mcp.launcher"]}
        if path == antigravity_workspace:
            return {"command": "hangeul-mcp", "args": []}
        return None

    monkeypatch.setattr(doctor, "load_registered_client_command", fake_load)
    monkeypatch.setattr(doctor, "command_exists", lambda command: bool(command))

    statuses = doctor.collect_client_statuses()

    assert statuses["claude"]["support"] == "auto_managed"
    assert statuses["claude"]["registered"] is True
    assert statuses["codex"]["support"] == "auto_and_manual"
    assert statuses["codex"]["status"] == "needs_manual_scope"
    assert any(surface["name"] == "project" and surface["mode"] == "manual_only" for surface in statuses["codex"]["surfaces"])
    assert statuses["codex"]["command"]["managed"] is True
    assert statuses["antigravity"]["support"] == "auto_and_manual"
    assert statuses["antigravity"]["status"] == "needs_manual_scope"
    assert statuses["antigravity"]["registered"] is True
    assert any(surface["name"] == "workspace" and surface["mode"] == "manual_only" and surface["registered"] for surface in statuses["antigravity"]["surfaces"])
    assert statuses["antigravity"]["manual_commands"][1] == "Use /mcp in Antigravity CLI."

def test_headless_extra_is_reported_as_unsupported(monkeypatch):
    monkeypatch.setattr(doctor, "headless_status", lambda: {"available": False, "checked": {"pyhwp": False}})

    status = doctor.collect_optional_extras_status()

    assert status["hwp-headless"]["available"] is False
    assert status["hwp-headless"]["status"] == "unsupported"
    assert status["hwp-headless"]["checked"] == {"pyhwp": False}
