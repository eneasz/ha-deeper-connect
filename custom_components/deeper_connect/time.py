"""Scheduled-reboot time."""
from __future__ import annotations

from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.exceptions import HomeAssistantError

from .api import DeeperError
from .const import FEATURE_CONTROLS, ICONS
from .entity import DeeperEntity


async def async_setup_entry(hass, entry, add):
    if FEATURE_CONTROLS in entry.runtime_data.features:
        add([RebootTime(entry.runtime_data, entry.entry_id)])


class RebootTime(DeeperEntity, TimeEntity):
    _attr_name = "Scheduled reboot time"

    def __init__(self, coordinator, entry_id) -> None:
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{entry_id}_reboot_time"
        self._attr_icon = ICONS["reboot_time"]

    @property
    def native_value(self):
        c = self.coordinator.data.get("autoreboot") or {}
        try:
            return time(int(c["hour"]), int(c["minute"]))
        except (KeyError, TypeError, ValueError):
            return None

    async def async_set_value(self, value: time) -> None:
        cfg = {**(self.coordinator.data.get("autoreboot") or {}), "hour": value.hour, "minute": value.minute}
        try:
            await self.coordinator.async_control(self.coordinator.client.set_auto_reboot, cfg)
        except DeeperError as err:
            raise HomeAssistantError(f"Could not set reboot time: {err}") from err
