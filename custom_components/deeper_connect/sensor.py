"""Sensors."""
from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfDataRate, UnitOfInformation, UnitOfTemperature, UnitOfTime

from .const import CONF_CLIENTS, FEATURE_ACCESS, FEATURE_APPS, FEATURE_TUNNELS, ICONS, TUNNEL_ICONS
from .entity import DeeperEntity, TunnelEntity, add_tunnel_entities
from .location import tunnel_location
from .util import (all_clients, apps_for_tunnel, avg_last, blackholed_clients, client_title, compute_health, last,
                   parse_size, parse_uptime, pinned_clients, relocated_apps, to_float)


@dataclass(frozen=True, kw_only=True)
class DeeperSensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict], Any]
    attrs_fn: Callable[[dict], dict] | None = None


def _g(d: dict, key: str) -> dict:
    return d.get(key) or {}


def _info(d: dict, i: int):
    info = d.get("info")
    return info[i] if isinstance(info, list) and len(info) > i else None


def _size(section: str, group: str, direction: str):
    return lambda d: parse_size(_g(_g(d, section), group).get(direction))


_BYTES = dict(device_class=SensorDeviceClass.DATA_SIZE, native_unit_of_measurement=UnitOfInformation.BYTES,
              suggested_unit_of_measurement=UnitOfInformation.MEGABYTES, state_class=SensorStateClass.TOTAL_INCREASING,
              suggested_display_precision=1)
_DIAG = dict(entity_category=EntityCategory.DIAGNOSTIC)

SENSORS: tuple[DeeperSensorDescription, ...] = (
    # --- health & resources ---
    DeeperSensorDescription(key="health", name="Health", device_class=SensorDeviceClass.ENUM,
                            options=["ok", "warning", "problem"], value_fn=lambda d: compute_health(d)[0],
                            attrs_fn=lambda d: {"reasons": compute_health(d)[1]}),
    DeeperSensorDescription(key="cpu", name="CPU usage", native_unit_of_measurement=PERCENTAGE,
                            state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=0,
                            value_fn=lambda d: last(_g(d, "usage").get("cpuUsageData")),
                            attrs_fn=lambda d: {"average_15min": avg_last(_g(d, "usage").get("cpuUsageData"), 3)}),
    DeeperSensorDescription(key="memory", name="Memory usage", native_unit_of_measurement=PERCENTAGE,
                            state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=0,
                            value_fn=lambda d: last(_g(d, "usage").get("memUsageData"))),
    DeeperSensorDescription(key="temperature", name="Temperature", device_class=SensorDeviceClass.TEMPERATURE,
                            native_unit_of_measurement=UnitOfTemperature.CELSIUS, state_class=SensorStateClass.MEASUREMENT,
                            value_fn=lambda d: to_float(_g(d, "hardware").get("tempInCelsius"))),
    DeeperSensorDescription(key="uptime", name="Uptime", device_class=SensorDeviceClass.DURATION,
                            native_unit_of_measurement=UnitOfTime.SECONDS, suggested_unit_of_measurement=UnitOfTime.HOURS,
                            state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=1,
                            value_fn=lambda d: parse_uptime(_info(d, 0))),
    # --- sessions ---
    DeeperSensorDescription(key="sessions", name="Sessions", state_class=SensorStateClass.MEASUREMENT,
                            value_fn=lambda d: to_float(_g(d, "sessions").get("currSessionNum")),
                            attrs_fn=lambda d: {k: to_float(v) for k, v in _g(d, "sessions").items()}),
    DeeperSensorDescription(key="tunnel_sessions", name="Tunnel sessions", state_class=SensorStateClass.MEASUREMENT,
                            value_fn=lambda d: to_float(_g(d, "sessions").get("tunnelSessionNum"))),
    DeeperSensorDescription(key="clients_online", name="Clients online", state_class=SensorStateClass.MEASUREMENT,
                            value_fn=lambda d: len(_g(d, "clients").get("online") or []),
                            attrs_fn=lambda d: {"clients": [c.get("name") or c.get("remark") or "unnamed"
                                                            for c in _g(d, "clients").get("online") or []]}),
    # --- traffic ---
    DeeperSensorDescription(key="live_upload", name="Upload speed", device_class=SensorDeviceClass.DATA_RATE,
                            native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
                            suggested_unit_of_measurement=UnitOfDataRate.MEGABYTES_PER_SECOND,
                            state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=2,
                            value_fn=lambda d: last(_g(d, "live").get("upLoadData"))),
    DeeperSensorDescription(key="live_download", name="Download speed", device_class=SensorDeviceClass.DATA_RATE,
                            native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
                            suggested_unit_of_measurement=UnitOfDataRate.MEGABYTES_PER_SECOND,
                            state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=2,
                            value_fn=lambda d: last(_g(d, "live").get("downLoadData"))),
    DeeperSensorDescription(key="local_upload", name="Local traffic upload", value_fn=_size("traffic", "localTraffic", "upload"), **_BYTES),
    DeeperSensorDescription(key="local_download", name="Local traffic download", value_fn=_size("traffic", "localTraffic", "download"), **_BYTES),
    DeeperSensorDescription(key="client_upload", name="Client traffic upload", value_fn=_size("traffic", "clientTraffic", "upload"), **_BYTES),
    DeeperSensorDescription(key="client_download", name="Client traffic download", value_fn=_size("traffic", "clientTraffic", "download"), **_BYTES),
    DeeperSensorDescription(key="routed_traffic", name="Routed traffic", value_fn=lambda d: to_float(_g(d, "routed").get("traffic")),
                            **{**_BYTES, "state_class": SensorStateClass.TOTAL_INCREASING}),
    DeeperSensorDescription(key="saved_traffic", name="Saved traffic", value_fn=lambda d: to_float(_g(d, "saved").get("saved")),
                            **_BYTES),
    # --- security ---
    DeeperSensorDescription(key="blocked_total", name="Blocked requests", state_class=SensorStateClass.TOTAL_INCREASING,
                            value_fn=lambda d: to_float(_g(d, "blocked").get("total")),
                            attrs_fn=lambda d: dict(_g(d, "blocked"))),
    # --- network / routing ---
    DeeperSensorDescription(key="public_ip", name="Public IP", value_fn=lambda d: _g(d, "network").get("pubIp")),
    DeeperSensorDescription(key="wan_status", name="WAN status", value_fn=lambda d: _g(d, "wifi").get("wanStatus")),
    DeeperSensorDescription(key="connection_mode", name="Connection mode", value_fn=lambda d: _g(d, "wifi").get("mode"), **_DIAG),
    DeeperSensorDescription(key="relocated_apps", name="Relocated apps", state_class=SensorStateClass.MEASUREMENT,
                            value_fn=lambda d: len(relocated_apps(d.get("apps"))) if d.get("apps") else None,
                            attrs_fn=lambda d: {"apps": relocated_apps(d.get("apps"))}),
    DeeperSensorDescription(key="tunnel_count", name="Tunnels", state_class=SensorStateClass.MEASUREMENT,
                            value_fn=lambda d: len(d.get("tunnels") or {})),
    # --- versions ---
    DeeperSensorDescription(key="app_sig", name="App signature version", value_fn=lambda d: _g(d, "software").get("appSigVersion"), **_DIAG),
    DeeperSensorDescription(key="rule_version", name="Built-in rule version", value_fn=lambda d: _g(d, "software").get("builtinRuleVersion"), **_DIAG),
    DeeperSensorDescription(key="url_sig", name="URL signature version", value_fn=lambda d: _g(d, "software").get("urlSigVersion"), **_DIAG),
)


BLACKHOLED_CLIENTS = DeeperSensorDescription(
    key="blackholed_clients", name="Blackholed clients", state_class=SensorStateClass.MEASUREMENT,
    value_fn=lambda d: len(blackholed_clients(d)) if d.get("clients") else None,
    attrs_fn=lambda d: {"clients": [client_title(c) for c in blackholed_clients(d)],
                        "route_modes": dict(Counter(c.get("routeMode") or "unknown" for c in all_clients(d).values()))})


async def async_setup_entry(hass, entry, add):
    coordinator = entry.runtime_data
    feats = coordinator.features
    descs = [d for d in SENSORS if d.key != "relocated_apps" or FEATURE_APPS in feats]
    add([DeeperSensor(coordinator, entry.entry_id, desc) for desc in descs])
    if FEATURE_ACCESS in feats:
        add([DeeperSensor(coordinator, entry.entry_id, BLACKHOLED_CLIENTS)])
        chosen = entry.options.get(CONF_CLIENTS)
        if chosen is None:  # never configured: follow the clients pinned in the Deeper UI
            chosen = pinned_clients(coordinator.data)
        add([ClientRouteMode(coordinator, entry.entry_id, mac) for mac in chosen])
    if FEATURE_TUNNELS in feats:
        add_tunnel_entities(coordinator, entry.entry_id, add,
                            lambda c, e, code: [TunnelLocation(c, e, code), TunnelNodes(c, e, code), TunnelIp(c, e, code)]
                            + ([TunnelApps(c, e, code)] if FEATURE_APPS in feats else []))


class DeeperSensor(DeeperEntity, SensorEntity):
    entity_description: DeeperSensorDescription

    def __init__(self, coordinator, entry_id, description) -> None:
        super().__init__(coordinator, entry_id)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_icon = description.icon or ICONS.get(description.key)

    @property
    def icon(self):
        if self.entity_description.key == "health":
            return {"ok": "mdi:heart-pulse", "warning": "mdi:alert-circle-outline", "problem": "mdi:alert-octagon"}.get(
                self.native_value, "mdi:heart-pulse")
        return self._attr_icon

    @property
    def native_value(self):
        try:
            return self.entity_description.value_fn(self.coordinator.data)
        except (KeyError, IndexError, TypeError, ValueError):
            return None

    @property
    def extra_state_attributes(self):
        fn = self.entity_description.attrs_fn
        try:
            return fn(self.coordinator.data) if fn else None
        except (KeyError, IndexError, TypeError, ValueError):
            return None


class TunnelNodes(TunnelEntity, SensorEntity):
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry_id, code):
        super().__init__(coordinator, entry_id, code)
        self._attr_unique_id = f"{entry_id}_{code}_nodes"
        self._attr_name = "Active nodes"
        self._attr_icon = TUNNEL_ICONS["nodes"]

    @property
    def native_value(self):
        return self.tunnel.get("activeNum")


class TunnelIp(TunnelEntity, SensorEntity):
    def __init__(self, coordinator, entry_id, code):
        super().__init__(coordinator, entry_id, code)
        self._attr_unique_id = f"{entry_id}_{code}_ip"
        self._attr_name = "Exit IP"
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
        self._attr_name = "Location"
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


class TunnelApps(TunnelEntity, SensorEntity):
    """How many apps are relocated through this tunnel (and which)."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry_id, code):
        super().__init__(coordinator, entry_id, code)
        self._attr_unique_id = f"{entry_id}_{code}_apps"
        self._attr_name = "Relocated apps"
        self._attr_icon = TUNNEL_ICONS["apps"]

    @property
    def available(self) -> bool:
        return super().available and bool(self.coordinator.data.get("apps"))

    @property
    def native_value(self):
        return len(apps_for_tunnel(self.coordinator.data.get("apps"), self.code))

    @property
    def extra_state_attributes(self):
        return {"apps": apps_for_tunnel(self.coordinator.data.get("apps"), self.code)}


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
