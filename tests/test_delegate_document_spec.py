import re

import pytest

pytest.importorskip("hwpx")

from hangeul_core.delegate import create_document_from_spec  # noqa: E402
from hangeul_core.owpml import HwpxPackage  # noqa: E402
from hangeul_mcp import server  # noqa: E402


def _all_text(hwpx) -> str:
    pkg = HwpxPackage.open(hwpx)
    return "".join(
        pkg.read(name).decode("utf-8")
        for name in pkg.names()
        if name.startswith("Contents/section") and name.endswith(".xml")
    )


def _section0(hwpx) -> str:
    return HwpxPackage.open(hwpx).read("Contents/section0.xml").decode("utf-8")


def _xml_contains(path, needle: str) -> bool:
    pkg = HwpxPackage.open(path)
    blob = needle.encode("utf-8")
    return any(blob in pkg.read(name) for name in pkg.names() if name.endswith(".xml"))


def test_create_document_from_spec_blocks_template_content_and_layout(tmp_path):
    out = tmp_path / "minutes.hwpx"
    spec = {
        "spec_version": 1,
        "template_kind": "blocks_template",
        "template_id": "school.minutes.v1",
        "title": "2026 학부모 회의록",
        "sections": [
            {
                "section_id": "meeting_overview",
                "blocks": [
                    {"type": "heading", "level": 1, "text": "2026 학부모 회의록"},
                    {"type": "paragraph", "text": "회의 개요"},
                ],
            },
            {
                "section_id": "attendance",
                "blocks": [{"type": "table", "rows": [["이름", "참석"], ["홍길동", "예"]]}],
            },
            {
                "section_id": "agenda",
                "blocks": [{"type": "bullet_list", "items": ["교육과정 안내"]}],
            },
            {
                "section_id": "decisions",
                "blocks": [{"type": "paragraph", "text": "방학 프로그램을 진행한다."}],
            },
        ],
        "page_setup": {
            "size": "A4",
            "orientation": "landscape",
            "margins": {"left": 4321, "right": 1234, "top": 999, "bottom": 888},
            "columns": 2,
        },
        "header_footer": {
            "header_text": "머리말-검증-문자열",
            "footer_text": "꼬리말-검증-문자열",
        },
    }

    res = create_document_from_spec(spec, out)
    assert res["ok"] is True
    assert res["template_kind"] == "blocks_template"
    assert res["base_stage"] == "new_document_blocks"
    assert res["layout_stage"]["operation_names"] == [
        "set_page_size",
        "set_page_margins",
        "set_columns",
        "set_header",
        "set_footer",
    ]

    text = _all_text(out)
    for expected in ("2026 학부모 회의록", "회의 개요", "교육과정 안내", "방학 프로그램을 진행한다."):
        assert expected in text

    pagepr = re.search(r"<hp:pagePr[^>]*>", _section0(out)).group(0)
    assert 'landscape="true"' in pagepr or 'landscape="false"' not in pagepr
    margin = re.search(r"<hp:margin[^>]*/?>", _section0(out)).group(0)
    for frag in ('left="4321"', 'right="1234"', 'top="999"', 'bottom="888"'):
        assert frag in margin
    assert 'colCount="2"' in _section0(out)
    assert _xml_contains(out, "머리말-검증-문자열")
    assert _xml_contains(out, "꼬리말-검증-문자열")


def test_create_document_from_spec_recipe_template_routes_to_recipe(tmp_path):
    out = tmp_path / "notice.hwpx"
    spec = {
        "spec_version": 1,
        "template_kind": "recipe_template",
        "template_id": "official.notice.v1",
        "metadata": {
            "기관명": "한국교육연구소",
            "수신": "각 학교장",
            "제목": "여름 특강 안내",
            "본문": "많은 참여 바랍니다.",
        },
        "header_footer": {
            "page_number": "BOTTOM_RIGHT",
        },
    }

    res = create_document_from_spec(spec, out)
    assert res["ok"] is True
    assert res["template_kind"] == "recipe_template"
    assert res["base_stage"] == "new_document_recipe"
    assert res["recipe_doc_type"] == "공문"
    assert res["layout_stage"]["operation_names"] == ["set_page_number"]
    text = _all_text(out)
    assert "한국교육연구소" in text
    assert "여름 특강 안내" in text
    assert "많은 참여 바랍니다." in text
    assert text.index("각 학교장") < text.index("여름 특강 안내") < text.index("많은 참여 바랍니다.")
    assert re.search(r'<hp:pageNum[^>]*pos="BOTTOM_RIGHT"', _section0(out))


def test_server_create_document_from_spec_tool(tmp_path):
    out = tmp_path / "server-spec.hwpx"
    res = server.create_document_from_spec(
        {
            "spec_version": 1,
            "template_kind": "recipe_template",
            "template_id": "official.notice.v1",
            "metadata": {"기관명": "기관", "제목": "제목", "본문": "본문"},
        },
        str(out),
    )
    assert res["available"] is True and res["ok"] is True
    assert "제목" in _all_text(out)


def _family_letter_spec():
    return {
        "spec_version": 1,
        "template_kind": "blocks_template",
        "template_id": "school.family-letter.v1",
        "title": "가정통신문",
        "sections": [
            {"section_id": "letter_header", "blocks": [{"type": "heading", "level": 1, "text": "가정통신문"}]},
            {"section_id": "recipient_intro", "blocks": [{"type": "paragraph", "text": "학부모님께"}]},
            {"section_id": "body", "blocks": [{"type": "paragraph", "text": "본문 안내"}]},
            {"section_id": "sender_footer", "blocks": [{"type": "paragraph", "text": "학교장 드림"}]},
        ],
    }


def _report_spec():
    return {
        "spec_version": 1,
        "template_kind": "blocks_template",
        "template_id": "school.report.v1",
        "title": "운영 보고서",
        "sections": [
            {"section_id": "report_header", "blocks": [{"type": "heading", "level": 1, "text": "운영 보고서"}]},
            {"section_id": "summary", "blocks": [{"type": "paragraph", "text": "요약"}]},
            {
                "section_id": "report_body",
                "blocks": [
                    {"type": "heading", "level": 2, "text": "세부"},
                    {"type": "paragraph", "text": "본문"},
                    {"type": "table", "rows": [["항목", "값"], ["참가", "20"]]},
                ],
            },
        ],
    }


def _application_spec():
    return {
        "spec_version": 1,
        "template_kind": "blocks_template",
        "template_id": "school.application.v1",
        "title": "신청서",
        "sections": [
            {"section_id": "application_header", "blocks": [{"type": "heading", "level": 1, "text": "신청서"}]},
            {"section_id": "applicant_info", "blocks": [{"type": "table", "rows": [["성명", "홍길동"]]}]},
            {"section_id": "application_body", "blocks": [{"type": "paragraph", "text": "신청 사유"}]},
            {"section_id": "fields_table", "blocks": [{"type": "table", "rows": [["항목", "값"], ["반", "3-1"]]}]},
            {"section_id": "approval_footer", "blocks": [{"type": "paragraph", "text": "승인 요청"}]},
        ],
    }


@pytest.mark.parametrize(
    ("spec", "expected"),
    [
        (_family_letter_spec(), ("가정통신문", "학부모님께", "본문 안내", "학교장 드림")),
        (_report_spec(), ("운영 보고서", "요약", "세부", "참가")),
        (_application_spec(), ("신청서", "홍길동", "신청 사유", "승인 요청")),
    ],
)
def test_create_document_from_spec_other_school_templates(tmp_path, spec, expected):
    out = tmp_path / f"{spec['template_id']}.hwpx"
    res = create_document_from_spec(spec, out)
    assert res["ok"] is True
    assert res["template_kind"] == "blocks_template"
    text = _all_text(out)
    for value in expected:
        assert value in text


@pytest.mark.parametrize(
    ("spec", "expected_doc_type", "expected"),
    [
        (
            {
                "spec_version": 1,
                "template_kind": "recipe_template",
                "template_id": "official.press-release.v1",
                "metadata": {
                    "기관명": "한국교육연구소",
                    "제목": "보도자료 제목",
                    "본문": "보도자료 본문",
                    "부제": "부제목",
                },
            },
            "보도자료",
            ("한국교육연구소", "보도자료", "보도자료 제목", "부제목"),
        ),
        (
            {
                "spec_version": 1,
                "template_kind": "recipe_template",
                "template_id": "official.draft.v1",
                "metadata": {
                    "제목": "기안 제목",
                    "목적": "사업 목적",
                    "내용": "세부 내용",
                },
            },
            "기안문",
            ("기안 제목", "1. 목적", "사업 목적", "2. 내용"),
        ),
    ],
)
def test_create_document_from_spec_other_official_templates(tmp_path, spec, expected_doc_type, expected):
    out = tmp_path / f"{spec['template_id']}.hwpx"
    res = create_document_from_spec(spec, out)
    assert res["ok"] is True
    assert res["template_kind"] == "recipe_template"
    assert res["recipe_doc_type"] == expected_doc_type
    text = _all_text(out)
    for value in expected:
        assert value in text


def test_server_create_document_from_spec_rejects_non_object(tmp_path):
    out = tmp_path / "bad-spec.hwpx"
    res = server.create_document_from_spec([], str(out))
    assert res["available"] is True
    assert res["ok"] is False
    assert res["error"] == "invalid_template_kind_shape"
