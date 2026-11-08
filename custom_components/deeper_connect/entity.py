"""Shared entity bases."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


class DeeperEntity(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry_id: str) -> None:
        super().__init__(coordinator)
        self._entry_id = entry_id

    @property
    def device_info(self) -> DeviceInfo:
        d = self.coordinator.data or {}
        hw, dev, sw = d.get("hardware") or {}, d.get("device") or {}, d.get("software") or {}
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=f"Deeper {dev.get('deviceName') or 'Connect'}",
            manufacturer="Deeper Network",
            model=dev.get("target"),
            serial_number=hw.get("SN"),
            sw_version=sw.get("softwareVersion"),
            configuration_url=f"https://{self.coordinator.config_entry.data['host']}",
        )


class TunnelEntity(DeeperEntity):
    def __init__(self, coordinator, entry_id: str, code: str) -> None:
        super().__init__(coordinator, entry_id)
        self.code = code

    @property
    def tunnel(self) -> dict:
        return self.coordinator.data["tunnels"].get(self.code, {})

    @property
    def available(self) -> bool:
        return super().available and self.code in self.coordinator.data["tunnels"]


def add_tunnel_entities(coordinator, entry_id, add, factory) -> None:
    """Create entities for current tunnels and for any added later."""
    known: set[str] = set()

    def _sync() -> None:
        new = [c for c in coordinator.data["tunnels"] if c not in known]
        known.update(new)
        if new:
            add([e for c in new for e in factory(coordinator, entry_id, c)])

    _sync()
    coordinator.config_entry.async_on_unload(coordinator.async_add_listener(_sync))
