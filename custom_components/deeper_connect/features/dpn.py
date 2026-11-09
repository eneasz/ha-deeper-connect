"""DPN: tunnels (sub-devices, refresh, map position), routing mode and node selection."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.components.button import ButtonEntity
from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.components.select import SelectEntity
from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.exceptions import HomeAssistantError

from ..api import DeeperError
from ..const import CONF_GEO_LOOKUP, FEATURE_APPS, ICONS, TUNNEL_ICONS
from ..entity import DeeperEntity, TunnelEntity, add_tunnel_entities, check_response
from ..location import tunnel_location
from ..util import ROUTING_MODES, routing_request, tunnel_unhealthy
from .app_relocator import TunnelApps


class TunnelNodes(TunnelEntity, SensorEntity):
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry_id, code):
        super().__init__(coordinator, entry_id, code)
        self._attr_unique_id = f"{entry_id}_{code}_nodes"
        self._attr_translation_key = "per_tunnel_nodes"
        self._attr_icon = TUNNEL_ICONS["nodes"]

    @property
    def native_value(self):
        return self.tunnel.get("activeNum")


class TunnelIp(TunnelEntity, SensorEntity):
    def __init__(self, coordinator, entry_id, code):
        super().__init__(coordinator, entry_id, code)
        self._attr_unique_id = f"{entry_id}_{code}_ip"
        self._attr_translation_key = "per_tunnel_ip"
        self._attr_icon = TUNNEL_ICONS["ip"]

    @property
    def native_value(self):
        return self.tunnel.get("activeIp")

    @property
    def extra_state_attributes(self):
        return {"region": self.tunnel.get("regionCode"), "country": self.tunnel.get("countryCode")}


class TunnelLocation(TunnelEntity, SensorEntity):
    """Where the tunnel's current exit node is (country always; city when geo lookup is enabled)."""

    def __init__(self, coordinator, entry_id, code):
        super().__init__(coordinator, entry_id, code)
        self._attr_unique_id = f"{entry_id}_{code}_location"
        self._attr_translation_key = "per_tunnel_location"
        self._attr_icon = TUNNEL_ICONS["location"]

    def _loc(self) -> dict:
        return tunnel_location(self.tunnel, self.coordinator.data.get("geo"))

    @property
    def native_value(self):
        return self._loc()["label"]

    @property
    def extra_state_attributes(self):
        loc = self._loc()
        return {k: loc[k] for k in ("flag", "country", "country_code", "city", "region", "latitude", "longitude", "org")
                if loc.get(k) is not None} | {
            "exit_ip": self.tunnel.get("activeIp"), "tunnel_region": self.tunnel.get("regionCode"),
            "city_lookup": "enabled" if getattr(self.coordinator, "geo", None) else "off (Configure the integration to enable)"}


class TunnelProblem(TunnelEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator, entry_id, code):
        super().__init__(coordinator, entry_id, code)
        self._attr_unique_id = f"{entry_id}_{code}_problem"
        self._attr_translation_key = "per_tunnel_problem"
        self._attr_icon = TUNNEL_ICONS["problem"]

    @property
    def is_on(self):
        return tunnel_unhealthy(self.tunnel)


class RefreshTunnel(TunnelEntity, ButtonEntity):
    """Ask the device to pick a fresh exit node for this tunnel."""

    def __init__(self, coordinator, entry_id, code):
        super().__init__(coordinator, entry_id, code)
        self._attr_unique_id = f"{entry_id}_{code}_refresh"
        self._attr_translation_key = "per_tunnel_refresh"
        self._attr_icon = TUNNEL_ICONS["refresh"]

    async def async_press(self):
        check_response(await self.coordinator.client.refresh_tunnel(self.code))
        await self.coordinator.async_request_refresh()


class TunnelTracker(TunnelEntity, TrackerEntity):
    _attr_source_type = SourceType.GPS
    _attr_location_accuracy = 25000  # geo-IP is city-level at best

    def __init__(self, coordinator, entry_id, code):
        super().__init__(coordinator, entry_id, code)
        self._attr_unique_id = f"{entry_id}_{code}_tracker"
        self._attr_translation_key = "per_tunnel_position"
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


class RoutingModeSelect(DeeperEntity, SelectEntity):
    """Device routing mode. 'full' uses the remembered full-mode tunnel (see the set_routing_mode service to pick one).

    The device does not report its kill-switch state, so changing the mode from HA sends kill switch = off.
    Disabled by default.
    """

    _attr_translation_key = "routing_mode"
    requires = ("dpn",)
    _attr_options = list(ROUTING_MODES)
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, entry_id) -> None:
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{entry_id}_routing_mode"
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
    """How connections are spread over a tunnel's nodes."""

    _attr_translation_key = "node_selection"
    requires = ("lb",)
    _attr_options = NODE_MODES

    def __init__(self, coordinator, entry_id) -> None:
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{entry_id}_node_selection"
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


def setup_sensor(entry, add) -> None:
    coordinator = entry.runtime_data
    with_apps = FEATURE_APPS in coordinator.features
    add_tunnel_entities(coordinator, entry.entry_id, add,
                        lambda c, e, code: [TunnelLocation(c, e, code), TunnelNodes(c, e, code), TunnelIp(c, e, code)]
                        + ([TunnelApps(c, e, code)] if with_apps else []))


def setup_binary_sensor(entry, add) -> None:
    add_tunnel_entities(entry.runtime_data, entry.entry_id, add, lambda c, e, code: [TunnelProblem(c, e, code)])


def setup_button(entry, add) -> None:
    add_tunnel_entities(entry.runtime_data, entry.entry_id, add, lambda c, e, code: [RefreshTunnel(c, e, code)])


def setup_device_tracker(entry, add) -> None:
    if entry.options.get(CONF_GEO_LOOKUP):  # sends exit-node IPs to a lookup service, so opt-in
        add_tunnel_entities(entry.runtime_data, entry.entry_id, add, lambda c, e, code: [TunnelTracker(c, e, code)])


def setup_select(entry, add) -> None:
    add([RoutingModeSelect(entry.runtime_data, entry.entry_id), NodeSelectionSelect(entry.runtime_data, entry.entry_id)])
