from __future__ import annotations

import multiprocessing as mp
import queue as queue_mod

import time
from typing import Any, Callable


def _invoke(queue, func: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
    try:
        queue.put(("ok", func(*args, **kwargs)))
    except BaseException as exc:  # pragma: no cover - exercised through parent API
        queue.put(
            (
                "error",
                {
                    "error": str(exc),
                    "error_type": exc.__class__.__name__,
                },
            )
        )



def run_with_timeout(func: Callable[..., Any], *args: Any, timeout_seconds: float, **kwargs: Any) -> dict[str, Any]:
    if timeout_seconds <= 0:
        return {"ok": True, "timed_out": False, "result": func(*args, **kwargs)}

    ctx = mp.get_context("spawn")
    queue = ctx.Queue()
    process = ctx.Process(target=_invoke, args=(queue, func, args, kwargs), daemon=True)
    started = time.monotonic()
    process.start()
    process.join(timeout_seconds)

    if process.is_alive():
        process.terminate()
        process.join(1.0)
        if process.is_alive() and hasattr(process, "kill"):
            process.kill()
            process.join(1.0)
        return {
            "ok": False,
            "timed_out": True,
            "state": "timeout_outcome_unknown",
            "may_have_partially_applied": True,
            "timeout_seconds": timeout_seconds,
            "elapsed_seconds": round(time.monotonic() - started, 2),
            "error": "operation timed out in isolated worker",
        }

    receipt_wait_seconds = min(max(timeout_seconds, 0.1), 1.0)
    try:
        status, payload = queue.get(timeout=receipt_wait_seconds)
    except queue_mod.Empty:
        return {
            "ok": False,
            "timed_out": False,
            "state": "worker_failed",
            "may_have_partially_applied": True,
            "timeout_seconds": timeout_seconds,
            "elapsed_seconds": round(time.monotonic() - started, 2),
            "error": "worker exited without returning a result",
        }
    if status == "error":
        return {
            "ok": False,
            "timed_out": False,
            "state": "worker_error",
            "may_have_partially_applied": True,
            "timeout_seconds": timeout_seconds,
            "elapsed_seconds": round(time.monotonic() - started, 2),
            **payload,
        }

    return {
        "ok": True,
        "timed_out": False,
        "result": payload,
        "timeout_seconds": timeout_seconds,
        "elapsed_seconds": round(time.monotonic() - started, 2),
    }
