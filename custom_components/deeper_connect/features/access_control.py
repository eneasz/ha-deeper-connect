"""Access Control: per-client routing visibility (route mode, blackholed alerts)."""
from __future__ import annotations

from collections import Counter

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.components.sensor import SensorEntity, SensorStateClass

from ..bases import DeeperSensor, DeeperSensorDescription
from homeassistant.components.select import SelectEntity
from homeassistant.exceptions import HomeAssistantError

from ..api import DeeperError
from ..const import CONF_CLIENT_CONTROL, CONF_CLIENTS, ICONS
from ..entity import DeeperEntity
from ..util import BLACKHOLE, all_clients, blackholed_clients, client_title, pinned_clients


BLACKHOLED_CLIENTS = DeeperSensorDescription(
    key="blackholed_clients", state_class=SensorStateClass.MEASUREMENT,
    value_fn=lambda d: len(blackholed_clients(d)) if d.get("clients") else None,
    attrs_fn=lambda d: {"clients": [client_title(c) for c in blackholed_clients(d)],
                        "route_modes": dict(Counter(c.get("routeMode") or "unknown" for c in all_clients(d).values()))})


class ClientNamed:
    """Names a per-client entity after the client's current title (the name can change in the Deeper app).

    HA caches `Entity.name`, so after updating the placeholder the cached value is dropped.
    """

    def _client_label(self) -> str:
        return client_title(self.client) if self.client else self.mac

    def _refresh_name(self) -> None:
        label = self._client_label()
        if getattr(self, "_attr_translation_placeholders", {}).get("client") != label:
            self._attr_translation_placeholders = {"client": label}
            self.__dict__.pop("name", None)

    def _handle_coordinator_update(self) -> None:
        self._refresh_name()
        super()._handle_coordinator_update()


class ClientRouteMode(ClientNamed, DeeperEntity, SensorEntity):
    """How the device routes one client: smart, disabled (direct), blackHole (dropped), ...

    Alert on this changing to `blackHole` to find out when a device was cut off.
    """

    def __init__(self, coordinator, entry_id, mac: str) -> None:
        super().__init__(coordinator, entry_id)
        self.mac = mac.lower()
        self._attr_unique_id = f"{entry_id}_client_{self.mac}_route"
        self._attr_icon = ICONS["client_route"]
        self._attr_translation_key = "client_route_mode"
        self._refresh_name()

    @property
    def client(self) -> dict:
        return all_clients(self.coordinator.data).get(self.mac) or {}

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


class ClientBlackholed(ClientNamed, DeeperEntity, BinarySensorEntity):
    """On while the device drops this client's traffic (route mode blackHole). Handy for alerting."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator, entry_id, mac: str) -> None:
        super().__init__(coordinator, entry_id)
        self.mac = mac.lower()
        self._attr_unique_id = f"{entry_id}_client_{self.mac}_blackholed"
        self._attr_icon = ICONS["client_blackholed"]
        self._attr_translation_key = "client_blackholed"
        self._refresh_name()

    @property
    def client(self) -> dict:
        return all_clients(self.coordinator.data).get(self.mac) or {}

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


# select option -> the device's routeMode. 'full' options are one per tunnel: "full_<TUNNEL CODE>".
CLIENT_FIXED_OPTIONS = {"smart": "smart", "disabled": "disabled", "blackhole": "blackHole"}


def client_option(client: dict) -> str | None:
    """The select option that describes a client's current routing, or None if it is not one we offer."""
    mode = client.get("routeMode")
    if mode == "full":
        return f"full_{client['regionCode']}" if client.get("regionCode") else None
    return next((opt for opt, device in CLIENT_FIXED_OPTIONS.items() if device == mode), None)


class ClientRouteSelect(ClientNamed, DeeperEntity, SelectEntity):
    """Change how one client is routed (smart route, full tunnel through a chosen tunnel, disabled, or blackhole = cut off).

    Only created when "Allow changing client routing" is on in the options. Choosing blackhole stops the device's traffic.
    """

    _attr_translation_key = "client_route_select"
    requires = ("clients",)

    def __init__(self, coordinator, entry_id, mac: str) -> None:
        super().__init__(coordinator, entry_id)
        self.mac = mac.lower()
        self._attr_unique_id = f"{entry_id}_client_{self.mac}_route_select"
        self._attr_icon = ICONS["client_route_select"]
        self._refresh_name()

    @property
    def client(self) -> dict:
        return all_clients(self.coordinator.data).get(self.mac) or {}

    @property
    def available(self) -> bool:
        return super().available and bool(self.client)

    @property
    def options(self) -> list[str]:
        opts = [*CLIENT_FIXED_OPTIONS, *(f"full_{code}" for code in sorted(self.coordinator.data.get("tunnels") or {}))]
        current = client_option(self.client)
        return opts + [current] if current and current not in opts else opts  # keep showing a tunnel that is no longer listed

    @property
    def current_option(self):
        return client_option(self.client)

    async def async_select_option(self, option: str) -> None:
        if option.startswith("full_"):
            mode, region = "full", option[len("full_"):]
        elif option in CLIENT_FIXED_OPTIONS:
            mode, region = CLIENT_FIXED_OPTIONS[option], None
        else:
            raise HomeAssistantError(f"Unknown routing option {option!r}")
        try:
            await self.coordinator.async_control(self.coordinator.client.set_client_route, self.mac, mode, region)
        except DeeperError as err:
            raise HomeAssistantError(f"Could not change routing of {self._client_label()}: {err}") from err


def _chosen_clients(entry) -> list[str]:
    chosen = entry.options.get(CONF_CLIENTS)
    return pinned_clients(entry.runtime_data.data) if chosen is None else chosen  # never configured: follow the UI pins


def setup_sensor(entry, add) -> None:
    coordinator = entry.runtime_data
    add([DeeperSensor(coordinator, entry.entry_id, BLACKHOLED_CLIENTS)])
    add([ClientRouteMode(coordinator, entry.entry_id, mac) for mac in _chosen_clients(entry)])


def setup_binary_sensor(entry, add) -> None:
    add([ClientBlackholed(entry.runtime_data, entry.entry_id, mac) for mac in _chosen_clients(entry)])


def setup_select(entry, add) -> None:
    if entry.options.get(CONF_CLIENT_CONTROL):
        add([ClientRouteSelect(entry.runtime_data, entry.entry_id, mac) for mac in _chosen_clients(entry)])
