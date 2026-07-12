import importlib
from pathlib import Path


import pytest


class FakeHwp:
    def __init__(self):
        self.opened = []

    def open(self, path):
        self.opened.append(path)
        return True


class FakeRefill:
    def __init__(self, *, filled, skipped, out_path):
        self.filled = filled
        self.skipped = skipped
        self.out_path = out_path


def _fail_fill(message):
    def _fail(*args, **kwargs):
        raise AssertionError(message)

    return _fail


def _live_reload_module():
    try:
        return importlib.import_module("hangeul_core.hwp.live_reload")
    except ModuleNotFoundError:  # pragma: no cover - RED until implementation lands
        pytest.fail(
            "safe-attach reload helper missing: expected hangeul_core.hwp.live_reload"
        )


def test_reload_if_unreached_is_a_noop_without_unreached():
    mod = _live_reload_module()
    hwp = FakeHwp()
    result = {
        "state": "attached_existing",
        "attached_existing": True,
        "opened": False,
        "applied": [{"label": "성명", "value": "홍길동"}],
        "skipped": [{"key": "성명", "reason": "different validation failure"}],
        "count": 1,
    }

    out = mod.reload_if_unreached(hwp, Path("C:/forms/form.hwpx"), {"성명": "홍길동"}, result)

    assert out is result
    assert result["state"] == "attached_existing"
    assert hwp.opened == []
    assert "file_reload" not in result
    assert "unreached" not in result



def test_reload_if_unreached_blocks_reload_for_attached_existing(monkeypatch):
    mod = _live_reload_module()
    hwp = FakeHwp()

    monkeypatch.setattr(
        mod,
        "fill",
        _fail_fill("attached_existing must not fall back to file-mode refill"),
        raising=False,
    )
    blocked = {"key": "성명", "reason": "cell address not reachable"}
    result = {
        "state": "attached_existing",
        "attached_existing": True,
        "opened": False,
        "applied": [],
        "skipped": [blocked],
        "count": 0,
    }

    out = mod.reload_if_unreached(hwp, Path("C:/forms/form.hwpx"), {"성명": "홍길동"}, result)

    assert out is result
    assert result["state"] == "reload_blocked_existing"
    assert result["attached_existing"] is True
    assert result["opened"] is False
    assert result["count"] == 0
    assert result["unreached"] == [blocked]
    assert "file_reload" not in result
    assert hwp.opened == []
    warning = (result.get("warning") or result.get("error") or "").lower()
    assert "reload" in warning and ("unsaved" in warning or "discard" in warning)



def test_reload_if_unreached_keeps_opened_new_quarantined_by_default(monkeypatch):
    mod = _live_reload_module()
    hwp = FakeHwp()

    monkeypatch.setattr(
        mod,
        "fill",
        _fail_fill("opened_new must stay quarantined unless file reload is allowed"),
        raising=False,
    )
    unreached = {"key": "성명", "reason": "table not found live"}
    untouched = {"key": "비고", "reason": "no matching cell field"}
    result = {
        "state": "opened_new",
        "opened": True,
        "applied": [],
        "skipped": [unreached, untouched],
        "count": 0,
    }

    out = mod.reload_if_unreached(hwp, Path("C:/forms/form.hwpx"), {"성명": "홍길동"}, result)

    assert out is result
    assert result["state"] == "opened_new"
    assert result["unreached"] == [unreached]
    assert result["skipped"] == [untouched, unreached]
    assert result["count"] == 0
    assert "file_reload" not in result
    assert hwp.opened == []


def test_reload_if_unreached_reopens_opened_new_only_with_allow_file_reload(monkeypatch):
    mod = _live_reload_module()
    hwp = FakeHwp()
    seen = {}

    def fake_fill(path, values, out_path, **kwargs):
        seen["path"] = str(path)
        seen["values"] = dict(values)
        seen["out_path"] = str(out_path)
        return FakeRefill(
            filled=[{"label": "성명", "value": "홍길동"}],
            skipped=[],
            out_path=str(out_path),
        )

    monkeypatch.setattr(mod, "fill", fake_fill, raising=False)
    path = Path("C:/forms/form.hwpx")
    unreached = {"key": "성명", "reason": "table not found live"}
    untouched = {"key": "비고", "reason": "no matching cell field"}
    result = {
        "state": "opened_new",
        "opened": True,
        "allow_file_reload": True,
        "applied": [],
        "skipped": [unreached, untouched],
        "count": 0,
    }

    out = mod.reload_if_unreached(hwp, path, {"성명": "홍길동"}, result)

    assert out is result
    assert result["state"] == "opened_new"
    assert seen["path"] == str(path)
    assert seen["values"] == {"성명": "홍길동"}
    assert hwp.opened == [seen["out_path"]]
    assert result["skipped"] == [untouched]
    assert "file_reload" in result
    assert any(item.get("via") == "file_reload" for item in result["applied"])
