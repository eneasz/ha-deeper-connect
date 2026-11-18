"""An expired session must cost ONE login, not one per parallel request, and a lockout must not look like a bad password.

Regression for the 18 Nov 2026 failure: the poll runs ~12 requests in parallel; when the device's session expired every
one of them saw a 401 and logged in on its own. The device read that burst as an attack, refused all logins, and the old
code then raised a re-authentication request ("login rejected") although the password had not changed.
"""
import asyncio
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "custom_components"))
from _stubs import with_platform  # noqa: E402,F401
from deeper_connect.api import DeeperAuthError, DeeperClient  # noqa: E402


class _Resp:
    def __init__(self, status=200, payload=None):
        self.status, self.payload = status, payload if payload is not None else {"success": True}

    async def __aenter__(self):
        await asyncio.sleep(0)  # let the parallel requests interleave like real network I/O
        return self

    async def __aexit__(self, *a):
        return False

    def raise_for_status(self):
        pass

    async def json(self, content_type=None):
        return self.payload


class Device:
    """Fake device: logins open a session, requests without one get 401, a lockout rejects every login."""

    def __init__(self):
        self.session_ok = False
        self.logins = 0
        self.locked = False

    def post(self, url, **k):  # login
        self.logins += 1
        if self.locked:
            return _Resp(200, {"success": False})
        self.session_ok = True
        return _Resp()

    def request(self, method, url, **k):
        return _Resp(200, {"ok": 1}) if self.session_ok else _Resp(401)


def make(dev):
    return DeeperClient(dev, "192.0.2.1", "admin", "pw")


def test_parallel_requests_after_session_expiry_log_in_once():
    dev = Device()
    c = make(dev)

    async def go():
        await c.get("/x")  # first login
        dev.session_ok = False  # the device drops the session
        dev.logins = 0
        return await asyncio.gather(*(c.get(f"/p{i}") for i in range(12)))

    assert all(r == {"ok": 1} for r in asyncio.run(go()))
    assert dev.logins == 1


def test_rejected_login_after_a_good_session_backs_off_instead_of_retrying():
    dev = Device()
    c = make(dev)

    async def go():
        await c.get("/x")
        dev.session_ok, dev.locked, dev.logins = False, True, 0
        for _ in range(3):
            with pytest.raises(DeeperAuthError):
                await c.get("/y")

    asyncio.run(go())
    assert dev.logins == 1  # the later polls did not poke the device again
    assert c.ever_logged_in


def test_backoff_ends_and_login_recovers(monkeypatch):
    import deeper_connect.api as api
    dev = Device()
    c = make(dev)

    async def go():
        await c.get("/x")
        dev.session_ok, dev.locked = False, True
        with pytest.raises(DeeperAuthError):
            await c.get("/y")
        dev.locked = False
        monkeypatch.setattr(api.time, "monotonic", lambda: c._blocked_until + 1)
        return await c.get("/y")

    assert asyncio.run(go()) == {"ok": 1}


def test_first_ever_login_rejected_is_a_real_auth_error_without_backoff():
    dev = Device()
    dev.locked = True
    c = make(dev)
    with pytest.raises(DeeperAuthError):
        asyncio.run(c.get("/x"))
    assert not c.ever_logged_in and c._blocked_until == 0.0
