from __future__ import annotations
import os


import time

from hangeul_core.live_timeout import run_with_timeout
from hangeul_mcp import server


def _exit_immediately():
    os._exit(0)



def test_run_with_timeout_reports_timeout_and_keeps_session_responsive(tmp_path):
    timed = run_with_timeout(time.sleep, 0.2, timeout_seconds=0.05)
    assert timed["ok"] is False
    assert timed["timed_out"] is True
    assert timed["state"] == "timeout_outcome_unknown"
    assert timed["may_have_partially_applied"] is True

    st = server.hwp_status()
    assert st["server_instance_id"]
    assert "attach_ladder" in st



def test_run_with_timeout_returns_successful_result():
    # Process spawn can exceed 0.5s on loaded Windows/WSL CI hosts. This test
    # verifies the successful worker path rather than the sub-second deadline.
    res = run_with_timeout(time.sleep, 0.0, timeout_seconds=3.0)
    assert res["ok"] is True
    assert res["timed_out"] is False
    assert res["result"] is None


def test_run_with_timeout_reads_worker_result_without_trusting_queue_empty(monkeypatch):
    import hangeul_core.live_timeout as live_timeout

    class LyingQueue:
        def empty(self):
            return True

        def get(self, timeout=None):
            return ("ok", "delivered")

    class FinishedProcess:
        def start(self):
            return None

        def join(self, timeout=None):
            return None

        def is_alive(self):
            return False

    class FakeContext:
        def Queue(self):
            return LyingQueue()

        def Process(self, target, args, daemon):
            return FinishedProcess()

    monkeypatch.setattr(live_timeout.mp, "get_context", lambda method: FakeContext())

    res = live_timeout.run_with_timeout(lambda: "unused", timeout_seconds=0.5)
    assert res["ok"] is True
    assert res["result"] == "delivered"


def test_run_with_timeout_reports_worker_exit_without_result():
    res = run_with_timeout(_exit_immediately, timeout_seconds=3.0)
    assert res["ok"] is False
    assert res["timed_out"] is False
    assert res["state"] == "worker_failed"
    assert res["may_have_partially_applied"] is True


def test_run_with_timeout_marks_worker_error_as_unknown_outcome():
    res = run_with_timeout(int, "x", timeout_seconds=0.5)
    assert res["ok"] is False
    assert res["state"] == "worker_error"
    assert res["may_have_partially_applied"] is True



def test_open_in_hwp_timeout_contract(monkeypatch, tmp_path):
    import hangeul_mcp.tools_live as live_tools

    src = tmp_path / "sample.hwpx"
    src.write_text("x", encoding="utf-8")

    monkeypatch.setattr(
        live_tools,
        "_run_open_in_hwp_timed",
        lambda path, visible, timeout_seconds: {
            "available": True,
            "ok": False,
            "state": "timeout_outcome_unknown",
            "may_have_partially_applied": True,
            "requested_path": path,
            "timeout_seconds": timeout_seconds,
        },
    )

    res = server.open_in_hwp(str(src), timeout_seconds=0.01)
    assert res["state"] == "timeout_outcome_unknown"
    assert res["may_have_partially_applied"] is True
    assert res["timeout_seconds"] == 0.01
