"""US-032: analyze_form capacity_hint (approx max Korean chars per value cell)."""

from pathlib import Path

from hangeul_core.understand import understand
from hangeul_mcp import server

FIXTURE = Path(__file__).parent / "fixtures" / "sample_form.hwpx"


def test_value_fields_have_capacity_hint():
    fields = understand(FIXTURE).fields
    assert fields
    with_hint = [f for f in fields if f.capacity_hint is not None]
    assert with_hint  # at least some value cells carry a hint
    for f in with_hint:
        assert isinstance(f.capacity_hint, int) and f.capacity_hint >= 0


def test_capacity_hint_matches_width_over_font():
    # 성명 value cell in the fixture is ~4966 wide at 10pt -> (4966-280)/1000 ~= 4
    f = next(x for x in understand(FIXTURE).fields if x.label.replace(" ", "") == "성명")
    assert f.capacity_hint is not None
    assert 2 <= f.capacity_hint <= 8  # a small, plausible Korean-char capacity


def test_analyze_form_tool_exposes_capacity_hint():
    res = server.analyze_form(str(FIXTURE))
    hinted = [x for x in res["fields"] if x.get("capacity_hint") is not None]
    assert hinted
