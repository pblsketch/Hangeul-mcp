from pathlib import Path

import pytest

import hangeul_core.assessment_cleanup as cleanup
from hangeul_core.assessment_cleanup import (
    CleanupError,
    OwnershipRegistry,
    cleanup_owned_staging,
    staging_directory_name,
    write_staging_marker,
)


def _owned_staging(
    root: Path,
    registry: OwnershipRegistry,
    *,
    session_id: str = "session-a",
    nonce: str = "nonce-a",
    marker_instance: str | None = None,
    register: bool = True,
) -> Path:
    staging = root / staging_directory_name(session_id, nonce)
    staging.mkdir()
    write_staging_marker(
        staging,
        marker_instance or registry.instance_id,
        nonce,
        session_id,
        created_at_epoch=1,
    )
    if register:
        registry.register(staging, nonce, session_id)
    return staging


def test_apply_requires_exact_registered_safe_root(tmp_path: Path) -> None:
    registered = tmp_path / "registered"
    registered.mkdir()
    registry_type = getattr(cleanup, "SafeOutputRootRegistry", None)

    assert callable(registry_type), "SafeOutputRootRegistry is required"
    registry = registry_type((registered,))
    assert registry.require_exact(registered) == registered.resolve()

    with pytest.raises(CleanupError) as caught:
        registry.require_exact(tmp_path / "other")
    assert caught.value.code == "unregistered_output_root"


def test_safe_root_alias_and_descendant_paths_are_rejected(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    descendant = root / "child"
    descendant.mkdir()
    alias = root / ".." / "root"
    registry_type = getattr(cleanup, "SafeOutputRootRegistry", None)

    assert callable(registry_type), "SafeOutputRootRegistry is required"
    registry = registry_type((root,))
    for candidate in (descendant, alias):
        with pytest.raises(CleanupError) as caught:
            registry.require_exact(candidate)
        assert caught.value.code == "unregistered_output_root"


def test_current_instance_registry_and_marker_are_both_required(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    registry = OwnershipRegistry("instance-a")
    staging = _owned_staging(root, registry, register=False)

    result = cleanup_owned_staging(staging, registry, root)

    assert result.cleanup_skipped_unowned == 1
    assert staging.exists()


def test_prior_instance_staging_is_reported_but_not_deleted(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    registry = OwnershipRegistry("instance-current")
    staging = _owned_staging(root, registry, marker_instance="instance-prior")

    result = cleanup_owned_staging(staging, registry, root)

    assert result.foreign_staging_detected == 1
    assert staging.exists()


def test_active_current_session_staging_is_excluded(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    registry = OwnershipRegistry("instance-a")
    staging = _owned_staging(root, registry)
    registry.activate("session-a")

    result = cleanup_owned_staging(staging, registry, root)

    assert result.cleanup_skipped_unowned == 1
    assert staging.exists()


def test_descendant_symlink_junction_or_reparse_aborts_cleanup(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    registry = OwnershipRegistry("instance-a")
    staging = _owned_staging(root, registry)
    outside = tmp_path / "outside"
    outside.mkdir()
    (staging / "escape").symlink_to(outside, target_is_directory=True)

    with pytest.raises(CleanupError) as caught:
        cleanup_owned_staging(staging, registry, root)

    assert caught.value.code == "cleanup_unsafe_descendant"
    assert staging.exists()


def test_cleanup_never_follows_descendants_outside_safe_root(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    registry = OwnershipRegistry("instance-a")
    staging = _owned_staging(root, registry)
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")
    (staging / "escape").symlink_to(outside, target_is_directory=True)

    with pytest.raises(CleanupError):
        cleanup_owned_staging(staging, registry, root)

    assert sentinel.read_text(encoding="utf-8") == "keep"


def test_cleanup_never_removes_final_bundle_or_unowned_directory(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    registry = OwnershipRegistry("instance-a")
    final = root / "assessment-session-a"
    final.mkdir()
    unowned = root / staging_directory_name("unowned", "nonce")
    unowned.mkdir()

    result = cleanup_owned_staging(unowned, registry, root)

    assert result.cleanup_skipped_unowned == 1
    assert final.is_dir()
    assert unowned.is_dir()
