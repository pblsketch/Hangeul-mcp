from __future__ import annotations

import socket
import ssl
from urllib.error import HTTPError

from hangeul_mcp import managed


class FakeResponse:
    def __init__(self, payload: bytes):
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_check_for_updates_prefers_stable_by_default():
    payload = {
        "info": {"version": "2.0.0b1"},
        "releases": {
            "1.0.0": [{}],
            "1.1.0": [{}],
            "2.0.0b1": [{}],
        },
    }

    outcome = managed.check_for_updates(
        "1.0.0",
        fetcher=lambda: {"ok": True, "payload": payload},
        now=1_000,
    )

    assert outcome["status"] == "update_available"
    assert outcome["latest_version"] == "1.1.0"
    assert outcome["prerelease_included"] is False


def test_check_for_updates_can_include_prereleases():
    payload = {
        "info": {"version": "2.0.0b2"},
        "releases": {
            "1.1.0": [{}],
            "2.0.0b2": [{}],
        },
    }

    outcome = managed.check_for_updates(
        "1.1.0",
        fetcher=lambda: {"ok": True, "payload": payload},
        include_prerelease=True,
        now=2_000,
    )

    assert outcome["status"] == "update_available"
    assert outcome["latest_version"] == "2.0.0b2"
    assert outcome["prerelease_included"] is True


def test_fetch_pypi_metadata_structures_timeout_tls_invalid_json_and_not_found():
    timeout = managed.fetch_pypi_json(
        urlopen=lambda *args, **kwargs: (_ for _ in ()).throw(socket.timeout("slow")),
    )
    assert timeout == {"ok": False, "error": "timeout", "detail": "slow"}

    tls = managed.fetch_pypi_json(
        urlopen=lambda *args, **kwargs: (_ for _ in ()).throw(ssl.SSLError("bad cert")),
    )
    assert tls == {"ok": False, "error": "tls", "detail": "('bad cert',)"}

    invalid = managed.fetch_pypi_json(
        urlopen=lambda *args, **kwargs: FakeResponse(b"{"),
    )
    assert invalid["ok"] is False
    assert invalid["error"] == "invalid_json"

    not_found = managed.fetch_pypi_json(
        urlopen=lambda *args, **kwargs: (_ for _ in ()).throw(
            HTTPError("https://pypi.org/pypi/hangeul-mcp/json", 404, "missing", {}, None)
        ),
    )
    assert not_found == {"ok": False, "error": "http", "status": 404, "detail": "missing"}


def test_check_for_updates_reports_not_published_for_missing_package():
    outcome = managed.check_for_updates(
        "0.1.0",
        fetcher=lambda: {"ok": False, "error": "http", "status": 404, "detail": "missing"},
        now=3_000,
    )

    assert outcome["status"] == "not_published"
    assert outcome["checked_at"] == 3_000


def test_update_check_ttl_helpers_use_24_hours():
    assert managed.is_update_check_stale(None, now=86_400) is True
    assert managed.is_update_check_stale(1, now=86_400) is False
    assert managed.is_update_check_stale(1, now=86_401) is True
