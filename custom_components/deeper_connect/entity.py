"""Shared helpers."""
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


def tunnel_list(data) -> list[dict]:
    """Normalise listTunnels output. TODO: confirm real shape against a device."""
    t = (data or {}).get("tunnels")
    if isinstance(t, dict):
        t = [{"name": k, **(v if isinstance(v, dict) else {})} for k, v in t.items()]
    return t if isinstance(t, list) else (data if isinstance(data, list) else [])


def tunnel_id(t: dict) -> str:
    return str(t.get("id") or t.get("name") or t.get("tunnelName") or "unknown")


class DeeperEntity(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry_id: str) -> None:
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry_id)}, name="Deeper Connect",
                                            manufacturer="Deeper Network")
