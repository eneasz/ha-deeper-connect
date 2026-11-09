"""Buttons."""
from __future__ import annotations

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.exceptions import HomeAssistantError

from .const import FEATURE_CONTROLS, FEATURE_TUNNELS, TUNNEL_ICONS
from .entity import DeeperEntity, TunnelEntity, add_tunnel_entities


def _check(resp) -> None:
    if isinstance(resp, dict) and resp.get("success") is False:
        raise HomeAssistantError(f"Device rejected the request: {resp.get('reason', 'unknown reason')}")


async def async_setup_entry(hass, entry, add):
    coordinator = entry.runtime_data
    if FEATURE_CONTROLS in coordinator.features:
        add([RebootButton(coordinator, entry.entry_id)])
    if FEATURE_TUNNELS in coordinator.features:
        add_tunnel_entities(coordinator, entry.entry_id, add, lambda c, e, code: [RefreshTunnel(c, e, code)])


class RefreshTunnel(TunnelEntity, ButtonEntity):
    """Ask the device to pick a fresh exit node for this tunnel."""

    def __init__(self, coordinator, entry_id, code):
        super().__init__(coordinator, entry_id, code)
        self._attr_unique_id = f"{entry_id}_{code}_refresh"
        self._attr_name = "Refresh exit node"
        self._attr_icon = TUNNEL_ICONS["refresh"]

    async def async_press(self):
        _check(await self.coordinator.client.refresh_tunnel(self.code))
        await self.coordinator.async_request_refresh()


class RebootButton(DeeperEntity, ButtonEntity):
    """Reboot the device. Disabled by default."""

    _attr_name = "Reboot"
    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, entry_id):
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{entry_id}_reboot"

    async def async_press(self):
        _check(await self.coordinator.client.reboot())
