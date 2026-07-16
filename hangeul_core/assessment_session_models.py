from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from types import TracebackType
from typing import Final, Literal

from .assessment_plan import AssessmentPlan


SESSION_TTL_SECONDS: Final = 15 * 60
SESSION_CAPACITY: Final = 64


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


@dataclass(slots=True)
class SessionRecord:
    session_id: str
    spec_fingerprint: str
    plan: AssessmentPlan
    token_digest: bytes
    expires_at_monotonic: float
    state: AssessmentSessionState = AssessmentSessionState.PREVIEW_READY
    lock: threading.Lock = field(default_factory=threading.Lock)

    def snapshot(self) -> AssessmentSessionSnapshot:
        return AssessmentSessionSnapshot(
            session_id=self.session_id,
            spec_fingerprint=self.spec_fingerprint,
            plan=self.plan,
            state=self.state,
            expires_at_monotonic=self.expires_at_monotonic,
        )


@dataclass(frozen=True, slots=True)
class SessionTombstone:
    token_digest: bytes
    snapshot: AssessmentSessionSnapshot
    bundle_id: str | None
    expires_at_monotonic: float


class AssessmentApplyLease:
    __slots__ = ("_bundle_id", "_finish_record", "_record", "_released")

    def __init__(
        self,
        record: SessionRecord,
        finish_record: Callable[
            [SessionRecord, AssessmentSessionState, str | None], None
        ],
    ) -> None:
        self._record = record
        self._finish_record = finish_record
        self._bundle_id: str | None = None
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
        if exc_type is None and self._bundle_id is None:
            self.mark_applied()
        state = AssessmentSessionState.APPLIED if exc_type is None or self._bundle_id else (
            AssessmentSessionState.FAILED_TERMINAL
        )
        self._finish(state)
        return False

    def mark_applied(self) -> None:
        self._bundle_id = f"assessment-{self._record.session_id}"

    def fail(self) -> None:
        self._finish(AssessmentSessionState.FAILED_TERMINAL)

    def _finish(self, state: AssessmentSessionState) -> None:
        if self._released:
            return
        self._record.state = state
        bundle_id = self._bundle_id if state is AssessmentSessionState.APPLIED else None
        self._finish_record(self._record, state, bundle_id)
        self._released = True
        self._record.lock.release()


__all__ = [
    "AssessmentApplyLease",
    "AssessmentSessionPolicy",
    "AssessmentSessionSnapshot",
    "AssessmentSessionState",
    "CreatedAssessmentSession",
    "SESSION_CAPACITY",
    "SESSION_TTL_SECONDS",
    "SessionRecord",
    "SessionTombstone",
]
