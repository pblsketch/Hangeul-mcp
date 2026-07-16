from pathlib import Path

from scripts.check_artifact_hygiene import FindingCode
from scripts.check_artifact_hygiene import check_paths
from scripts.check_artifact_hygiene import repository_runtime_findings


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_repository_contains_no_assessment_runtime_artifacts() -> None:
    assert repository_runtime_findings(REPOSITORY_ROOT) == ()


def test_artifact_hygiene_checker_rejects_forbidden_text_and_runtime_artifact_fixtures(
    tmp_path: Path,
) -> None:
    clean = tmp_path / "clean.md"
    clean.write_text(
        "[local documentation](docs/guide.md)\n"
        "[project source](https://github.com/pblsketch/Hangeul-mcp)\n",
        encoding="utf-8",
    )
    assert check_paths((clean,), repository_root=tmp_path) == ()

    text_cases = {
        FindingCode.ABSOLUTE_LOCAL_PATH: r"private source: C:\Users\account\notes.txt",
        FindingCode.TEMPORARY_EXECUTABLE: r"Downloads\payload.exe",
        FindingCode.BINARY_DIGEST: "a" * 64,
        FindingCode.FORBIDDEN_MARKDOWN_LINK: (
            "[private reference](https://example.invalid/source)"
        ),
    }
    for code, content in text_cases.items():
        fixture = tmp_path / f"{code}.md"
        fixture.write_text(content, encoding="utf-8")
        assert {finding.code for finding in check_paths((fixture,), repository_root=tmp_path)} == {
            code
        }

    runtime_cases = {
        FindingCode.RUNTIME_STAGING: tmp_path
        / ".hangeul-assessment-staging-session-nonce",
        FindingCode.RUNTIME_JOURNAL: tmp_path / "assessment-session.journal.json",
        FindingCode.RUNTIME_SNAPSHOT: tmp_path / "assessment-session.snapshot.json",
        FindingCode.RUNTIME_HWPX: tmp_path / "assessment-session" / "student.hwpx",
    }
    for code, fixture in runtime_cases.items():
        fixture.parent.mkdir(parents=True, exist_ok=True)
        if fixture.suffix:
            fixture.write_bytes(b"fixture")
        else:
            fixture.mkdir()
        assert {
            finding.code
            for finding in check_paths((fixture,), repository_root=tmp_path)
        } == {code}
