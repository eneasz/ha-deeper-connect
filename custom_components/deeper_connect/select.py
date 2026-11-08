"""App relocation selects (one per app chosen in the integration options)."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.exceptions import HomeAssistantError

from .api import DeeperError
from .const import CONF_APPS, TUNNEL_ICONS
from .entity import DeeperEntity
from .util import OPT_DIRECT, OPT_NOT_SET, app_title, code_to_option, option_to_code


async def async_setup_entry(hass, entry, add):
    coordinator = entry.runtime_data
    known = coordinator.data.get("apps") or {}
    add([AppRelocationSelect(coordinator, entry.entry_id, app) for app in entry.options.get(CONF_APPS, []) if app in known])


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
