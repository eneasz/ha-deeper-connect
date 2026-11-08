"""Buttons."""
from homeassistant.components.button import ButtonEntity

from .const import DOMAIN
from .entity import TunnelEntity, add_tunnel_entities


async def async_setup_entry(hass, entry, add):
    coordinator, _ = hass.data[DOMAIN][entry.entry_id]
    add_tunnel_entities(coordinator, entry.entry_id, add, lambda c, e, code: [RefreshTunnel(c, e, code)])


class RefreshTunnel(TunnelEntity, ButtonEntity):
    def __init__(self, coordinator, entry_id, code):
        super().__init__(coordinator, entry_id, code)
        self._attr_unique_id = f"{entry_id}_{code}_refresh"
        self._attr_name = f"Refresh tunnel {code}"

    async def async_press(self):
        await self.coordinator.client.refresh_tunnel(self.code)
        await self.coordinator.async_request_refresh()
