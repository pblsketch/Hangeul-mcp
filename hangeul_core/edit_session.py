from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Dict, Mapping, Optional


from hangeul_core.analyze import _section_names
from hangeul_core.locate import replace_literals
from hangeul_core.owpml import HwpxPackage

OWN_TEXT_SUBSTRATE = "own.byte_preserving_text"
_JOURNAL_VERSION = 1
_SESSIONS: Dict[str, "_SessionState"] = {}


@dataclass(frozen=True)
class EditPlan:
    session_id: str
    kind: str
    substrate: str
    source_path: str
    source_sha256: str
    mapping: Mapping[str, str] = MappingProxyType({})
    counts: Mapping[str, int] = MappingProxyType({})
    total: int = 0
    changed_entries: tuple[str, ...] = ()
    audit: tuple[str, ...] = ()



@dataclass(frozen=True)
class EditSession:
    session_id: str
    kind: str
    substrate: str
    source_path: str
    target_path: str
    journal_path: str
    snapshot_path: str
    counts: Mapping[str, int] = MappingProxyType({})
    total: int = 0
    changed_entries: tuple[str, ...] = ()
    audit: tuple[str, ...] = ()



@dataclass(frozen=True)
class RestoreResult:
    session_id: str
    substrate: str
    target_path: str
    journal_path: str
    snapshot_path: str
    restored: bool
    target_exists: bool


@dataclass
class _SessionState:
    plan: EditPlan
    applied: bool = False


def preview_batch_replace(path: str | Path, mapping: Dict[str, str]) -> EditPlan:
    source = Path(path)
    pkg = HwpxPackage.open(source)
    normalized = dict(mapping)
    counts: Dict[str, int] = {}
    changed_entries: list[str] = []
    audit: list[str] = []
    for sname in _section_names(pkg):
        text = pkg.read(sname).decode("utf-8")
        _, section_counts = replace_literals(text, normalized)
        if not section_counts:
            continue
        changed_entries.append(sname)
        for key, value in section_counts.items():
            counts[key] = counts.get(key, 0) + value
        summary = ", ".join(f"{key}×{section_counts[key]}" for key in sorted(section_counts))
        audit.append(f"{sname}: {sum(section_counts.values())} replacement(s) [{summary}]")
    plan = EditPlan(
        session_id=uuid.uuid4().hex,
        kind="batch_replace",
        substrate=OWN_TEXT_SUBSTRATE,
        source_path=str(source),
        source_sha256=_sha256_path(source),
        mapping=MappingProxyType(dict(normalized)),
        counts=MappingProxyType(dict(counts)),
        total=sum(counts.values()),
        changed_entries=tuple(changed_entries),
        audit=tuple(audit or ["No matching replacements found."]),

    )
    _SESSIONS[plan.session_id] = _SessionState(plan=plan)
    return plan


def preview_search_and_replace(path: str | Path, find: str, replace: str) -> EditPlan:
    plan = preview_batch_replace(path, {find: replace})
    wrapped = EditPlan(
        session_id=plan.session_id,
        kind="search_and_replace",
        substrate=plan.substrate,
        source_path=plan.source_path,
        source_sha256=plan.source_sha256,
        mapping=plan.mapping,
        counts=plan.counts,
        total=plan.total,
        changed_entries=plan.changed_entries,
        audit=plan.audit,

    )
    _SESSIONS[plan.session_id] = _SessionState(plan=wrapped)
    return wrapped


def apply_edit_session(session_id: str, out_path: Optional[str | Path] = None) -> EditSession:
    state = _SESSIONS.get(session_id)
    if state is None:
        raise KeyError(f"unknown edit session: {session_id}")
    if state.applied:
        raise RuntimeError(f"edit session already applied: {session_id}")
    plan = state.plan
    source = Path(plan.source_path)
    if _sha256_path(source) != plan.source_sha256:
        raise RuntimeError("source file changed after preview; create a new preview before apply")

    target = Path(out_path) if out_path is not None else source
    snapshot_path = _snapshot_path(target, session_id)
    journal_path = _journal_path(target, session_id)
    target_existed = target.exists()
    snapshot_source = target if target_existed else source
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(snapshot_source, snapshot_path)

    pkg = HwpxPackage.open(source)
    counts: Dict[str, int] = {}
    changed_entries: list[str] = []
    audit: list[str] = []
    for sname in _section_names(pkg):
        text = pkg.read(sname).decode("utf-8")
        newtext, section_counts = replace_literals(text, plan.mapping)
        if not section_counts:
            continue
        pkg.replace(sname, newtext.encode("utf-8"))
        changed_entries.append(sname)
        for key, value in section_counts.items():
            counts[key] = counts.get(key, 0) + value
        summary = ", ".join(f"{key}×{section_counts[key]}" for key in sorted(section_counts))
        audit.append(f"{sname}: {sum(section_counts.values())} replacement(s) [{summary}]")

    target.parent.mkdir(parents=True, exist_ok=True)
    pkg.save(target)
    state.applied = True

    journal = {
        "journal_version": _JOURNAL_VERSION,
        "session_id": session_id,
        "kind": plan.kind,
        "substrate": plan.substrate,
        "source_path": str(source),
        "source_sha256": plan.source_sha256,
        "target_path": str(target),
        "target_existed_before_apply": target_existed,
        "snapshot_path": str(snapshot_path),
        "snapshot_role": "target_before_apply" if target_existed else "source_reference",
        "applied_target_sha256": _sha256_path(target),
        "counts": counts,
        "total": sum(counts.values()),
        "changed_entries": changed_entries,
        "audit": audit or ["No matching replacements found."],
        "created_at": _utc_now(),
    }
    journal_path.write_text(json.dumps(journal, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return EditSession(
        session_id=session_id,
        kind=plan.kind,
        substrate=plan.substrate,
        source_path=str(source),
        target_path=str(target),
        journal_path=str(journal_path),
        snapshot_path=str(snapshot_path),
        counts=MappingProxyType(dict(counts)),
        total=sum(counts.values()),
        changed_entries=tuple(changed_entries),
        audit=tuple(journal["audit"]),
    )


def restore_edit_session(journal_path: str | Path) -> RestoreResult:
    journal_file = Path(journal_path)
    payload = json.loads(journal_file.read_text(encoding="utf-8"))
    if payload.get("journal_version") != _JOURNAL_VERSION:
        raise RuntimeError("unsupported edit session journal version")
    if payload.get("substrate") != OWN_TEXT_SUBSTRATE:
        raise RuntimeError("restore_session only supports own.byte_preserving_text journals")

    target = Path(str(payload["target_path"]))
    snapshot = Path(str(payload["snapshot_path"]))
    if not snapshot.exists():
        raise FileNotFoundError(f"missing restore snapshot: {snapshot}")
    applied_target_sha256 = str(payload.get("applied_target_sha256") or "")
    if not applied_target_sha256:
        raise RuntimeError("restore journal is missing applied_target_sha256")

    target_exists_now = target.exists()
    if not target_exists_now and not payload.get("target_existed_before_apply"):
        raise RuntimeError("target changed after apply; refusing restore")
    if target_exists_now and _sha256_path(target) != applied_target_sha256:
        raise RuntimeError("target changed after apply; refusing restore")

    if payload.get("target_existed_before_apply"):
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(snapshot, target)
        target_exists = True
    else:
        target.unlink()
        target_exists = False

    return RestoreResult(
        session_id=str(payload["session_id"]),
        substrate=str(payload["substrate"]),
        target_path=str(target),
        journal_path=str(journal_file),
        snapshot_path=str(snapshot),
        restored=True,
        target_exists=target_exists,
    )


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _journal_path(target: Path, session_id: str) -> Path:
    return target.with_name(f".{target.name}.edit-session-{session_id}.journal.json")


def _snapshot_path(target: Path, session_id: str) -> Path:
    suffix = "".join(target.suffixes) or ".bin"
    return target.with_name(f".{target.name}.edit-session-{session_id}.snapshot{suffix}")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = [
    "EditPlan",
    "EditSession",
    "OWN_TEXT_SUBSTRATE",
    "RestoreResult",
    "apply_edit_session",
    "preview_batch_replace",
    "preview_search_and_replace",
    "restore_edit_session",
]
