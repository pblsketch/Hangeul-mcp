"""S5: delete_row is live-only. Offline fails closed; the live planner is PURE."""

from pathlib import Path
import pytest

from hangeul_core.addressed import preview_addressed_edits
from hangeul_core.hwp.live_table import plan_live_row_deletes
from hangeul_mcp.tools_file_edit import AddressedEdit, _normalize_addressed_edits

FIXTURE = Path(__file__).parent / "hwpx template" / "12_형성평가 양식.hwpx"

pytestmark = pytest.mark.skipif(
    not FIXTURE.exists(), reason="template fixture not present in this checkout"
)


def test_offline_delete_row_fails_closed():
    prev = preview_addressed_edits(
        FIXTURE,
        _normalize_addressed_edits([AddressedEdit(target="t2.r1", operation="delete_row")]),
    )
    assert not prev["ok"]
    assert prev["unresolved"][0]["reason"] == "delete_row_is_live_only"


def test_live_planner_resolves_known_row():
    plan = plan_live_row_deletes(
        FIXTURE, [{"target": "t2.r1", "operation": "delete_row"}]
    )
    assert plan["ok"], plan
    assert plan["targets"][0] == {"target": "t2.r1", "table": 2, "row": 1}


def test_live_planner_orders_bottom_up():
    plan = plan_live_row_deletes(
        FIXTURE,
        [
            {"target": "t2.r0", "operation": "delete_row"},
            {"target": "t2.r2", "operation": "delete_row"},
            {"target": "t2.r1", "operation": "delete_row"},
        ],
    )
    assert plan["ok"], plan
    rows = [t["row"] for t in plan["targets"]]
    assert rows == [2, 1, 0]  # descending -> earlier deletes never shift later ones


def test_live_planner_unknown_row_fails_closed():
    plan = plan_live_row_deletes(
        FIXTURE, [{"target": "t2.r99", "operation": "delete_row"}]
    )
    assert not plan["ok"]
    assert plan["unresolved"][0]["reason"] == "target_not_found"
