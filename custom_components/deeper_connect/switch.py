"""Switches (EXPERIMENTAL: request bodies inferred from the web UI, disabled by default)."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.exceptions import HomeAssistantError

from .const import ICONS
from .entity import DeeperEntity

SWITCHES = (
    ("ads_filter", "Ad filter", "ads", "/api/tproxy/adsFilter"),
    ("ssl_bypass", "SSL bypass", "ssl", "/api/tproxy/sslBypass"),
)


async def async_setup_entry(hass, entry, add):
    add([DeeperSwitch(entry.runtime_data, entry.entry_id, *s) for s in SWITCHES])


class DeeperSwitch(DeeperEntity, SwitchEntity):
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, entry_id, key, name, data_key, path):
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{entry_id}_{key}"
        self._attr_name = name
        self._attr_icon = ICONS.get(key)
        self._data_key, self._path = data_key, path

    @property
    def is_on(self):
        v = (self.coordinator.data.get(self._data_key) or {}).get("enable")
        return None if v is None else bool(v)

    async def _set(self, value: bool) -> None:
        resp = await self.coordinator.client.post(self._path, {"enable": value})
        if not (isinstance(resp, dict) and resp.get("success")):
            raise HomeAssistantError(f"Device rejected the change: {resp}")
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs):
        await self._set(True)

    async def async_turn_off(self, **kwargs):
        await self._set(False)
