"""Binary sensors."""
from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity

from .const import DOMAIN
from .entity import DeeperEntity, TunnelEntity, add_tunnel_entities, tunnel_unhealthy


async def async_setup_entry(hass, entry, add):
    coordinator, _ = hass.data[DOMAIN][entry.entry_id]
    add([AnyTunnelProblem(coordinator, entry.entry_id)])
    add_tunnel_entities(coordinator, entry.entry_id, add, lambda c, e, code: [TunnelProblem(c, e, code)])


class AnyTunnelProblem(DeeperEntity, BinarySensorEntity):
    _attr_name = "Tunnel problem"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator, entry_id):
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{entry_id}_tunnel_problem"

    @property
    def is_on(self):
        return any(tunnel_unhealthy(t) for t in self.coordinator.data["tunnels"].values())

    @property
    def extra_state_attributes(self):
        return {"unhealthy": [c for c, t in self.coordinator.data["tunnels"].items() if tunnel_unhealthy(t)]}


class TunnelProblem(TunnelEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator, entry_id, code):
        super().__init__(coordinator, entry_id, code)
        self._attr_unique_id = f"{entry_id}_{code}_problem"
        self._attr_name = f"Tunnel {code} problem"

    @property
    def is_on(self):
        return tunnel_unhealthy(self.tunnel)
