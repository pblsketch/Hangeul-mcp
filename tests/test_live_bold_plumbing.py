"""S2: bold plumbs through the PURE live planner (COM application is Windows-gated).

The live COM write itself needs a running Hangul instance and is exercised in
desktop QA; here we lock the no-COM contract that ``plan_live_addressed_edits``
carries the per-edit ``bold`` flag into each resolved live target so
``apply_live_addressed`` can apply CharShape weight.
"""

from pathlib import Path
import pytest

from hangeul_core.hwp.live_addressed import plan_live_addressed_edits
from hangeul_mcp.tools_file_edit import AddressedEdit, _normalize_addressed_edits

FIXTURE = Path(__file__).parent / "hwpx template" / "12_형성평가 양식.hwpx"

pytestmark = pytest.mark.skipif(
    not FIXTURE.exists(), reason="template fixture not present in this checkout"
)


def _plan(edits):
    return plan_live_addressed_edits(
        FIXTURE, _normalize_addressed_edits([AddressedEdit(**e) for e in edits])
    )


def test_bold_flag_reaches_live_targets():
    plan = _plan(
        [{"target": "t2.r0.c1", "value": "< 보기 >", "expected_text": "< 보기 >", "bold": True}]
    )
    assert plan["ok"], plan
    target = next(t for t in plan["targets"] if t["target"] == "t2.r0.c1")
    assert target["bold"] is True


def test_no_bold_leaves_flag_none():
    plan = _plan(
        [{"target": "t2.r0.c1", "value": "< 보기 >", "expected_text": "< 보기 >"}]
    )
    assert plan["ok"], plan
    target = next(t for t in plan["targets"] if t["target"] == "t2.r0.c1")
    assert target["bold"] is None
