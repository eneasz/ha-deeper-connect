"""Sensors for the always-on core; the optional groups live in features/<name>.py."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfDataRate, UnitOfInformation, UnitOfTemperature, UnitOfTime

from .bases import DeeperSensor, DeeperSensorDescription
from .features import app_relocator
from .features.access_control import BLACKHOLED_CLIENTS, ClientRouteMode
from .features.app_relocator import TunnelApps
from .features.dpn import TunnelIp, TunnelLocation, TunnelNodes
from .features.loader import setup_features
from .util import avg_last, compute_health, last, parse_size, parse_uptime, to_float

__all__ = ["BLACKHOLED_CLIENTS", "CORE_SENSORS", "ClientRouteMode", "DeeperSensor", "DeeperSensorDescription", "SENSORS",
           "TunnelApps", "TunnelIp", "TunnelLocation", "TunnelNodes"]


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

CORE_SENSORS: tuple[DeeperSensorDescription, ...] = (
    # --- health & resources ---
    DeeperSensorDescription(key="health", device_class=SensorDeviceClass.ENUM,
                            options=["ok", "warning", "problem"], value_fn=lambda d: compute_health(d)[0],
                            attrs_fn=lambda d: {"reasons": compute_health(d)[1]}),
    DeeperSensorDescription(key="cpu", requires=("usage",), native_unit_of_measurement=PERCENTAGE,
                            state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=0,
                            value_fn=lambda d: last(_g(d, "usage").get("cpuUsageData")),
                            attrs_fn=lambda d: {"average_15min": avg_last(_g(d, "usage").get("cpuUsageData"), 3)}),
    DeeperSensorDescription(key="memory", requires=("usage",), native_unit_of_measurement=PERCENTAGE,
                            state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=0,
                            value_fn=lambda d: last(_g(d, "usage").get("memUsageData"))),
    DeeperSensorDescription(key="temperature", requires=("hardware",), device_class=SensorDeviceClass.TEMPERATURE,
                            native_unit_of_measurement=UnitOfTemperature.CELSIUS, state_class=SensorStateClass.MEASUREMENT,
                            value_fn=lambda d: to_float(_g(d, "hardware").get("tempInCelsius"))),
    DeeperSensorDescription(key="uptime", requires=("info",), device_class=SensorDeviceClass.DURATION,
                            native_unit_of_measurement=UnitOfTime.SECONDS, suggested_unit_of_measurement=UnitOfTime.HOURS,
                            state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=1,
                            value_fn=lambda d: parse_uptime(_info(d, 0))),
    # --- sessions ---
    DeeperSensorDescription(key="sessions", requires=("sessions",), state_class=SensorStateClass.MEASUREMENT,
                            value_fn=lambda d: to_float(_g(d, "sessions").get("currSessionNum")),
                            attrs_fn=lambda d: {k: to_float(v) for k, v in _g(d, "sessions").items()}),
    DeeperSensorDescription(key="tunnel_sessions", requires=("sessions",), state_class=SensorStateClass.MEASUREMENT,
                            value_fn=lambda d: to_float(_g(d, "sessions").get("tunnelSessionNum"))),
    DeeperSensorDescription(key="clients_online", requires=("clients",), state_class=SensorStateClass.MEASUREMENT,
                            value_fn=lambda d: len(_g(d, "clients").get("online") or []),
                            attrs_fn=lambda d: {"clients": [c.get("name") or c.get("remark") or "unnamed"
                                                            for c in _g(d, "clients").get("online") or []]}),
    # --- traffic ---
    DeeperSensorDescription(key="live_upload", requires=("live",), device_class=SensorDeviceClass.DATA_RATE,
                            native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
                            suggested_unit_of_measurement=UnitOfDataRate.MEGABYTES_PER_SECOND,
                            state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=2,
                            value_fn=lambda d: last(_g(d, "live").get("upLoadData"))),
    DeeperSensorDescription(key="live_download", requires=("live",), device_class=SensorDeviceClass.DATA_RATE,
                            native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
                            suggested_unit_of_measurement=UnitOfDataRate.MEGABYTES_PER_SECOND,
                            state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=2,
                            value_fn=lambda d: last(_g(d, "live").get("downLoadData"))),
    DeeperSensorDescription(key="local_upload", requires=("traffic",), value_fn=_size("traffic", "localTraffic", "upload"), **_BYTES),
    DeeperSensorDescription(key="local_download", requires=("traffic",), value_fn=_size("traffic", "localTraffic", "download"), **_BYTES),
    DeeperSensorDescription(key="client_upload", requires=("traffic",), value_fn=_size("traffic", "clientTraffic", "upload"), **_BYTES),
    DeeperSensorDescription(key="client_download", requires=("traffic",), value_fn=_size("traffic", "clientTraffic", "download"), **_BYTES),
    DeeperSensorDescription(key="routed_traffic", requires=("routed",), value_fn=lambda d: to_float(_g(d, "routed").get("traffic")),
                            **{**_BYTES, "state_class": SensorStateClass.TOTAL_INCREASING}),
    DeeperSensorDescription(key="saved_traffic", requires=("saved",), value_fn=lambda d: to_float(_g(d, "saved").get("saved")),
                            **_BYTES),
    # --- security ---
    DeeperSensorDescription(key="blocked_total", requires=("blocked",), state_class=SensorStateClass.TOTAL_INCREASING,
                            value_fn=lambda d: to_float(_g(d, "blocked").get("total")),
                            attrs_fn=lambda d: dict(_g(d, "blocked"))),
    # --- network / routing ---
    DeeperSensorDescription(key="public_ip", requires=("network",), value_fn=lambda d: _g(d, "network").get("pubIp")),
    DeeperSensorDescription(key="wan_status", requires=("wifi",), value_fn=lambda d: _g(d, "wifi").get("wanStatus")),
    DeeperSensorDescription(key="connection_mode", requires=("wifi",), value_fn=lambda d: _g(d, "wifi").get("mode"), **_DIAG),
    DeeperSensorDescription(key="tunnel_count", state_class=SensorStateClass.MEASUREMENT,
                            value_fn=lambda d: len(d.get("tunnels") or {})),
    # --- versions ---
    DeeperSensorDescription(key="app_sig", requires=("software",), value_fn=lambda d: _g(d, "software").get("appSigVersion"), **_DIAG),
    DeeperSensorDescription(key="rule_version", requires=("software",), value_fn=lambda d: _g(d, "software").get("builtinRuleVersion"), **_DIAG),
    DeeperSensorDescription(key="url_sig", requires=("software",), value_fn=lambda d: _g(d, "software").get("urlSigVersion"), **_DIAG),
)


SENSORS = (*CORE_SENSORS, *app_relocator.SENSORS)  # every description, for tests and docs


async def async_setup_entry(hass, entry, add):
    add([DeeperSensor(entry.runtime_data, entry.entry_id, desc) for desc in CORE_SENSORS])
    setup_features("sensor", entry, add)
