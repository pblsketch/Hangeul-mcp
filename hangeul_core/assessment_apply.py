from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal


ApplyErrorCode = Literal[
    "source_output_collision",
    "stale_plan",
    "stale_profile",
    "stale_source",
]


class ApplyError(ValueError):
    __slots__ = ("code",)

    def __init__(self, code: ApplyErrorCode) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class ApplyPreconditions:
    source_path: Path
    output_path: Path
    expected_source_digest: str
    current_profile_definition_digest: str
    expected_profile_definition_digest: str
    current_plan_digest: str
    expected_plan_digest: str

    def with_expected_source_digest(self, digest: str) -> ApplyPreconditions:
        return replace(self, expected_source_digest=digest)

    def with_current_profile_digest(self, digest: str) -> ApplyPreconditions:
        return replace(self, current_profile_definition_digest=digest)

    def with_current_plan_digest(self, digest: str) -> ApplyPreconditions:
        return replace(self, current_plan_digest=digest)


def validate_apply(preconditions: ApplyPreconditions) -> None:
    current_source_digest: str | None
    try:
        current_source_digest = hashlib.sha256(preconditions.source_path.read_bytes()).hexdigest()
    except OSError:
        current_source_digest = None
    if (
        current_source_digest is None
        or current_source_digest != preconditions.expected_source_digest
    ):
        raise ApplyError("stale_source")
    if (
        preconditions.current_profile_definition_digest
        != preconditions.expected_profile_definition_digest
    ):
        raise ApplyError("stale_profile")
    if preconditions.current_plan_digest != preconditions.expected_plan_digest:
        raise ApplyError("stale_plan")

    source: Path | None
    output: Path | None
    try:
        source = preconditions.source_path.resolve(strict=True)
        output = preconditions.output_path.resolve(strict=False)
    except OSError:
        source = None
        output = None
    if source is None or output is None:
        raise ApplyError("stale_source")
    if source == output:
        raise ApplyError("source_output_collision")
    identity_failed = False
    output_collides = False
    try:
        output_collides = (
            preconditions.output_path.exists()
            and source.samefile(preconditions.output_path)
        )
    except OSError:
        identity_failed = True
    if identity_failed or output_collides:
        raise ApplyError("source_output_collision")


__all__ = ["ApplyError", "ApplyPreconditions", "validate_apply"]
