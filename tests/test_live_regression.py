from __future__ import annotations

from hangeul_core.live_regression import build_windows_live_artifact, validate_windows_live_artifact



def test_build_current_document_artifact_template_requires_all_refs():
    payload = build_windows_live_artifact("current_document")
    assert payload["flow"] == "current_document"
    assert set(payload["jsonRefs"]) == {"status", "resolve", "preview", "apply"}



def test_validate_windows_live_artifact_rejects_missing_current_document_refs():
    payload = build_windows_live_artifact("current_document")
    payload["jsonRefs"]["status"] = "status.json"
    payload["jsonRefs"]["preview"] = "preview.json"
    payload["jsonRefs"]["apply"] = "apply.json"
    payload["screenshotPath"] = "capture.png"
    payload["readback"]["verified"] = True

    report = validate_windows_live_artifact(payload)

    assert report["valid"] is False
    assert "jsonRefs.resolve is required" in report["errors"]



def test_validate_windows_live_artifact_accepts_exact_path_capture():
    payload = build_windows_live_artifact("exact_path")
    payload["jsonRefs"].update(
        {
            "status": "status.json",
            "preview": "preview.json",
            "apply": "apply.json",
        }
    )
    payload["readback"]["verified"] = True
    payload["screenshotPath"] = "capture.png"

    report = validate_windows_live_artifact(payload)

    assert report == {"valid": True, "errors": []}
