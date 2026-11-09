"""Import every platform and evaluate all entity descriptions against captured real-device data."""
import json, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "custom_components"))
FIX = pathlib.Path(__file__).parent / "fixtures" / "device.json"


def data():
    return json.loads(FIX.read_text())


def test_imports():
    import importlib
    for m in ("api", "coordinator", "config_flow", "sensor", "binary_sensor", "button", "switch", "update", "diagnostics", "device_tracker", "location", "geo", "select", "time", "features"):
        importlib.import_module(f"deeper_connect.{m}")


def test_sensor_values():
    from deeper_connect.sensor import SENSORS
    d = data()
    vals = {s.key: s.value_fn(d) for s in SENSORS}
    assert vals["health"] in ("ok", "warning", "problem")
    assert vals["temperature"] == 40 and vals["cpu"] is not None
    assert vals["uptime"] > 0 and vals["tunnel_count"] == 3
    assert vals["client_download"] > 0 and vals["public_ip"] and vals["wan_status"] == "connected"
    for s in SENSORS:
        if s.attrs_fn:
            s.attrs_fn(d)
    assert all(v is None for v in (s.value_fn({}) for s in SENSORS if s.key not in ("health", "tunnel_count", "clients_online"))) 


def test_binary_values():
    from deeper_connect.binary_sensor import BINARY_SENSORS
    d = data()
    vals = {s.key: s.is_on_fn(d) for s in BINARY_SENSORS}
    assert vals["tunnel_problem"] is False and vals["wan_connected"] is True
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
    ents += [DeeperSwitch(coord, "e1", s) for s in SWITCHES]
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
                            config_entry=SimpleNamespace(data={"host": "x"}), async_set_app_tunnel=set_tunnel,
                            features=frozenset({"app_relocation"}))

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


def test_routing_request():
    import pytest
    from deeper_connect.util import routing_request
    dpn = {"dpnMode": "smart", "fullTunnel": "FR"}
    tunnels = {"AU": {}, "PL": {}, "US": {}}
    assert routing_request("smart", None, dpn, tunnels) == {"dpnMode": "smart", "tunnelCode": "ZZ", "killSwitch": False}
    assert routing_request("Disabled", None, dpn, tunnels) == {"dpnMode": "disabled", "tunnelCode": "", "killSwitch": False}
    assert routing_request("full", "us", dpn, tunnels) == {"dpnMode": "full", "tunnelCode": "US", "killSwitch": False}
    assert routing_request("full", None, {"fullTunnel": "PL"}, tunnels)["tunnelCode"] == "PL"
    with pytest.raises(ValueError):  # remembered full tunnel FR is not one of the user's tunnels
        routing_request("full", None, dpn, tunnels)
    with pytest.raises(ValueError):
        routing_request("turbo", None, dpn, tunnels)


def test_customised_apps():
    from deeper_connect.util import customised_apps
    assert customised_apps(data()["apps"]) == ["hboMax", "netflix"]


def test_api_setter_bodies():
    import asyncio
    import pytest
    from deeper_connect.api import DeeperClient, DeeperRejectedError

    calls = []

    class C(DeeperClient):
        def __init__(self, resp=None): self.resp = resp or {"success": True}
        async def post(self, path, json=None): calls.append(("POST", path, json)); return self.resp
        async def get(self, path): calls.append(("GET", path)); return self.resp

    c = C()
    run = asyncio.run
    run(c.set_dpn_mode({"dpnMode": "smart", "tunnelCode": "ZZ", "killSwitch": False}))
    run(c.set_node_lb_mode("rr")); run(c.set_udp_server(True)); run(c.set_ssl_bypass(False))
    run(c.set_youtube_ads(True)); run(c.set_auto_reboot({"on": True, "hour": 3}))
    run(C({"code": 0}).set_auto_update(True)); run(C({"code": 0}).set_auto_update(False))
    assert calls == [
        ("POST", "/api/smartRoute/setDpnMode", {"dpnMode": "smart", "tunnelCode": "ZZ", "killSwitch": False}),
        ("POST", "/api/smartRoute/nodeLbMode", {"mode": "rr"}),
        ("POST", "/api/security/settings/udpServer", {"enabled": True}),
        ("POST", "/api/tproxy/sslBypass", {"enable": False}),
        ("POST", "/api/tproxy/adsFilter", {"enable": True, "type": "youtube"}),
        ("POST", "/api/autoReboot/config", {"on": True, "hour": 3}),
        ("GET", "/api/system-info/set-autoupdate?autoUpdate=1"),
        ("GET", "/api/system-info/set-autoupdate?autoUpdate=0"),
    ]
    with pytest.raises(DeeperRejectedError):
        run(C({"code": 1, "message": "nope"}).set_auto_update(True))
    with pytest.raises(DeeperRejectedError):
        run(C({"success": False, "reason": "needHttps"}).set_youtube_ads(True))


def test_controls():
    import asyncio
    from datetime import time
    from types import SimpleNamespace
    from deeper_connect.select import NodeSelectionSelect, RoutingModeSelect
    from deeper_connect.switch import SWITCHES, DeeperSwitch
    from deeper_connect.time import RebootTime

    d = data()
    sent = []

    class Client:
        async def set_dpn_mode(self, b): sent.append(("dpn", b))
        async def set_node_lb_mode(self, m): sent.append(("lb", m))
        async def set_auto_reboot(self, c): sent.append(("reboot", c))
        async def set_auto_update(self, v): sent.append(("autoupdate", v))
        async def set_ssl_bypass(self, v): sent.append(("ssl", v))

    async def control(setter, *args): await setter(*args)
    coord = SimpleNamespace(data=d, client=Client(), last_update_success=True, async_control=control,
                            async_add_listener=lambda *a, **k: (lambda: None), config_entry=SimpleNamespace(data={"host": "x"}))
    run = asyncio.run

    rm = RoutingModeSelect(coord, "e1")
    assert rm.current_option == "smart" and rm.options == ["smart", "full", "disabled"]
    assert rm.entity_registry_enabled_default is False
    run(rm.async_select_option("disabled"))
    from homeassistant.exceptions import HomeAssistantError
    import pytest
    with pytest.raises(HomeAssistantError):  # remembered full tunnel FR isn't one of the user's tunnels
        run(rm.async_select_option("full"))
    lb = NodeSelectionSelect(coord, "e1")
    assert lb.entity_registry_enabled_default is True
    assert lb.current_option == "none"; run(lb.async_select_option("rr"))

    sw = {s.key: DeeperSwitch(coord, "e1", s) for s in SWITCHES}
    assert sw["auto_update"].is_on is True and sw["ssl_bypass"].is_on is False and sw["udp_server"].is_on is False
    assert sw["auto_reboot"].is_on is True
    assert all(v.entity_registry_enabled_default for v in sw.values())
    run(sw["auto_update"].async_turn_off()); run(sw["ssl_bypass"].async_turn_on()); run(sw["auto_reboot"].async_turn_off())

    rt = RebootTime(coord, "e1")
    assert rt.native_value == time(2, 0)
    run(rt.async_set_value(time(4, 30)))
    assert sent[0] == ("dpn", {"dpnMode": "disabled", "tunnelCode": "", "killSwitch": False})
    assert ("lb", "rr") in sent and ("autoupdate", False) in sent and ("ssl", True) in sent
    reboots = [c for k, c in sent if k == "reboot"]
    assert reboots[0]["on"] is False and reboots[0]["hour"] == 2          # keeps the rest of the config
    assert (reboots[1]["hour"], reboots[1]["minute"], reboots[1]["on"]) == (4, 30, True)
