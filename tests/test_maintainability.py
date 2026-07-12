import asyncio
import json
import re
import tomllib
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]

# README count-drift guards (US-048). Two labeled occurrences are guarded,
# each unique in README.md:
#   1. repo-tree line  "... FastMCP stdio 서버 (NN tools)"      -> len(mcp.list_tools())
#   2. status line     "마일스톤·유저 스토리(NN개 — MM pass ..." -> prd story/pass counts
# Test-count wording ("NNN collected") is a SOFT guard by design: parametrize/
# skip variance makes a hard assert brittle. To resync it, run
#   python -m pytest -q --collect-only | tail -1
# and update the README "collected" figures in the same commit.
_TOOLS_RE = re.compile(r"\((\d+)\s*tools\)")
_STORIES_RE = re.compile(r"(\d+)개 — (\d+) pass")


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
        "hangeul_core/hwp/live_inline.py",
        "hangeul_core/hwp/live_body.py",
        "hangeul_core/hwp/live_reload.py",
        "hangeul_core/body.py",
        "hangeul_core/delegate_base.py",
        "hangeul_core/delegate_edit.py",
        "hangeul_core/delegate_generate.py",
    ]
    oversized = {path: pure_loc(path) for path in modules if pure_loc(path) > 250}
    assert oversized == {}


@pytest.mark.parametrize(
    ("doc_name", "pattern"),
    [
        ("README.md", _TOOLS_RE),
        ("HANDOFF.md", re.compile(r"런타임 MCP 툴: \*\*(\d+)\*\*")),
    ],
)
def test_doc_tool_count_matches_runtime(doc_name, pattern):
    from hangeul_mcp import server

    text = (ROOT / doc_name).read_text(encoding="utf-8")
    matches = pattern.findall(text)
    assert len(matches) == 1, f"{doc_name} must state the tool count exactly once ({pattern.pattern})"
    runtime = len(asyncio.run(server.mcp.list_tools()))
    assert int(matches[0]) == runtime, (
        f"{doc_name} says {matches[0]} tools but runtime registers {runtime}; "
        "update it in the same commit that adds/removes tools"
    )


def test_readme_story_counts_match_prd():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    matches = _STORIES_RE.findall(readme)
    assert len(matches) == 1, "README must state story counts exactly once as 'NN개 — MM pass'"
    stories = json.loads((ROOT / "docs" / "prd.json").read_text(encoding="utf-8"))["stories"]
    total, passing = int(matches[0][0]), int(matches[0][1])
    assert total == len(stories), f"README says {total} stories, prd.json has {len(stories)}"
    # pass count definition: passes==true (BC3 / Minor-1), independent of status field
    actual_pass = sum(1 for s in stories if s["passes"] is True)
    assert passing == actual_pass, f"README says {passing} pass, prd.json has {actual_pass}"


def test_live_extra_declares_pyhwpx_transitive_deps():
    # pyhwpx 1.7 imports numpy/pandas/pyperclip/PIL without declaring them;
    # missing ones make live_available() silently false (observed 2026-07-10).
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    live = " ".join(data["project"]["optional-dependencies"]["live"])
    for dep in ("pyhwpx", "numpy", "pandas", "pyperclip", "pillow"):
        assert dep in live, f"'live' extra must declare {dep}"


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
