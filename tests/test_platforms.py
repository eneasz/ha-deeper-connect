"""Import every platform and evaluate all entity descriptions against captured real-device data."""
import json, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "custom_components"))
FIX = pathlib.Path(__file__).parent / "fixtures" / "device.json"


def data():
    return json.loads(FIX.read_text())


def test_imports():
    import importlib
    for m in ("api", "coordinator", "config_flow", "sensor", "binary_sensor", "button", "switch", "update", "diagnostics"):
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
