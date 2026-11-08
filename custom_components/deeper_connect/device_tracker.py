"""Map position of each tunnel's exit node (only when geo lookup is enabled)."""
from __future__ import annotations

from homeassistant.components.device_tracker import SourceType, TrackerEntity

from .const import CONF_GEO_LOOKUP, TUNNEL_ICONS
from .entity import TunnelEntity, add_tunnel_entities
from .location import tunnel_location


async def async_setup_entry(hass, entry, add):
    if not entry.options.get(CONF_GEO_LOOKUP):
        return
    add_tunnel_entities(entry.runtime_data, entry.entry_id, add, lambda c, e, code: [TunnelTracker(c, e, code)])


class TunnelTracker(TunnelEntity, TrackerEntity):
    _attr_source_type = SourceType.GPS
    _attr_location_accuracy = 25000  # geo-IP is city-level at best

    def __init__(self, coordinator, entry_id, code):
        super().__init__(coordinator, entry_id, code)
        self._attr_unique_id = f"{entry_id}_{code}_tracker"
        self._attr_name = "Exit node position"
        self._attr_icon = TUNNEL_ICONS["location"]

    def _loc(self) -> dict:
        return tunnel_location(self.tunnel, self.coordinator.data.get("geo"))

    @property
    def latitude(self):
        return self._loc()["latitude"]

    @property
    def longitude(self):
        return self._loc()["longitude"]

    @property
    def available(self) -> bool:
        return super().available and self.latitude is not None
