"""Sensors."""
from homeassistant.components.sensor import SensorEntity

from .const import DOMAIN
from .entity import DeeperEntity, TunnelEntity, add_tunnel_entities


async def async_setup_entry(hass, entry, add):
    coordinator, _ = hass.data[DOMAIN][entry.entry_id]
    add([PublicIp(coordinator, entry.entry_id), WanStatus(coordinator, entry.entry_id)])
    add_tunnel_entities(coordinator, entry.entry_id, add,
                        lambda c, e, code: [TunnelNodes(c, e, code), TunnelIp(c, e, code)])


class PublicIp(DeeperEntity, SensorEntity):
    _attr_name = "Public IP"

    def __init__(self, coordinator, entry_id):
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{entry_id}_public_ip"

    @property
    def native_value(self):
        return self.coordinator.data["network"].get("pubIp")


class WanStatus(DeeperEntity, SensorEntity):
    _attr_name = "WAN status"

    def __init__(self, coordinator, entry_id):
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{entry_id}_wan_status"

    @property
    def native_value(self):
        return self.coordinator.data["wifi"].get("wanStatus")


class TunnelNodes(TunnelEntity, SensorEntity):
    def __init__(self, coordinator, entry_id, code):
        super().__init__(coordinator, entry_id, code)
        self._attr_unique_id = f"{entry_id}_{code}_nodes"
        self._attr_name = f"Tunnel {code} active nodes"

    @property
    def native_value(self):
        return self.tunnel.get("activeNum")


class TunnelIp(TunnelEntity, SensorEntity):
    def __init__(self, coordinator, entry_id, code):
        super().__init__(coordinator, entry_id, code)
        self._attr_unique_id = f"{entry_id}_{code}_ip"
        self._attr_name = f"Tunnel {code} exit IP"

    @property
    def native_value(self):
        return self.tunnel.get("activeIp")

    @property
    def extra_state_attributes(self):
        return {"region": self.tunnel.get("regionCode"), "country": self.tunnel.get("countryCode")}
