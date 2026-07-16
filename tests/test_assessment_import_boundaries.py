from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "hangeul_core"
TOML = importlib.import_module("tomllib" if sys.version_info >= (3, 11) else "tomli")
ASSESSMENT_MODULES = tuple(sorted(CORE.glob("assessment_*.py")))
BASE_DEPENDENCIES = [
    "mcp>=1.2.0",
    "tomli>=2; python_version < '3.11'",
]
FORBIDDEN_CORE_PREFIXES = (
    "hangeul_core.delegate",
    "hangeul_core.hwp",
    "hangeul_core.hwp_headless",
    "hangeul_core.render",
)
OPTIONAL_MODULES = (
    "PIL",
    "hwpx",
    "numpy",
    "pandas",
    "playwright",
    "pyhwpx",
    "pyperclip",
    "pythoncom",
    "pywintypes",
    "win32api",
    "win32com",
)


def _import_origins(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    origins: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            origins.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            origins.add(f"hangeul_core.{module}" if node.level else module)
    return origins


def test_assessment_core_imports_only_allowed_modules() -> None:
    violations: dict[str, list[str]] = {}
    for path in ASSESSMENT_MODULES:
        invalid = []
        for origin in _import_origins(path):
            root = origin.partition(".")[0]
            is_core = origin == "hangeul_core" or origin.startswith("hangeul_core.")
            is_forbidden_core = origin.startswith(FORBIDDEN_CORE_PREFIXES)
            if is_forbidden_core or (not is_core and root not in sys.stdlib_module_names):
                invalid.append(origin)
        if invalid:
            violations[path.name] = sorted(invalid)

    assert ASSESSMENT_MODULES
    assert violations == {}


def test_base_dependency_snapshot_is_unchanged() -> None:
    project = TOML.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]

    assert project["dependencies"] == BASE_DEPENDENCIES


def test_optional_modules_are_not_imported_by_default() -> None:
    script = "\n".join(
        (
            "import importlib",
            "import json",
            "from pathlib import Path",
            "import sys",
            f"root = Path({str(ROOT)!r})",
            "sys.path.insert(0, str(root))",
            "for path in sorted((root / 'hangeul_core').glob('assessment_*.py')):",
            "    importlib.import_module(f'hangeul_core.{path.stem}')",
            "importlib.import_module('hangeul_mcp.tools_assessment')",
            f"optional = {OPTIONAL_MODULES!r}",
            "loaded = sorted(name for name in optional if name in sys.modules)",
            "print(json.dumps({'loaded': loaded}))",
        )
    )
    completed = subprocess.run(
        [sys.executable, "-I", "-c", script],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == {"loaded": []}
