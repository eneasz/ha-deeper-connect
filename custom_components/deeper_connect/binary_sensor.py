"""Binary sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass, BinarySensorEntity, BinarySensorEntityDescription)
from homeassistant.const import EntityCategory

from .const import CONF_CLIENTS, FEATURE_ACCESS, FEATURE_TUNNELS, ICONS, TUNNEL_ICONS
from .entity import DeeperEntity, TunnelEntity, add_tunnel_entities
from .util import BLACKHOLE, all_clients, client_title, compute_health, pinned_clients, tunnel_unhealthy


@dataclass(frozen=True, kw_only=True)
class DeeperBinaryDescription(BinarySensorEntityDescription):
    is_on_fn: Callable[[dict], bool | None]
    attrs_fn: Callable[[dict], dict] | None = None


def _g(d, k):
    return d.get(k) or {}


_DIAG = dict(entity_category=EntityCategory.DIAGNOSTIC)

BINARY_SENSORS: tuple[DeeperBinaryDescription, ...] = (
    DeeperBinaryDescription(key="health_problem", name="Health problem", device_class=BinarySensorDeviceClass.PROBLEM,
                            is_on_fn=lambda d: compute_health(d)[0] == "problem",
                            attrs_fn=lambda d: {"reasons": compute_health(d)[1]}),
    DeeperBinaryDescription(key="tunnel_problem", name="Tunnel problem", device_class=BinarySensorDeviceClass.PROBLEM,
                            is_on_fn=lambda d: any(tunnel_unhealthy(t) for t in (d.get("tunnels") or {}).values()),
                            attrs_fn=lambda d: {"unhealthy": [c for c, t in (d.get("tunnels") or {}).items() if tunnel_unhealthy(t)]}),
    DeeperBinaryDescription(key="wan_connected", name="WAN connected", device_class=BinarySensorDeviceClass.CONNECTIVITY,
                            is_on_fn=lambda d: (_g(d, "wifi").get("wanStatus") == "connected") if _g(d, "wifi") else None),
    DeeperBinaryDescription(key="sharing", name="Bandwidth sharing", is_on_fn=lambda d: _g(d, "sharing").get("sharingEnabled"), **_DIAG),
)


async def async_setup_entry(hass, entry, add):
    coordinator = entry.runtime_data
    add([DeeperBinary(coordinator, entry.entry_id, desc) for desc in BINARY_SENSORS])
    if FEATURE_ACCESS in coordinator.features:
        chosen = entry.options.get(CONF_CLIENTS)
        if chosen is None:
            chosen = pinned_clients(coordinator.data)
        add([ClientBlackholed(coordinator, entry.entry_id, mac) for mac in chosen])
    if FEATURE_TUNNELS in coordinator.features:
        add_tunnel_entities(coordinator, entry.entry_id, add, lambda c, e, code: [TunnelProblem(c, e, code)])


class DeeperBinary(DeeperEntity, BinarySensorEntity):
    entity_description: DeeperBinaryDescription

    def __init__(self, coordinator, entry_id, description) -> None:
        super().__init__(coordinator, entry_id)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_icon = description.icon or ICONS.get(description.key)

    @property
    def is_on(self):
        try:
            return self.entity_description.is_on_fn(self.coordinator.data)
        except (KeyError, TypeError):
            return None

    @property
    def extra_state_attributes(self):
        fn = self.entity_description.attrs_fn
        try:
            return fn(self.coordinator.data) if fn else None
        except (KeyError, TypeError):
            return None


class TunnelProblem(TunnelEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator, entry_id, code):
        super().__init__(coordinator, entry_id, code)
        self._attr_unique_id = f"{entry_id}_{code}_problem"
        self._attr_name = "Problem"
        self._attr_icon = TUNNEL_ICONS["problem"]

    @property
    def is_on(self):
        return tunnel_unhealthy(self.tunnel)


class ClientBlackholed(DeeperEntity, BinarySensorEntity):
    """On while the device drops this client's traffic (route mode blackHole). Handy for alerting."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator, entry_id, mac: str) -> None:
        super().__init__(coordinator, entry_id)
        self.mac = mac.lower()
        self._attr_unique_id = f"{entry_id}_client_{self.mac}_blackholed"
        self._attr_icon = ICONS["client_blackholed"]

    @property
    def client(self) -> dict:
        return all_clients(self.coordinator.data).get(self.mac) or {}

    @property
    def name(self):
        return f"Client {client_title(self.client) if self.client else self.mac} blackholed"

    @property
    def available(self) -> bool:
        return super().available and bool(self.client)

    @property
    def is_on(self):
        return self.client.get("routeMode") == BLACKHOLE

    @property
    def extra_state_attributes(self):
        c = self.client
        return {"mac": self.mac, "online": c.get("online"), "route_mode": c.get("routeMode")}
