from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_decisions_records_separate_management_cli_and_versioned_runtime_launcher():
    doc = _read("docs/DECISIONS.md")
    for required in [
        "hangeul-mcp-manage",
        "MCP stdio 서버",
        "stable launcher",
        "versioned runtime",
        "versions/",
        "rollback",
    ]:
        assert required in doc



def test_workflow_documents_management_doc_tdd_slice():
    doc = _read("docs/feature-implementation-workflow.md")
    for required in [
        "관리/설치",
        "RED",
        "tests/test_docs_manage_install.py",
        "doctor --json",
        "SECURITY.md",
    ]:
        assert required in doc



def test_research_strategy_documents_managed_setup_and_honest_update_checks():
    doc = _read("docs/research-strategy.md")
    for required in [
        "hangeul-mcp-manage setup",
        "sys.executable -m hangeul_mcp.server",
        "PyPI JSON API",
        "not_published",
        "com",
        "live",
    ]:
        assert required in doc



def test_security_documents_trust_boundaries_and_backup_sensitivity():
    doc = _read("docs/SECURITY.md")
    for required in [
        "allowlisted",
        "PyPI unavailable",
        "not_published",
        "backup",
        "rollback",
        "stable launcher",
        "stderr/file only",
    ]:
        assert required in doc
