"""Coordinator polling: tiers, per-endpoint failure handling, and how errors map to HA exceptions."""
import asyncio
import logging
from datetime import timedelta

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


def make(features, client, interval=60):
    """A coordinator with a fake clock: every poll() advances time by one polling interval."""
    from deeper_connect.coordinator import DeeperCoordinator
    c = object.__new__(DeeperCoordinator)  # skip DataUpdateCoordinator.__init__ (needs a running hass)
    c.client, c.features, c.session, c.geo = client, frozenset(features), None, None
    c.update_interval = timedelta(seconds=interval)
    c._init_state()
    c.now = 1000.0
    c._clock = lambda: c.now
    return c


def run(coro):
    return asyncio.run(coro)


def poll(c, n=1):
    out = None
    for _ in range(n):
        out = run(c._async_update_data())
        c.now += c.update_interval.total_seconds()
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
def test_medium_endpoints_polled_first_then_about_every_five_minutes(path, features):
    client = FakeClient()
    seen = counts_per_poll(make(features, client), client, path, 6)  # 60 s polls: the 6th poll is 300 s after the first
    assert seen == [1, 0, 0, 0, 0, 1]


@pytest.mark.parametrize("interval,medium_every,slow_every", [(15, 20, 120), (60, 5, 30), (120, 2, 15), (360, 1, 5), (900, 1, 2)])
def test_tiers_follow_elapsed_time_not_poll_count(interval, medium_every, slow_every):
    """Whatever the polling interval, medium data is at most ~5 min old and slow data ~30 min (never rarer than a poll)."""
    client = FakeClient()
    c = make(("dpn",), client, interval)
    medium = counts_per_poll(c, client, "/api/smartRoute/getDpnMode", slow_every * 2 + 1)
    assert [i for i, n in enumerate(medium) if n] == list(range(0, len(medium), medium_every))
    client2 = FakeClient()
    slow = counts_per_poll(make((), client2, interval), client2, SOFTWARE, slow_every * 2 + 1)
    assert [i for i, n in enumerate(slow) if n] == [0, slow_every, slow_every * 2]


def test_timing_jitter_does_not_push_a_refresh_to_the_next_poll():
    client = FakeClient()
    c = make(("dpn",), client, 60)
    for t in (0, 59.5, 119.0, 178.7, 238.4, 298.1):  # polls arrive a little early or late
        c.now = 1000.0 + t
        run(c._async_update_data())
    assert client.paths.count("/api/smartRoute/getDpnMode") == 2  # first poll + the one at ~300 s


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
    assert before[SOFTWARE] == 1 and before["/api/smartRoute/getDpnMode"] == 1  # not due yet
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
    assert counts_per_poll(c, client, SOFTWARE, 4) == [1, 1, 1, 1]  # not once per SLOW_SECONDS
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


# ---- Repairs: device unreachable ----
class Issues:
    def __init__(self, monkeypatch):
        import deeper_connect.coordinator as mod
        self.created, self.deleted = [], []
        monkeypatch.setattr(mod.ir, "async_create_issue", lambda hass, domain, issue_id, **kw: self.created.append((issue_id, kw)))
        monkeypatch.setattr(mod.ir, "async_delete_issue", lambda hass, domain, issue_id: self.deleted.append(issue_id))


def down_coordinator(monkeypatch, interval=60):
    from types import SimpleNamespace
    from deeper_connect.api import DeeperConnectionError
    issues = Issues(monkeypatch)
    client = FakeClient(tunnels_exc=DeeperConnectionError("down"))
    c = make((), client, interval)
    c.hass, c.config_entry = object(), SimpleNamespace(entry_id="e1", data={"host": "192.0.2.10"})
    return c, client, issues


def poll_ignoring_failure(c):
    from homeassistant.helpers.update_coordinator import UpdateFailed
    try:
        poll(c)
    except UpdateFailed:
        # poll() raised before advancing the fake clock
        c.now += c.update_interval.total_seconds()


def test_no_issue_for_a_short_outage(monkeypatch):
    c, _, issues = down_coordinator(monkeypatch)
    for _ in range(10):  # 10 minutes at 60 s
        poll_ignoring_failure(c)
    assert issues.created == []


def test_issue_is_raised_once_after_fifteen_minutes_with_host_and_minutes(monkeypatch):
    c, _, issues = down_coordinator(monkeypatch)
    for _ in range(40):
        poll_ignoring_failure(c)
    assert len(issues.created) == 1
    issue_id, kw = issues.created[0]
    assert issue_id == "device_unreachable_e1" and kw["translation_key"] == "device_unreachable" and kw["is_fixable"] is False
    assert kw["translation_placeholders"] == {"host": "192.0.2.10", "minutes": "15"}


def test_issue_clears_on_the_first_successful_poll_and_timer_restarts(monkeypatch):
    c, client, issues = down_coordinator(monkeypatch)
    for _ in range(20):
        poll_ignoring_failure(c)
    assert len(issues.created) == 1
    client._tunnels_exc = None
    poll(c)
    assert issues.deleted == ["device_unreachable_e1"] and c._down_since is None
    from deeper_connect.api import DeeperConnectionError
    client._tunnels_exc = DeeperConnectionError("down again")
    for _ in range(5):  # a new, short outage must not raise the issue straight away
        poll_ignoring_failure(c)
    assert len(issues.created) == 1


def test_a_success_in_between_resets_the_outage_timer(monkeypatch):
    from deeper_connect.api import DeeperConnectionError
    c, client, issues = down_coordinator(monkeypatch)
    for _ in range(10):
        poll_ignoring_failure(c)
    client._tunnels_exc = None
    poll(c)
    client._tunnels_exc = DeeperConnectionError("down")
    for _ in range(10):  # 10 + 10 minutes in total, but never 15 in a row
        poll_ignoring_failure(c)
    assert issues.created == []


def test_wrong_password_and_failing_optional_endpoints_do_not_raise_the_issue(monkeypatch):
    from homeassistant.exceptions import ConfigEntryAuthFailed
    from deeper_connect.api import DeeperAuthError, DeeperConnectionError
    issues = Issues(monkeypatch)
    c = make((), FakeClient(tunnels_exc=DeeperAuthError("401")))
    for _ in range(30):
        with pytest.raises(ConfigEntryAuthFailed):
            poll(c)
    c2 = make((), FakeClient(fail={USAGE: DeeperConnectionError("x"), SOFTWARE: DeeperConnectionError("x")}))
    for _ in range(40):
        poll(c2)
    assert issues.created == []  # HA already shows its own re-authentication card; one bad endpoint is not an outage


def test_unload_removes_an_open_issue(monkeypatch):
    c, _, issues = down_coordinator(monkeypatch)
    for _ in range(20):
        poll_ignoring_failure(c)
    c.clear_issue()
    c.clear_issue()  # second call is a no-op
    assert issues.deleted == ["device_unreachable_e1"]
