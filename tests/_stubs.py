"""Shared stubs for tests that need a coordinator/entry without a running Home Assistant."""
import json
import pathlib
import sys
from types import SimpleNamespace

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "custom_components"))
FIX = pathlib.Path(__file__).parent / "fixtures" / "device.json"

ALL = ("dpn", "app_relocator", "access_control", "ads_security", "system")


def data() -> dict:
    return json.loads(FIX.read_text())


def make_entry(features, options=None, entry_id="e1"):
    """A config-entry stand-in whose runtime_data is a coordinator stand-in carrying `features`."""
    coord = SimpleNamespace(
        data=data(), last_update_success=True, features=frozenset(features), geo=None,
        async_add_listener=lambda *a, **k: (lambda: None),
    )
    entry = SimpleNamespace(entry_id=entry_id, runtime_data=coord, options=dict(options or {}),
                            data={"host": "192.0.2.10"}, async_on_unload=lambda fn: None)
    coord.config_entry = entry
    return entry


def collect_entities(features, options=None) -> list:
    """Run every platform's async_setup_entry for this feature set and return the entities it adds."""
    import asyncio
    import importlib

    entry = make_entry(features, options)
    added: list = []
    for platform in ("sensor", "binary_sensor", "button", "switch", "update", "device_tracker", "select", "time"):
        mod = importlib.import_module(f"deeper_connect.{platform}")
        asyncio.run(mod.async_setup_entry(None, entry, lambda ents, *a, **k: added.extend(ents)))
    return added


def rest_of(entity, entry_id="e1") -> str:
    """unique_id without the leading '<entry id>_' (what features_owning expects)."""
    uid = entity.unique_id
    assert uid.startswith(f"{entry_id}_"), uid
    return uid[len(entry_id) + 1:]
