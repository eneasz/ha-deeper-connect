"""Minimal async client for the Deeper Connect web API (reverse engineered)."""
from __future__ import annotations

import base64
from typing import Any

import aiohttp
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from .const import LOGIN_PUBLIC_KEY


class DeeperError(Exception):
    """Base error."""


class DeeperAuthError(DeeperError):
    """Bad credentials / session expired."""


class DeeperConnectionError(DeeperError):
    """Device unreachable."""


def _encrypt(password: str) -> str:
    key = serialization.load_pem_public_key(LOGIN_PUBLIC_KEY.encode())
    # crypto-browserify publicEncrypt defaults to RSA-OAEP (SHA-1)
    ct = key.encrypt(
        password.encode(),
        padding.OAEP(mgf=padding.MGF1(hashes.SHA1()), algorithm=hashes.SHA1(), label=None),
    )
    return base64.b64encode(ct).decode()


class DeeperClient:
    def __init__(self, session: aiohttp.ClientSession, host: str, username: str, password: str) -> None:
        self._s = session  # must use a CookieJar(unsafe=True) since host is an IP
        self._base = f"https://{host}"
        self._user, self._pw = username, password
        self._logged_in = False

    async def _req(self, method: str, path: str, json: Any = None, retry: bool = True) -> Any:
        try:
            async with self._s.request(method, self._base + path, json=json, ssl=False,
                                       timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status == 401:
                    self._logged_in = False
                    if retry:
                        await self.login()
                        return await self._req(method, path, json, retry=False)
                    raise DeeperAuthError("unauthorized")
                r.raise_for_status()
                return await r.json(content_type=None)
        except aiohttp.ClientError as err:
            raise DeeperConnectionError(str(err)) from err

    async def login(self) -> None:
        try:
            async with self._s.post(self._base + "/api/admin/login", ssl=False,
                                    json={"username": self._user, "password": _encrypt(self._pw)},
                                    timeout=aiohttp.ClientTimeout(total=15)) as r:
                data = await r.json(content_type=None)
        except aiohttp.ClientError as err:
            raise DeeperConnectionError(str(err)) from err
        if not (isinstance(data, dict) and data.get("success")):
            raise DeeperAuthError("login rejected")
        self._logged_in = True

    async def get(self, path: str) -> Any:
        if not self._logged_in:
            await self.login()
        return await self._req("GET", path)

    async def post(self, path: str, json: Any = None) -> Any:
        if not self._logged_in:
            await self.login()
        return await self._req("POST", path, json or {})

    # --- endpoints (shapes to be confirmed against a real device) ---
    async def device_id(self) -> str:
        async with self._s.get(self._base + "/api/admin/getDeviceId", ssl=False,
                               timeout=aiohttp.ClientTimeout(total=15)) as r:
            return (await r.json(content_type=None))["deviceId"]

    async def tunnels(self) -> Any:
        return await self.get("/api/smartRoute/listTunnels")

    async def network(self) -> Any:
        return await self.get("/api/system-info/network-address")

    async def wifi(self) -> Any:
        return await self.get("/api/wifi/workingInfo")

    async def refresh_tunnel(self, tunnel_code: str) -> Any:
        # Payload assumed from UI code; UNVERIFIED on hardware.
        return await self.post("/api/smartRoute/refreshTunnel", {"tunnelCode": tunnel_code})

    async def reboot(self) -> Any:
        return await self.post("/api/admin/reboot")
