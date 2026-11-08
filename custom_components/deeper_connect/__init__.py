"""Deeper Connect integration."""
from __future__ import annotations

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .api import DeeperClient, DeeperError
from .const import DOMAIN, PLATFORMS
from .coordinator import DeeperCoordinator
from .util import DIRECT, NOT_SET, find_app, option_to_code

type DeeperConfigEntry = ConfigEntry[DeeperCoordinator]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
SET_APP_SCHEMA = vol.Schema({
    vol.Optional("config_entry"): cv.string,
    vol.Required("app"): cv.string,
    vol.Required("tunnel"): cv.string,
})


async def async_setup(hass: HomeAssistant, config) -> bool:
    async def set_app_relocation(call: ServiceCall) -> None:
        entries = [e for e in hass.config_entries.async_entries(DOMAIN) if e.state.value == "loaded"]
        if call.data.get("config_entry"):
            entries = [e for e in entries if e.entry_id == call.data["config_entry"]]
        if not entries:
            raise ServiceValidationError("No loaded Deeper Connect device found")
        coordinator = entries[0].runtime_data
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

    hass.services.async_register(DOMAIN, "set_app_relocation", set_app_relocation, schema=SET_APP_SCHEMA)
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
    entry.async_on_unload(entry.add_update_listener(_reload))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _reload(hass: HomeAssistant, entry: DeeperConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: DeeperConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        await entry.runtime_data.session.close()
    return ok
