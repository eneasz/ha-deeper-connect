"""Access Control: per-client routing visibility (route mode, blackholed alerts)."""
from __future__ import annotations

from collections import Counter

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.components.sensor import SensorEntity, SensorStateClass

from ..bases import DeeperSensor, DeeperSensorDescription
from ..const import CONF_CLIENTS, ICONS
from ..entity import DeeperEntity
from ..util import BLACKHOLE, all_clients, blackholed_clients, client_title, pinned_clients


BLACKHOLED_CLIENTS = DeeperSensorDescription(
    key="blackholed_clients", name="Blackholed clients", state_class=SensorStateClass.MEASUREMENT,
    value_fn=lambda d: len(blackholed_clients(d)) if d.get("clients") else None,
    attrs_fn=lambda d: {"clients": [client_title(c) for c in blackholed_clients(d)],
                        "route_modes": dict(Counter(c.get("routeMode") or "unknown" for c in all_clients(d).values()))})


class ClientRouteMode(DeeperEntity, SensorEntity):
    """How the device routes one client: smart, disabled (direct), blackHole (dropped), ...

    Alert on this changing to `blackHole` to find out when a device was cut off.
    """

    def __init__(self, coordinator, entry_id, mac: str) -> None:
        super().__init__(coordinator, entry_id)
        self.mac = mac.lower()
        self._attr_unique_id = f"{entry_id}_client_{self.mac}_route"
        self._attr_icon = ICONS["client_route"]

    @property
    def client(self) -> dict:
        return all_clients(self.coordinator.data).get(self.mac) or {}

    @property
    def name(self):
        return f"Client {client_title(self.client) if self.client else self.mac} route mode"

    @property
    def available(self) -> bool:
        return super().available and bool(self.client)

    @property
    def native_value(self):
        return self.client.get("routeMode")

    @property
    def extra_state_attributes(self):
        c = self.client
        return {"mac": self.mac, "online": c.get("online"), "ip": c.get("ip"), "device_name": c.get("name") or None,
                "remark": c.get("remark") or None, "region": c.get("regionCode"), "https_filter": c.get("httpsFilter"),
                "bandwidth_limit": c.get("bwLimit")}


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


def _chosen_clients(entry) -> list[str]:
    chosen = entry.options.get(CONF_CLIENTS)
    return pinned_clients(entry.runtime_data.data) if chosen is None else chosen  # never configured: follow the UI pins


def setup_sensor(entry, add) -> None:
    coordinator = entry.runtime_data
    add([DeeperSensor(coordinator, entry.entry_id, BLACKHOLED_CLIENTS)])
    add([ClientRouteMode(coordinator, entry.entry_id, mac) for mac in _chosen_clients(entry)])


def setup_binary_sensor(entry, add) -> None:
    add([ClientBlackholed(entry.runtime_data, entry.entry_id, mac) for mac in _chosen_clients(entry)])
