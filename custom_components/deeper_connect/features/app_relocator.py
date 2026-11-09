"""App Relocator: relocated-apps sensors and one relocation dropdown per chosen app."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.exceptions import HomeAssistantError

from ..api import DeeperError
from ..bases import DeeperSensor, DeeperSensorDescription
from ..const import CONF_APPS, TUNNEL_ICONS
from ..entity import DeeperEntity, TunnelEntity
from ..util import (OPT_DIRECT, OPT_NOT_SET, app_title, apps_for_tunnel, code_to_option, customised_apps, option_to_code,
                    relocated_apps)

SENSORS = (
    DeeperSensorDescription(key="relocated_apps", requires=("apps",), state_class=SensorStateClass.MEASUREMENT,
                            value_fn=lambda d: len(relocated_apps(d.get("apps"))) if d.get("apps") else None,
                            attrs_fn=lambda d: {"apps": relocated_apps(d.get("apps"))}),
)


class TunnelApps(TunnelEntity, SensorEntity):
    """How many apps are relocated through this tunnel (and which)."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry_id, code):
        super().__init__(coordinator, entry_id, code)
        self._attr_unique_id = f"{entry_id}_{code}_apps"
        self._attr_translation_key = "per_tunnel_apps"
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


class AppRelocationSelect(DeeperEntity, SelectEntity):
    """Which tunnel an app is relocated through: not_set, direct, or a tunnel code."""

    _attr_icon = TUNNEL_ICONS["apps"]

    def __init__(self, coordinator, entry_id, app: str) -> None:
        super().__init__(coordinator, entry_id)
        self.app = app
        self._attr_unique_id = f"{entry_id}_app_{app}"
        self._attr_translation_key = "app_relocation"
        self._attr_translation_placeholders = {"app": app_title(app)}

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


def setup_sensor(entry, add) -> None:
    add([DeeperSensor(entry.runtime_data, entry.entry_id, desc) for desc in SENSORS])


def setup_select(entry, add) -> None:
    coordinator = entry.runtime_data
    known = coordinator.data.get("apps") or {}
    chosen = entry.options.get(CONF_APPS)
    if chosen is None:  # never configured: start with the apps whose tunnel differs from the device default
        chosen = customised_apps(known)
    add([AppRelocationSelect(coordinator, entry.entry_id, app) for app in chosen if app in known])
