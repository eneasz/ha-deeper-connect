import importlib.util, pathlib, sys

spec = importlib.util.spec_from_file_location(
    "util", pathlib.Path(__file__).parent.parent / "custom_components/deeper_connect/util.py")
u = importlib.util.module_from_spec(spec); sys.modules["util"] = u; spec.loader.exec_module(u)

HEALTHY = {
    "tunnels": {"AU": {"activeNum": 7, "activeIp": "1.1.1.1"}},
    "wifi": {"wanStatus": "connected"},
    "hardware": {"tempInCelsius": 40},
    "usage": {"cpuUsageData": ["2", "10", "3"], "memUsageData": ["32", "32", "32"]},
    "sessions": {"currSessionNum": "1354", "maxSessionNum": "65536"},
    "software": {"softwareVersion": "2.0.6.h2"}, "latest": {"latestVersion": "2.0.6.h2"},
}

def test_parsers():
    assert u.parse_size("89.0 MB") == 93323264
    assert u.parse_size("2.6 GB") == int(2.6 * 1024**3)
    assert u.parse_size("0.0 B") == 0 and u.parse_size("junk") is None
    assert u.parse_uptime("0d2h10m") == 7800 and u.parse_uptime("3d0h5m") == 259500
    assert u.parse_uptime("") is None
    assert u.last(["1", "2.5"]) == 2.5 and u.last([]) is None
    assert u.avg_last(["100", "100", "1"], 3) == 67.0

def test_health_ok():
    assert u.compute_health(HEALTHY) == ("ok", [])

def test_health_levels():
    d = {**HEALTHY, "latest": {"latestVersion": "2.0.7.h2"}}
    assert u.compute_health(d) == ("warning", ["firmware update available"])
    d = {**HEALTHY, "tunnels": {"AU": {"activeNum": 0, "activeIp": None}}}
    assert u.compute_health(d) == ("problem", ["tunnel down: AU"])
    d = {**HEALTHY, "wifi": {"wanStatus": "disconnected"}}
    assert u.compute_health(d)[0] == "problem"
    d = {**HEALTHY, "hardware": {"tempInCelsius": 80}}
    assert u.compute_health(d)[0] == "warning"
    assert u.compute_health({})[0] == "ok"  # missing data never raises
