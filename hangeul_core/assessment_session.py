from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from types import TracebackType
from typing import Final, Literal, assert_never

from .assessment_plan import AssessmentPlan


SESSION_TTL_SECONDS: Final = 15 * 60
SESSION_CAPACITY: Final = 64
AssessmentSessionErrorCode = Literal[
    "already_applied", "apply_in_progress", "expired_session",
    "invalid_session_instance", "session_capacity",
]

class AssessmentSessionError(ValueError):
    __slots__ = ("code",)
    def __init__(self, code: AssessmentSessionErrorCode) -> None:
        super().__init__(code)
        self.code = code


class AssessmentSessionState(StrEnum):
    PREVIEW_READY = "PREVIEW_READY"
    APPLYING = "APPLYING"
    APPLIED = "APPLIED"
    FAILED_TERMINAL = "FAILED_TERMINAL"
    EXPIRED = "EXPIRED"


@dataclass(frozen=True, slots=True)
class AssessmentSessionPolicy:
    ttl_seconds: float = SESSION_TTL_SECONDS
    capacity: int = SESSION_CAPACITY


@dataclass(frozen=True, slots=True)
class CreatedAssessmentSession:
    session_id: str
    possession_token: str = field(repr=False)
    expires_at_monotonic: float


@dataclass(frozen=True, slots=True)
class AssessmentSessionSnapshot:
    session_id: str
    spec_fingerprint: str
    plan: AssessmentPlan
    state: AssessmentSessionState
    expires_at_monotonic: float


class _SessionRecord:
    __slots__ = (
        "expires_at_monotonic", "instance_id", "lock", "plan", "session_id",
        "spec_fingerprint", "state", "token_consumed", "token_digest",
    )

    def __init__(
        self,
        *,
        session_id: str,
        instance_id: str,
        spec_fingerprint: str,
        plan: AssessmentPlan,
        token_digest: bytes,
        expires_at_monotonic: float,
    ) -> None:
        self.session_id = session_id
        self.instance_id = instance_id
        self.spec_fingerprint = spec_fingerprint
        self.plan = plan
        self.token_digest = token_digest
        self.expires_at_monotonic = expires_at_monotonic
        self.state = AssessmentSessionState.PREVIEW_READY
        self.token_consumed = False
        self.lock = threading.Lock()

    def snapshot(self) -> AssessmentSessionSnapshot:
        return AssessmentSessionSnapshot(
            session_id=self.session_id,
            spec_fingerprint=self.spec_fingerprint,
            plan=self.plan,
            state=self.state,
            expires_at_monotonic=self.expires_at_monotonic,
        )


class AssessmentApplyLease:
    __slots__ = ("_record", "_released")

    def __init__(self, record: _SessionRecord) -> None:
        self._record = record
        self._released = False

    def __enter__(self) -> AssessmentSessionSnapshot:
        return self._record.snapshot()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> Literal[False]:
        del exc_value, traceback
        self._finish(
            AssessmentSessionState.APPLIED
            if exc_type is None
            else AssessmentSessionState.FAILED_TERMINAL
        )
        return False

    def fail(self) -> None:
        self._finish(AssessmentSessionState.FAILED_TERMINAL)

    def _finish(self, state: AssessmentSessionState) -> None:
        if self._released:
            return
        self._record.state = state
        self._released = True
        self._record.lock.release()


class AssessmentSessionStore:
    __slots__ = ("_clock", "_instance_id", "_policy", "_sessions", "_store_lock")

    def __init__(
        self,
        *,
        instance_id: str | None = None,
        clock: Callable[[], float] = time.monotonic,
        policy: AssessmentSessionPolicy = AssessmentSessionPolicy(),
    ) -> None:
        self._instance_id = instance_id or secrets.token_hex(32)
        self._clock = clock
        self._policy = policy
        self._sessions: dict[str, _SessionRecord] = {}
        self._store_lock = threading.Lock()

    @property
    def instance_id(self) -> str:
        return self._instance_id

    def create(
        self,
        *,
        spec_fingerprint: str,
        plan: AssessmentPlan,
    ) -> CreatedAssessmentSession:
        now = self._clock()
        with self._store_lock:
            self._expire_ready_sessions(now)
            active_count = sum(
                record.state
                in (AssessmentSessionState.PREVIEW_READY, AssessmentSessionState.APPLYING)
                for record in self._sessions.values()
            )
            if active_count >= self._policy.capacity:
                raise AssessmentSessionError("session_capacity")

            session_id = secrets.token_hex(16)
            while session_id in self._sessions:
                session_id = secrets.token_hex(16)
            token_bytes = secrets.token_bytes(32)
            possession_token = base64.urlsafe_b64encode(token_bytes).rstrip(b"=").decode("ascii")
            expires_at = now + self._policy.ttl_seconds
            self._sessions[session_id] = _SessionRecord(
                session_id=session_id,
                instance_id=self._instance_id,
                spec_fingerprint=spec_fingerprint,
                plan=plan,
                token_digest=hashlib.sha256(possession_token.encode("ascii")).digest(),
                expires_at_monotonic=expires_at,
            )
        return CreatedAssessmentSession(
            session_id=session_id,
            possession_token=possession_token,
            expires_at_monotonic=expires_at,
        )

    def apply(self, session_id: str, possession_token: str) -> AssessmentApplyLease:
        with self._store_lock:
            record = self._sessions.get(session_id)
        if record is None or record.instance_id != self._instance_id:
            raise AssessmentSessionError("invalid_session_instance")
        if not record.lock.acquire(blocking=False):
            raise AssessmentSessionError("apply_in_progress")

        try:
            self._authorize_locked(record, possession_token)
        except AssessmentSessionError:
            record.lock.release()
            raise
        return AssessmentApplyLease(record)

    def snapshot(self, session_id: str) -> AssessmentSessionSnapshot:
        with self._store_lock:
            record = self._sessions.get(session_id)
        if record is None or record.instance_id != self._instance_id:
            raise AssessmentSessionError("invalid_session_instance")
        with record.lock:
            return record.snapshot()

    def _authorize_locked(self, record: _SessionRecord, possession_token: str) -> None:
        supplied_digest = hashlib.sha256(possession_token.encode("utf-8")).digest()
        if not hmac.compare_digest(record.token_digest, supplied_digest):
            raise AssessmentSessionError("invalid_session_instance")

        match record.state:
            case AssessmentSessionState.APPLIED | AssessmentSessionState.FAILED_TERMINAL:
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
            record.state = AssessmentSessionState.EXPIRED
            raise AssessmentSessionError("expired_session")
        record.token_consumed = True
        record.state = AssessmentSessionState.APPLYING

    def _expire_ready_sessions(self, now: float) -> None:
        for record in self._sessions.values():
            if (
                record.state is AssessmentSessionState.PREVIEW_READY
                and now >= record.expires_at_monotonic
            ):
                record.state = AssessmentSessionState.EXPIRED


__all__ = [
    "SESSION_CAPACITY", "SESSION_TTL_SECONDS", "AssessmentApplyLease",
    "AssessmentSessionError", "AssessmentSessionPolicy", "AssessmentSessionSnapshot",
    "AssessmentSessionState", "AssessmentSessionStore", "CreatedAssessmentSession",
]
