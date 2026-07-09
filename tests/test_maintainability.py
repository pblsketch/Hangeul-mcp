from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def pure_loc(path: str) -> int:
    lines = (ROOT / path).read_text(encoding="utf-8").splitlines()
    return sum(1 for line in lines if line.strip() and not line.lstrip().startswith("#"))


def test_entrypoints_remain_facades():
    assert pure_loc("hangeul_mcp/server.py") <= 80
    assert pure_loc("hangeul_core/delegate.py") <= 80


def test_byo_ai_harness_modules_remain_small():
    modules = [
        "hangeul_mcp/tools_core.py",
        "hangeul_mcp/tools_read.py",
        "hangeul_mcp/tools_delegate.py",
        "hangeul_mcp/tools_live.py",
        "hangeul_core/capabilities.py",
        "hangeul_core/render.py",
        "hangeul_core/hwp/live.py",
        "hangeul_core/delegate_base.py",
        "hangeul_core/delegate_edit.py",
        "hangeul_core/delegate_generate.py",
    ]
    oversized = {path: pure_loc(path) for path in modules if pure_loc(path) > 250}
    assert oversized == {}


def test_feature_implementation_workflow_is_documented():
    doc = (ROOT / "docs/feature-implementation-workflow.md").read_text(encoding="utf-8")
    for required in [
        "RED",
        "GREEN",
        "REFACTOR",
        "pytest -q",
        "pyflakes",
        "json.tool",
        "git diff --check",
        "available:false",
    ]:
        assert required in doc
