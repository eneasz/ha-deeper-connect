"""Switches for device settings (request bodies taken from the device's web UI)."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.exceptions import HomeAssistantError

from .api import DeeperError
from .const import FEATURE_CONTROLS, ICONS
from .entity import DeeperEntity


@dataclass(frozen=True, kw_only=True)
class DeeperSwitchDescription(SwitchEntityDescription):
    is_on_fn: Callable[[dict], bool | None]
    set_fn: Callable[[Any, bool, dict], Any]  # (client, value, data) -> awaitable


def _flag(section: str, field: str):
    def fn(d: dict):
        v = (d.get(section) or {}).get(field)
        return None if v is None else bool(v)
    return fn


def _reboot_cfg(client, on: bool, data: dict):
    return client.set_auto_reboot({**(data.get("autoreboot") or {}), "on": on})


SWITCHES: tuple[DeeperSwitchDescription, ...] = (
    DeeperSwitchDescription(key="ads_filter", name="YouTube ad blocking", is_on_fn=_flag("ads", "enable"),
                            set_fn=lambda c, v, d: c.set_youtube_ads(v)),
    DeeperSwitchDescription(key="ssl_bypass", name="SSL bypass", is_on_fn=_flag("ssl", "enable"),
                            set_fn=lambda c, v, d: c.set_ssl_bypass(v)),
    DeeperSwitchDescription(key="udp_server", name="UDP server", is_on_fn=_flag("udp", "enabled"),
                            set_fn=lambda c, v, d: c.set_udp_server(v)),
    DeeperSwitchDescription(key="auto_update", name="Auto-update", is_on_fn=_flag("autoupdate", "autoUpdate"),
                            set_fn=lambda c, v, d: c.set_auto_update(v)),
    DeeperSwitchDescription(key="auto_reboot", name="Scheduled reboot", is_on_fn=_flag("autoreboot", "on"),
                            set_fn=_reboot_cfg),
)


async def async_setup_entry(hass, entry, add):
    if FEATURE_CONTROLS in entry.runtime_data.features:
        add([DeeperSwitch(entry.runtime_data, entry.entry_id, d) for d in SWITCHES])


class DeeperSwitch(DeeperEntity, SwitchEntity):
    entity_description: DeeperSwitchDescription

    def __init__(self, coordinator, entry_id, description) -> None:
        super().__init__(coordinator, entry_id)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_icon = ICONS.get(description.key)

    @property
    def is_on(self):
        return self.entity_description.is_on_fn(self.coordinator.data)

    async def _set(self, value: bool) -> None:
        d = self.entity_description
        try:
            await self.coordinator.async_control(lambda: d.set_fn(self.coordinator.client, value, self.coordinator.data))
        except DeeperError as err:
            raise HomeAssistantError(f"{d.name}: {err}") from err

    async def async_turn_on(self, **kwargs):
        await self._set(True)

    async def async_turn_off(self, **kwargs):
        await self._set(False)
