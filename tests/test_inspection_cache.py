from __future__ import annotations

import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from hangeul_core import addressed as addressed_core
from hangeul_mcp import server

_NS = (
    'xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
    'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"'
)


def _run(text: str) -> str:
    return f'<hp:run charPrIDRef="0"><hp:t>{text}</hp:t></hp:run>'


def _write_hwpx(dst: Path, *, body_text: str, cell_lines: tuple[str, ...] = ("자료", "추가")) -> None:
    cell_xml = "".join(
        f'<hp:p id="{11 + index}">{_run(text)}</hp:p>' for index, text in enumerate(cell_lines)
    )
    section0 = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?><hs:sec {_NS}>'
        f'<hp:p id="10">{_run(body_text)}</hp:p>'
        '<hp:tbl rowCnt="1" colCnt="1"><hp:tr>'
        '<hp:tc><hp:cellAddr rowAddr="0" colAddr="0"/><hp:subList>'
        f"{cell_xml}"
        '</hp:subList></hp:tc>'
        '</hp:tr></hp:tbl>'
        '</hs:sec>'
    )
    header = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
        b'<hh:head xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head"/>'
    )
    with zipfile.ZipFile(dst, "w") as archive:
        info = zipfile.ZipInfo("mimetype")
        info.compress_type = zipfile.ZIP_STORED
        archive.writestr(info, b"application/hwp+zip")
        archive.writestr("Contents/header.xml", header)
        archive.writestr("Contents/section0.xml", section0.encode("utf-8"))


@pytest.fixture(autouse=True)
def _clear_inspection_cache() -> None:
    addressed_core._INSPECTION_CACHE.clear()
    yield
    addressed_core._INSPECTION_CACHE.clear()


def test_second_inspection_of_unchanged_content_reuses_cache(tmp_path):
    src = tmp_path / "regions.hwpx"
    _write_hwpx(src, body_text="▶ 본문 안내")

    analyze_calls = 0
    original_analyze = addressed_core.analyze

    def wrapped_analyze(path):
        nonlocal analyze_calls
        analyze_calls += 1
        return original_analyze(path)

    with patch.object(addressed_core, "analyze", side_effect=wrapped_analyze):
        first = addressed_core.inspect_editable_regions(src)
        second = addressed_core.inspect_editable_regions(src)

    assert analyze_calls == 1
    assert first == second
    assert len(addressed_core._INSPECTION_CACHE) == 1


def test_mutating_returned_response_does_not_poison_cached_result(tmp_path):
    src = tmp_path / "regions.hwpx"
    _write_hwpx(src, body_text="▶ 본문 안내")

    first = addressed_core.inspect_editable_regions(src)
    first["counts"]["regions"] = 999
    first["regions"][0]["text"] = "poisoned"
    first["regions"][0]["paragraph_targets"].append("bad-target")

    second = addressed_core.inspect_editable_regions(src)

    assert second["counts"] == {"regions": 2, "unsupported": 0}
    assert second["regions"][0]["text"] == "▶ 본문 안내"
    assert second["regions"][0]["paragraph_targets"] == ["s1.p1"]


def test_editing_file_invalidates_cached_result(tmp_path):
    src = tmp_path / "regions.hwpx"
    _write_hwpx(src, body_text="첫 번째 본문")

    analyze_calls = 0
    original_analyze = addressed_core.analyze

    def wrapped_analyze(path):
        nonlocal analyze_calls
        analyze_calls += 1
        return original_analyze(path)

    with patch.object(addressed_core, "analyze", side_effect=wrapped_analyze):
        first = addressed_core.inspect_editable_regions(src)
        _write_hwpx(src, body_text="두 번째 본문")
        second = addressed_core.inspect_editable_regions(src)

    assert analyze_calls == 2
    assert first["source_sha256"] != second["source_sha256"]
    assert first["regions"][0]["text"] == "첫 번째 본문"
    assert second["regions"][0]["text"] == "두 번째 본문"


def test_inspection_cache_stays_bounded(tmp_path, monkeypatch):
    src = tmp_path / "regions.hwpx"
    monkeypatch.setattr(addressed_core, "_INSPECTION_CACHE_MAX", 2)

    seen_keys = []
    for body_text in ("본문 1", "본문 2", "본문 3"):
        _write_hwpx(src, body_text=body_text)
        inspected = addressed_core.inspect_editable_regions(src)
        seen_keys.append(addressed_core._inspection_cache_key(src, inspected["source_sha256"]))

    assert len(addressed_core._INSPECTION_CACHE) == 2
    assert seen_keys[0] not in addressed_core._INSPECTION_CACHE
    assert seen_keys[1] in addressed_core._INSPECTION_CACHE
    assert seen_keys[2] in addressed_core._INSPECTION_CACHE

def test_direct_structural_readers_retry_on_post_read_hash_change(tmp_path, monkeypatch):
    src = tmp_path / "regions.hwpx"
    _write_hwpx(src, body_text="본문")

    inspect_hashes = iter(("sha-old", "sha-new", "sha-new", "sha-new"))
    paragraph_hashes = iter(("sha-old", "sha-new", "sha-new", "sha-new"))

    with patch.object(addressed_core, "_sha256_path", side_effect=lambda path: next(inspect_hashes)):
        inspected = addressed_core.inspect_editable_regions(src)
    assert inspected["source_sha256"] == "sha-new"

    with patch.object(addressed_core, "_sha256_path", side_effect=lambda path: next(paragraph_hashes)):
        paragraphs = addressed_core.get_paragraph_map(src)
    assert paragraphs["source_sha256"] == "sha-new"


def test_mcp_wrapper_uses_safe_cached_inspection_result(tmp_path):
    src = tmp_path / "regions.hwpx"
    _write_hwpx(src, body_text="▶ 본문 안내")

    first = server.inspect_editable_regions(str(src))
    first["regions"][0]["text"] = "poisoned"

    second = server.inspect_editable_regions(str(src))
    planned = server.plan_template_completion(str(src))

    assert second["regions"][0]["text"] == "▶ 본문 안내"
    assert planned["source_sha256"] == second["source_sha256"]
    assert planned["addressable_regions"] == second["regions"]
def test_stable_bundle_retries_until_source_hashes_align(tmp_path, monkeypatch):
    src = tmp_path / "regions.hwpx"
    _write_hwpx(src, body_text="▶ 본문 안내")

    inspect_calls = 0
    paragraph_calls = 0

    def fake_inspect(path, compact=False):
        nonlocal inspect_calls
        inspect_calls += 1
        source_sha256 = "sha-one" if inspect_calls == 1 else "sha-two"
        return {
            "source_path": str(src),
            "source_sha256": source_sha256,
            "counts": {"regions": 0, "unsupported": 0},
            "regions": [],
            "unsupported_controls": [],
        }

    def fake_paragraph_map(path):
        nonlocal paragraph_calls
        paragraph_calls += 1
        return {
            "source_path": str(src),
            "source_sha256": "sha-two",
            "counts": {"paragraphs": 0},
            "paragraphs": [],
        }

    monkeypatch.setattr(addressed_core, "inspect_editable_regions", fake_inspect)
    monkeypatch.setattr(addressed_core, "get_paragraph_map", fake_paragraph_map)
    monkeypatch.setattr(addressed_core, "_sha256_path", lambda path: "sha-two")

    inspected, paragraph_map = addressed_core._stable_inspection_paragraph_bundle(src)

    assert inspect_calls == 2
    assert paragraph_calls == 2
    assert inspected["source_sha256"] == "sha-two"
    assert paragraph_map["source_sha256"] == "sha-two"


def test_structural_read_wrappers_keep_failure_envelopes():
    paragraphs = server.get_paragraph_map("missing-input.hwp")
    assert paragraphs["paragraphs"] == []
    assert paragraphs["counts"] == {"paragraphs": 0}
    assert paragraphs["source_path"] == "missing-input.hwp"
    assert paragraphs["source_sha256"] is None
    assert paragraphs["error"]

    occurrences = server.find_text_occurrences("missing-input.hwp", "○○○")
    assert occurrences["occurrences"] == []
    assert occurrences["count"] == 0
    assert occurrences["source_path"] == "missing-input.hwp"
    assert occurrences["source_sha256"] is None
    assert occurrences["error"]

    verified = server.verify_targets("missing-input.hwp", [{"target": "b1", "expected_text": "x"}])
    assert verified["verified"] is False
    assert verified["counts"] == {"requested": 1, "verified": 0, "failed": 1}
    assert verified["results"] == []
    assert verified["source_path"] == "missing-input.hwp"
    assert verified["source_sha256"] is None
    assert verified["error"]
def test_plan_template_completion_retries_until_understand_matches_snapshot(tmp_path, monkeypatch):
    src = tmp_path / "regions.hwpx"
    _write_hwpx(src, body_text="▶ 본문 안내")

    bundle_calls = 0
    schema_values = iter(("sha-new", "sha-stable"))
    label_entry = type("LabelEntry", (), {"label": "성명", "field_id": "t1.r0.c0"})()

    def fake_bundle(path, compact=False):
        nonlocal bundle_calls
        bundle_calls += 1
        return (
            {
                "source_path": str(src),
                "source_sha256": "sha-stable",
                "counts": {"regions": 1, "unsupported": 0},
                "regions": [{"target": "b1", "kind": "body_para", "text": "▶ 본문 안내", "snippet": "▶ 본문 안내"}],
                "unsupported_controls": [],
            },
            {
                "source_path": str(src),
                "source_sha256": "sha-stable",
                "counts": {"paragraphs": 1},
                "paragraphs": [{"target": "s1.p1", "text": "▶ 본문 안내"}],
            },
        )

    monkeypatch.setattr(addressed_core, "_stable_inspection_paragraph_bundle", fake_bundle)
    monkeypatch.setattr(
        "hangeul_core.understand.understand",
        lambda path: type("UnderstandResult", (), {"fields": [label_entry], "source_sha256": next(schema_values)})(),
    )

    planned = addressed_core.plan_template_completion(src)

    assert bundle_calls == 2
    assert planned["source_sha256"] == "sha-stable"
    assert planned["directly_fillable_fields"] == [{"label": "성명", "field_id": "t1.r0.c0"}]


def test_runtime_read_failures_keep_stable_tool_envelopes(monkeypatch):
    error = RuntimeError("source file changed during structural read; retry")
    monkeypatch.setattr("hangeul_mcp.tools_read._verify_targets", lambda *args, **kwargs: (_ for _ in ()).throw(error))
    monkeypatch.setattr("hangeul_mcp.tools_read._plan_template_completion", lambda *args, **kwargs: (_ for _ in ()).throw(error))

    verified = server.verify_targets("tests/fixtures/lesson_plan_addressed.hwpx", [{"target": "b1", "expected_text": "x"}])
    assert verified["verified"] is False
    assert verified["counts"] == {"requested": 1, "verified": 0, "failed": 1}
    assert verified["results"] == []
    assert verified["source_path"] == "tests/fixtures/lesson_plan_addressed.hwpx"
    assert verified["source_sha256"] is None
    assert verified["error"] == "source file changed during structural read; retry"

    planned = server.plan_template_completion("tests/fixtures/lesson_plan_addressed.hwpx", compact=True)
    assert planned["state"] == "failed"
    assert planned["addressable_regions"] == []
    assert planned["directly_fillable_fields"] == []
    assert planned["raw_structural_targets"] == []
    assert planned["user_attention_required"] is True
    assert planned["source_path"] == "tests/fixtures/lesson_plan_addressed.hwpx"
    assert planned["source_sha256"] is None
    assert planned["error"] == "source file changed during structural read; retry"

    monkeypatch.setattr("hangeul_mcp.tools_read._verify_targets", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(RuntimeError, match="boom"):
        server.verify_targets("tests/fixtures/lesson_plan_addressed.hwpx", [{"target": "b1", "expected_text": "x"}])

    monkeypatch.setattr("hangeul_mcp.tools_read._plan_template_completion", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(RuntimeError, match="boom"):
        server.plan_template_completion("tests/fixtures/lesson_plan_addressed.hwpx", compact=True)
def test_structural_read_wrappers_envelope_retry_exhaustion_only(monkeypatch):
    retry_error = RuntimeError("source file changed during inspect read; retry")
    monkeypatch.setattr("hangeul_mcp.tools_read._inspect_editable_regions", lambda *args, **kwargs: (_ for _ in ()).throw(retry_error))
    inspected = server.inspect_editable_regions("tests/fixtures/lesson_plan_addressed.hwpx")
    assert inspected["regions"] == []
    assert inspected["source_sha256"] is None
    assert inspected["error"] == "source file changed during inspect read; retry"

    paragraph_error = RuntimeError("source file changed during paragraph read; retry")
    monkeypatch.setattr("hangeul_mcp.tools_read._get_paragraph_map", lambda *args, **kwargs: (_ for _ in ()).throw(paragraph_error))
    paragraphs = server.get_paragraph_map("tests/fixtures/lesson_plan_addressed.hwpx")
    assert paragraphs["paragraphs"] == []
    assert paragraphs["source_sha256"] is None
    assert paragraphs["error"] == "source file changed during paragraph read; retry"

    occurrence_error = RuntimeError("source file changed during paragraph read; retry")
    monkeypatch.setattr("hangeul_mcp.tools_read._find_text_occurrences", lambda *args, **kwargs: (_ for _ in ()).throw(occurrence_error))
    occurrences = server.find_text_occurrences("tests/fixtures/lesson_plan_addressed.hwpx", "○○○")
    assert occurrences["occurrences"] == []
    assert occurrences["source_sha256"] is None
    assert occurrences["error"] == "source file changed during paragraph read; retry"
