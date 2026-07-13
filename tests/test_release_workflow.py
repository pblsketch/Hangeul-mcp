"""Focused coverage for the verified release workflow."""

from pathlib import Path


WORKFLOW = Path(".github/workflows/release.yml")


def _workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_release_workflow_triggers_on_tags_and_manual_dispatch():
    text = _workflow()
    assert "name: Release" in text
    assert "workflow_dispatch:" in text
    assert "tags:" in text
    assert "- 'v*'" in text or '- "v*"' in text


def test_release_workflow_builds_tests_checks_and_uploads_artifacts():
    text = _workflow()
    assert "python -m build" in text
    assert "pytest -q" in text
    assert "twine check dist/*" in text
    assert "actions/upload-artifact" in text
    assert "dist" in text


def test_release_workflow_uses_trusted_publishing_gate():
    text = _workflow()
    assert "id-token: write" in text
    assert "environment: pypi" in text
    assert "pypa/gh-action-pypi-publish" in text
    assert "needs: build" in text


def test_release_workflow_stays_honest_about_publish_state():
    text = _workflow().lower()
    assert "trusted publishing is configured" in text
    assert "registry and clean-install verification" in text
    assert "publication success" not in text
    assert "already published" not in text
