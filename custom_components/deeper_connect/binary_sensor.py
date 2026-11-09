"""Binary sensors for the always-on core; the optional groups live in features/<name>.py."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import EntityCategory

from .bases import DeeperBinary, DeeperBinaryDescription
from .features.access_control import ClientBlackholed
from .features.dpn import TunnelProblem
from .features.loader import setup_features
from .util import compute_health, tunnel_unhealthy

__all__ = ["BINARY_SENSORS", "ClientBlackholed", "DeeperBinary", "DeeperBinaryDescription", "TunnelProblem"]


def _g(d, k):
    return d.get(k) or {}


_DIAG = dict(entity_category=EntityCategory.DIAGNOSTIC)

BINARY_SENSORS: tuple[DeeperBinaryDescription, ...] = (
    DeeperBinaryDescription(key="health_problem", device_class=BinarySensorDeviceClass.PROBLEM,
                            is_on_fn=lambda d: compute_health(d)[0] == "problem",
                            attrs_fn=lambda d: {"reasons": compute_health(d)[1]}),
    DeeperBinaryDescription(key="tunnel_problem", device_class=BinarySensorDeviceClass.PROBLEM,
                            is_on_fn=lambda d: any(tunnel_unhealthy(t) for t in (d.get("tunnels") or {}).values()),
                            attrs_fn=lambda d: {"unhealthy": [c for c, t in (d.get("tunnels") or {}).items() if tunnel_unhealthy(t)]}),
    DeeperBinaryDescription(key="wan_connected", requires=("wifi",), device_class=BinarySensorDeviceClass.CONNECTIVITY,
                            is_on_fn=lambda d: (_g(d, "wifi").get("wanStatus") == "connected") if _g(d, "wifi") else None),
    DeeperBinaryDescription(key="sharing", requires=("sharing",), is_on_fn=lambda d: _g(d, "sharing").get("sharingEnabled"), **_DIAG),
)


async def async_setup_entry(hass, entry, add):
    add([DeeperBinary(entry.runtime_data, entry.entry_id, desc) for desc in BINARY_SENSORS])
    setup_features("binary_sensor", entry, add)
