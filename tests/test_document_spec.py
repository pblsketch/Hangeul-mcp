import pytest

from hangeul_core.document_spec import plan_document_spec


def _minutes_spec(**extra):
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
    }
    spec.update(extra)
    return spec


def _family_letter_spec(**extra):
    spec = {
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
    spec.update(extra)
    return spec


def _report_spec(**extra):
    spec = {
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
    spec.update(extra)
    return spec


def _application_spec(**extra):
    spec = {
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
    spec.update(extra)
    return spec


def _notice_spec(**extra):
    spec = {
        "spec_version": 1,
        "template_kind": "recipe_template",
        "template_id": "official.notice.v1",
        "metadata": {
            "기관명": "한국교육연구소",
            "제목": "여름 특강 안내",
            "본문": "본문입니다.",
        },
    }
    spec.update(extra)
    return spec


def _press_release_spec(**extra):
    spec = {
        "spec_version": 1,
        "template_kind": "recipe_template",
        "template_id": "official.press-release.v1",
        "metadata": {
            "기관명": "한국교육연구소",
            "제목": "보도자료 제목",
            "본문": "보도자료 본문",
        },
    }
    spec.update(extra)
    return spec


def _draft_spec(**extra):
    spec = {
        "spec_version": 1,
        "template_kind": "recipe_template",
        "template_id": "official.draft.v1",
        "metadata": {
            "제목": "기안 제목",
            "목적": "목적 설명",
        },
    }
    spec.update(extra)
    return spec


@pytest.mark.parametrize(
    ("factory", "expected_types"),
    [
        (_minutes_spec, ["heading", "paragraph", "table", "bullet_list", "paragraph"]),
        (_family_letter_spec, ["heading", "paragraph", "paragraph", "paragraph"]),
        (_report_spec, ["heading", "paragraph", "heading", "paragraph", "table"]),
        (_application_spec, ["heading", "table", "paragraph", "table", "paragraph"]),
    ],
)
def test_plan_blocks_template_routes_all_school_templates(factory, expected_types):
    plan = plan_document_spec(factory())
    assert plan["ok"] is True
    assert plan["template_kind"] == "blocks_template"
    assert plan["base_stage"] == "new_document_blocks"
    assert [block["type"] for block in plan["flattened_blocks"]] == expected_types
    assert plan["layout_stage"] is None


@pytest.mark.parametrize(
    ("spec", "doc_type"),
    [
        (_notice_spec(), "공문"),
        (_press_release_spec(), "보도자료"),
        (_draft_spec(), "기안문"),
    ],
)
def test_plan_recipe_template_routes_all_official_templates(spec, doc_type):
    plan = plan_document_spec(spec)
    assert plan["ok"] is True
    assert plan["template_kind"] == "recipe_template"
    assert plan["base_stage"] == "new_document_recipe"
    assert plan["recipe_doc_type"] == doc_type
    assert plan["layout_stage"] is None


def test_plan_rejects_mixed_family_shape():
    plan = plan_document_spec(_notice_spec(title="잘못된 제목", sections=[]))
    assert plan == {"ok": False, "error": "invalid_template_kind_shape"}


def test_plan_rejects_missing_required_section():
    spec = _minutes_spec(sections=_minutes_spec()["sections"][:-1])
    plan = plan_document_spec(spec)
    assert plan == {"ok": False, "error": "missing_required_section", "section_id": "decisions"}


def test_plan_rejects_required_section_order_mismatch():
    sections = list(_minutes_spec()["sections"])
    sections[1], sections[2] = sections[2], sections[1]
    plan = plan_document_spec(_minutes_spec(sections=sections))
    assert plan == {"ok": False, "error": "section_order_mismatch", "section_id": "attendance"}


def test_plan_rejects_title_heading_mismatch():
    spec = _minutes_spec()
    spec["sections"][0]["blocks"][0]["text"] = "다른 제목"
    plan = plan_document_spec(spec)
    assert plan == {"ok": False, "error": "title_section_mismatch"}


@pytest.mark.parametrize(
    "spec",
    [
        _notice_spec(metadata={"제목": "제목", "본문": "본문"}),
        _notice_spec(metadata={"기관명": "기관", "본문": "본문"}),
        _notice_spec(metadata={"기관명": "기관", "제목": "제목"}),
        _press_release_spec(metadata={"기관명": "기관", "본문": "본문"}),
        _draft_spec(metadata={"제목": "기안 제목"}),
        _draft_spec(metadata={"제목": "기안 제목", "목적": "", "내용": ""}),
    ],
)
def test_plan_rejects_recipe_templates_missing_required_metadata(spec):
    plan = plan_document_spec(spec)
    assert plan == {"ok": False, "error": "invalid_template_kind_shape"}


def test_plan_rejects_assets_and_alignment_hints():
    asset_plan = plan_document_spec(_minutes_spec(assets=[{"image_path": "logo.png"}]))
    assert asset_plan == {"ok": False, "error": "unsupported_template_assets_v1"}

    align_plan = plan_document_spec(
        _minutes_spec(
            sections=[
                {
                    "section_id": "meeting_overview",
                    "blocks": [
                        {"type": "heading", "level": 1, "text": "2026 학부모 회의록", "alignment": "center"},
                        {"type": "paragraph", "text": "회의 개요"},
                    ],
                }
            ]
            + _minutes_spec()["sections"][1:]
        )
    )
    assert align_plan == {"ok": False, "error": "unsupported_alignment_hint_v1"}

    centered_plan = plan_document_spec(
        _minutes_spec(
            sections=[
                {
                    "section_id": "meeting_overview",
                    "blocks": [
                        {"type": "heading", "level": 1, "text": "2026 학부모 회의록", "centered": True},
                        {"type": "paragraph", "text": "회의 개요"},
                    ],
                }
            ]
            + _minutes_spec()["sections"][1:]
        )
    )
    assert centered_plan == {"ok": False, "error": "unsupported_alignment_hint_v1"}


def test_plan_emits_one_layout_stage_with_fixed_operation_order():
    plan = plan_document_spec(
        _minutes_spec(
            page_setup={
                "size": "A4",
                "orientation": "landscape",
                "margins": {"left": 4321, "right": 1234, "top": 999, "bottom": 888},
                "columns": 2,
            },
            header_footer={
                "header_text": "머리말",
                "footer_text": "꼬리말",
                "page_number": "BOTTOM_RIGHT",
            },
        )
    )
    assert plan["ok"] is True
    assert plan["layout_stage"]["kind"] == "delegate_file"
    assert plan["layout_stage"]["operation_names"] == [
        "set_page_size",
        "set_page_margins",
        "set_columns",
        "set_header",
        "set_footer",
        "set_page_number",
    ]


def test_plan_rejects_columns_outside_page_setup():
    plan = plan_document_spec(_minutes_spec(header_footer={"columns": 2}))
    assert plan == {"ok": False, "error": "invalid_template_kind_shape"}


@pytest.mark.parametrize(
    ("spec", "section_id"),
    [
        (
            _minutes_spec(
                sections=[
                    {
                        "section_id": "meeting_overview",
                        "blocks": [
                            {"type": "heading", "level": 1, "text": "2026 학부모 회의록"},
                            {"type": "table", "rows": [["항목", "값"]]},
                        ],
                    }
                ]
                + _minutes_spec()["sections"][1:]
            ),
            "meeting_overview",
        ),
        (
            _family_letter_spec(
                sections=[
                    {"section_id": "letter_header", "blocks": [{"type": "heading", "level": 1, "text": "가정통신문"}]},
                    {"section_id": "recipient_intro", "blocks": [{"type": "table", "rows": [["수신", "학부모님"]]}]},
                    {"section_id": "body", "blocks": [{"type": "paragraph", "text": "본문 안내"}]},
                    {"section_id": "sender_footer", "blocks": [{"type": "paragraph", "text": "학교장 드림"}]},
                ]
            ),
            "recipient_intro",
        ),
        (
            _report_spec(
                sections=[
                    {"section_id": "report_header", "blocks": [{"type": "heading", "level": 1, "text": "운영 보고서"}]},
                    {"section_id": "summary", "blocks": [{"type": "table", "rows": [["요약", "잘못됨"]]}]},
                    _report_spec()["sections"][2],
                ]
            ),
            "summary",
        ),
        (
            _application_spec(
                sections=[
                    _application_spec()["sections"][0],
                    _application_spec()["sections"][1],
                    _application_spec()["sections"][2],
                    _application_spec()["sections"][3],
                    {"section_id": "approval_footer", "blocks": [{"type": "table", "rows": [["승인", "대기"]]}]},
                ]
            ),
            "approval_footer",
        ),
    ],
)
def test_plan_rejects_invalid_block_types_for_strict_sections(spec, section_id):
    plan = plan_document_spec(spec)
    assert plan == {"ok": False, "error": "invalid_block_type_for_section", "section_id": section_id}


def test_plan_rejects_empty_assets_and_misplaced_layout_keys():
    assert plan_document_spec(_minutes_spec(assets=[])) == {
        "ok": False,
        "error": "unsupported_template_assets_v1",
    }
    assert plan_document_spec(_minutes_spec(page_setup={"header_text": "잘못된 경로"})) == {
        "ok": False,
        "error": "invalid_template_kind_shape",
    }
    assert plan_document_spec(_minutes_spec(header_footer={"orientation": "landscape"})) == {
        "ok": False,
        "error": "invalid_template_kind_shape",
    }


def test_plan_allows_mixed_content_for_at_least_one_sections():
    minutes_plan = plan_document_spec(
        _minutes_spec(
            sections=[
                _minutes_spec()["sections"][0],
                {
                    "section_id": "attendance",
                    "blocks": [
                        {"type": "paragraph", "text": "참석 현황"},
                        {"type": "table", "rows": [["이름", "참석"], ["홍길동", "예"]]},
                    ],
                },
                {
                    "section_id": "agenda",
                    "blocks": [
                        {"type": "paragraph", "text": "주요 안건"},
                        {"type": "bullet_list", "items": ["교육과정 안내"]},
                    ],
                },
                _minutes_spec()["sections"][3],
            ]
        )
    )
    assert minutes_plan["ok"] is True

    application_plan = plan_document_spec(
        _application_spec(
            sections=[
                _application_spec()["sections"][0],
                _application_spec()["sections"][1],
                _application_spec()["sections"][2],
                {
                    "section_id": "fields_table",
                    "blocks": [
                        {"type": "paragraph", "text": "선택 항목"},
                        {"type": "table", "rows": [["항목", "값"], ["반", "3-1"]]},
                    ],
                },
                _application_spec()["sections"][4],
            ]
        )
    )
    assert application_plan["ok"] is True


def test_plan_rejects_removed_school_metadata_and_bad_layout_value_types():
    assert plan_document_spec(_minutes_spec(metadata={"summary": "남은 stage-04 필드"})) == {
        "ok": False,
        "error": "invalid_template_kind_shape",
    }
    assert plan_document_spec(_minutes_spec(page_setup={"orientation": "sideways"})) == {
        "ok": False,
        "error": "invalid_template_kind_shape",
    }
    assert plan_document_spec(_minutes_spec(page_setup={"columns": 0})) == {
        "ok": False,
        "error": "invalid_template_kind_shape",
    }
    assert plan_document_spec(_minutes_spec(page_setup={"margins": {"left": -1}})) == {
        "ok": False,
        "error": "invalid_template_kind_shape",
    }
    assert plan_document_spec(_minutes_spec(header_footer={"header_text": 1})) == {
        "ok": False,
        "error": "invalid_template_kind_shape",
    }
    assert plan_document_spec(_minutes_spec(header_footer={"page_number": "BOTTOM_LEFT"})) == {
        "ok": False,
        "error": "invalid_template_kind_shape",
    }


def test_plan_rejects_non_string_optional_recipe_metadata():
    plan = plan_document_spec(
        _press_release_spec(
            metadata={
                "기관명": "한국교육연구소",
                "제목": "보도자료 제목",
                "본문": "보도자료 본문",
                "부제": 123,
            }
        )
    )
    assert plan == {"ok": False, "error": "invalid_template_kind_shape"}


def test_plan_rejects_unknown_top_level_fields_and_unknown_contract_keys():
    assert plan_document_spec(_family_letter_spec(defaults={"font": "Batang"})) == {
        "ok": False,
        "error": "invalid_template_kind_shape",
    }
    assert plan_document_spec(
        _report_spec(
            sections=_report_spec()["sections"]
            + [{"section_id": "unexpected", "blocks": [{"type": "paragraph", "text": "추가 섹션"}]}]
        )
    ) == {
        "ok": False,
        "error": "invalid_template_kind_shape",
    }
    assert plan_document_spec(
        _notice_spec(
            metadata={
                "기관명": "한국교육연구소",
                "제목": "여름 특강 안내",
                "본문": "본문입니다.",
                "알수없음": "거절",
            }
        )
    ) == {
        "ok": False,
        "error": "invalid_template_kind_shape",
    }


def test_plan_rejects_recipe_defaults_shape():
    assert plan_document_spec(_notice_spec(defaults={})) == {"ok": False, "error": "invalid_template_kind_shape"}
    bad_plan = plan_document_spec(_notice_spec(defaults="formal"))
    assert bad_plan == {"ok": False, "error": "invalid_template_kind_shape"}


def test_plan_rejects_duplicate_section_ids():
    plan = plan_document_spec(
        _minutes_spec(
            sections=_minutes_spec()["sections"] + [_minutes_spec()["sections"][1]]
        )
    )
    assert plan == {"ok": False, "error": "invalid_template_kind_shape"}


def test_plan_rejects_malformed_sections_and_blocks():
    missing_blocks = _minutes_spec(
        sections=[
            {"section_id": "meeting_overview"},
            _minutes_spec()["sections"][1],
            _minutes_spec()["sections"][2],
            _minutes_spec()["sections"][3],
        ]
    )
    assert plan_document_spec(missing_blocks) == {"ok": False, "error": "invalid_template_kind_shape"}

    extra_block_key = _minutes_spec()
    extra_block_key["sections"][0]["blocks"][0]["foo"] = "bar"
    assert plan_document_spec(extra_block_key) == {"ok": False, "error": "invalid_template_kind_shape"}

    bad_rows = _minutes_spec()
    bad_rows["sections"][1]["blocks"] = [{"type": "table", "rows": ["bad-row"]}]
    assert plan_document_spec(bad_rows) == {"ok": False, "error": "invalid_template_kind_shape"}


def test_plan_rejects_nested_table_payloads_and_bool_int_confusion():
    nested_cell = _minutes_spec()
    nested_cell["sections"][1]["blocks"] = [{"type": "table", "rows": [[{"bad": "cell"}]]}]
    assert plan_document_spec(nested_cell) == {"ok": False, "error": "invalid_template_kind_shape"}

    assert plan_document_spec(_minutes_spec(spec_version=True)) == {"ok": False, "error": "invalid_template_kind_shape"}
    assert plan_document_spec(_minutes_spec(page_setup={"columns": True})) == {"ok": False, "error": "invalid_template_kind_shape"}


def test_plan_rejects_non_object_nested_sections_without_crashing():
    bad_section = _minutes_spec(sections=["bad-section"] + _minutes_spec()["sections"][1:])
    assert plan_document_spec(bad_section) == {"ok": False, "error": "invalid_template_kind_shape"}


@pytest.mark.parametrize(
    ("spec", "section_id"),
    [
        (
            _family_letter_spec(
                sections=[
                    {
                        "section_id": "letter_header",
                        "blocks": [
                            {"type": "heading", "level": 1, "text": "가정통신문"},
                            {"type": "paragraph", "text": "추가 문단"},
                        ],
                    },
                    _family_letter_spec()["sections"][1],
                    _family_letter_spec()["sections"][2],
                    _family_letter_spec()["sections"][3],
                ]
            ),
            "letter_header",
        ),
        (
            _report_spec(
                sections=[
                    {
                        "section_id": "report_header",
                        "blocks": [
                            {"type": "heading", "level": 1, "text": "운영 보고서"},
                            {"type": "paragraph", "text": "추가 문단"},
                        ],
                    },
                    _report_spec()["sections"][1],
                    _report_spec()["sections"][2],
                ]
            ),
            "report_header",
        ),
        (
            _application_spec(
                sections=[
                    {
                        "section_id": "application_header",
                        "blocks": [
                            {"type": "heading", "level": 1, "text": "신청서"},
                            {"type": "paragraph", "text": "추가 문단"},
                        ],
                    },
                    _application_spec()["sections"][1],
                    _application_spec()["sections"][2],
                    _application_spec()["sections"][3],
                    _application_spec()["sections"][4],
                ]
            ),
            "application_header",
        ),
    ],
)
def test_plan_rejects_trailing_paragraphs_in_strict_title_sections(spec, section_id):
    plan = plan_document_spec(spec)
    assert plan == {"ok": False, "error": "invalid_block_type_for_section", "section_id": section_id}


def test_plan_rejects_optional_sections_before_title_and_missing_overview_paragraph():
    out_of_order = _minutes_spec(
        sections=[
            {"section_id": "attachments", "blocks": [{"type": "paragraph", "text": "붙임"}]},
            *_minutes_spec()["sections"],
        ]
    )
    assert plan_document_spec(out_of_order) == {
        "ok": False,
        "error": "section_order_mismatch",
        "section_id": "meeting_overview",
    }

    no_overview_paragraph = _minutes_spec()
    no_overview_paragraph["sections"][0]["blocks"] = [{"type": "heading", "level": 1, "text": "2026 학부모 회의록"}]
    assert plan_document_spec(no_overview_paragraph) == {
        "ok": False,
        "error": "invalid_block_type_for_section",
        "section_id": "meeting_overview",
    }
