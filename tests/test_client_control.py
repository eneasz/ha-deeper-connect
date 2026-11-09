"""Client route control: the one write the integration makes to Access Control (opt-in)."""
import asyncio
from types import SimpleNamespace

import pytest

from _stubs import ALL, collect_entities, data, make_entry, with_platform

TV = "aa:bb:cc:00:00:03"  # a blackholed client in the fixture
STREAMER = "aa:bb:cc:00:00:01"  # smart route


def _client(listing):
    from deeper_connect.api import DeeperClient
    calls = []

    class C(DeeperClient):
        def __init__(self): pass
        async def get(self, path):
            calls.append(("GET", path)); return listing
        async def post(self, path, json=None):
            calls.append(("POST", path, json)); return {"success": True}
    return C(), calls


def _listing():
    return data()["clients"]


def test_set_client_route_sends_the_whole_fresh_record_with_only_the_route_changed():
    c, calls = _client(_listing())
    asyncio.run(c.set_client_route(STREAMER.upper(), "disabled"))
    assert calls[0] == ("GET", "/api/accessControl/list")  # re-read just before writing
    record = next(r for r in _listing()["online"] if r["mac"] == STREAMER)
    assert calls[1] == ("POST", "/api/accessControl/setOne", {**record, "routeMode": "disabled"})


def test_full_tunnel_sets_the_region_code():
    c, calls = _client(_listing())
    asyncio.run(c.set_client_route(STREAMER, "full", "US"))
    assert calls[1][2]["routeMode"] == "full" and calls[1][2]["regionCode"] == "US"


def test_other_modes_leave_the_region_code_as_the_device_has_it():
    c, calls = _client(_listing())
    asyncio.run(c.set_client_route(STREAMER, "smart"))
    assert "regionCode" in calls[1][2] and calls[1][2]["regionCode"] is None


def test_works_for_offline_clients_too():
    c, calls = _client(_listing())
    asyncio.run(c.set_client_route(TV, "smart"))  # the TV is in the offline list
    assert calls[1][2]["mac"] == TV and calls[1][2]["routeMode"] == "smart"


@pytest.mark.parametrize("mac,mode,region", [("ff:ff:ff:ff:ff:ff", "smart", None), (STREAMER, "bogus", None), (STREAMER, "full", None)])
def test_bad_requests_never_reach_the_device(mac, mode, region):
    from deeper_connect.api import DeeperError
    c, calls = _client(_listing())
    with pytest.raises(DeeperError):
        asyncio.run(c.set_client_route(mac, mode, region))
    assert not [x for x in calls if x[0] == "POST"]


def test_device_refusal_is_raised():
    from deeper_connect.api import DeeperClient, DeeperRejectedError

    class C(DeeperClient):
        def __init__(self): pass
        async def get(self, path): return _listing()
        async def post(self, path, json=None): return {"success": False, "reason": "nope"}
    with pytest.raises(DeeperRejectedError):
        asyncio.run(C().set_client_route(STREAMER, "smart"))


# ---- entity ----
def _select(mac, tunnels=("AU", "US")):
    from deeper_connect.features.access_control import ClientRouteSelect
    entry = make_entry(ALL)
    coord = entry.runtime_data
    coord.data["tunnels"] = {code: {} for code in tunnels}
    calls = []

    async def control(setter, *args):
        calls.append(args)
    coord.async_control = control
    coord.client = SimpleNamespace(set_client_route="set_client_route")
    return with_platform(ClientRouteSelect(coord, "e1", mac)), calls, coord


def test_options_are_the_fixed_modes_plus_one_full_tunnel_per_tunnel():
    sel, _, _ = _select(STREAMER)
    assert sel.options == ["smart", "disabled", "blackhole", "full_AU", "full_US"]


def test_current_option_follows_the_device():
    assert _select(STREAMER)[0].current_option == "smart"
    assert _select(TV)[0].current_option == "blackhole"
    sel, _, coord = _select(STREAMER)
    rec = next(r for r in coord.data["clients"]["online"] if r["mac"] == STREAMER)
    rec.update(routeMode="full", regionCode="PL")
    assert sel.current_option == "full_PL" and "full_PL" in sel.options  # shown even though PL is not a listed tunnel
    rec.update(routeMode="mystery")
    assert sel.current_option is None


@pytest.mark.parametrize("option,expected", [("smart", ("smart", None)), ("blackhole", ("blackHole", None)),
                                             ("disabled", ("disabled", None)), ("full_US", ("full", "US"))])
def test_selecting_calls_the_client_with_the_device_mode(option, expected):
    sel, calls, _ = _select(STREAMER)
    asyncio.run(sel.async_select_option(option))
    assert calls == [(STREAMER, *expected)]


def test_unknown_option_is_rejected_without_a_write():
    from homeassistant.exceptions import HomeAssistantError
    sel, calls, _ = _select(STREAMER)
    with pytest.raises(HomeAssistantError):
        asyncio.run(sel.async_select_option("bogus"))
    assert calls == []


def test_device_errors_become_ha_errors():
    from homeassistant.exceptions import HomeAssistantError
    from deeper_connect.api import DeeperRejectedError
    sel, _, coord = _select(STREAMER)

    async def control(setter, *args):
        raise DeeperRejectedError("no")
    coord.async_control = control
    with pytest.raises(HomeAssistantError, match="Streamer"):
        asyncio.run(sel.async_select_option("smart"))


def test_unavailable_when_the_client_is_gone_and_name_follows_rename():
    assert _select("ff:ff:ff:ff:ff:ff")[0].available is False
    sel, _, coord = _select(STREAMER)
    assert sel.name == "Client Streamer routing"
    next(r for r in coord.data["clients"]["online"] if r["mac"] == STREAMER)["remark"] = "Box"
    sel.async_write_ha_state = lambda: None
    sel._handle_coordinator_update()
    assert sel.name == "Client Box routing"


# ---- opt-in ----
def test_selects_exist_only_when_client_control_is_on():
    def selects(opts):
        return [e for e in collect_entities(ALL, opts) if e.unique_id.endswith("_route_select")]
    assert selects({}) == [] and selects({"client_control": False}) == []
    on = selects({"client_control": True})
    assert on and all(e.unique_id.startswith("e1_client_") for e in on)


def test_selects_need_the_access_control_feature():
    assert not [e for e in collect_entities(("dpn", "system"), {"client_control": True}) if e.unique_id.endswith("_route_select")]


def test_default_setup_creates_no_writable_client_entities():
    assert not [e for e in collect_entities(ALL, {}) if "_client_" in e.unique_id and hasattr(e, "async_select_option")]
