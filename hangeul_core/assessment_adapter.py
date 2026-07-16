from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from typing import Mapping

from .assessment_plan import AssessmentPlan, JsonValue, SpecMapping
from .assessment_spec_models import AssessmentSpec
from .assessment_values import canonical_bytes, mapping_value


def assessment_spec_to_compiler_mapping(spec: AssessmentSpec) -> SpecMapping:
    items: list[JsonValue] = []
    for item in spec.items:
        payload = asdict(item)
        payload["item_type"] = payload.pop("type")
        if not item.choices:
            payload.pop("choices", None)
        if item.rubric is None:
            payload.pop("rubric", None)
        items.append(payload)
    return {
        "spec_version": spec.spec_version,
        "profile_id": spec.profile_id,
        "metadata": asdict(spec.metadata),
        "learning_evidence": [asdict(row) for row in spec.learning_evidence],
        "items": items,
    }


def assessment_inspection_to_compiler_mapping(
    inspection: Mapping[str, object],
) -> SpecMapping:
    payload: object = json.loads(json.dumps(inspection, ensure_ascii=False))
    return mapping_value(payload, "profile_mismatch")


def assessment_plan_digest(plan: AssessmentPlan) -> str:
    return hashlib.sha256(canonical_bytes(asdict(plan))).hexdigest()


__all__ = [
    "assessment_inspection_to_compiler_mapping",
    "assessment_plan_digest",
    "assessment_spec_to_compiler_mapping",
]
