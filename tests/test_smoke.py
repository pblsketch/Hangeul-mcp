"""Scaffold smoke tests (US-001): package imports and fixture presence."""

from pathlib import Path

import hangeul_core
import hangeul_mcp


def test_package_versions():
    assert hangeul_core.__version__
    assert hangeul_mcp.__version__


def test_sample_fixture_present():
    fixture = Path(__file__).parent / "fixtures" / "sample_form.hwpx"
    assert fixture.exists(), "blank sample form fixture missing"
    assert fixture.stat().st_size > 0
