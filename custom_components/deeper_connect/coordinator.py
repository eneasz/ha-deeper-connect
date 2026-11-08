"""Data coordinator."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .geo import GeoLocator
from .api import DeeperAuthError, DeeperClient, DeeperError
from .const import APPS_EVERY, CONF_GEO_LOOKUP, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN, SLOW_EVERY

_LOGGER = logging.getLogger(__name__)

FAST = {
    "usage": "/api/system-info/usage",
    "sessions": "/api/system-info/session-info",
    "hardware": "/api/system-info/hardware-info",
    "info": "/api/info",
    "network": "/api/system-info/network-address",
    "wifi": "/api/wifi/workingInfo",
    "traffic": "/api/traffic/total-traffic",
    "routed": "/api/traffic/routedInfo",
    "saved": "/api/traffic/savedTraffic",
    "blocked": "/api/security/blockedCounts",
    "dpn": "/api/smartRoute/getDpnMode",
    "lb": "/api/smartRoute/nodeLbMode",
    "clients": "/api/accessControl/list",
    "live": "/api/dynamic-data",
    "ads": "/api/tproxy/adsFilter",
    "ssl": "/api/tproxy/sslBypass",
}
SLOW = {
    "software": "/api/system-info/software-info",
    "latest": "/api/system-info/get-latestversion",
    "device": "/api/system-info/device-name",
    "autoupdate": "/api/system-info/get-autoupdate",
    "autoreboot": "/api/autoReboot/config",
    "sharing": "/api/sharing/getSharingConfig",
}


class DeeperCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls the device. Only the tunnel list is mandatory; other endpoints degrade to empty."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: DeeperClient, session) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, config_entry=entry,
                         update_interval=timedelta(seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)))
        self.client = client
        self.session = session
        self._slow: dict[str, Any] = {}
        self.geo = GeoLocator(async_get_clientsession(hass)) if entry.options.get(CONF_GEO_LOOKUP) else None
        self._polls = 0
        self._apps: dict[str, Any] = {}
        self._force_apps = True

    async def _fetch(self, path: str) -> Any:
        try:
            return await self.client.get(path)
        except DeeperAuthError:
            raise
        except (DeeperError, ValueError) as err:
            _LOGGER.debug("Optional endpoint %s failed: %s", path, err)
            return None

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            await self.client.ensure_login()
            tunnels = await self.client.tunnels()
            keys = list(FAST)
            results = await asyncio.gather(*(self._fetch(FAST[k]) for k in keys))
            data: dict[str, Any] = dict(zip(keys, results))
            if self._polls % SLOW_EVERY == 0 or not self._slow:
                skeys = list(SLOW)
                sres = await asyncio.gather(*(self._fetch(SLOW[k]) for k in skeys))
                self._slow = dict(zip(skeys, sres))
            if self._force_apps or self._polls % APPS_EVERY == 0:
                apps = await self._fetch("/api/appRelocator/appsData")
                if isinstance(apps, dict) and isinstance(apps.get("apps"), dict):
                    self._apps = apps["apps"]
                self._force_apps = False
            self._polls += 1
        except DeeperAuthError as err:
            raise ConfigEntryAuthFailed from err
        except DeeperError as err:
            raise UpdateFailed(str(err)) from err
        data.update(self._slow)
        data["tunnels"] = {t["tunnelCode"]: t for t in tunnels if isinstance(t, dict) and "tunnelCode" in t}
        data["apps"] = self._apps
        data["geo"] = {}
        if self.geo:
            ips = {t.get("activeIp") for t in data["tunnels"].values() if t.get("activeIp")}
            for ip, res in zip(ips, await asyncio.gather(*(self.geo.lookup(i) for i in ips))):
                if res:
                    data["geo"][ip] = res
        data["wifi"] = (data.get("wifi") or {}).get("workingInfo", {})
        return data

    async def async_set_app_tunnel(self, app: str, code: str) -> None:
        """Relocate an app, then refresh the app table straight away."""
        await self.client.set_app_tunnel(app, code)
        self._force_apps = True
        await self.async_request_refresh()
