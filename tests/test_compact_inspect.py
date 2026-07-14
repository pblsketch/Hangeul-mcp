from __future__ import annotations

import inspect
import zipfile
from pathlib import Path

from hangeul_core.addressed import inspect_editable_regions, plan_template_completion
from hangeul_mcp import server

_NS = (
    'xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
    'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"'
)


def _run(text: str) -> str:
    return f'<hp:run charPrIDRef="0"><hp:t>{text}</hp:t></hp:run>'


def _write_hwpx(dst: Path, section0: str) -> None:
    header = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
        b'<hh:head xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head"/>'
    )
    with zipfile.ZipFile(dst, "w") as z:
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        z.writestr(zi, b"application/hwp+zip")
        z.writestr("Contents/header.xml", header)
        z.writestr("Contents/section0.xml", section0.encode("utf-8"))



def _build_region_fixture(dst: Path) -> None:
    section0 = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?><hs:sec {_NS}>'
        '<hp:p id="10">' + _run("▶ 본문 안내") + '</hp:p>'
        '<hp:tbl rowCnt="1" colCnt="1"><hp:tr>'
        '<hp:tc><hp:cellAddr rowAddr="0" colAddr="0"/><hp:subList>'
        '<hp:p id="11">' + _run("자료") + '</hp:p>'
        '<hp:p id="12">' + _run("추가") + '</hp:p>'
        '</hp:subList></hp:tc>'
        '</hp:tr></hp:tbl>'
        '</hs:sec>'
    )
    _write_hwpx(dst, section0)



def _build_duplicate_label_fixture(dst: Path) -> None:
    section0 = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?><hs:sec {_NS}>'
        '<hp:tbl rowCnt="2" colCnt="2"><hp:tr>'
        '<hp:tc><hp:cellAddr rowAddr="0" colAddr="0"/><hp:subList><hp:p id="1">' + _run("성명") + '</hp:p></hp:subList></hp:tc>'
        '<hp:tc><hp:cellAddr rowAddr="0" colAddr="1"/><hp:subList><hp:p id="2">' + _run("") + '</hp:p></hp:subList></hp:tc>'
        '</hp:tr><hp:tr>'
        '<hp:tc><hp:cellAddr rowAddr="1" colAddr="0"/><hp:subList><hp:p id="3">' + _run("성명") + '</hp:p></hp:subList></hp:tc>'
        '<hp:tc><hp:cellAddr rowAddr="1" colAddr="1"/><hp:subList><hp:p id="4">' + _run("") + '</hp:p></hp:subList></hp:tc>'
        '</hp:tr></hp:tbl>'
        '</hs:sec>'
    )
    _write_hwpx(dst, section0)



def _build_nested_table_fixture(dst: Path) -> None:
    section0 = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?><hs:sec {_NS}>'
        '<hp:tbl rowCnt="1" colCnt="1"><hp:tr>'
        '<hp:tc><hp:cellAddr rowAddr="0" colAddr="0"/><hp:subList>'
        '<hp:p id="30">' + _run("외부") + '</hp:p>'
        '<hp:tbl rowCnt="1" colCnt="1"><hp:tr>'
        '<hp:tc><hp:cellAddr rowAddr="0" colAddr="0"/><hp:subList><hp:p id="31">' + _run("내부") + '</hp:p></hp:subList></hp:tc>'
        '</hp:tr></hp:tbl>'
        '</hp:subList></hp:tc>'
        '</hp:tr></hp:tbl>'
        '</hs:sec>'
    )
    _write_hwpx(dst, section0)



def test_inspect_compact_preserves_targets_and_hoists_source_hash(tmp_path):
    src = tmp_path / "regions.hwpx"
    _build_region_fixture(src)

    full = inspect_editable_regions(src)
    compact = inspect_editable_regions(src, compact=True)

    assert compact["source_sha256"] == full["source_sha256"]
    assert compact["counts"] == full["counts"]
    assert [region["target"] for region in compact["regions"]] == [region["target"] for region in full["regions"]]
    assert compact["regions"] == [
        {
            "target": "b1",
            "kind": "body_para",
            "text": "▶ 본문 안내",
            "snippet": "▶ 본문 안내",
            "paragraph_target": "s1.p1",
            "paragraph_targets": ["s1.p1"],
            "aliases": ["s1.p1"],
            "paragraph_id": "10",
            "paragraph_ordinal": 1,
            "editable": True,
        },
        {
            "target": "t1.r0.c0",
            "kind": "cell",
            "text": "자료추가",
            "snippet": "자료추가",
            "paragraph_targets": ["t1.r0.c0.p1", "t1.r0.c0.p2"],
            "paragraph_count": 2,
            "paragraphs": [
                {"target": "t1.r0.c0.p1", "text": "자료", "marker": ""},
                {"target": "t1.r0.c0.p2", "text": "추가", "marker": ""},
            ],
            "table": 1,
            "row": 0,
            "col": 0,
            "aliases": [],
            "paragraph_ids": ["11", "12"],
            "editable": True,
        },
    ]
    assert all("source_sha256" in region for region in full["regions"])
    assert all("source_sha256" not in region for region in compact["regions"])
    assert all("section" not in region for region in compact["regions"])
    assert all("section_index" not in region for region in compact["regions"])



def test_plan_template_completion_compact_preserves_target_coverage_and_warnings(tmp_path):
    duplicate = tmp_path / "duplicate.hwpx"
    nested = tmp_path / "nested.hwpx"
    _build_duplicate_label_fixture(duplicate)
    _build_nested_table_fixture(nested)

    full = plan_template_completion(duplicate)
    compact = plan_template_completion(duplicate, compact=True)
    nested_full = plan_template_completion(nested)
    nested_compact = plan_template_completion(nested, compact=True)

    assert compact["source_sha256"] == full["source_sha256"]
    assert [region["target"] for region in compact["addressable_regions"]] == [region["target"] for region in full["addressable_regions"]]
    assert compact["raw_structural_targets"] == full["raw_structural_targets"]
    assert compact["ambiguous_labels"] == full["ambiguous_labels"]
    assert compact["recommended_next_tool"] == "inspect_editable_regions"
    assert all("source_sha256" not in region for region in compact["addressable_regions"])

    assert nested_compact["unsupported_controls"] == [
        {
            "target": nested_full["unsupported_controls"][0]["target"],
            "kind": nested_full["unsupported_controls"][0]["kind"],
            "text": nested_full["unsupported_controls"][0]["text"],
            "snippet": nested_full["unsupported_controls"][0]["snippet"],
            "table": nested_full["unsupported_controls"][0]["table"],
            "row": nested_full["unsupported_controls"][0]["row"],
            "col": nested_full["unsupported_controls"][0]["col"],
            "reason": nested_full["unsupported_controls"][0]["reason"],
            "editable": nested_full["unsupported_controls"][0]["editable"],
        }
    ]
    assert nested_compact["recommended_next_tool"] == nested_full["recommended_next_tool"]
    assert nested_compact["state"] == nested_full["state"]



def test_mcp_wrappers_expose_compact_parameter_and_forward_response(tmp_path):
    src = tmp_path / "regions.hwpx"
    _build_region_fixture(src)

    inspect_sig = inspect.signature(server.inspect_editable_regions)
    plan_sig = inspect.signature(server.plan_template_completion)
    assert inspect_sig.parameters["compact"].default is False
    assert plan_sig.parameters["compact"].default is False

    server_inspected = server.inspect_editable_regions(str(src), compact=True)
    core_inspected = inspect_editable_regions(src, compact=True)
    # wrapper = core response + the common envelope keys (P1-2), nothing else
    assert server_inspected == {**core_inspected, "available": True, "ok": True}

    server_plan = server.plan_template_completion(str(src), compact=True)
    core_plan = plan_template_completion(src, compact=True)
    assert server_plan == {**core_plan, "available": True, "ok": True}
def test_mcp_wrapper_failures_keep_stable_top_level_shape():
    inspected = server.inspect_editable_regions("missing-input.hwp", compact=True)
    assert inspected["regions"] == []
    assert inspected["unsupported_controls"] == []
    assert inspected["counts"] == {"regions": 0, "unsupported": 0}
    assert inspected["source_path"] == "missing-input.hwp"
    assert inspected["source_sha256"] is None
    assert inspected["error"]

    planned = server.plan_template_completion("missing-input.hwp", compact=True)
    assert planned["state"] == "failed"
    assert planned["addressable_regions"] == []
    assert planned["unsupported_controls"] == []
    assert planned["raw_structural_targets"] == []
    assert planned["coverage_ratio"] == 0.0
    assert planned["recommended_next_tool"] == "inspect_editable_regions"
    assert planned["source_path"] == "missing-input.hwp"
    assert planned["source_sha256"] is None
    assert planned["error"]
    assert planned["directly_fillable_fields"] == []
    assert planned["repeated_text_candidates"] == []
    assert planned["ambiguous_labels"] == []
    assert planned["user_attention_required"] is True
