"""Reboot: the device drops the connection while restarting (seen on hardware), which must count as success."""
import asyncio
import pathlib
import sys

import aiohttp
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "custom_components"))
from _stubs import with_platform  # noqa: E402,F401  (installs the Home Assistant stubs the package imports)
from deeper_connect.api import DeeperAuthError, DeeperClient, DeeperConnectionError  # noqa: E402
from deeper_connect.entity import check_response  # noqa: E402


class Stub(DeeperClient):
    def __init__(self, post_exc=None, resp=None, login_exc=None):
        self.post_exc, self.resp, self.login_exc, self.calls = post_exc, resp or {"success": True}, login_exc, []

    async def ensure_login(self):
        if self.login_exc:
            raise self.login_exc

    async def post(self, path, json=None):
        self.calls.append(path)
        if self.post_exc:
            raise self.post_exc
        return self.resp


def reboot(c):
    return asyncio.run(c.reboot())


def cut(exc_type=aiohttp.ServerDisconnectedError):
    err = DeeperConnectionError("cut")
    err.__cause__ = exc_type()
    return err


def test_normal_answer_passes_through():
    c = Stub()
    assert reboot(c) == {"success": True} and c.calls == ["/api/admin/reboot"]


def test_timeout_means_rebooting():
    assert reboot(Stub(post_exc=asyncio.TimeoutError()))["success"] is True


def test_dropped_connection_means_rebooting():
    assert reboot(Stub(post_exc=cut()))["success"] is True
    assert reboot(Stub(post_exc=cut(aiohttp.ClientConnectionError)))["success"] is True


def test_http_error_is_not_swallowed():
    err = DeeperConnectionError("500")
    err.__cause__ = aiohttp.ClientResponseError(None, (), status=500)
    with pytest.raises(DeeperConnectionError):
        reboot(Stub(post_exc=err))


def test_auth_failure_is_not_swallowed():
    with pytest.raises(DeeperAuthError):
        reboot(Stub(post_exc=DeeperAuthError("unauthorized")))


def test_unreachable_device_fails_at_login_and_never_sends_reboot():
    c = Stub(login_exc=DeeperConnectionError("no route"))
    with pytest.raises(DeeperConnectionError):
        reboot(c)
    assert c.calls == []
    c = Stub(login_exc=asyncio.TimeoutError())
    with pytest.raises(asyncio.TimeoutError):
        reboot(c)
    assert c.calls == []


def test_explicit_refusal_still_raises_in_the_button_path():
    with pytest.raises(Exception):
        check_response(reboot(Stub(resp={"success": False, "reason": "nope"})))


def test_timeout_wrapped_as_connection_error_still_means_rebooting():
    err = DeeperConnectionError("TimeoutError")
    err.__cause__ = asyncio.TimeoutError()
    assert reboot(Stub(post_exc=err))["success"] is True
