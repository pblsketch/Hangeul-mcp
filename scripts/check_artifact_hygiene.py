# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
# How to run: python scripts/check_artifact_hygiene.py [changed-path ...]

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Final, Iterator, Sequence
from urllib.parse import urlsplit


class FindingCode(str, Enum):
    ABSOLUTE_LOCAL_PATH = "absolute_local_path"
    TEMPORARY_EXECUTABLE = "temporary_executable"
    BINARY_DIGEST = "binary_digest"
    FORBIDDEN_MARKDOWN_LINK = "forbidden_markdown_link"
    RUNTIME_STAGING = "runtime_staging"
    RUNTIME_JOURNAL = "runtime_journal"
    RUNTIME_SNAPSHOT = "runtime_snapshot"
    RUNTIME_HWPX = "runtime_hwpx"


@dataclass(frozen=True, slots=True)
class HygieneFinding:
    code: FindingCode
    path: Path
    line: int | None = None


_SKIPPED_DIRECTORIES: Final = frozenset(
    {".git", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".venv", "build", "dist"}
)
_ALLOWED_EXTERNAL_HOSTS: Final = frozenset(
    {
        "docs.python.org",
        "github.com",
        "oasis-open.org",
        "packaging.python.org",
        "pypi.org",
        "www.oasis-open.org",
    }
)
_GENERATED_HWPX_NAMES: Final = frozenset(
    {"answer-key.hwpx", "answer_key.hwpx", "student.hwpx", "teacher.hwpx"}
)
_ABSOLUTE_LOCAL_PATH = re.compile(
    r"(?<![\w])(?:[A-Za-z]:[\\/]|\\\\[^\\/\s]+[\\/][^\\/\s]+[\\/]"
    r"|/(?:Users|home|private|tmp|var/tmp)/)"
)
_TEMPORARY_EXECUTABLE = re.compile(
    r"(?i)(?:downloads?|temp|tmp)[\\/][^\s\"'`<>]+\.(?:bat|cmd|exe|msi|ps1|sh)\b"
)
_BINARY_DIGEST = re.compile(r"(?i)(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])")
_MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)\s]+)(?:\s+[^)]*)?\)")


def check_paths(
    paths: Sequence[Path],
    *,
    repository_root: Path,
) -> tuple[HygieneFinding, ...]:
    root = repository_root.resolve()
    findings: list[HygieneFinding] = []
    for path in _expanded_paths(paths):
        findings.extend(_runtime_findings(path, root))
        if path.is_file():
            findings.extend(_text_findings(path, root))
    return tuple(findings)


def check_artifact_hygiene(paths: tuple[Path, ...]) -> tuple[HygieneFinding, ...]:
    return check_paths(paths, repository_root=Path.cwd())


def repository_runtime_findings(repository_root: Path) -> tuple[HygieneFinding, ...]:
    root = repository_root.resolve()
    findings: list[HygieneFinding] = []
    for path in _expanded_paths((root,)):
        findings.extend(_runtime_findings(path, root))
    return tuple(findings)


def _expanded_paths(paths: Sequence[Path]) -> Iterator[Path]:
    for path in sorted(paths, key=lambda candidate: candidate.as_posix().casefold()):
        yield path
        if not path.is_dir():
            continue
        for descendant in path.rglob("*"):
            if not any(part in _SKIPPED_DIRECTORIES for part in descendant.parts):
                yield descendant


def _runtime_findings(path: Path, root: Path) -> tuple[HygieneFinding, ...]:
    relative = _display_path(path, root)
    names = tuple(part.casefold() for part in relative.parts)
    name = relative.name.casefold()
    if any(part.startswith(".hangeul-assessment-staging-") for part in names):
        return (HygieneFinding(FindingCode.RUNTIME_STAGING, relative),)
    if "assessment" in name and ".journal" in name:
        return (HygieneFinding(FindingCode.RUNTIME_JOURNAL, relative),)
    if "assessment" in name and ".snapshot" in name:
        return (HygieneFinding(FindingCode.RUNTIME_SNAPSHOT, relative),)
    if (
        path.suffix.casefold() == ".hwpx"
        and name in _GENERATED_HWPX_NAMES
        and path.parent.name.casefold().startswith("assessment-")
    ):
        return (HygieneFinding(FindingCode.RUNTIME_HWPX, relative),)
    return ()


def _text_findings(path: Path, root: Path) -> tuple[HygieneFinding, ...]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ()
    relative = _display_path(path, root)
    findings: list[HygieneFinding] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if _ABSOLUTE_LOCAL_PATH.search(line):
            findings.append(
                HygieneFinding(FindingCode.ABSOLUTE_LOCAL_PATH, relative, line_number)
            )
        if _TEMPORARY_EXECUTABLE.search(line):
            findings.append(
                HygieneFinding(FindingCode.TEMPORARY_EXECUTABLE, relative, line_number)
            )
        if _BINARY_DIGEST.search(line):
            findings.append(HygieneFinding(FindingCode.BINARY_DIGEST, relative, line_number))
        for target in _MARKDOWN_LINK.findall(line):
            if not _allowed_markdown_target(target):
                findings.append(
                    HygieneFinding(FindingCode.FORBIDDEN_MARKDOWN_LINK, relative, line_number)
                )
    return tuple(findings)


def _allowed_markdown_target(target: str) -> bool:
    if target.startswith(("#", "./", "../")) or ":" not in target:
        return True
    parsed = urlsplit(target)
    return parsed.scheme == "https" and parsed.hostname in _ALLOWED_EXTERNAL_HOSTS


def _display_path(path: Path, root: Path) -> Path:
    resolved = path.resolve(strict=False)
    try:
        return resolved.relative_to(root)
    except ValueError:
        return resolved


def main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check repository artifact hygiene.")
    parser.add_argument("paths", nargs="*", type=Path)
    parsed = parser.parse_args(arguments)
    root = Path.cwd()
    findings = (
        check_paths(parsed.paths, repository_root=root)
        if parsed.paths
        else repository_runtime_findings(root)
    )
    for finding in findings:
        location = f":{finding.line}" if finding.line is not None else ""
        print(f"{finding.code.value}:{finding.path.as_posix()}{location}")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
