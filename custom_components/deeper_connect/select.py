"""App relocation selects (one per app chosen in the integration options)."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.exceptions import HomeAssistantError

from .api import DeeperError
from .const import CONF_APPS, ICONS, TUNNEL_ICONS
from .entity import DeeperEntity
from .util import (OPT_DIRECT, OPT_NOT_SET, ROUTING_MODES, app_title, code_to_option, customised_apps, option_to_code,
                   routing_request)


async def async_setup_entry(hass, entry, add):
    coordinator = entry.runtime_data
    known = coordinator.data.get("apps") or {}
    chosen = entry.options.get(CONF_APPS)
    if chosen is None:  # never configured: start with the apps whose tunnel differs from the device default
        chosen = customised_apps(known)
    add([RoutingModeSelect(coordinator, entry.entry_id), NodeSelectionSelect(coordinator, entry.entry_id)])
    add([AppRelocationSelect(coordinator, entry.entry_id, app) for app in chosen if app in known])


class AppRelocationSelect(DeeperEntity, SelectEntity):
    """Which tunnel an app is relocated through: not_set, direct, or a tunnel code."""

    _attr_icon = TUNNEL_ICONS["apps"]

    def __init__(self, coordinator, entry_id, app: str) -> None:
        super().__init__(coordinator, entry_id)
        self.app = app
        self._attr_unique_id = f"{entry_id}_app_{app}"
        self._attr_name = f"App {app_title(app)} relocation"

    @property
    def _info(self) -> dict:
        return (self.coordinator.data.get("apps") or {}).get(self.app) or {}

    @property
    def available(self) -> bool:
        return super().available and bool(self._info)

    @property
    def current_option(self):
        return code_to_option(self._info.get("tunnel"))

    @property
    def options(self) -> list[str]:
        opts = [OPT_NOT_SET, OPT_DIRECT, *sorted(self.coordinator.data["tunnels"])]
        cur = self.current_option
        return opts if cur in opts else [*opts, cur]

    @property
    def extra_state_attributes(self):
        i = self._info
        return {"locked_tunnels": i.get("lockedTunnels"), "recommended_tunnels": i.get("recommendedTunnels"),
                "default_tunnel": i.get("defaultTunnel"), "website": i.get("website"), "inactive": i.get("inactive")}

    async def async_select_option(self, option: str) -> None:
        try:
            await self.coordinator.async_set_app_tunnel(self.app, option_to_code(option))
        except DeeperError as err:
            raise HomeAssistantError(f"Could not relocate {self.app}: {err}") from err


class RoutingModeSelect(DeeperEntity, SelectEntity):
    """Device routing mode. 'full' uses the remembered full-mode tunnel (see the set_routing_mode service to pick one).

    The device does not report its kill-switch state, so changing the mode from HA sends kill switch = off.
    Disabled by default.
    """

    _attr_translation_key = "routing_mode"
    _attr_options = list(ROUTING_MODES)
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, entry_id) -> None:
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{entry_id}_routing_mode"
        self._attr_name = "Routing mode"
        self._attr_icon = ICONS["routing_mode"]

    @property
    def current_option(self):
        v = (self.coordinator.data.get("dpn") or {}).get("dpnMode")
        return v if v in ROUTING_MODES else None

    @property
    def extra_state_attributes(self):
        d = self.coordinator.data.get("dpn") or {}
        return {"smart_tunnel": d.get("smartTunnel"), "full_tunnel": d.get("fullTunnel"), "tunnel": d.get("tunnelCode")}

    async def async_select_option(self, option: str) -> None:
        data = self.coordinator.data
        try:
            body = routing_request(option, None, data.get("dpn"), data["tunnels"])
            await self.coordinator.async_control(self.coordinator.client.set_dpn_mode, body)
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err
        except DeeperError as err:
            raise HomeAssistantError(f"Could not set routing mode: {err}") from err


NODE_MODES = ["none", "random", "domain", "rr"]


class NodeSelectionSelect(DeeperEntity, SelectEntity):
    """How connections are spread over a tunnel's nodes. Request body inferred: disabled by default."""

    _attr_translation_key = "node_selection"
    _attr_options = NODE_MODES
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, entry_id) -> None:
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{entry_id}_node_selection"
        self._attr_name = "Node selection mode"
        self._attr_icon = ICONS["node_selection"]

    @property
    def current_option(self):
        v = (self.coordinator.data.get("lb") or {}).get("mode")
        return v if v in NODE_MODES else None

    async def async_select_option(self, option: str) -> None:
        try:
            await self.coordinator.async_control(self.coordinator.client.set_node_lb_mode, option)
        except DeeperError as err:
            raise HomeAssistantError(f"Could not set node selection mode: {err}") from err
