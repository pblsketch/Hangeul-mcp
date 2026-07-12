import json
from pathlib import Path

from hangeul_mcp import client_config

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "tests" / "fixtures" / "client_doc_sources.json").read_text(encoding="utf-8"))


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_clients_readme_records_verified_sources():
    doc = _read("docs/clients/README.md")
    assert FIXTURE["accessed_on"] in doc
    for item in FIXTURE["clients"]:
        assert item["surface"] in doc
        assert item["confidence"] in doc
        assert item["schema"] in doc
        for url in item["urls"]:
            assert url in doc



def test_per_client_docs_match_verified_contract():
    for item in FIXTURE["clients"]:
        doc = _read(item["doc"])
        assert FIXTURE["accessed_on"] in doc
        assert item["confidence"] in doc
        assert item["schema"] in doc
        for url in item["urls"]:
            assert url in doc
        for path in item["paths"]:
            assert path in doc



def test_client_config_path_helpers_match_verified_contract(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setattr(client_config.Path, "home", lambda: home)

    monkeypatch.setattr(client_config.sys, "platform", "darwin")
    assert client_config.default_client_path("claude") == home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"

    monkeypatch.setattr(client_config.sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", str(home / "AppData" / "Roaming"))
    assert client_config.default_client_path("claude") == home / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json"

    monkeypatch.setattr(client_config.sys, "platform", "linux")
    assert client_config.default_client_path("claude") is None

    monkeypatch.chdir(tmp_path)
    assert client_config.default_client_path("codex") == home / ".codex" / "config.toml"
    assert client_config.default_codex_project_path() == tmp_path / ".codex" / "config.toml"
    assert client_config.default_client_path("antigravity") == home / ".gemini" / "config" / "mcp_config.json"
    assert client_config.default_antigravity_workspace_path() == tmp_path / ".agents" / "mcp_config.json"
