"""Coordinator polling: tiers, per-endpoint failure handling, and how errors map to HA exceptions."""
import asyncio
import logging

import pytest

from _stubs import data  # noqa: F401  (also puts custom_components on sys.path)

USAGE, SOFTWARE, NETWORK = "/api/system-info/usage", "/api/system-info/software-info", "/api/system-info/network-address"
APPS = "/api/appRelocator/appsData"


class FakeClient:
    def __init__(self, tunnels=None, fail=None, tunnels_exc=None):
        self.paths: list[str] = []
        self._tunnels = [{"tunnelCode": "AU", "activeNum": 1, "activeIp": "198.51.100.1"}] if tunnels is None else tunnels
        self.fail = fail or {}  # path -> exception; mutate between polls to simulate outages
        self._tunnels_exc = tunnels_exc

    async def ensure_login(self):
        return None

    async def tunnels(self):
        if self._tunnels_exc:
            raise self._tunnels_exc
        return self._tunnels

    async def get(self, path):
        self.paths.append(path)
        if path in self.fail:
            raise self.fail[path]
        if path == APPS:
            return {"apps": {"netflix": {"app": "Netflix", "tunnel": "AU"}}}
        if path == "/api/wifi/workingInfo":
            return {"workingInfo": {"wanStatus": "connected"}}
        return {"path": path}


def make(features, client):
    from deeper_connect.coordinator import DeeperCoordinator
    c = object.__new__(DeeperCoordinator)  # skip DataUpdateCoordinator.__init__ (needs a running hass)
    c.client, c.features, c.session, c.geo = client, frozenset(features), None, None
    c._init_state()
    return c


def run(coro):
    return asyncio.run(coro)


def poll(c, n=1):
    out = None
    for _ in range(n):
        out = run(c._async_update_data())
    return out


def counts_per_poll(c, client, path, n):
    seen = []
    for _ in range(n):
        before = client.paths.count(path)
        poll(c)
        seen.append(client.paths.count(path) - before)
    return seen


# ---- which endpoints belong to which feature ----
ENDPOINTS = {  # feature -> endpoints only it needs
    "dpn": ("/api/smartRoute/getDpnMode", "/api/smartRoute/nodeLbMode"),
    "ads_security": ("/api/tproxy/adsFilter", "/api/tproxy/sslBypass", "/api/security/settings/udpServer"),
    "system": ("/api/autoReboot/config", "/api/system-info/get-autoupdate"),
    "app_relocator": (APPS,),
}


def test_core_only_polls_no_feature_endpoints():
    client = FakeClient()
    poll(make((), client))
    for path in (p for paths in ENDPOINTS.values() for p in paths):
        assert path not in client.paths, path
    assert USAGE in client.paths and SOFTWARE in client.paths and NETWORK in client.paths


@pytest.mark.parametrize("feature", ENDPOINTS)
def test_each_feature_polls_only_its_own_endpoints(feature):
    client = FakeClient()
    poll(make((feature,), client))
    for f, paths in ENDPOINTS.items():
        for path in paths:
            assert (path in client.paths) == (f == feature), f"{path} with only {feature} on"


# ---- tiers ----
def test_fast_endpoints_are_polled_every_time():
    client = FakeClient()
    assert counts_per_poll(make((), client), client, USAGE, 4) == [1, 1, 1, 1]


@pytest.mark.parametrize("path,features", [(APPS, ("app_relocator",)), ("/api/smartRoute/getDpnMode", ("dpn",)),
                                           ("/api/tproxy/adsFilter", ("ads_security",)), (NETWORK, ())])
def test_medium_endpoints_polled_first_then_every_fifth(path, features):
    from deeper_connect.const import MEDIUM_EVERY
    client = FakeClient()
    seen = counts_per_poll(make(features, client), client, path, MEDIUM_EVERY + 1)
    assert seen == [1] + [0] * (MEDIUM_EVERY - 1) + [1]


def test_slow_endpoints_polled_first_then_every_slow_interval():
    from deeper_connect.const import SLOW_EVERY
    client = FakeClient()
    seen = counts_per_poll(make((), client), client, SOFTWARE, SLOW_EVERY + 1)
    assert seen[0] == 1 and seen[-1] == 1 and sum(seen) == 2


def test_cached_values_are_served_between_polls():
    client = FakeClient()
    c = make(("app_relocator",), client)
    poll(c)
    assert poll(c)["apps"]["netflix"]["tunnel"] == "AU" and client.paths.count(APPS) == 1


def test_forced_refresh_rereads_medium_and_slow_then_resets():
    client = FakeClient()
    c = make(("dpn", "system"), client)
    poll(c, 2)
    before = {p: client.paths.count(p) for p in (SOFTWARE, "/api/smartRoute/getDpnMode")}
    c._force_medium = c._force_slow = True
    poll(c)
    assert client.paths.count(SOFTWARE) == before[SOFTWARE] + 1
    assert client.paths.count("/api/smartRoute/getDpnMode") == before["/api/smartRoute/getDpnMode"] + 1
    assert (c._force_medium, c._force_slow) == (False, False)


def test_control_actions_force_both_tiers_and_refresh():
    c = make((), FakeClient())
    calls = []

    async def setter(x):
        calls.append(x)

    async def refresh():
        calls.append("refresh")

    c.async_request_refresh = refresh
    run(c.async_control(setter, 7))
    assert calls == [7, "refresh"] and c._force_medium and c._force_slow


# ---- failure handling ----
def test_failed_endpoint_keeps_last_value_then_goes_stale():
    from deeper_connect.api import DeeperConnectionError
    from deeper_connect.const import STALE_AFTER
    client = FakeClient()
    c = make((), client)
    good = poll(c)["usage"]
    assert good == {"path": USAGE}
    client.fail[USAGE] = DeeperConnectionError("boom")
    for _ in range(STALE_AFTER - 1):
        assert poll(c)["usage"] == good  # still the last known value
    assert poll(c)["usage"] is None  # now stale: entities that require "usage" become unavailable
    assert c.endpoint_failures == {"usage": STALE_AFTER}


def test_failing_endpoint_is_retried_every_poll_even_if_slow():
    from deeper_connect.api import DeeperConnectionError
    client = FakeClient(fail={SOFTWARE: DeeperConnectionError("boom")})
    c = make((), client)
    assert counts_per_poll(c, client, SOFTWARE, 4) == [1, 1, 1, 1]  # not once per SLOW_EVERY polls
    del client.fail[SOFTWARE]
    assert poll(c)["software"] == {"path": SOFTWARE} and c.endpoint_failures == {}
    assert counts_per_poll(c, client, SOFTWARE, 3) == [0, 0, 0]  # back to its normal cadence


def test_one_bad_endpoint_does_not_affect_the_others():
    from deeper_connect.api import DeeperConnectionError
    client = FakeClient(fail={USAGE: DeeperConnectionError("boom")})
    out = poll(make((), client))
    assert out["usage"] is None and out["traffic"] == {"path": "/api/traffic/total-traffic"} and out["tunnels"]["AU"]


def test_failure_is_warned_once_and_recovery_logged(caplog):
    from deeper_connect.api import DeeperConnectionError
    from deeper_connect.const import STALE_AFTER
    client = FakeClient(fail={USAGE: DeeperConnectionError("boom")})
    c = make((), client)
    with caplog.at_level(logging.DEBUG, logger="deeper_connect.coordinator"):
        poll(c, STALE_AFTER + 2)
        del client.fail[USAGE]
        poll(c)
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 2  # first failure, and once when it turns stale; not once per poll
    assert [r for r in caplog.records if r.levelno == logging.INFO and "recovered" in r.getMessage()]


def test_apps_and_wifi_are_none_when_unavailable():
    from deeper_connect.api import DeeperConnectionError
    client = FakeClient(fail={APPS: DeeperConnectionError("x"), "/api/wifi/workingInfo": DeeperConnectionError("x")})
    out = poll(make(("app_relocator",), client))
    assert out["apps"] is None and out["wifi"] is None


def test_tunnels_are_keyed_by_code_and_junk_is_dropped():
    client = FakeClient(tunnels=[{"tunnelCode": "PL"}, {"no": "code"}, "junk", {"tunnelCode": "US"}])
    assert sorted(poll(make((), client))["tunnels"]) == ["PL", "US"]


def test_wifi_section_is_unwrapped():
    assert poll(make((), FakeClient()))["wifi"] == {"wanStatus": "connected"}


# ---- errors that fail the whole poll ----
def test_mandatory_tunnel_list_failure_is_update_failed():
    from homeassistant.helpers.update_coordinator import UpdateFailed
    from deeper_connect.api import DeeperConnectionError
    with pytest.raises(UpdateFailed):
        poll(make((), FakeClient(tunnels_exc=DeeperConnectionError("down"))))


def test_failed_first_poll_is_still_treated_as_first_poll():
    from homeassistant.helpers.update_coordinator import UpdateFailed
    from deeper_connect.api import DeeperConnectionError
    client = FakeClient(tunnels_exc=DeeperConnectionError("down"))
    c = make((), client)
    with pytest.raises(UpdateFailed):
        poll(c)
    client._tunnels_exc = None
    poll(c)
    assert SOFTWARE in client.paths  # slow tier fetched on the first poll that succeeded


def test_auth_error_triggers_reauth():
    from homeassistant.exceptions import ConfigEntryAuthFailed
    from deeper_connect.api import DeeperAuthError
    with pytest.raises(ConfigEntryAuthFailed):
        poll(make((), FakeClient(tunnels_exc=DeeperAuthError("401"))))


def test_auth_error_on_optional_endpoint_still_triggers_reauth():
    from homeassistant.exceptions import ConfigEntryAuthFailed
    from deeper_connect.api import DeeperAuthError
    with pytest.raises(ConfigEntryAuthFailed):
        poll(make((), FakeClient(fail={USAGE: DeeperAuthError("401")})))
