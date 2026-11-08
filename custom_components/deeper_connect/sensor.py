"""Sensors."""
from homeassistant.components.sensor import SensorEntity

from .const import DOMAIN
from .entity import DeeperEntity, tunnel_id, tunnel_list


async def async_setup_entry(hass, entry, add):
    coordinator, _ = hass.data[DOMAIN][entry.entry_id]
    add([TunnelCountSensor(coordinator, entry.entry_id)])


class TunnelCountSensor(DeeperEntity, SensorEntity):
    _attr_name = "Tunnels"

    def __init__(self, coordinator, entry_id):
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{entry_id}_tunnel_count"

    @property
    def native_value(self):
        return len(tunnel_list(self.coordinator.data["tunnels"]))

    @property
    def extra_state_attributes(self):
        return {tunnel_id(t): t for t in tunnel_list(self.coordinator.data["tunnels"])}
