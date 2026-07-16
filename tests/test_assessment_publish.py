import errno
import json
from hashlib import sha256
from pathlib import Path

import pytest

from hangeul_core.assessment_publish import (
    RENAME_NOREPLACE,
    AtomicPublishAdapter,
    PublishError,
    recover_published_session,
    run_atomic_publish_probe,
)
from hangeul_core.assessment_observability import (
    AssessmentManifest,
    ManifestInput,
    VariantManifestInput,
    build_manifest,
)


class MoveRecorder:
    def __init__(self, error: int | None = None) -> None:
        self.calls: list[tuple[Path, Path, int]] = []
        self.error = error

    def __call__(self, source: Path, destination: Path, flags: int) -> None:
        self.calls.append((source, destination, flags))
        if self.error is not None:
            raise OSError(self.error, "sensitive detail")
        if flags == RENAME_NOREPLACE and destination.exists():
            raise OSError(errno.EEXIST, "destination exists")
        source.replace(destination)


def _directories(tmp_path: Path) -> tuple[Path, Path]:
    staging = tmp_path / "staging"
    staging.mkdir()
    return staging, tmp_path / "final"


def _published_bundle(final: Path) -> AssessmentManifest:
    final.mkdir()
    digests: dict[str, str] = {}
    for variant, filename in {
        "student": "student.hwpx",
        "teacher": "teacher.hwpx",
        "answer_key": "answer-key.hwpx",
    }.items():
        content = f"{variant}-content".encode()
        (final / filename).write_bytes(content)
        digests[variant] = sha256(content).hexdigest()
    manifest = build_manifest(
        ManifestInput(
            bundle_id="assessment-session-a",
            session_id="session-a",
            created_at="2026-07-16T00:00:00Z",
            spec_fingerprint="spec-a",
            source_digest="source-a",
            profile_id="profile-a",
            profile_version=1,
            profile_definition_digest="profile-definition-a",
            student=VariantManifestInput(digests["student"], 1, 1, 1),
            teacher=VariantManifestInput(digests["teacher"], 1, 1, 1),
            answer_key=VariantManifestInput(digests["answer_key"], 1, 1, 1),
        )
    )
    (final / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return manifest


def test_windows_movefileex_omits_replace_flag(tmp_path: Path) -> None:
    staging, final = _directories(tmp_path)
    move = MoveRecorder()

    AtomicPublishAdapter.windows(move, device_id=lambda _path: 1).publish(staging, final)

    assert move.calls == [(staging, final, 0)]


def test_windows_collision_maps_to_output_collision(tmp_path: Path) -> None:
    staging, final = _directories(tmp_path)
    adapter = AtomicPublishAdapter.windows(
        MoveRecorder(errno.EEXIST), device_id=lambda _path: 1
    )

    with pytest.raises(PublishError) as caught:
        adapter.publish(staging, final)

    assert caught.value.code == "output_collision"


def test_linux_renameat2_uses_rename_noreplace(tmp_path: Path) -> None:
    staging, final = _directories(tmp_path)
    rename = MoveRecorder()

    AtomicPublishAdapter.linux(rename, device_id=lambda _path: 1).publish(staging, final)

    assert rename.calls == [(staging, final, RENAME_NOREPLACE)]


def test_linux_collision_maps_to_output_collision(tmp_path: Path) -> None:
    staging, final = _directories(tmp_path)
    adapter = AtomicPublishAdapter.linux(
        MoveRecorder(errno.EEXIST), device_id=lambda _path: 1
    )

    with pytest.raises(PublishError) as caught:
        adapter.publish(staging, final)

    assert caught.value.code == "output_collision"


def test_device_mismatch_and_exdev_map_to_cross_device_publish(tmp_path: Path) -> None:
    staging, final = _directories(tmp_path)
    mismatch = AtomicPublishAdapter.linux(
        MoveRecorder(), device_id=lambda path: 1 if path == staging else 2
    )
    exdev = AtomicPublishAdapter.linux(
        MoveRecorder(errno.EXDEV), device_id=lambda _path: 1
    )

    for adapter in (mismatch, exdev):
        with pytest.raises(PublishError) as caught:
            adapter.publish(staging, final)
        assert caught.value.code == "cross_device_publish"


def test_missing_primitive_maps_to_atomic_publish_unavailable(tmp_path: Path) -> None:
    staging, final = _directories(tmp_path)

    with pytest.raises(PublishError) as caught:
        AtomicPublishAdapter.unavailable().publish(staging, final)

    assert caught.value.code == "atomic_publish_unavailable"


def test_unclassified_os_error_maps_to_publish_io_error_without_details(tmp_path: Path) -> None:
    staging, final = _directories(tmp_path)
    adapter = AtomicPublishAdapter.linux(
        MoveRecorder(errno.EACCES), device_id=lambda _path: 1
    )

    with pytest.raises(PublishError) as caught:
        adapter.publish(staging, final)

    assert caught.value.code == "publish_io_error"
    assert "sensitive" not in str(caught.value)
    assert str(tmp_path) not in str(caught.value)


def test_capability_probe_calls_production_publish_adapter(tmp_path: Path) -> None:
    adapter = AtomicPublishAdapter.linux(MoveRecorder(), device_id=lambda _path: 1)

    result = run_atomic_publish_probe(tmp_path, adapter)

    assert result.available is True
    assert adapter.publish_count == 2


def test_probe_directories_are_owned_and_cleaned_on_success_and_failure(tmp_path: Path) -> None:
    success = AtomicPublishAdapter.linux(MoveRecorder(), device_id=lambda _path: 1)
    failure = AtomicPublishAdapter.linux(
        MoveRecorder(errno.EACCES), device_id=lambda _path: 1
    )

    assert run_atomic_publish_probe(tmp_path, success).available is True
    assert run_atomic_publish_probe(tmp_path, failure).available is False
    assert tuple(tmp_path.iterdir()) == ()


def test_response_failure_after_publish_recovers_as_applied_without_republish(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    final = tmp_path / "final"
    adapter = AtomicPublishAdapter.linux(MoveRecorder(), device_id=lambda _path: 1)
    manifest = _published_bundle(staging)
    adapter.publish(staging, final)

    result = recover_published_session(final, adapter, manifest)

    assert result.code == "already_applied"
    assert adapter.publish_count == 1
    assert final.is_dir()


def test_recovery_rejects_manifest_schema_or_identity_change(tmp_path: Path) -> None:
    final = tmp_path / "final"
    manifest = _published_bundle(final)
    changed = json.loads((final / "manifest.json").read_text(encoding="utf-8"))
    changed["unexpected"] = "field"
    (final / "manifest.json").write_text(json.dumps(changed), encoding="utf-8")
    adapter = AtomicPublishAdapter.linux(MoveRecorder(), device_id=lambda _path: 1)

    with pytest.raises(PublishError) as caught:
        recover_published_session(final, adapter, manifest)

    assert caught.value.code == "publish_io_error"
    assert adapter.publish_count == 0


def test_recovery_rejects_manifest_identity_change(tmp_path: Path) -> None:
    final = tmp_path / "final"
    manifest = _published_bundle(final)
    changed = json.loads((final / "manifest.json").read_text(encoding="utf-8"))
    changed["session_id"] = "other-session"
    (final / "manifest.json").write_text(json.dumps(changed), encoding="utf-8")
    adapter = AtomicPublishAdapter.linux(MoveRecorder(), device_id=lambda _path: 1)

    with pytest.raises(PublishError) as caught:
        recover_published_session(final, adapter, manifest)

    assert caught.value.code == "publish_io_error"
    assert adapter.publish_count == 0


def test_recovery_rejects_manifest_scalar_type_change(tmp_path: Path) -> None:
    final = tmp_path / "final"
    manifest = _published_bundle(final)
    changed = json.loads((final / "manifest.json").read_text(encoding="utf-8"))
    changed["profile_version"] = True
    (final / "manifest.json").write_text(
        json.dumps(changed, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    adapter = AtomicPublishAdapter.linux(MoveRecorder(), device_id=lambda _path: 1)

    with pytest.raises(PublishError) as caught:
        recover_published_session(final, adapter, manifest)

    assert caught.value.code == "publish_io_error"
    assert adapter.publish_count == 0


def test_recovery_rejects_variant_filename_change(tmp_path: Path) -> None:
    final = tmp_path / "final"
    manifest = _published_bundle(final)
    changed = json.loads((final / "manifest.json").read_text(encoding="utf-8"))
    changed["variants"]["student"]["filename"] = "other.hwpx"
    (final / "manifest.json").write_text(json.dumps(changed), encoding="utf-8")
    adapter = AtomicPublishAdapter.linux(MoveRecorder(), device_id=lambda _path: 1)

    with pytest.raises(PublishError) as caught:
        recover_published_session(final, adapter, manifest)

    assert caught.value.code == "publish_io_error"
    assert adapter.publish_count == 0


def test_recovery_rejects_variant_digest_mismatch(tmp_path: Path) -> None:
    final = tmp_path / "final"
    manifest = _published_bundle(final)
    (final / "student.hwpx").write_bytes(b"tampered")
    adapter = AtomicPublishAdapter.linux(MoveRecorder(), device_id=lambda _path: 1)

    with pytest.raises(PublishError) as caught:
        recover_published_session(final, adapter, manifest)

    assert caught.value.code == "publish_io_error"
    assert adapter.publish_count == 0
