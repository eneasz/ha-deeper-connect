"""Binary sensors."""
from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity

from .const import DOMAIN
from .entity import DeeperEntity, tunnel_list

# TODO: confirm which field/values mean "healthy" once real listTunnels output is captured.
BAD_STATES = {"failed", "error", "disconnected", "offline", "down"}


async def async_setup_entry(hass, entry, add):
    coordinator, _ = hass.data[DOMAIN][entry.entry_id]
    add([TunnelProblem(coordinator, entry.entry_id)])


class TunnelProblem(DeeperEntity, BinarySensorEntity):
    _attr_name = "Tunnel problem"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator, entry_id):
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{entry_id}_tunnel_problem"

    @property
    def is_on(self):
        return any(str(t.get("status", t.get("state", ""))).lower() in BAD_STATES
                   for t in tunnel_list(self.coordinator.data["tunnels"]))
