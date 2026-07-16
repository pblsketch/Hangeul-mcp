from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from typing import Mapping

from .assessment_plan import (
    AddressedEdit,
    AssessmentPlan,
    ItemTrace,
    JsonValue,
    ProvenanceEdge,
    SpecMapping,
    VariantPlan,
)
from .assessment_profile import (
    AssessmentProfile,
    AssessmentProfileError,
    SemanticItemSlot,
    VariantRule,
    match_assessment_profile,
)
from .assessment_values import (
    AssessmentCompilerError,
    canonical_bytes as _canonical_bytes,
    integer_value as _integer,
    mapping_value as _mapping,
    normalized_value as _normalized,
    sequence_value as _sequence,
    text_value as _text,
)


VARIANTS = ("student", "teacher", "answer_key")
ADDRESSED_OPERATION_ALLOWLIST = frozenset({
    "replace_text",
    "preserve_marker_replace_tail",
    "insert_blank_before",
    "insert_blank_after",
    "delete_paragraph",
    "delete_table",
})


def _region_map(inspection: SpecMapping) -> dict[str, SpecMapping]:
    regions: dict[str, SpecMapping] = {}
    for value in _sequence(inspection.get("regions"), "profile_mismatch"):
        region = _mapping(value, "profile_mismatch")
        target = region.get("target")
        if not isinstance(target, str):
            raise AssessmentCompilerError("profile_mismatch")
        if target in regions:
            raise AssessmentCompilerError("ambiguous_mapping")
        regions[target] = region
    return regions


def _items(spec: SpecMapping) -> tuple[SpecMapping, ...]:
    items = tuple(_mapping(value) for value in _sequence(spec.get("items")))
    return tuple(sorted(items, key=lambda item: (_integer(item.get("order")), _text(item.get("item_id")))))


def _strings(value: object) -> tuple[str, ...]:
    return tuple(_text(item) for item in _sequence(value))


def _display(value: JsonValue) -> str:
    if isinstance(value, str):
        return _text(value)
    return json.dumps(_normalized(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _choices(item: SpecMapping) -> tuple[str, ...]:
    choices = item.get("choices")
    if choices is None:
        return ()
    rendered: list[str] = []
    for value in _sequence(choices):
        if isinstance(value, Mapping):
            choice = _mapping(value)
            rendered.append(f"{_text(choice.get('choice_id'))}. {_text(choice.get('text', choice.get('content')))}")
        else:
            rendered.append(_text(value))
    return tuple(rendered)


def _category(item: SpecMapping) -> str:
    explicit = item.get("item_type")
    if explicit is not None:
        item_type = _text(explicit)
        if item_type in {"multiple_choice", "short_answer", "constructed_response"}:
            return item_type
        raise AssessmentCompilerError("invalid_item_shape")
    return "multiple_choice" if item.get("choices") is not None else (
        "constructed_response" if item.get("rubric") is not None else "short_answer"
    )


def _select_slots(profile: AssessmentProfile, items: tuple[SpecMapping, ...]) -> tuple[SemanticItemSlot, ...]:
    available: dict[str, list[SemanticItemSlot]] = {}
    for slot in profile.item_slots:
        available.setdefault(slot.item_type, []).append(slot)
    used: dict[str, int] = {}
    selected: list[SemanticItemSlot] = []
    for item in items:
        category = _category(item)
        ordinal = used.get(category, 0)
        try:
            selected.append(available[category][ordinal])
        except (KeyError, IndexError) as exc:
            raise AssessmentCompilerError("profile_mismatch") from exc
        used[category] = ordinal + 1
    return tuple(selected)


def _render(item: SpecMapping, rule: VariantRule) -> tuple[str, tuple[tuple[str, str], ...]]:
    order = _integer(item.get("order"))
    points = _integer(item.get("points"))
    lines = [f"{order}. {_text(item.get('stem'))} ({points}\uc810)", *_choices(item)]
    sources = [(name, "student_visible") for name in ("order", "stem", "points")]
    if item.get("choices") is not None:
        sources.append(("choices", "student_visible"))
    for name in rule.teacher_fields:
        value = item.get(name)
        if value is not None:
            lines.append(f"{name}: {_display(value)}")
            sources.append((name, "teacher_only"))
    return "\n".join(lines), tuple(sources)


def _digest(variant: str, edits: tuple[AddressedEdit, ...], traces: tuple[ItemTrace, ...], edges: tuple[ProvenanceEdge, ...]) -> str:
    payload: JsonValue = {
        "variant": variant,
        "edits": [asdict(value) for value in edits],
        "item_trace": [asdict(value) for value in traces],
        "provenance": [asdict(value) for value in edges],
    }
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def compile_assessment(spec: SpecMapping, profile: AssessmentProfile, inspection: SpecMapping) -> AssessmentPlan:
    try:
        matched = match_assessment_profile(profile.profile_id, inspection)
    except AssessmentProfileError as exc:
        raise AssessmentCompilerError(exc.code) from exc
    if matched != profile:
        raise AssessmentCompilerError("profile_mismatch")
    operation = "replace_text"
    if operation not in ADDRESSED_OPERATION_ALLOWLIST or operation not in profile.allowed_operations:
        raise AssessmentCompilerError("unsupported_operation")

    regions = _region_map(inspection)
    items = _items(_mapping(_normalized(spec)))
    slots = _select_slots(profile, items)

    variants: list[VariantPlan] = []
    rules = {rule.variant: rule for rule in profile.variant_rules}
    if tuple(rules) != VARIANTS:
        raise AssessmentCompilerError("profile_mismatch")
    for variant in VARIANTS:
        edits: list[AddressedEdit] = []
        traces: list[ItemTrace] = []
        edges: list[ProvenanceEdge] = []
        for item, semantic_slot in zip(items, slots):
            slot = next((region for region in profile.regions if region.target == semantic_slot.target), None)
            if slot is None:
                raise AssessmentCompilerError("profile_mismatch")
            region = regions.get(slot.target)
            if region is None or not isinstance(region.get("text"), str) or not region["text"]:
                raise AssessmentCompilerError("profile_mismatch")
            value, sources = _render(item, rules[variant])
            edits.append(AddressedEdit(slot.target, value, _text(region["text"]), slot.kind, operation))
            traces.append(
                ItemTrace(
                    _text(item.get("item_id")),
                    _integer(item.get("order")),
                    _integer(item.get("points")),
                    _strings(item.get("evidence_ids")),
                    slot.target,
                )
            )
            edges.extend(ProvenanceEdge(slot.target, source, classification) for source, classification in sources)
        frozen_edits, frozen_traces, frozen_edges = tuple(edits), tuple(traces), tuple(edges)
        variants.append(
            VariantPlan(
                variant,
                frozen_edits,
                frozen_traces,
                frozen_edges,
                _digest(variant, frozen_edits, frozen_traces, frozen_edges),
            )
        )
    source_digest = inspection.get("source_sha256")
    if not isinstance(source_digest, str) or not source_digest:
        raise AssessmentCompilerError("profile_mismatch")
    return AssessmentPlan(
        profile.profile_id,
        profile.profile_version,
        profile.profile_definition_digest,
        source_digest,
        tuple(variants),
    )


compile_assessment_plan = compile_assessment


__all__ = [
    "ADDRESSED_OPERATION_ALLOWLIST", "VARIANTS", "AddressedEdit",
    "AssessmentCompilerError", "AssessmentPlan", "ItemTrace", "ProvenanceEdge",
    "VariantPlan", "compile_assessment", "compile_assessment_plan",
]
