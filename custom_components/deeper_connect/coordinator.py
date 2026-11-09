"""Data coordinator: one poll loop with fast / medium / slow endpoint tiers and per-endpoint failure handling."""
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
from .const import (CONF_GEO_LOOKUP, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN, FEATURE_DPN, MEDIUM_EVERY,
                    SLOW_EVERY, STALE_AFTER)
from .features import enabled_features, polled

_LOGGER = logging.getLogger(__name__)

# Which endpoints belong to which feature is declared in features.SPECS (medium=/slow=); the rest is always polled.
FAST = {  # every poll
    "usage": "/api/system-info/usage",
    "sessions": "/api/system-info/session-info",
    "hardware": "/api/system-info/hardware-info",
    "info": "/api/info",
    "wifi": "/api/wifi/workingInfo",
    "traffic": "/api/traffic/total-traffic",
    "routed": "/api/traffic/routedInfo",
    "saved": "/api/traffic/savedTraffic",
    "blocked": "/api/security/blockedCounts",
    "clients": "/api/accessControl/list",
    "live": "/api/dynamic-data",
}
MEDIUM = {  # every MEDIUM_EVERY polls: settings that only change when someone edits them, the public IP, the app table
    "network": "/api/system-info/network-address",
    "dpn": "/api/smartRoute/getDpnMode",
    "lb": "/api/smartRoute/nodeLbMode",
    "ads": "/api/tproxy/adsFilter",
    "ssl": "/api/tproxy/sslBypass",
    "udp": "/api/security/settings/udpServer",
    "apps": "/api/appRelocator/appsData",
}
SLOW = {  # every SLOW_EVERY polls
    "software": "/api/system-info/software-info",
    "latest": "/api/system-info/get-latestversion",
    "device": "/api/system-info/device-name",
    "autoupdate": "/api/system-info/get-autoupdate",
    "autoreboot": "/api/autoReboot/config",
    "sharing": "/api/sharing/getSharingConfig",
}


class DeeperCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls the device. Only the tunnel list is mandatory; other endpoints degrade per endpoint, not per poll.

    A failing endpoint keeps its last known value for STALE_AFTER - 1 polls, then its entities become unavailable
    (they declare the data sections they read in `requires`). It is retried every poll until it recovers.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: DeeperClient, session) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, config_entry=entry,
                         update_interval=timedelta(seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)))
        self.client = client
        self.features = enabled_features(entry.options)
        self.session = session
        self.geo = GeoLocator(async_get_clientsession(hass)) if entry.options.get(CONF_GEO_LOOKUP) and FEATURE_DPN in self.features else None
        self._init_state()

    def _init_state(self) -> None:
        self._cache: dict[str, Any] = {}  # last good response per endpoint key
        self._fails: dict[str, int] = {}  # consecutive failed polls per endpoint key
        self._retry: set[str] = set()  # failed keys, refetched next poll even if their tier is not due
        self._polls = 0
        self._force_medium = False
        self._force_slow = False

    @property
    def endpoint_failures(self) -> dict[str, int]:
        """Endpoint key -> consecutive failed polls (for diagnostics)."""
        return dict(self._fails)

    async def _fetch(self, key: str, path: str) -> Any:
        try:
            value = await self.client.get(path)
        except DeeperAuthError:
            raise
        except (DeeperError, ValueError) as err:
            n = self._fails[key] = self._fails.get(key, 0) + 1
            self._retry.add(key)
            if n == 1:
                _LOGGER.warning("Deeper endpoint %s failed (%s); keeping its last known value, entities that use it become "
                                "unavailable after %d failed polls", path, err, STALE_AFTER)
            elif n == STALE_AFTER:
                _LOGGER.warning("Deeper endpoint %s is still failing (%s); the entities that use it are now unavailable", path, err)
            else:
                _LOGGER.debug("Deeper endpoint %s failed again (%s)", path, err)
            if n >= STALE_AFTER:
                self._cache.pop(key, None)
            return self._cache.get(key)
        if self._fails.pop(key, 0):
            _LOGGER.info("Deeper endpoint %s recovered", path)
        self._retry.discard(key)
        self._cache[key] = value
        return value

    async def _async_update_data(self) -> dict[str, Any]:
        first = self._polls == 0
        due_medium = first or self._force_medium or self._polls % MEDIUM_EVERY == 0
        due_slow = first or self._force_slow or self._polls % SLOW_EVERY == 0
        medium, slow = polled(MEDIUM, self.features, "medium"), polled(SLOW, self.features, "slow")
        todo = dict(FAST)
        todo.update({k: MEDIUM[k] for k in medium if due_medium or k in self._retry})
        todo.update({k: SLOW[k] for k in slow if due_slow or k in self._retry})
        try:
            await self.client.ensure_login()
            tunnels = await self.client.tunnels()
            await asyncio.gather(*(self._fetch(k, p) for k, p in todo.items()))
            self._force_medium = self._force_slow = False
            self._polls += 1
        except DeeperAuthError as err:
            raise ConfigEntryAuthFailed from err
        except DeeperError as err:
            raise UpdateFailed(str(err)) from err
        data: dict[str, Any] = {k: self._cache.get(k) for k in (*FAST, *medium, *slow)}
        data["tunnels"] = {t["tunnelCode"]: t for t in tunnels if isinstance(t, dict) and "tunnelCode" in t}
        apps = data.get("apps")
        data["apps"] = apps["apps"] if isinstance(apps, dict) and isinstance(apps.get("apps"), dict) else None
        data["geo"] = {}
        if self.geo:
            ips = {t.get("activeIp") for t in data["tunnels"].values() if t.get("activeIp")}
            for ip, res in zip(ips, await asyncio.gather(*(self.geo.lookup(i) for i in ips))):
                if res:
                    data["geo"][ip] = res
        wifi = data.get("wifi")
        data["wifi"] = wifi.get("workingInfo") if isinstance(wifi, dict) else None
        return data

    async def async_set_app_tunnel(self, app: str, code: str) -> None:
        """Relocate an app, then refresh the app table straight away."""
        await self.client.set_app_tunnel(app, code)
        self._force_medium = True
        await self.async_request_refresh()

    async def async_control(self, setter, *args) -> None:
        """Run a client setter, then re-read settings straight away."""
        await setter(*args)
        self._force_medium = self._force_slow = True
        await self.async_request_refresh()
