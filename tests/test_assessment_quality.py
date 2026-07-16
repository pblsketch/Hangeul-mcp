from __future__ import annotations

import zipfile
from pathlib import Path

from hangeul_core.assessment_quality import (
    AssessmentQualityRequirements,
    ExpectedMarkers,
    check_assessment_quality,
)


_SECTION = "Contents/section0.xml"
_HEADER = b'''<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>
<hh:head xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head"/>'''


def _paragraph(paragraph_id: str, text: str) -> str:
    return (
        f'<hp:p id="{paragraph_id}" paraPrIDRef="0">'
        f'<hp:run charPrIDRef="0"><hp:t>{text}</hp:t></hp:run>'
        "</hp:p>"
    )


def _write_fixture(path: Path, first: str, second: str) -> None:
    section = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
        '<hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
        'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">'
        f'{_paragraph("1", first)}{_paragraph("2", second)}</hs:sec>'
    )
    with zipfile.ZipFile(path, "w") as package:
        mimetype = zipfile.ZipInfo("mimetype")
        mimetype.compress_type = zipfile.ZIP_STORED
        package.writestr(mimetype, b"application/hwp+zip")
        package.writestr("Contents/header.xml", _HEADER)
        package.writestr(_SECTION, section.encode("utf-8"))


def _break_structure(source: Path, target: Path) -> None:
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(target, "w") as damaged:
        for entry in original.infolist():
            payload = original.read(entry.filename)
            if entry.filename == _SECTION:
                payload = payload.replace(b"</hs:sec>", b"")
            damaged.writestr(entry, payload)


def test_quality_checker_rejects_placeholder_empty_required_marker_damage_and_invalid_structure_fixtures(
    tmp_path: Path,
) -> None:
    requirements = AssessmentQualityRequirements(
        required_targets=("b1",),
        expected_markers=(ExpectedMarkers("b1", ("○ ",)),),
    )
    clean = tmp_path / "clean.hwpx"
    placeholder = tmp_path / "placeholder.hwpx"
    empty_required = tmp_path / "empty-required.hwpx"
    marker_damage = tmp_path / "marker-damage.hwpx"
    invalid_structure = tmp_path / "invalid-structure.hwpx"

    _write_fixture(clean, "○ 필수 내용", "평가 완료")
    _write_fixture(placeholder, "○ 필수 내용", "{남은값}")
    _write_fixture(empty_required, "○ ", "평가 완료")
    _write_fixture(marker_damage, "- 필수 내용", "평가 완료")
    _break_structure(clean, invalid_structure)

    assert check_assessment_quality(clean, requirements).valid is True
    assert check_assessment_quality(placeholder, requirements).codes == (
        "visible_placeholder",
    )
    assert check_assessment_quality(empty_required, requirements).codes == (
        "empty_required_target",
    )
    assert check_assessment_quality(marker_damage, requirements).codes == (
        "marker_damage",
    )
    assert check_assessment_quality(invalid_structure, requirements).codes == (
        "invalid_structure",
    )


def test_json_object_text_is_not_treated_as_a_template_placeholder(tmp_path: Path) -> None:
    path = tmp_path / "json-text.hwpx"
    _write_fixture(path, "필수 내용", '{"correct":"좋음"}')

    assert check_assessment_quality(
        path,
        AssessmentQualityRequirements(required_targets=("b1",)),
    ).valid is True
