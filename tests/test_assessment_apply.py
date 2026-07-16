from hashlib import sha256
from pathlib import Path

import pytest


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def test_apply_rejects_stale_source_before_any_write(tmp_path: Path) -> None:
    from hangeul_core.assessment_apply import ApplyError, ApplyPreconditions, validate_apply

    source = tmp_path / "source.hwpx"
    output = tmp_path / "bundle"
    source.write_bytes(b"current")
    original = source.read_bytes()
    check = ApplyPreconditions(
        source, output, "stale", "profile-a", "profile-a", "plan-a", "plan-a"
    )

    with pytest.raises(ApplyError) as caught:
        validate_apply(check)

    assert caught.value.code == "stale_source"
    assert source.read_bytes() == original
    assert not output.exists()


def test_apply_rejects_changed_profile_definition_before_any_write(tmp_path: Path) -> None:
    from hangeul_core.assessment_apply import ApplyError, ApplyPreconditions, validate_apply

    source = tmp_path / "source.hwpx"
    output = tmp_path / "bundle"
    source.write_bytes(b"source")
    original = source.read_bytes()
    check = ApplyPreconditions(
        source,
        output,
        _digest(source),
        "profile-b",
        "profile-a",
        "plan-a",
        "plan-a",
    )

    with pytest.raises(ApplyError) as caught:
        validate_apply(check)

    assert caught.value.code == "stale_profile"
    assert source.read_bytes() == original
    assert not output.exists()


def test_apply_rejects_frozen_plan_digest_mismatch_before_any_write(tmp_path: Path) -> None:
    from hangeul_core.assessment_apply import ApplyError, ApplyPreconditions, validate_apply

    source = tmp_path / "source.hwpx"
    output = tmp_path / "bundle"
    source.write_bytes(b"source")
    original = source.read_bytes()
    check = ApplyPreconditions(
        source,
        output,
        _digest(source),
        "profile-a",
        "profile-a",
        "plan-b",
        "plan-a",
    )

    with pytest.raises(ApplyError) as caught:
        validate_apply(check)

    assert caught.value.code == "stale_plan"
    assert source.read_bytes() == original
    assert not output.exists()


def test_apply_rejects_source_and_output_same_path(tmp_path: Path) -> None:
    from hangeul_core.assessment_apply import ApplyError, ApplyPreconditions, validate_apply

    source = tmp_path / "source.hwpx"
    source.write_bytes(b"source")

    with pytest.raises(ApplyError) as caught:
        validate_apply(
            ApplyPreconditions(
                source, source, _digest(source), "profile-a", "profile-a", "plan-a", "plan-a"
            )
        )

    assert caught.value.code == "source_output_collision"
    assert source.read_bytes() == b"source"


def test_apply_rejects_source_output_path_alias(tmp_path: Path) -> None:
    from hangeul_core.assessment_apply import ApplyError, ApplyPreconditions, validate_apply

    source = tmp_path / "source.hwpx"
    source.write_bytes(b"source")
    alias = tmp_path / "." / "source.hwpx"

    with pytest.raises(ApplyError) as caught:
        validate_apply(
            ApplyPreconditions(
                source, alias, _digest(source), "profile-a", "profile-a", "plan-a", "plan-a"
            )
        )

    assert caught.value.code == "source_output_collision"
    assert source.read_bytes() == b"source"


def test_apply_rejects_source_output_hardlink_identity(tmp_path: Path) -> None:
    from hangeul_core.assessment_apply import ApplyError, ApplyPreconditions, validate_apply

    source = tmp_path / "source.hwpx"
    source.write_bytes(b"source")
    hardlink = tmp_path / "hardlink.hwpx"
    hardlink.hardlink_to(source)

    with pytest.raises(ApplyError) as caught:
        validate_apply(
            ApplyPreconditions(
                source,
                hardlink,
                _digest(source),
                "profile-a",
                "profile-a",
                "plan-a",
                "plan-a",
            )
        )

    assert caught.value.code == "source_output_collision"
    assert source.read_bytes() == b"source"
