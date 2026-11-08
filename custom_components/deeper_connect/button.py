"""Buttons."""
from homeassistant.components.button import ButtonEntity

from .const import DOMAIN
from .entity import DeeperEntity


async def async_setup_entry(hass, entry, add):
    coordinator, _ = hass.data[DOMAIN][entry.entry_id]
    add([RefreshTunnelsButton(coordinator, entry.entry_id)])


class RefreshTunnelsButton(DeeperEntity, ButtonEntity):
    _attr_name = "Refresh tunnels"

    def __init__(self, coordinator, entry_id):
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{entry_id}_refresh_tunnels"

    async def async_press(self):
        await self.coordinator.client.refresh_tunnel({})  # TODO: confirm payload
        await self.coordinator.async_request_refresh()
