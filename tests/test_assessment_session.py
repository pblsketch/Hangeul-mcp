from dataclasses import dataclass

import pytest

from hangeul_core.assessment_plan import AssessmentPlan
from hangeul_core.assessment_session import (
    AssessmentSessionError,
    AssessmentSessionPolicy,
    AssessmentSessionState,
    AssessmentSessionStore,
    CreatedAssessmentSession,
)


@dataclass(slots=True)
class FakeClock:
    now: float = 0.0

    def __call__(self) -> float:
        return self.now


def _plan(index: int = 0) -> AssessmentPlan:
    return AssessmentPlan(
        profile_id="profile",
        profile_version=1,
        profile_definition_digest=f"profile-{index}",
        source_digest=f"source-{index}",
        variants=(),
    )


def _store(*, clock: FakeClock | None = None, capacity: int = 64) -> AssessmentSessionStore:
    return AssessmentSessionStore(
        instance_id="instance-a",
        clock=clock or FakeClock(),
        policy=AssessmentSessionPolicy(ttl_seconds=900.0, capacity=capacity),
    )


def _create(
    store: AssessmentSessionStore,
    index: int = 0,
) -> CreatedAssessmentSession:
    return store.create(spec_fingerprint=f"spec-{index}", plan=_plan(index))


def _assert_code(
    expected: str,
    caught: pytest.ExceptionInfo[AssessmentSessionError],
) -> None:
    assert caught.value.code == expected
    assert str(caught.value) == expected


def test_apply_requires_valid_possession_token() -> None:
    store = _store()
    credentials = _create(store)

    with pytest.raises(AssessmentSessionError) as caught:
        store.apply(credentials.session_id, "wrong-token")

    _assert_code("invalid_session_instance", caught)
    assert store.snapshot(credentials.session_id).state is AssessmentSessionState.PREVIEW_READY


def test_token_is_consumed_after_success() -> None:
    store = _store()
    credentials = _create(store)

    with store.apply(credentials.session_id, credentials.possession_token):
        pass

    with pytest.raises(AssessmentSessionError) as caught:
        store.apply(credentials.session_id, credentials.possession_token)
    _assert_code("already_applied", caught)
    assert caught.value.bundle_id == f"assessment-{credentials.session_id}"


def test_wrong_token_against_applied_session_is_invalid() -> None:
    store = _store()
    credentials = _create(store)
    with store.apply(credentials.session_id, credentials.possession_token):
        pass

    with pytest.raises(AssessmentSessionError) as caught:
        store.apply(credentials.session_id, "wrong-token")

    _assert_code("invalid_session_instance", caught)


def test_wrong_token_against_failed_terminal_session_is_invalid() -> None:
    store = _store()
    credentials = _create(store)
    store.apply(credentials.session_id, credentials.possession_token).fail()

    with pytest.raises(AssessmentSessionError) as caught:
        store.apply(credentials.session_id, "wrong-token")

    _assert_code("invalid_session_instance", caught)


def test_token_is_consumed_after_terminal_failure() -> None:
    store = _store()
    credentials = _create(store)
    lease = store.apply(credentials.session_id, credentials.possession_token)

    lease.fail()

    with pytest.raises(AssessmentSessionError) as caught:
        store.apply(credentials.session_id, credentials.possession_token)
    _assert_code("already_applied", caught)
    assert store.snapshot(credentials.session_id).state is AssessmentSessionState.FAILED_TERMINAL


def test_session_expires_at_monotonic_ttl_boundary() -> None:
    clock = FakeClock()
    store = _store(clock=clock)
    credentials = _create(store)
    clock.now = 900.0

    with pytest.raises(AssessmentSessionError) as caught:
        store.apply(credentials.session_id, credentials.possession_token)

    _assert_code("expired_session", caught)
    assert store.snapshot(credentials.session_id).state is AssessmentSessionState.EXPIRED


def test_capacity_rejects_without_evicting_valid_sessions() -> None:
    store = _store(capacity=2)
    first = _create(store, 1)
    second = _create(store, 2)

    with pytest.raises(AssessmentSessionError) as caught:
        _create(store, 3)

    _assert_code("session_capacity", caught)
    assert store.snapshot(first.session_id).state is AssessmentSessionState.PREVIEW_READY
    assert store.snapshot(second.session_id).state is AssessmentSessionState.PREVIEW_READY


def test_apply_lock_allows_exactly_one_caller() -> None:
    store = _store()
    credentials = _create(store)
    first_lease = store.apply(credentials.session_id, credentials.possession_token)

    with pytest.raises(AssessmentSessionError) as caught:
        store.apply(credentials.session_id, credentials.possession_token)

    _assert_code("apply_in_progress", caught)
    first_lease.fail()


def test_restart_invalidates_prior_instance_tokens() -> None:
    first_store = _store()
    credentials = _create(first_store)
    restarted_store = AssessmentSessionStore(instance_id="instance-b", clock=FakeClock())

    with pytest.raises(AssessmentSessionError) as caught:
        restarted_store.apply(credentials.session_id, credentials.possession_token)

    _assert_code("invalid_session_instance", caught)


def test_terminal_records_move_to_bounded_replay_tombstones() -> None:
    store = _store(capacity=2)
    credentials: list[CreatedAssessmentSession] = []
    for index in range(3):
        created = _create(store, index)
        credentials.append(created)
        with store.apply(created.session_id, created.possession_token):
            pass

    assert store.active_session_ids == frozenset()
    assert store.tombstone_count == 2
    with pytest.raises(AssessmentSessionError) as evicted:
        store.apply(credentials[0].session_id, credentials[0].possession_token)
    _assert_code("invalid_session_instance", evicted)
    with pytest.raises(AssessmentSessionError) as retained:
        store.apply(credentials[-1].session_id, credentials[-1].possession_token)
    _assert_code("already_applied", retained)


def test_expired_records_are_pruned_before_capacity_check() -> None:
    clock = FakeClock()
    store = _store(clock=clock, capacity=1)
    expired = _create(store)
    clock.now = 900.0

    replacement = _create(store, 1)

    assert store.active_session_ids == frozenset({replacement.session_id})
    with pytest.raises(AssessmentSessionError) as caught:
        store.apply(expired.session_id, expired.possession_token)
    _assert_code("expired_session", caught)


def test_token_never_appears_in_persistent_or_observable_state() -> None:
    store = _store()
    credentials = _create(store)

    observable = repr(store.snapshot(credentials.session_id)) + repr(store)

    assert credentials.possession_token not in observable
