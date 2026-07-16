from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import threading
import time
from collections.abc import Callable
from typing import Literal, assert_never

from .assessment_plan import AssessmentPlan
from .assessment_session_models import (
    AssessmentApplyLease,
    AssessmentSessionPolicy,
    AssessmentSessionSnapshot,
    AssessmentSessionState,
    CreatedAssessmentSession,
    SESSION_CAPACITY,
    SESSION_TTL_SECONDS,
    SessionRecord,
    SessionTombstone,
)


AssessmentSessionErrorCode = Literal[
    "already_applied", "apply_in_progress", "expired_session",
    "invalid_session_instance", "session_capacity",
]

class AssessmentSessionError(ValueError):
    __slots__ = ("bundle_id", "code")
    def __init__(self, code: AssessmentSessionErrorCode, bundle_id: str | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.bundle_id = bundle_id


class AssessmentSessionStore:
    __slots__ = (
        "_clock", "_instance_id", "_policy", "_sessions", "_store_lock", "_tombstones",
    )

    def __init__(self, *, instance_id: str | None = None,
                 clock: Callable[[], float] = time.monotonic,
                 policy: AssessmentSessionPolicy = AssessmentSessionPolicy()) -> None:
        self._instance_id = instance_id or secrets.token_hex(32)
        self._clock = clock
        self._policy = policy
        self._sessions: dict[str, SessionRecord] = {}
        self._tombstones: dict[str, SessionTombstone] = {}
        self._store_lock = threading.Lock()

    @property
    def instance_id(self) -> str:
        return self._instance_id

    @property
    def active_session_ids(self) -> frozenset[str]:
        with self._store_lock:
            self._prune_locked(self._clock())
            return frozenset(self._sessions)

    @property
    def tombstone_count(self) -> int:
        with self._store_lock:
            self._prune_locked(self._clock())
            return len(self._tombstones)

    def create(self, *, spec_fingerprint: str,
               plan: AssessmentPlan) -> CreatedAssessmentSession:
        now = self._clock()
        with self._store_lock:
            self._prune_locked(now)
            if len(self._sessions) >= self._policy.capacity:
                raise AssessmentSessionError("session_capacity")

            session_id = secrets.token_hex(16)
            while session_id in self._sessions:
                session_id = secrets.token_hex(16)
            token_bytes = secrets.token_bytes(32)
            possession_token = base64.urlsafe_b64encode(token_bytes).rstrip(b"=").decode("ascii")
            expires_at = now + self._policy.ttl_seconds
            self._sessions[session_id] = SessionRecord(
                session_id=session_id,
                spec_fingerprint=spec_fingerprint,
                plan=plan,
                token_digest=hashlib.sha256(possession_token.encode("ascii")).digest(),
                expires_at_monotonic=expires_at,
            )
        return CreatedAssessmentSession(session_id, possession_token, expires_at)

    def apply(self, session_id: str, possession_token: str) -> AssessmentApplyLease:
        with self._store_lock:
            self._prune_locked(self._clock())
            record = self._sessions.get(session_id)
            tombstone = self._tombstones.get(session_id)
        if record is None:
            if tombstone is not None:
                self._raise_tombstone(tombstone, possession_token)
            raise AssessmentSessionError("invalid_session_instance")
        if not record.lock.acquire(blocking=False):
            raise AssessmentSessionError("apply_in_progress")

        try:
            self._authorize_locked(record, possession_token)
        except AssessmentSessionError as exc:
            if exc.code == "expired_session":
                self._finish_record(record, AssessmentSessionState.EXPIRED, None)
            record.lock.release()
            raise
        return AssessmentApplyLease(record, self._finish_record)

    def snapshot(self, session_id: str) -> AssessmentSessionSnapshot:
        with self._store_lock:
            self._prune_locked(self._clock())
            record = self._sessions.get(session_id)
            tombstone = self._tombstones.get(session_id)
        if record is None:
            if tombstone is not None:
                return tombstone.snapshot
            raise AssessmentSessionError("invalid_session_instance")
        with record.lock:
            return record.snapshot()

    def _authorize_locked(self, record: SessionRecord, possession_token: str) -> None:
        supplied_digest = hashlib.sha256(possession_token.encode("utf-8")).digest()
        if not hmac.compare_digest(record.token_digest, supplied_digest):
            raise AssessmentSessionError("invalid_session_instance")

        match record.state:
            case AssessmentSessionState.APPLIED:
                raise AssessmentSessionError(
                    "already_applied", f"assessment-{record.session_id}"
                )
            case AssessmentSessionState.FAILED_TERMINAL:
                raise AssessmentSessionError("already_applied")
            case AssessmentSessionState.EXPIRED:
                raise AssessmentSessionError("expired_session")
            case AssessmentSessionState.APPLYING:
                raise AssessmentSessionError("apply_in_progress")
            case AssessmentSessionState.PREVIEW_READY:
                pass
            case unreachable:
                assert_never(unreachable)

        if self._clock() >= record.expires_at_monotonic:
            raise AssessmentSessionError("expired_session")
        record.state = AssessmentSessionState.APPLYING

    def _finish_record(self, record: SessionRecord, state: AssessmentSessionState,
                       bundle_id: str | None) -> None:
        with self._store_lock:
            if self._sessions.get(record.session_id) is not record:
                return
            self._sessions.pop(record.session_id)
            record.state = state
            self._remember_locked(record, bundle_id, self._clock())

    def _remember_locked(self, record: SessionRecord, bundle_id: str | None,
                         now: float) -> None:
        if self._policy.capacity <= 0:
            return
        while len(self._tombstones) >= self._policy.capacity:
            self._tombstones.pop(next(iter(self._tombstones)))
        self._tombstones[record.session_id] = SessionTombstone(
            record.token_digest, record.snapshot(), bundle_id, now + self._policy.ttl_seconds
        )

    def _prune_locked(self, now: float) -> None:
        for session_id, tombstone in tuple(self._tombstones.items()):
            if now >= tombstone.expires_at_monotonic:
                self._tombstones.pop(session_id)
        for session_id, record in tuple(self._sessions.items()):
            if record.state is not AssessmentSessionState.PREVIEW_READY:
                continue
            if now < record.expires_at_monotonic or not record.lock.acquire(blocking=False):
                continue
            try:
                self._sessions.pop(session_id)
                record.state = AssessmentSessionState.EXPIRED
                self._remember_locked(record, None, now)
            finally:
                record.lock.release()

    @staticmethod
    def _raise_tombstone(tombstone: SessionTombstone, possession_token: str) -> None:
        supplied = hashlib.sha256(possession_token.encode("utf-8")).digest()
        if not hmac.compare_digest(tombstone.token_digest, supplied):
            raise AssessmentSessionError("invalid_session_instance")
        match tombstone.snapshot.state:
            case AssessmentSessionState.APPLIED:
                raise AssessmentSessionError("already_applied", tombstone.bundle_id)
            case AssessmentSessionState.FAILED_TERMINAL:
                raise AssessmentSessionError("already_applied")
            case AssessmentSessionState.EXPIRED:
                raise AssessmentSessionError("expired_session")
            case AssessmentSessionState.PREVIEW_READY | AssessmentSessionState.APPLYING:
                raise AssessmentSessionError("invalid_session_instance")
            case unreachable:
                assert_never(unreachable)


__all__ = [
    "SESSION_CAPACITY", "SESSION_TTL_SECONDS", "AssessmentApplyLease",
    "AssessmentSessionError", "AssessmentSessionPolicy", "AssessmentSessionSnapshot",
    "AssessmentSessionState", "AssessmentSessionStore", "CreatedAssessmentSession",
]
