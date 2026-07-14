"""Non-destructive response envelope for MCP tools.

Converges the historical per-module error shapes on common `available`/`ok`
keys by ADDING them when missing — existing keys are never removed, renamed,
or overwritten, so legacy clients keep working.
"""

from __future__ import annotations

import functools
from typing import Any


def enveloped(fn):
    """Ensure a dict-returning tool answer carries `available` and `ok`.

    `ok` defaults to False when the answer carries an `error` or reports
    itself unavailable; non-dict answers pass through untouched.
    """

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any):
        result = fn(*args, **kwargs)
        if isinstance(result, dict):
            result.setdefault("available", True)
            result.setdefault("ok", "error" not in result and result.get("available") is not False)
        return result

    return wrapper
