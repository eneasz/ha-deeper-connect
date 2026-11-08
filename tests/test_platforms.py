"""Import every platform and evaluate all entity descriptions against captured real-device data."""
import json, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "custom_components"))
FIX = pathlib.Path(__file__).parent / "fixtures" / "device.json"


def data():
    return json.loads(FIX.read_text())


def test_imports():
    import importlib
    for m in ("api", "coordinator", "config_flow", "sensor", "binary_sensor", "button", "switch", "update", "diagnostics", "device_tracker", "location", "geo", "select"):
        importlib.import_module(f"deeper_connect.{m}")


def test_sensor_values():
    from deeper_connect.sensor import SENSORS
    d = data()
    vals = {s.key: s.value_fn(d) for s in SENSORS}
    assert vals["health"] in ("ok", "warning", "problem")
    assert vals["temperature"] == 40 and vals["cpu"] is not None
    assert vals["uptime"] > 0 and vals["tunnel_count"] == 3
    assert vals["client_download"] > 0 and vals["public_ip"] and vals["wan_status"] == "connected"
    assert vals["dpn_mode"] == "smart"
    for s in SENSORS:
        if s.attrs_fn:
            s.attrs_fn(d)
    assert all(v is None for v in (s.value_fn({}) for s in SENSORS if s.key not in ("health", "tunnel_count", "clients_online"))) 


def test_binary_values():
    from deeper_connect.binary_sensor import BINARY_SENSORS
    d = data()
    vals = {s.key: s.is_on_fn(d) for s in BINARY_SENSORS}
    assert vals["tunnel_problem"] is False and vals["wan_connected"] is True
    assert vals["auto_reboot"] is True
    for s in BINARY_SENSORS:
        s.is_on_fn({})


def test_entities_instantiate():
    from types import SimpleNamespace
    from deeper_connect.sensor import SENSORS, DeeperSensor, TunnelNodes, TunnelIp
    from deeper_connect.binary_sensor import BINARY_SENSORS, DeeperBinary, TunnelProblem
    from deeper_connect.button import RebootButton, RefreshTunnel
    from deeper_connect.switch import SWITCHES, DeeperSwitch
    from deeper_connect.update import FirmwareUpdate

    coord = SimpleNamespace(data=data(), last_update_success=True, async_add_listener=lambda *a, **k: (lambda: None),
                            config_entry=SimpleNamespace(data={"host": "192.0.2.10"}))
    ents = [DeeperSensor(coord, "e1", s) for s in SENSORS] + [DeeperBinary(coord, "e1", b) for b in BINARY_SENSORS]
    ents += [TunnelNodes(coord, "e1", "AU"), TunnelIp(coord, "e1", "PL"), TunnelProblem(coord, "e1", "US"),
             RefreshTunnel(coord, "e1", "AU"), RebootButton(coord, "e1"), FirmwareUpdate(coord, "e1")]
    ents += [DeeperSwitch(coord, "e1", *s) for s in SWITCHES]
    ids = [e.unique_id for e in ents]
    assert len(ids) == len(set(ids)), "duplicate unique ids"
    info = ents[0].device_info
    assert info["model"] == "DCN-MINI-V1" and info["sw_version"] == "2.0.6.h2"
    for e in ents:
        getattr(e, "native_value", None); getattr(e, "is_on", None)
    fw = next(e for e in ents if isinstance(e, FirmwareUpdate))
    assert (fw.installed_version, fw.latest_version) == ("2.0.6.h2", "2.0.7.h2")


def test_every_entity_has_an_icon_or_device_class():
    from deeper_connect.sensor import SENSORS
    from deeper_connect.binary_sensor import BINARY_SENSORS
    from deeper_connect.const import ICONS
    for s in (*SENSORS, *BINARY_SENSORS):
        assert s.device_class or s.key in ICONS, f"{s.key} would show a generic icon"


def test_tunnel_location_and_devices():
    from types import SimpleNamespace
    from deeper_connect.location import tunnel_location, tunnel_title
    from deeper_connect.sensor import TunnelLocation, TunnelNodes, TunnelIp
    from deeper_connect.binary_sensor import TunnelProblem
    from deeper_connect.button import RefreshTunnel
    from deeper_connect.device_tracker import TunnelTracker

    d = data()
    au = d["tunnels"]["AU"]
    # offline baseline: country only
    loc = tunnel_location(au, {})
    assert loc["label"] == "Australia" and loc["flag"] == "🇦🇺" and loc["latitude"] is None
    assert tunnel_title(au) == "Tunnel AU (🇦🇺 Australia)"
    assert tunnel_title({"tunnelCode": "UB"}) == "Tunnel UB"
    # with geo data the exit IP wins
    geo = {au["activeIp"]: {"city": "Sydney", "region": "NSW", "country_code": "AU", "latitude": -33.87, "longitude": 151.2}}
    assert tunnel_location(au, geo)["label"] == "Sydney, Australia"

    coord = SimpleNamespace(data={**d, "geo": geo}, last_update_success=True,
                            async_add_listener=lambda *a, **k: (lambda: None), config_entry=SimpleNamespace(data={"host": "x"}))
    kinds = (TunnelLocation, TunnelNodes, TunnelIp, TunnelProblem, RefreshTunnel, TunnelTracker)
    ents = [k(coord, "e1", "AU") for k in kinds]
    # every tunnel entity shares ONE sub-device linked to the main device
    ids = {tuple(e.device_info["identifiers"])[0] for e in ents}
    assert ids == {("deeper_connect", "e1_AU")}
    assert all(e.device_info["via_device"] == ("deeper_connect", "e1") for e in ents)
    assert len({e.unique_id for e in ents}) == len(ents)
    loc_sensor, tracker = ents[0], ents[-1]
    assert loc_sensor.native_value == "Sydney, Australia"
    assert loc_sensor.extra_state_attributes["flag"] == "🇦🇺"
    assert (tracker.latitude, tracker.longitude) == (-33.87, 151.2) and tracker.available
    # no geo data -> tracker unavailable, location still shows the country
    coord.data = {**d, "geo": {}}
    assert not tracker.available and loc_sensor.native_value == "Australia"


def test_geo_parsers():
    from deeper_connect.geo import _from_geojs, _from_ipinfo
    r = _from_ipinfo({"city": "Warsaw", "region": "Mazovia", "country": "PL", "loc": "52.2,21.0", "org": "AS1 X"})
    assert (r["city"], r["country_code"], r["latitude"], r["longitude"]) == ("Warsaw", "PL", 52.2, 21.0)
    r = _from_geojs({"country_code": "US", "latitude": "37.7", "longitude": "-97.8", "organization_name": "G"})
    assert r["country_code"] == "US" and r["latitude"] == 37.7 and r["city"] is None
    assert _from_ipinfo({}) is None and _from_geojs({}) is None


def test_geo_locator_falls_back_and_caches():
    import asyncio, aiohttp
    from deeper_connect import geo

    calls = []

    class Resp:
        def __init__(self, url): self.url = url
        async def __aenter__(self):
            calls.append(self.url)
            if "ipinfo" in self.url: raise aiohttp.ClientConnectionError("blocked")
            return self
        async def __aexit__(self, *a): return False
        def raise_for_status(self): pass
        async def json(self, content_type=None): return {"country_code": "PL", "latitude": "52.2", "longitude": "21.0"}

    class Sess:
        def get(self, url, **kw): return Resp(url)

    async def run():
        g = geo.GeoLocator(Sess())
        a = await g.lookup("198.51.100.1")
        b = await g.lookup("198.51.100.1")
        return a, b

    a, b = asyncio.run(run())
    assert a["country_code"] == "PL" and a is b
    assert len(calls) == 2  # ipinfo failed, geojs ok, second lookup served from cache


def test_app_helpers():
    from deeper_connect.util import (app_title, apps_for_tunnel, code_to_option, find_app, option_to_code,
                                     relocated_apps)
    assert app_title("disneyPlus") == "Disney Plus" and app_title("netflix") == "Netflix"
    assert [code_to_option(c) for c in ("ZZ", "LL", "US", None)] == ["not_set", "direct", "US", "not_set"]
    assert [option_to_code(o) for o in ("not_set", "Direct", "us", "NONE", " PL ")] == ["ZZ", "LL", "US", "ZZ", "PL"]
    apps = data()["apps"]
    assert relocated_apps(apps) == {"netflix": "direct", "hboMax": "PL", "disneyPlus": "US", "plex": "US"}
    assert apps_for_tunnel(apps, "PL") == ["hboMax"] and apps_for_tunnel(apps, "AU") == []
    assert find_app(apps, "Disney Plus") == "disneyPlus" and find_app(apps, "NETFLIX") == "netflix"
    assert find_app(apps, "nope") is None


def test_api_app_payloads():
    import asyncio
    from deeper_connect.api import DeeperClient, DeeperRejectedError

    calls = []

    class C(DeeperClient):
        def __init__(self, resp): self.resp = resp
        async def post(self, path, json=None):
            calls.append((path, json)); return self.resp

    asyncio.run(C({"success": True}).set_app_tunnel("netflix", "PL"))
    asyncio.run(C({"success": True}).set_app_tunnel("netflix", "LL"))
    asyncio.run(C({"success": True}).set_app_tunnel("netflix", "ZZ"))
    assert calls == [("/api/appRelocator/addApp", {"appName": "netflix", "tunnelCode": "PL"}),
                     ("/api/appRelocator/addApp", {"appName": "netflix", "tunnelCode": "LL"}),
                     ("/api/appRelocator/delApp", {"appName": "netflix"})]
    try:
        asyncio.run(C({"success": False, "reason": "noTunnelNodes"}).set_app_tunnel("netflix", "PL"))
        raise AssertionError("should have raised")
    except DeeperRejectedError as e:
        assert "noTunnelNodes" in str(e)


def test_app_entities_and_service():
    import asyncio
    from types import SimpleNamespace
    import pytest
    from homeassistant.exceptions import ServiceValidationError
    import deeper_connect as integ
    from deeper_connect.select import AppRelocationSelect
    from deeper_connect.sensor import SENSORS, TunnelApps

    d = data()
    sent = []

    async def set_tunnel(app, code): sent.append((app, code))
    coord = SimpleNamespace(data=d, last_update_success=True, async_add_listener=lambda *a, **k: (lambda: None),
                            config_entry=SimpleNamespace(data={"host": "x"}), async_set_app_tunnel=set_tunnel)

    sel = AppRelocationSelect(coord, "e1", "hboMax")
    assert sel.current_option == "PL" and sel.options == ["not_set", "direct", "AU", "PL", "US"]
    assert AppRelocationSelect(coord, "e1", "netflix").current_option == "direct"
    assert AppRelocationSelect(coord, "e1", "zattoo").current_option == "not_set"
    assert sel.name == "App Hbo Max relocation" and sel.unique_id == "e1_app_hboMax"
    asyncio.run(sel.async_select_option("US")); asyncio.run(sel.async_select_option("not_set"))
    assert sent == [("hboMax", "US"), ("hboMax", "ZZ")]

    relocated = next(s for s in SENSORS if s.key == "relocated_apps")
    assert relocated.value_fn(d) == 4 and relocated.value_fn({}) is None
    assert TunnelApps(coord, "e1", "PL").native_value == 1 and TunnelApps(coord, "e1", "AU").native_value == 0

    # service: validation + dispatch
    handlers = {}
    hass = SimpleNamespace(services=SimpleNamespace(async_register=lambda dom, name, fn, schema=None: handlers.update({name: fn})),
                           config_entries=SimpleNamespace(async_entries=lambda dom: [
                               SimpleNamespace(entry_id="e1", state=SimpleNamespace(value="loaded"), runtime_data=coord)]))
    asyncio.run(integ.async_setup(hass, {}))
    call = lambda **kw: SimpleNamespace(data=kw)
    asyncio.run(handlers["set_app_relocation"](call(app="Disney Plus", tunnel="pl")))
    asyncio.run(handlers["set_app_relocation"](call(app="netflix", tunnel="direct")))
    assert sent[-2:] == [("disneyPlus", "PL"), ("netflix", "LL")]
    for bad in (dict(app="nope", tunnel="US"), dict(app="netflix", tunnel="JP")):
        with pytest.raises(ServiceValidationError):
            asyncio.run(handlers["set_app_relocation"](call(**bad)))
