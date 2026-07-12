"""Focused coverage for the Windows installer draft."""

from pathlib import Path
import re

INSTALLER = Path("scripts/install.ps1")


def _script() -> str:
    return INSTALLER.read_text(encoding="utf-8")


def test_installer_declares_expected_flags_and_user_scope_defaults():
    script = _script()
    assert "[CmdletBinding()]" in script
    assert re.search(r"\[string\[\]\]\s*\$Features", script)
    assert re.search(r"\[string\]\s*\$Client", script)
    assert re.search(r"\[string\]\s*\$Version", script)
    assert re.search(r"\[switch\]\s*\$NonInteractive", script)
    assert re.search(r"\[switch\]\s*\$AllowWingetPythonInstall", script)
    assert "APPDATA" in script
    assert "currentVersion" in script
    assert "current.json" in script
    assert "current_version" in script
    assert "previous_version" in script
    assert "install_source" in script



def test_installer_checks_python_version_and_gives_official_guidance():
    script = _script()
    assert "Python 3.10 or newer" in script
    assert "https://www.python.org/downloads/windows/" in script
    assert "winget install" in script
    assert "AllowWingetPythonInstall" in script
    assert "if (-not $PythonCommand)" in script


def test_installer_uses_checked_commands_and_avoids_secret_logging():
    script = _script()
    assert "function Invoke-CheckedCommand" in script
    assert "$process.ExitCode" in script
    assert "throw" in script
    assert "PYPI_TOKEN" not in script
    assert "TWINE_PASSWORD" not in script
    assert "Write-Host $ArgumentList" not in script


def test_installer_builds_base_launcher_and_runs_setup_doctor_from_base_runtime():
    script = _script()
    assert "Join-Path $baseRoot 'venv'" in script
    assert "currentVersion" in script
    assert "hangeul_mcp.launcher" in script
    assert "hangeul_mcp.manage" in script
    assert "setup" in script
    assert "doctor" in script
    assert "--client" in script
    assert "--json" in script


def test_installer_surfaces_setup_and_doctor_results_and_writes_json_without_bom():
    script = _script()
    assert "ConvertFrom-Json" in script
    assert "Managed install completed." in script
    assert "needs_manual_steps" in script or "mcp_smoke" in script
    assert "UTF8Encoding($false)" in script

def test_installer_supports_version_pins_and_standalone_source_fallback():
    script = _script()
    assert "git+https://github.com/pblsketch/Hangeul-mcp" in script
    assert "Get-VersionedPackageSpec" in script
    assert "hangeul-mcp$ExtrasSuffix==$PinnedVersion" in script
    assert "not verifiably published to PyPI yet" not in script
