"""Optional exit-node geolocation (opt-in; sends only tunnel exit IPs to a third-party service)."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)
RETRY_AFTER = 3600  # seconds before re-trying a failed lookup


def _from_ipinfo(j: dict) -> dict | None:
    try:
        lat, lon = (float(x) for x in j["loc"].split(","))
    except (KeyError, ValueError, AttributeError):
        lat = lon = None
    if lat is None and not j.get("country"):
        return None
    return {"city": j.get("city"), "region": j.get("region"), "country_code": j.get("country"),
            "latitude": lat, "longitude": lon, "org": j.get("org")}


def _from_geojs(j: dict) -> dict | None:
    def f(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return None
    if not j.get("country_code"):
        return None
    return {"city": j.get("city"), "region": j.get("region"), "country_code": j.get("country_code"),
            "latitude": f(j.get("latitude")), "longitude": f(j.get("longitude")),
            "org": j.get("organization_name")}


# Tried in order. Several geo-IP hosts are commonly blocked by DNS filters (Pi-hole), so we fall back.
PROVIDERS = (
    ("https://ipinfo.io/{ip}/json", _from_ipinfo),
    ("https://get.geojs.io/v1/ip/geo/{ip}.json", _from_geojs),
)


class GeoLocator:
    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session
        self._cache: dict[str, dict] = {}
        self._retry_at: dict[str, float] = {}

    async def lookup(self, ip: str) -> dict[str, Any] | None:
        if ip in self._cache:
            return self._cache[ip]
        if time.monotonic() < self._retry_at.get(ip, 0):
            return None
        for url, parse in PROVIDERS:
            try:
                async with self._session.get(url.format(ip=ip), timeout=aiohttp.ClientTimeout(total=10)) as r:
                    r.raise_for_status()
                    res = parse(await r.json(content_type=None))
            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
                _LOGGER.debug("Geo lookup via %s failed: %s", url.split("/")[2], err)
                continue
            if res:
                self._cache[ip] = res
                return res
        self._retry_at[ip] = time.monotonic() + RETRY_AFTER
        return None
