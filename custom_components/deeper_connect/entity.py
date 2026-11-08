"""Shared helpers."""
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


def tunnel_unhealthy(t: dict) -> bool:
    """A tunnel is unhealthy when it has no active node/IP (observed fields: activeNum, activeIp)."""
    return not t.get("activeNum") or not t.get("activeIp")


class DeeperEntity(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry_id: str) -> None:
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry_id)}, name="Deeper Connect",
                                            manufacturer="Deeper Network")


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
    coordinator.async_add_listener(_sync)
