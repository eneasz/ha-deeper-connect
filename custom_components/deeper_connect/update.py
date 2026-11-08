"""Firmware update entity (notification only: installing is done in the Deeper UI)."""
from __future__ import annotations

from homeassistant.components.update import UpdateEntity
from homeassistant.const import EntityCategory

from .entity import DeeperEntity


async def async_setup_entry(hass, entry, add):
    add([FirmwareUpdate(entry.runtime_data, entry.entry_id)])


class FirmwareUpdate(DeeperEntity, UpdateEntity):
    _attr_name = "Firmware"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry_id):
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{entry_id}_firmware"

    @property
    def installed_version(self):
        d = self.coordinator.data
        return (d.get("software") or {}).get("softwareVersion") or (d.get("latest") or {}).get("currentVersion")

    @property
    def latest_version(self):
        return (self.coordinator.data.get("latest") or {}).get("latestVersion") or self.installed_version
