"""Feature flags and the access list (per-client routing)."""
import json, pathlib, sys
from types import SimpleNamespace

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "custom_components"))
from _stubs import with_platform  # noqa: E402

FIX = pathlib.Path(__file__).parent / "fixtures" / "device.json"


def data():
    return json.loads(FIX.read_text())


def test_enabled_features_defaults_keep_old_behaviour():
    from deeper_connect.features import enabled_features
    assert enabled_features({}) == {"dpn", "app_relocator", "ads_security", "system"}  # what was always on before flags
    assert enabled_features({"features": ["access_control", "bogus"]}) == {"access_control"}
    assert enabled_features({"features": []}) == frozenset()


def test_client_helpers():
    from deeper_connect.util import all_clients, blackholed_clients, client_title, pinned_clients
    d = data()
    clients = all_clients(d)
    assert len(clients) == 4 and clients["aa:bb:cc:00:00:01"]["online"] is True
    assert [client_title(c) for c in blackholed_clients(d)] == ["Blocked TV"]
    assert sorted(pinned_clients(d)) == ["aa:bb:cc:00:00:01", "aa:bb:cc:00:00:03"]
    assert client_title({"mac": "m", "name": "n"}) == "n" and client_title({"mac": "m"}) == "m"
    assert all_clients({}) == {} and blackholed_clients({"clients": None}) == []


def test_features_owning():
    from deeper_connect.features import features_owning
    assert features_owning("ads_filter") == {"ads_security"} == features_owning("udp_server") == features_owning("ssl_bypass")
    assert features_owning("reboot") == {"system"} == features_owning("auto_update") == features_owning("reboot_time")
    assert features_owning("routing_mode") == {"dpn"} == features_owning("node_selection")
    assert features_owning("relocated_apps") == {"app_relocator"} and features_owning("app_netflix") == {"app_relocator"}
    assert features_owning("AU_apps") == {"dpn", "app_relocator"} and features_owning("AU_refresh") == {"dpn"}
    assert features_owning("client_aa:bb:cc:00:00:03_route") == {"access_control"} == features_owning("blackholed_clients")
    for always in ("health", "cpu", "tunnel_count", "tunnel_problem", "firmware", "clients_online", "wan_connected",
                   "public_ip", "app_sig", "client_upload", "client_download", "local_upload", "rule_version", "sharing"):
        assert features_owning(always) == set(), always


def test_access_entities():
    from deeper_connect.binary_sensor import ClientBlackholed
    from deeper_connect.sensor import BLACKHOLED_CLIENTS, ClientRouteMode, DeeperSensor
    coord = SimpleNamespace(data=data(), last_update_success=True, async_add_listener=lambda *a, **k: (lambda: None),
                            config_entry=SimpleNamespace(data={"host": "192.0.2.10"}))
    count = DeeperSensor(coord, "e1", BLACKHOLED_CLIENTS)
    assert count.native_value == 1 and count.extra_state_attributes["clients"] == ["Blocked TV"]
    assert count.extra_state_attributes["route_modes"] == {"smart": 2, "disabled": 1, "blackHole": 1}
    tv, streamer = "AA:BB:CC:00:00:03", "aa:bb:cc:00:00:01"
    assert ClientRouteMode(coord, "e1", tv).native_value == "blackHole"
    assert ClientBlackholed(coord, "e1", tv).is_on is True
    assert ClientBlackholed(coord, "e1", streamer).is_on is False
    assert with_platform(ClientRouteMode(coord, "e1", streamer)).name == "Client Streamer route mode"
    missing = ClientBlackholed(coord, "e1", "ff:ff:ff:ff:ff:ff")
    assert missing.available is False and missing.is_on is False
    assert ClientRouteMode(coord, "e1", tv).unique_id == "e1_client_aa:bb:cc:00:00:03_route"


def test_blackholed_count_unknown_without_data():
    from deeper_connect.sensor import BLACKHOLED_CLIENTS
    assert BLACKHOLED_CLIENTS.value_fn({}) is None
