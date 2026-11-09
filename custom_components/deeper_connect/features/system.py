"""System (Settings, Device): auto-update, scheduled reboot and its time, Reboot button."""
from __future__ import annotations

from datetime import time

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.components.time import TimeEntity
from homeassistant.exceptions import HomeAssistantError

from ..api import DeeperError
from ..bases import DeeperSwitch, DeeperSwitchDescription, flag
from ..const import ICONS
from ..entity import DeeperEntity, check_response


def _reboot_cfg(client, on: bool, data: dict):
    return client.set_auto_reboot({**(data.get("autoreboot") or {}), "on": on})


SWITCHES: tuple[DeeperSwitchDescription, ...] = (
    DeeperSwitchDescription(key="auto_update", requires=("autoupdate",), name="Auto-update", is_on_fn=flag("autoupdate", "autoUpdate"),
                            set_fn=lambda c, v, d: c.set_auto_update(v)),
    DeeperSwitchDescription(key="auto_reboot", requires=("autoreboot",), name="Scheduled reboot", is_on_fn=flag("autoreboot", "on"),
                            set_fn=_reboot_cfg),
)


class RebootButton(DeeperEntity, ButtonEntity):
    """Reboot the device. Disabled by default."""

    _attr_name = "Reboot"
    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, entry_id):
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{entry_id}_reboot"

    async def async_press(self):
        check_response(await self.coordinator.client.reboot())


class RebootTime(DeeperEntity, TimeEntity):
    _attr_name = "Scheduled reboot time"
    requires = ("autoreboot",)

    def __init__(self, coordinator, entry_id) -> None:
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{entry_id}_reboot_time"
        self._attr_icon = ICONS["reboot_time"]

    @property
    def native_value(self):
        c = self.coordinator.data.get("autoreboot") or {}
        try:
            return time(int(c["hour"]), int(c["minute"]))
        except (KeyError, TypeError, ValueError):
            return None

    async def async_set_value(self, value: time) -> None:
        cfg = {**(self.coordinator.data.get("autoreboot") or {}), "hour": value.hour, "minute": value.minute}
        try:
            await self.coordinator.async_control(self.coordinator.client.set_auto_reboot, cfg)
        except DeeperError as err:
            raise HomeAssistantError(f"Could not set reboot time: {err}") from err


def setup_switch(entry, add) -> None:
    add([DeeperSwitch(entry.runtime_data, entry.entry_id, d) for d in SWITCHES])


def setup_button(entry, add) -> None:
    add([RebootButton(entry.runtime_data, entry.entry_id)])


def setup_time(entry, add) -> None:
    add([RebootTime(entry.runtime_data, entry.entry_id)])
