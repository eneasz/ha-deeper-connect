"""Diagnostics."""
from __future__ import annotations

from homeassistant.components.diagnostics import async_redact_data

REDACT = {"host", "username", "password", "pubIp", "ip", "routerMac", "gatewayMac", "activeIp", "mac",
          "SN", "deviceId", "name", "remark", "bypass", "udpServerBypass"}


async def async_get_config_entry_diagnostics(hass, entry):
    data = dict(entry.runtime_data.data or {})
    clients = data.pop("clients", None) or {}
    data["clients"] = {k: len(v) for k, v in clients.items() if isinstance(v, list)}
    data.pop("live", None)
    return {"entry": async_redact_data(dict(entry.data), REDACT), "options": dict(entry.options),
            "endpoint_failures": entry.runtime_data.endpoint_failures,  # endpoint key -> consecutive failed polls
            "data": async_redact_data(data, REDACT)}
