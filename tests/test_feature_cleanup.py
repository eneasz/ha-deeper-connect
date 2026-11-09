"""Switching a feature off removes its registry entities, and tunnel sub-devices that end up empty."""
from types import SimpleNamespace

import pytest

from _stubs import ALL  # noqa: F401  (also puts custom_components on sys.path)

PREFIX = "e1_"


class FakeRegistry:
    def __init__(self, unique_ids):
        self.entities = {f"x.{i}": SimpleNamespace(entity_id=f"x.{i}", unique_id=u, device=d)
                         for i, (u, d) in enumerate(unique_ids)}
        self.removed_devices: list[str] = []

    def async_remove(self, entity_id):
        self.entities.pop(entity_id)

    def remove_device(self, device_id):
        self.removed_devices.append(device_id)

    @property
    def uids(self):
        return {e.unique_id for e in self.entities.values()}


def _setup(monkeypatch, entities, devices):
    """entities: [(unique_id, device_id)]; devices: {device_id: identifiers}."""
    import deeper_connect as pkg
    reg = FakeRegistry(entities)
    dev_reg = SimpleNamespace(async_remove_device=reg.remove_device)
    dev_objs = [SimpleNamespace(id=i, identifiers=ids) for i, ids in devices.items()]
    monkeypatch.setattr(pkg.er, "async_get", lambda hass: reg)
    monkeypatch.setattr(pkg.er, "async_entries_for_config_entry", lambda r, eid: list(r.entities.values()))
    monkeypatch.setattr(pkg.er, "async_entries_for_device",
                        lambda r, dev_id, include_disabled_entities=False: [e for e in r.entities.values() if e.device == dev_id])
    monkeypatch.setattr(pkg.dr, "async_get", lambda hass: dev_reg)
    monkeypatch.setattr(pkg.dr, "async_entries_for_config_entry", lambda d, eid: dev_objs)
    return reg


ENTITIES = [
    ("e1_health", "main"), ("e1_cpu", "main"), ("e1_tunnel_problem", "main"), ("e1_firmware", "main"),
    ("e1_ads_filter", "main"), ("e1_reboot", "main"), ("e1_routing_mode", "main"), ("e1_reboot_time", "main"),
    ("e1_relocated_apps", "main"), ("e1_app_netflix", "main"),
    ("e1_blackholed_clients", "main"), ("e1_client_aa:bb:cc:00:00:03_route", "main"),
    ("e1_client_aa:bb:cc:00:00:03_blackholed", "main"),
    ("e1_AU_location", "tun_au"), ("e1_AU_nodes", "tun_au"), ("e1_AU_refresh", "tun_au"), ("e1_AU_apps", "tun_au"),
    ("e1_PL_location", "tun_pl"), ("e1_PL_tracker", "tun_pl"),
]
DEVICES = {"main": {("deeper_connect", "e1")}, "tun_au": {("deeper_connect", "e1_AU")}, "tun_pl": {("deeper_connect", "e1_PL")}}


def _run(monkeypatch, features):
    import deeper_connect as pkg
    reg = _setup(monkeypatch, ENTITIES, DEVICES)
    entry = SimpleNamespace(entry_id="e1")
    pkg._remove_disabled_feature_entities(None, entry, frozenset(features))
    return reg


def test_all_features_on_removes_nothing(monkeypatch):
    reg = _run(monkeypatch, ALL)
    assert reg.uids == {u for u, _ in ENTITIES} and reg.removed_devices == []


def test_default_features_drop_only_access_control(monkeypatch):
    reg = _run(monkeypatch, ("dpn", "app_relocator", "ads_security", "system"))
    gone = {u for u, _ in ENTITIES} - reg.uids
    assert gone == {"e1_blackholed_clients", "e1_client_aa:bb:cc:00:00:03_route", "e1_client_aa:bb:cc:00:00:03_blackholed"}
    assert reg.removed_devices == []


def test_everything_off_keeps_core_and_removes_tunnel_devices(monkeypatch):
    reg = _run(monkeypatch, ())
    assert reg.uids == {"e1_health", "e1_cpu", "e1_tunnel_problem", "e1_firmware"}
    assert sorted(reg.removed_devices) == ["tun_au", "tun_pl"]  # the main device is never removed


def test_tunnels_off_but_apps_on_keeps_nothing_tunnel_scoped(monkeypatch):
    reg = _run(monkeypatch, ("app_relocator",))
    assert not [u for u in reg.uids if u.startswith(("e1_AU_", "e1_PL_"))]  # AU_apps needs dpn AND app_relocator
    assert "e1_relocated_apps" in reg.uids and "e1_app_netflix" in reg.uids


def test_tunnel_device_survives_while_it_still_has_entities(monkeypatch):
    # DPN on, apps off: AU keeps location/nodes/refresh, so its sub-device stays.
    reg = _run(monkeypatch, ("dpn",))
    assert "e1_AU_apps" not in reg.uids and "e1_AU_location" in reg.uids
    assert reg.removed_devices == []


@pytest.mark.parametrize("unique_id", ["foreign_thing", "e2_AU_location"])
def test_entities_without_our_prefix_are_left_alone(monkeypatch, unique_id):
    import deeper_connect as pkg
    reg = _setup(monkeypatch, [(unique_id, "main")], {"main": {("deeper_connect", "e1")}})
    pkg._remove_disabled_feature_entities(None, SimpleNamespace(entry_id="e1"), frozenset())
    assert unique_id in reg.uids
