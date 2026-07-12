from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Dict, Iterable

_OFFICIAL_DOC_TYPES = {
    "official.notice.v1": "공문",
    "official.press-release.v1": "보도자료",
    "official.draft.v1": "기안문",
}

_OFFICIAL_REQUIRED_METADATA = {
    "official.notice.v1": ("기관명", "제목", "본문"),
    "official.press-release.v1": ("기관명", "제목", "본문"),
}

_OFFICIAL_ALLOWED_METADATA = {
    "official.notice.v1": {"기관명", "제목", "본문", "수신", "참조", "날짜", "발신명의", "담당자"},
    "official.press-release.v1": {"기관명", "제목", "본문", "배포일", "담당", "연락처", "부제", "문의"},
    "official.draft.v1": {"제목", "목적", "내용", "기안자", "기안일", "시행일", "수신", "붙임"},
}



_BLOCKS_TEMPLATE_RULES = {
    "school.minutes.v1": {
        "title_section_id": "meeting_overview",
        "required_sections": ["meeting_overview", "attendance", "agenda", "decisions"],
        "optional_sections": ["next_meeting", "signatures", "attachments"],
        "validators": {
            "meeting_overview": "title_heading_with_paragraph_tail",
            "attendance": "table",
            "agenda": "list",
            "decisions": "decision_content",
        },
    },
    "school.family-letter.v1": {
        "title_section_id": "letter_header",
        "required_sections": ["letter_header", "recipient_intro", "body", "sender_footer"],
        "optional_sections": ["attachments", "notices"],
        "validators": {
            "letter_header": "title_heading_only",
            "recipient_intro": "paragraph",
            "body": "paragraph_or_list",
            "sender_footer": "paragraph",
        },
    },
    "school.report.v1": {
        "title_section_id": "report_header",
        "required_sections": ["report_header", "summary", "report_body"],
        "optional_sections": ["appendix", "data_tables"],
        "validators": {
            "report_header": "title_heading_only",
            "summary": "paragraph",
            "report_body": "report_body",
        },
    },
    "school.application.v1": {
        "title_section_id": "application_header",
        "required_sections": [
            "application_header",
            "applicant_info",
            "application_body",
            "fields_table",
            "approval_footer",
        ],
        "optional_sections": [],
        "validators": {
            "application_header": "title_heading_only",
            "applicant_info": "paragraph_or_table",
            "application_body": "paragraph",
            "fields_table": "table",
            "approval_footer": "paragraph",
        },
    },
}

_A4_SIZE = {"width": 59528, "height": 84189}


def _invalid_shape() -> Dict[str, Any]:
    return {"ok": False, "error": "invalid_template_kind_shape"}


def _section_blocks(section: Dict[str, Any]) -> list | None:
    if not isinstance(section, dict):
        return None
    blocks = section.get("blocks")
    return blocks if isinstance(blocks, list) else None


def _block_type(block: Dict[str, Any]) -> Any:
    return block.get("type") if isinstance(block, dict) else None


def _valid_table_rows(rows: Any) -> bool:
    return (
        isinstance(rows, list)
        and bool(rows)
        and all(
            isinstance(row, list)
            and all(cell is None or type(cell) in {str, int, float} for cell in row)
            for row in rows
        )
    )


def _valid_block_shape(block: Any) -> bool:
    if not isinstance(block, dict) or not isinstance(block.get("type"), str):
        return False
    kind = block["type"]
    if kind == "heading":
        return set(block) <= {"type", "level", "text"} and isinstance(block.get("text"), str) and type(block.get("level", 1)) is int
    if kind == "paragraph":
        return set(block) <= {"type", "text"} and isinstance(block.get("text"), str)
    if kind in {"bullet_list", "numbered_list"}:
        items = block.get("items")
        return set(block) <= {"type", "items"} and isinstance(items, list) and all(isinstance(item, str) for item in items)
    if kind == "table":
        return set(block) <= {"type", "rows"} and _valid_table_rows(block.get("rows"))
    if kind == "page_break":
        return set(block) == {"type"}
    if kind == "image":
        return False
    return False


def _has_alignment_hint(blocks: Iterable[Dict[str, Any]]) -> bool:
    def contains_hint(value: Any) -> bool:
        if isinstance(value, dict):
            for key, item in value.items():
                lowered = str(key).lower()
                if lowered in {"alignment", "align", "centered", "centred", "text_align", "textalign"}:
                    return True
                if contains_hint(item):
                    return True
            return False
        if isinstance(value, list):
            return any(contains_hint(item) for item in value)
        return False

    return any(contains_hint(block) for block in blocks)


def _has_image_payload(spec: Dict[str, Any], sections: list[Dict[str, Any]] | None = None) -> bool:
    if "assets" in spec:
        return True
    for section in sections or []:
        blocks = _section_blocks(section) or []
        for block in blocks:
            if isinstance(block, dict) and (_block_type(block) == "image" or block.get("image_path")):
                return True
    return False


def _match_section_validator(kind: str, title: str, blocks: list[Dict[str, Any]]) -> bool:
    block_types = [_block_type(block) for block in blocks]
    if kind == "title_heading_with_paragraph_tail":
        first = blocks[0] if blocks else None
        return bool(
            len(blocks) > 1
            and isinstance(first, dict)
            and first.get("type") == "heading"
            and first.get("text") == title
            and all(block_type == "paragraph" for block_type in block_types[1:])
        )
    if kind == "title_heading_only":
        return len(blocks) == 1 and bool(blocks) and _block_type(blocks[0]) == "heading" and blocks[0].get("text") == title
    if kind == "table":
        allowed = {"paragraph", "table"}
        return bool(block_types) and all(block_type in allowed for block_type in block_types) and any(
            block_type == "table" for block_type in block_types
        )
    if kind == "list":
        allowed = {"paragraph", "bullet_list", "numbered_list"}
        return bool(block_types) and all(block_type in allowed for block_type in block_types) and any(
            block_type in {"bullet_list", "numbered_list"} for block_type in block_types
        )
    if kind == "decision_content":
        allowed = {"table", "paragraph", "bullet_list", "numbered_list"}
        return bool(block_types) and all(block_type in allowed for block_type in block_types) and any(
            block_type in {"table", "paragraph", "bullet_list", "numbered_list"} for block_type in block_types
        )
    if kind == "paragraph":
        return bool(block_types) and all(block_type == "paragraph" for block_type in block_types)
    if kind == "paragraph_or_list":
        allowed = {"paragraph", "bullet_list", "numbered_list"}
        return bool(block_types) and all(block_type in allowed for block_type in block_types)
    if kind == "paragraph_or_table":
        allowed = {"paragraph", "table"}
        return bool(block_types) and all(block_type in allowed for block_type in block_types)
    if kind == "report_body":
        return bool(blocks) and all(
            _block_type(block) in {"heading", "paragraph", "table"} for block in blocks
        )
    return True


def _plan_layout_stage(spec: Dict[str, Any]) -> Dict[str, Any] | None:
    page_setup = spec.get("page_setup")
    header_footer = spec.get("header_footer")
    if page_setup is None and header_footer is None:
        return None
    if page_setup is not None and not isinstance(page_setup, dict):
        return _invalid_shape()
    if header_footer is not None and not isinstance(header_footer, dict):
        return _invalid_shape()

    allowed_page_setup = {"size", "orientation", "margins", "columns"}
    allowed_header_footer = {"header_text", "footer_text", "page_number"}
    if isinstance(page_setup, dict) and set(page_setup) - allowed_page_setup:
        return _invalid_shape()
    if isinstance(header_footer, dict) and set(header_footer) - allowed_header_footer:
        return _invalid_shape()

    operations: list[Dict[str, Any]] = []
    if isinstance(page_setup, dict):
        size = page_setup.get("size")
        orientation = page_setup.get("orientation")
        if size is not None or orientation is not None:
            params: Dict[str, Any] = {}
            if size is not None:
                if size != "A4":
                    return _invalid_shape()
                params.update(_A4_SIZE)
            if orientation is not None:
                if orientation not in {"portrait", "landscape"}:
                    return _invalid_shape()
                params["orientation"] = orientation
            operations.append({"name": "set_page_size", "params": params})

        margins = page_setup.get("margins")
        if margins is not None and not isinstance(margins, dict):
            return _invalid_shape()
        allowed_margin_keys = {"left", "right", "top", "bottom", "header", "footer", "gutter"}
        if isinstance(margins, dict) and set(margins) - allowed_margin_keys:
            return _invalid_shape()
        if isinstance(margins, dict):
            if any(type(value) is not int or value < 0 for value in margins.values()):
                return _invalid_shape()
        if isinstance(margins, dict) and margins:
            operations.append(
                {
                    "name": "set_page_margins",
                    "params": {
                        key: margins[key]
                        for key in ("left", "right", "top", "bottom", "header", "footer", "gutter")
                        if key in margins
                    },
                }
            )

        columns = page_setup.get("columns")
        if columns is not None:
            if type(columns) is not int or columns < 1:
                return _invalid_shape()
            operations.append({"name": "set_columns", "params": {"col_count": columns}})

    if isinstance(header_footer, dict):
        if header_footer.get("header_text") is not None:
            if not isinstance(header_footer["header_text"], str):
                return _invalid_shape()
            operations.append({"name": "set_header", "params": {"text": header_footer["header_text"]}})
        if header_footer.get("footer_text") is not None:
            if not isinstance(header_footer["footer_text"], str):
                return _invalid_shape()
            operations.append({"name": "set_footer", "params": {"text": header_footer["footer_text"]}})
        if header_footer.get("page_number") is not None:
            if header_footer["page_number"] not in {"BOTTOM_CENTER", "BOTTOM_RIGHT", "TOP_RIGHT"}:
                return _invalid_shape()
            operations.append({"name": "set_page_number", "params": {"position": header_footer["page_number"]}})

    if not operations:
        return None
    return {
        "kind": "delegate_file",
        "operation_names": [operation["name"] for operation in operations],
        "operations": operations,
    }


def _plan_blocks_template(spec: Dict[str, Any]) -> Dict[str, Any]:
    template_id = spec.get("template_id")
    title = spec.get("title")
    sections = spec.get("sections")
    allowed_top_level = {"spec_version", "template_kind", "template_id", "title", "sections", "page_setup", "header_footer", "assets"}
    if set(spec) - allowed_top_level:
        return _invalid_shape()
    if template_id not in _BLOCKS_TEMPLATE_RULES or not isinstance(title, str) or not isinstance(sections, list):
        return _invalid_shape()
    if _has_image_payload(spec, sections):
        return {"ok": False, "error": "unsupported_template_assets_v1"}

    rules = _BLOCKS_TEMPLATE_RULES[template_id]
    allowed_sections = set(rules["required_sections"]) | set(rules["optional_sections"])
    section_map: Dict[str, Dict[str, Any]] = {}
    section_order: list[str] = []
    for section in sections:
        if not isinstance(section, dict) or set(section) != {"section_id", "blocks"}:
            return _invalid_shape()
        section_id = section.get("section_id")
        blocks = _section_blocks(section)
        if not isinstance(section_id, str) or section_id not in allowed_sections or blocks is None:
            return _invalid_shape()
        if _has_alignment_hint(blocks):
            return {"ok": False, "error": "unsupported_alignment_hint_v1"}
        if any(not _valid_block_shape(block) for block in blocks):
            return _invalid_shape()
        if section_id in section_map:
            return _invalid_shape()
        section_map[section_id] = section
        section_order.append(section_id)

    required_sections = rules["required_sections"]
    for section_id in required_sections:
        if section_id not in section_map:
            return {"ok": False, "error": "missing_required_section", "section_id": section_id}
    if section_order[0] != rules["title_section_id"]:
        return {"ok": False, "error": "section_order_mismatch", "section_id": rules["title_section_id"]}

    actual_required_order = [section_id for section_id in section_order if section_id in required_sections]
    for expected_index, section_id in enumerate(required_sections):
        if actual_required_order.index(section_id) != expected_index:
            return {"ok": False, "error": "section_order_mismatch", "section_id": section_id}

    title_section = section_map[rules["title_section_id"]]
    title_blocks = _section_blocks(title_section)
    first_block = title_blocks[0] if title_blocks else None
    if not (
        isinstance(first_block, dict)
        and first_block.get("type") == "heading"
        and first_block.get("text") == title
    ):
        return {"ok": False, "error": "title_section_mismatch"}

    flattened_blocks: list[Dict[str, Any]] = []
    for section in sections:
        blocks = _section_blocks(section)
        if blocks is None:
            return _invalid_shape()
        if _has_alignment_hint(blocks):
            return {"ok": False, "error": "unsupported_alignment_hint_v1"}
        section_id = section.get("section_id")
        validator = rules["validators"].get(section_id)
        if validator and not _match_section_validator(validator, title, blocks):
            return {"ok": False, "error": "invalid_block_type_for_section", "section_id": section_id}
        flattened_blocks.extend(blocks)

    layout_stage = _plan_layout_stage(spec)
    if isinstance(layout_stage, dict) and layout_stage.get("ok") is False:
        return layout_stage
    return {
        "ok": True,
        "template_kind": "blocks_template",
        "base_stage": "new_document_blocks",
        "flattened_blocks": flattened_blocks,
        "recipe_doc_type": None,
        "layout_stage": layout_stage,
    }


def _plan_recipe_template(spec: Dict[str, Any]) -> Dict[str, Any]:
    template_id = spec.get("template_id")
    metadata = spec.get("metadata")
    allowed_top_level = {"spec_version", "template_kind", "template_id", "metadata", "page_setup", "header_footer", "assets"}
    if set(spec) - allowed_top_level:
        return _invalid_shape()
    if template_id not in _OFFICIAL_DOC_TYPES or not isinstance(metadata, dict):
        return _invalid_shape()
    if _has_image_payload(spec):
        return {"ok": False, "error": "unsupported_template_assets_v1"}

    allowed_metadata = _OFFICIAL_ALLOWED_METADATA[template_id]
    if set(metadata) - allowed_metadata:
        return _invalid_shape()
    if any(value is not None and not isinstance(value, str) for value in metadata.values()):
        return _invalid_shape()

    required_keys = _OFFICIAL_REQUIRED_METADATA.get(template_id, ())
    if any(not isinstance(metadata.get(key), str) or not metadata.get(key).strip() for key in required_keys):
        return _invalid_shape()
    if template_id == "official.draft.v1":
        title = metadata.get("제목")
        purpose = metadata.get("목적")
        body = metadata.get("내용")
        if not isinstance(title, str) or not title.strip():
            return _invalid_shape()
        if not ((isinstance(purpose, str) and purpose.strip()) or (isinstance(body, str) and body.strip())):
            return _invalid_shape()

    layout_stage = _plan_layout_stage(spec)
    if isinstance(layout_stage, dict) and layout_stage.get("ok") is False:
        return layout_stage
    return {
        "ok": True,
        "template_kind": "recipe_template",
        "base_stage": "new_document_recipe",
        "flattened_blocks": None,
        "recipe_doc_type": _OFFICIAL_DOC_TYPES[template_id],
        "layout_stage": layout_stage,
    }


def plan_document_spec(spec: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(spec, dict) or type(spec.get("spec_version")) is not int or spec.get("spec_version") != 1:
        return _invalid_shape()

    template_kind = spec.get("template_kind")
    template_id = spec.get("template_id")
    if template_kind == "blocks_template":
        if not isinstance(template_id, str) or not template_id.startswith("school."):
            return _invalid_shape()
        return _plan_blocks_template(spec)
    if template_kind == "recipe_template":
        if not isinstance(template_id, str) or not template_id.startswith("official."):
            return _invalid_shape()
        return _plan_recipe_template(spec)
    return _invalid_shape()


def _create_base_document(spec: Dict[str, Any], plan: Dict[str, Any], out_path: str | Path) -> Dict[str, Any]:
    if plan["template_kind"] == "blocks_template":
        from hangeul_core.delegate_generate import create_document_from_blocks

        return create_document_from_blocks(plan["flattened_blocks"], out_path)

    from hangeul_core.delegate_generate import create_official_document

    return create_official_document(spec["metadata"], out_path, doc_type=plan["recipe_doc_type"])


def _apply_layout_stage(layout_stage: Dict[str, Any], source_path: str | Path, out_path: str | Path) -> Dict[str, Any]:
    from hangeul_core.delegate_edit import (
        set_columns,
        set_footer,
        set_header,
        set_page_margins,
        set_page_number,
        set_page_size,
    )

    operations = {
        "set_page_size": set_page_size,
        "set_page_margins": set_page_margins,
        "set_columns": set_columns,
        "set_header": set_header,
        "set_footer": set_footer,
        "set_page_number": set_page_number,
    }
    sequence = layout_stage.get("operations") or []
    with TemporaryDirectory(dir=str(Path(out_path).parent)) as temp_dir:
        current_path = Path(source_path)
        last_result: Dict[str, Any] | None = None
        for index, operation in enumerate(sequence):
            name = operation["name"]
            target_path = (
                Path(out_path)
                if index == len(sequence) - 1
                else Path(temp_dir) / f"layout-{index}{Path(out_path).suffix}"
            )
            params = dict(operation.get("params", {}))
            if name in {"set_header", "set_footer"}:
                result = operations[name](current_path, params.pop("text"), target_path, **params)
            else:
                result = operations[name](current_path, target_path, **params)
            if not result.get("ok"):
                return result
            current_path = target_path
            last_result = result
        return last_result or {"ok": True, "out_path": str(out_path)}


def create_document_from_spec(spec: Dict[str, Any], out_path: str | Path) -> Dict[str, Any]:
    plan = plan_document_spec(spec)
    if not plan.get("ok"):
        return plan

    layout_stage = plan["layout_stage"]
    if layout_stage is None:
        base_result = _create_base_document(spec, plan, out_path)
        return {**plan, **base_result}

    with TemporaryDirectory(dir=str(Path(out_path).parent)) as temp_dir:
        base_path = Path(temp_dir) / f"base{Path(out_path).suffix}"
        base_result = _create_base_document(spec, plan, base_path)
        if not base_result.get("ok"):
            return {**plan, **base_result}
        layout_result = _apply_layout_stage(layout_stage, base_path, out_path)
        return {**plan, **base_result, **layout_result}
