from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias


@dataclass(frozen=True)
class Feedback:
    correct: str
    incorrect: str


@dataclass(frozen=True)
class Choice:
    choice_id: str
    text: str


@dataclass(frozen=True)
class LearningEvidence:
    evidence_id: str
    claim: str
    expected_evidence: str


@dataclass(frozen=True)
class RubricLevel:
    level_id: str
    min_score: int
    max_score: int
    descriptor: str


@dataclass(frozen=True)
class RubricCriterion:
    criterion_id: str
    description: str
    levels: tuple[RubricLevel, ...]


@dataclass(frozen=True)
class Rubric:
    criteria: tuple[RubricCriterion, ...]


@dataclass(frozen=True)
class MultipleChoiceItem:
    item_id: str
    order: int
    type: str
    stem: str
    points: int
    evidence_ids: tuple[str, ...]
    choices: tuple[Choice, ...]
    answer: str
    rationale: str
    misconceptions: tuple[str, ...]
    feedback: Feedback
    rubric: None = None


@dataclass(frozen=True)
class ShortAnswerItem:
    item_id: str
    order: int
    type: str
    stem: str
    points: int
    evidence_ids: tuple[str, ...]
    answer: tuple[str, ...]
    rationale: str
    misconceptions: tuple[str, ...]
    feedback: Feedback
    choices: tuple[Choice, ...] = ()
    rubric: None = None


@dataclass(frozen=True)
class ConstructedResponseItem:
    item_id: str
    order: int
    type: str
    stem: str
    points: int
    evidence_ids: tuple[str, ...]
    answer: str
    rationale: str
    misconceptions: tuple[str, ...]
    feedback: Feedback
    rubric: Rubric
    choices: tuple[Choice, ...] = ()


AssessmentItem: TypeAlias = MultipleChoiceItem | ShortAnswerItem | ConstructedResponseItem
AssessmentAnswer: TypeAlias = str | tuple[str, ...]


@dataclass(frozen=True)
class AssessmentMetadata:
    title: str
    subject: str
    grade: str
    unit: str
    learning_objectives: tuple[str, ...]
    total_points: int


@dataclass(frozen=True)
class AssessmentSpec:
    spec_version: int
    profile_id: str
    metadata: AssessmentMetadata
    learning_evidence: tuple[LearningEvidence, ...]
    items: tuple[AssessmentItem, ...]
    spec_fingerprint: str


__all__ = [
    "AssessmentAnswer", "AssessmentItem", "AssessmentMetadata", "AssessmentSpec",
    "Choice", "ConstructedResponseItem", "Feedback", "LearningEvidence",
    "MultipleChoiceItem", "Rubric", "RubricCriterion", "RubricLevel", "ShortAnswerItem",
]
