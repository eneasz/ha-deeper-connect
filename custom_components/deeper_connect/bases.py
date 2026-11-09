"""Description-driven entity classes shared by the core platforms and the feature modules."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorEntityDescription
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.exceptions import HomeAssistantError

from .api import DeeperError
from .const import ICONS
from .entity import DeeperEntity


@dataclass(frozen=True, kw_only=True)
class DeeperSensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict], Any]
    attrs_fn: Callable[[dict], dict] | None = None
    requires: tuple[str, ...] = ()  # coordinator data sections the entity reads (see DeeperEntity.available)


class DeeperSensor(DeeperEntity, SensorEntity):
    entity_description: DeeperSensorDescription

    def __init__(self, coordinator, entry_id, description) -> None:
        super().__init__(coordinator, entry_id)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_translation_key = description.key
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


@dataclass(frozen=True, kw_only=True)
class DeeperBinaryDescription(BinarySensorEntityDescription):
    is_on_fn: Callable[[dict], bool | None]
    attrs_fn: Callable[[dict], dict] | None = None
    requires: tuple[str, ...] = ()  # coordinator data sections the entity reads (see DeeperEntity.available)


class DeeperBinary(DeeperEntity, BinarySensorEntity):
    entity_description: DeeperBinaryDescription

    def __init__(self, coordinator, entry_id, description) -> None:
        super().__init__(coordinator, entry_id)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_translation_key = description.key
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


@dataclass(frozen=True, kw_only=True)
class DeeperSwitchDescription(SwitchEntityDescription):
    is_on_fn: Callable[[dict], bool | None]
    set_fn: Callable[[Any, bool, dict], Any]  # (client, value, data) -> awaitable
    requires: tuple[str, ...] = ()  # coordinator data sections the entity reads (see DeeperEntity.available)


def flag(section: str, field: str):
    def fn(d: dict):
        v = (d.get(section) or {}).get(field)
        return None if v is None else bool(v)
    return fn


class DeeperSwitch(DeeperEntity, SwitchEntity):
    entity_description: DeeperSwitchDescription

    def __init__(self, coordinator, entry_id, description) -> None:
        super().__init__(coordinator, entry_id)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_translation_key = description.key
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
