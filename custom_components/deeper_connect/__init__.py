"""Deeper Connect integration."""
from __future__ import annotations

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .api import DeeperClient, DeeperError
from .const import CONF_APPS, CONF_CLIENT_CONTROL, CONF_CLIENTS, CONF_FEATURES, CONFIG_VERSION, DOMAIN, FEATURE_APPS, FEATURE_DPN, PLATFORMS
from .coordinator import DeeperCoordinator
from .features import CLIENT_ENTITY_RE, CLIENT_SELECT_RE, features_owning, migrate_features
from .util import DIRECT, NOT_SET, find_app, option_to_code, routing_request

type DeeperConfigEntry = ConfigEntry[DeeperCoordinator]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
SET_APP_SCHEMA = vol.Schema({
    vol.Optional("config_entry"): cv.string,
    vol.Required("app"): cv.string,
    vol.Required("tunnel"): cv.string,
})


SET_ROUTING_SCHEMA = vol.Schema({
    vol.Optional("config_entry"): cv.string,
    vol.Required("mode"): cv.string,
    vol.Optional("tunnel"): cv.string,
})

# Read-only entities of earlier versions that are now controls (switch/select); removed to avoid duplicates.
_REPLACED = (("binary_sensor", "auto_update"), ("binary_sensor", "auto_reboot"), ("sensor", "dpn_mode"), ("sensor", "lb_mode"))


def _loaded_entry(hass, entry_id=None):
    entries = [e for e in hass.config_entries.async_entries(DOMAIN) if e.state.value == "loaded"]
    if entry_id:
        entries = [e for e in entries if e.entry_id == entry_id]
    if not entries:
        raise ServiceValidationError("No loaded Deeper Connect device found")
    return entries[0]


async def async_setup(hass: HomeAssistant, config) -> bool:
    async def set_app_relocation(call: ServiceCall) -> None:
        entries = [e for e in hass.config_entries.async_entries(DOMAIN) if e.state.value == "loaded"]
        if call.data.get("config_entry"):
            entries = [e for e in entries if e.entry_id == call.data["config_entry"]]
        if not entries:
            raise ServiceValidationError("No loaded Deeper Connect device found")
        coordinator = entries[0].runtime_data
        if FEATURE_APPS not in coordinator.features:
            raise ServiceValidationError("Enable the 'App Relocator' feature in the integration options first")
        apps = coordinator.data.get("apps") or {}
        app = find_app(apps, call.data["app"])
        if app is None:
            raise ServiceValidationError(f"Unknown app '{call.data['app']}'")
        code = option_to_code(call.data["tunnel"])
        if code not in (NOT_SET, DIRECT) and code not in coordinator.data["tunnels"]:
            raise ServiceValidationError(
                f"Tunnel '{call.data['tunnel']}' does not exist (have: {', '.join(sorted(coordinator.data['tunnels']))})")
        try:
            await coordinator.async_set_app_tunnel(app, code)
        except DeeperError as err:
            raise HomeAssistantError(f"Could not relocate {app}: {err}") from err

    async def set_routing_mode(call: ServiceCall) -> None:
        coordinator = _loaded_entry(hass, call.data.get("config_entry")).runtime_data
        if FEATURE_DPN not in coordinator.features:
            raise ServiceValidationError("Enable the 'DPN' feature in the integration options first")
        try:
            body = routing_request(call.data["mode"], call.data.get("tunnel"), coordinator.data.get("dpn"),
                                   coordinator.data["tunnels"])
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err
        try:
            await coordinator.async_control(coordinator.client.set_dpn_mode, body)
        except DeeperError as err:
            raise HomeAssistantError(f"Could not set routing mode: {err}") from err

    hass.services.async_register(DOMAIN, "set_app_relocation", set_app_relocation, schema=SET_APP_SCHEMA)
    hass.services.async_register(DOMAIN, "set_routing_mode", set_routing_mode, schema=SET_ROUTING_SCHEMA)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: DeeperConfigEntry) -> bool:
    """v1 -> v2: feature groups were renamed after the Deeper UI sections. Unique ids are unchanged."""
    if entry.version > CONFIG_VERSION:
        return False  # created by a newer release; do not guess
    if entry.version == 1:
        options = dict(entry.options)
        if options.get(CONF_FEATURES) is not None:  # entries that never saved the option follow the new defaults
            options[CONF_FEATURES] = migrate_features(options[CONF_FEATURES])
        hass.config_entries.async_update_entry(entry, options=options, version=CONFIG_VERSION)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: DeeperConfigEntry) -> bool:
    # Own session with an unsafe cookie jar: the device is addressed by IP.
    session = aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True))
    client = DeeperClient(session, entry.data[CONF_HOST], entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
    coordinator = DeeperCoordinator(hass, entry, client, session)
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        await session.close()
        raise
    entry.runtime_data = coordinator
    registry = er.async_get(hass)
    for platform, key in _REPLACED:
        if entity_id := registry.async_get_entity_id(platform, DOMAIN, f"{entry.entry_id}_{key}"):
            registry.async_remove(entity_id)
    _remove_disabled_feature_entities(hass, entry, coordinator.features)
    entry.async_on_unload(entry.add_update_listener(_reload))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


def _remove_disabled_feature_entities(hass: HomeAssistant, entry: DeeperConfigEntry, features) -> None:
    """Drop registry entries (and emptied tunnel sub-devices) belonging to feature groups that are switched off."""
    registry = er.async_get(hass)
    prefix = f"{entry.entry_id}_"
    # Only an explicitly saved choice counts: when never configured the defaults come from live device data.
    watched = entry.options.get(CONF_CLIENTS)
    watched = None if watched is None else {m.lower() for m in watched}
    apps = entry.options.get(CONF_APPS)
    for ent in er.async_entries_for_config_entry(registry, entry.entry_id):
        uid = ent.unique_id
        rest = uid[len(prefix):] if uid.startswith(prefix) else ""
        needs = features_owning(rest) if rest else set()
        client = CLIENT_ENTITY_RE.match(rest)
        if needs and not needs <= features:
            registry.async_remove(ent.entity_id)
        elif not entry.options.get(CONF_CLIENT_CONTROL) and CLIENT_SELECT_RE.match(rest):
            registry.async_remove(ent.entity_id)  # client routing is opt-in: drop the selects when it is switched off
        elif client and watched is not None and client["mac"] not in watched:
            registry.async_remove(ent.entity_id)  # the client was taken off the watch list
        elif apps is not None and rest.startswith("app_") and rest != "app_sig" and rest[4:] not in apps:
            registry.async_remove(ent.entity_id)  # the app was taken off the dropdown list
    devices = dr.async_get(hass)
    for dev in dr.async_entries_for_config_entry(devices, entry.entry_id):
        if (DOMAIN, entry.entry_id) not in dev.identifiers and not er.async_entries_for_device(
                registry, dev.id, include_disabled_entities=True):
            devices.async_remove_device(dev.id)


async def _reload(hass: HomeAssistant, entry: DeeperConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: DeeperConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        entry.runtime_data.clear_issue()  # a reload starts counting afresh
        await entry.runtime_data.session.close()
    return ok
