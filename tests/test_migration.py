"""Config entry v1 -> v2: feature groups renamed after the Deeper UI sections."""
import asyncio
import re
from types import SimpleNamespace

import pytest

from _stubs import ALL  # noqa: F401  (also puts custom_components on sys.path)


def migrated(version=1, options=None):
    import deeper_connect as integ
    entry = SimpleNamespace(version=version, options=dict(options or {}))
    calls = []

    def update(e, options=None, version=None):
        calls.append((options, version))
        e.options, e.version = options, version

    hass = SimpleNamespace(config_entries=SimpleNamespace(async_update_entry=update))
    ok = asyncio.run(integ.async_migrate_entry(hass, entry))
    return ok, entry, calls


@pytest.mark.parametrize("old,new", [
    (["tunnels"], ["dpn"]),
    (["app_relocation"], ["app_relocator"]),
    (["access_control"], ["access_control"]),
    (["controls"], ["dpn", "ads_security", "system"]),
    (["tunnels", "app_relocation", "controls"], ["dpn", "app_relocator", "ads_security", "system"]),  # the old defaults
    (["access_control", "tunnels", "app_relocation", "controls"], list(ALL)),
    ([], []),
    (["bogus", "tunnels"], ["dpn"]),
])
def test_every_old_combination_maps_to_the_same_entities(old, new):
    from deeper_connect.features import migrate_features
    assert migrate_features(old) == new


def test_old_defaults_equal_new_defaults():
    """An entry that never saved features keeps exactly what it had (no migration of options needed)."""
    from deeper_connect.const import DEFAULT_FEATURES
    from deeper_connect.features import migrate_features
    assert set(migrate_features(["tunnels", "app_relocation", "controls"])) == set(DEFAULT_FEATURES)


def test_migrate_entry_rewrites_saved_features_and_keeps_other_options():
    ok, entry, calls = migrated(1, {"features": ["controls", "access_control"], "scan_interval": 30, "apps": ["netflix"],
                                    "geo_lookup": True})
    assert ok and entry.version == 2 and len(calls) == 1
    assert entry.options == {"features": ["dpn", "access_control", "ads_security", "system"], "scan_interval": 30,
                             "apps": ["netflix"], "geo_lookup": True}


def test_migrate_entry_without_saved_features_only_bumps_version():
    ok, entry, calls = migrated(1, {"scan_interval": 60})
    assert ok and entry.version == 2 and entry.options == {"scan_interval": 60}


def test_migrate_entry_is_idempotent():
    ok, entry, calls = migrated(2, {"features": ["dpn"]})
    assert ok and calls == [] and entry.options == {"features": ["dpn"]}


def test_migrate_entry_refuses_newer_versions():
    ok, entry, calls = migrated(3, {"features": ["dpn"]})
    assert ok is False and calls == []


def test_migrated_features_enable_the_same_entities_as_before():
    """Old 'controls' on must still create switches/selects/reboot controls; old 'tunnels' the tunnel devices."""
    from _stubs import collect_entities
    from deeper_connect.features import migrate_features
    ids = lambda feats: {e.unique_id for e in collect_entities(feats, {"geo_lookup": True})}  # noqa: E731
    before_defaults = ids(migrate_features(["tunnels", "app_relocation", "controls"]))
    for needed in ("e1_ads_filter", "e1_reboot", "e1_routing_mode", "e1_node_selection", "e1_reboot_time",
                   "e1_AU_refresh", "e1_AU_apps", "e1_relocated_apps", "e1_auto_update", "e1_udp_server"):
        assert needed in before_defaults, needed
    assert not [u for u in before_defaults if re.search(r"client_[0-9a-f]{2}:", u) or u.endswith("blackholed_clients")]


def test_routing_service_needs_dpn():
    import deeper_connect as integ
    from homeassistant.exceptions import ServiceValidationError
    handlers = {}
    hass = SimpleNamespace(services=SimpleNamespace(async_register=lambda d, n, h, schema=None: handlers.update({n: h})))
    asyncio.run(integ.async_setup(hass, {}))
    coord = SimpleNamespace(features=frozenset({"system"}), data={"tunnels": {}})
    entry = SimpleNamespace(state=SimpleNamespace(value="loaded"), entry_id="e1", runtime_data=coord)
    hass.config_entries = SimpleNamespace(async_entries=lambda domain: [entry])
    with pytest.raises(ServiceValidationError, match="DPN"):
        asyncio.run(handlers["set_routing_mode"](SimpleNamespace(data={"mode": "smart"})))
