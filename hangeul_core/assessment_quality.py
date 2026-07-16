from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Mapping, Sequence

from .addressed import _paragraph_marker, inspect_editable_regions
from .assessment_plan import VariantPlan
from .owpml import HwpxPackage
from .validate import validate_hwpx


_PLACEHOLDER: Final = re.compile(r"\{[\w .-]+\}")


@dataclass(frozen=True, slots=True)
class ExpectedMarkers:
    target: str
    markers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AssessmentQualityRequirements:
    required_targets: tuple[str, ...]
    expected_markers: tuple[ExpectedMarkers, ...] = ()
    expected_values: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AssessmentQualityReport:
    valid: bool
    codes: tuple[str, ...]


def requirements_for_variant(variant: VariantPlan) -> AssessmentQualityRequirements:
    rendered_edits = tuple(
        edit for edit in variant.edits if edit.operation != "delete_paragraph"
    )
    return AssessmentQualityRequirements(
        required_targets=tuple(
            edit.target for edit in rendered_edits if edit.kind != "body_para"
        ),
        expected_markers=tuple(
            ExpectedMarkers(
                edit.target,
                tuple(_paragraph_marker(line) for line in edit.value.splitlines()),
            )
            for edit in rendered_edits
            if edit.kind != "body_para"
        ),
        expected_values=tuple(edit.value for edit in rendered_edits),
    )


def addressed_requirements_for_variant(
    variant: VariantPlan,
) -> AssessmentQualityRequirements:
    rendered_edits = tuple(
        edit for edit in variant.edits if edit.operation != "delete_paragraph"
    )
    return AssessmentQualityRequirements(
        required_targets=tuple(edit.target for edit in rendered_edits),
        expected_markers=tuple(
            ExpectedMarkers(
                edit.target,
                tuple(_paragraph_marker(line) for line in edit.value.splitlines()),
            )
            for edit in rendered_edits
        ),
        expected_values=tuple(edit.value for edit in rendered_edits),
    )


def _visible_text(path: str | Path) -> str:
    package = HwpxPackage.open(path)
    fragments: list[str] = []
    for name in sorted(package.names()):
        if not name.endswith((".xml", ".hpf", ".rdf")):
            continue
        root = ET.fromstring(package.read(name))
        fragments.extend(
            fragment
            for element in root.iter()
            for fragment in (element.text, element.tail)
            if fragment is not None
        )
    return "".join(fragments)


def _regions(inspection: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    raw_regions = inspection.get("regions")
    if not isinstance(raw_regions, Sequence) or isinstance(raw_regions, (str, bytes)):
        return {}
    regions: dict[str, Mapping[str, object]] = {}
    for region in raw_regions:
        if not isinstance(region, Mapping):
            continue
        target = region.get("target")
        if isinstance(target, str):
            regions[target] = region
        raw_paragraphs = region.get("paragraphs")
        if isinstance(raw_paragraphs, Sequence) and not isinstance(
            raw_paragraphs,
            (str, bytes),
        ):
            for paragraph in raw_paragraphs:
                if not isinstance(paragraph, Mapping):
                    continue
                paragraph_target = paragraph.get("target")
                if isinstance(paragraph_target, str):
                    regions[paragraph_target] = paragraph
    return regions


def _markers(region: Mapping[str, object]) -> tuple[str, ...]:
    raw_paragraphs = region.get("paragraphs")
    if isinstance(raw_paragraphs, Sequence) and not isinstance(
        raw_paragraphs,
        (str, bytes),
    ):
        markers: list[str] = []
        for paragraph in raw_paragraphs:
            if not isinstance(paragraph, Mapping):
                return ()
            marker = paragraph.get("marker")
            if not isinstance(marker, str):
                return ()
            markers.append(marker)
        return tuple(markers)
    text = region.get("text")
    return (_paragraph_marker(text),) if isinstance(text, str) else ()


def _required_target_is_empty(
    region: Mapping[str, object] | None,
    expected_markers: tuple[str, ...],
) -> bool:
    if region is None:
        return True
    text = region.get("text")
    if not isinstance(text, str) or not text.strip():
        return True
    if len(expected_markers) != 1 or not text.startswith(expected_markers[0]):
        return False
    return not text.removeprefix(expected_markers[0]).strip()


def check_assessment_quality(
    path: str | Path,
    requirements: AssessmentQualityRequirements,
) -> AssessmentQualityReport:
    if validate_hwpx(path).get("valid") is not True:
        return AssessmentQualityReport(False, ("invalid_structure",))

    try:
        regions = _regions(inspect_editable_regions(path))
        visible_text = _visible_text(path)
    except (ET.ParseError, KeyError, OSError, RuntimeError, ValueError):
        return AssessmentQualityReport(False, ("invalid_structure",))

    expected = {item.target: item.markers for item in requirements.expected_markers}
    codes: list[str] = []
    if _PLACEHOLDER.search(visible_text) is not None:
        codes.append("visible_placeholder")
    if any(
        _required_target_is_empty(regions.get(target), expected.get(target, ()))
        for target in requirements.required_targets
    ) or any(value not in visible_text for value in requirements.expected_values):
        codes.append("empty_required_target")
    if any(
        expected_markers != _markers(regions[target])
        for target, expected_markers in expected.items()
        if target in regions
    ) or any(target not in regions for target in expected):
        codes.append("marker_damage")
    return AssessmentQualityReport(not codes, tuple(codes))


__all__ = [
    "AssessmentQualityReport",
    "AssessmentQualityRequirements",
    "ExpectedMarkers",
    "addressed_requirements_for_variant",
    "check_assessment_quality",
    "requirements_for_variant",
]
