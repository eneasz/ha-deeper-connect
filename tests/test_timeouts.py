"""A device that is off or silent makes requests time out. That must surface as DeeperConnectionError everywhere.

Otherwise the config flow reports "unknown" instead of "cannot connect", and (worse) the coordinator never notes the
failure, so the "device not reachable" Repairs issue would not appear for the most common way a device is unreachable.
"""
import asyncio
import pathlib
import sys

import aiohttp
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "custom_components"))
from _stubs import with_platform  # noqa: E402,F401
from deeper_connect.api import DeeperAuthError, DeeperClient, DeeperConnectionError  # noqa: E402


class _Ctx:
    def __init__(self, exc=None, payload=None):
        self.exc, self.payload = exc, payload

    async def __aenter__(self):
        if self.exc:
            raise self.exc
        return self

    async def __aexit__(self, *a):
        return False

    status = 200

    def raise_for_status(self):
        pass

    async def json(self, content_type=None):
        return self.payload


class Session:
    def __init__(self, exc=None, payload=None):
        self.exc, self.payload = exc, payload

    def get(self, *a, **k):
        return _Ctx(self.exc, self.payload)

    post = request = get


def client(exc=None, payload=None, logged_in=True):
    c = DeeperClient(Session(exc, payload), "192.0.2.1", "admin", "pw")
    c._logged_in = logged_in
    return c


ERRORS = [asyncio.TimeoutError(), aiohttp.ClientConnectionError("no route"), aiohttp.ServerDisconnectedError()]


@pytest.mark.parametrize("exc", ERRORS)
def test_login_failures_to_reach_the_device_are_connection_errors(exc):
    with pytest.raises(DeeperConnectionError):
        asyncio.run(client(exc, logged_in=False).login())


@pytest.mark.parametrize("exc", ERRORS)
def test_device_id_failures_are_connection_errors(exc):
    with pytest.raises(DeeperConnectionError):
        asyncio.run(client(exc).device_id())


@pytest.mark.parametrize("exc", ERRORS)
def test_get_and_post_failures_are_connection_errors(exc):
    with pytest.raises(DeeperConnectionError):
        asyncio.run(client(exc).get("/api/x"))
    with pytest.raises(DeeperConnectionError):
        asyncio.run(client(exc).post("/api/x", {}))


def test_timeout_message_is_not_empty():
    with pytest.raises(DeeperConnectionError, match="TimeoutError"):
        asyncio.run(client(asyncio.TimeoutError()).get("/api/x"))


def test_a_rejected_login_is_still_an_auth_error_not_a_connection_error():
    with pytest.raises(DeeperAuthError):
        asyncio.run(client(None, {"success": False}, logged_in=False).login())
