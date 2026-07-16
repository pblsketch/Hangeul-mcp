from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
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


def test_preview_and_apply_work_without_optional_extras() -> None:
    script = "\n".join(
        (
            "import builtins",
            "from hashlib import sha256",
            "import importlib.util",
            "import json",
            "from pathlib import Path",
            "import runpy",
            "import sys",
            "import tempfile",
            f"root = Path({str(ROOT)!r})",
            "sys.path.insert(0, str(root))",
            f"optional = frozenset({OPTIONAL_MODULES!r})",
            "real_find_spec = importlib.util.find_spec",
            "real_import = builtins.__import__",
            "def find_spec(name, package=None):",
            "    if name.partition('.')[0] in optional:",
            "        return None",
            "    return real_find_spec(name, package)",
            "def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):",
            "    if name.partition('.')[0] in optional:",
            "        raise ModuleNotFoundError(name)",
            "    return real_import(name, globals, locals, fromlist, level)",
            "importlib.util.find_spec = find_spec",
            "builtins.__import__ = guarded_import",
            "from hangeul_mcp.tools_assessment import apply_assessment, configure_assessment_output_roots, preview_assessment",
            "spec = runpy.run_path(str(root / 'tests' / 'test_assessment_spec.py'))['valid_spec']()",
            "fixture = next((root / 'tests' / 'hwpx template').glob('12_*양식.hwpx'))",
            "source_digest = sha256(fixture.read_bytes()).hexdigest()",
            "with tempfile.TemporaryDirectory() as output_root:",
            "    configure_assessment_output_roots((output_root,))",
            "    preview = preview_assessment(str(fixture), spec)",
            "    assert preview['ok'] is True, preview",
            "    applied = apply_assessment(preview['session_id'], preview['possession_token'], output_root)",
            "    assert applied['ok'] is True, applied",
            "    bundle = Path(output_root) / applied['bundle_id']",
            "    files = sorted(path.name for path in bundle.iterdir())",
            "    assert files == ['answer-key.hwpx', 'manifest.json', 'student.hwpx', 'teacher.hwpx']",
            "    assert sha256(fixture.read_bytes()).hexdigest() == source_digest",
            "    print(json.dumps({'preview': preview['ok'], 'apply': applied['ok'], 'files': files}))",
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
    payload = json.loads(completed.stdout.splitlines()[-1])
    assert payload == {
        "preview": True,
        "apply": True,
        "files": ["answer-key.hwpx", "manifest.json", "student.hwpx", "teacher.hwpx"],
    }
