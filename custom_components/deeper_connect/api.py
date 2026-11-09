"""Minimal async client for the Deeper Connect web API (reverse engineered)."""
from __future__ import annotations

import asyncio
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


class DeeperRejectedError(DeeperError):
    """The device answered but refused the request."""


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


def _check(resp: Any) -> Any:
    """Raise if the device answered but refused (it uses success:false, or code != 0 for some calls)."""
    if isinstance(resp, dict) and (resp.get("success") is False or resp.get("code") not in (None, 0)):
        raise DeeperRejectedError(str(resp.get("reason") or resp.get("error") or resp.get("message") or "rejected by device"))
    return resp


class DeeperClient:
    def __init__(self, session: aiohttp.ClientSession, host: str, username: str, password: str) -> None:
        self._s = session  # must use a CookieJar(unsafe=True) since host is an IP
        self._base = f"https://{host}"
        self._user, self._pw = username, password
        self._logged_in = False
        self._lock = asyncio.Lock()

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
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:  # a silent device times out, it does not refuse
            raise DeeperConnectionError(str(err) or type(err).__name__) from err

    async def ensure_login(self) -> None:
        async with self._lock:
            if not self._logged_in:
                await self.login()

    async def login(self) -> None:
        try:
            async with self._s.post(self._base + "/api/admin/login", ssl=False,
                                    json={"username": self._user, "password": _encrypt(self._pw)},
                                    timeout=aiohttp.ClientTimeout(total=15)) as r:
                data = await r.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise DeeperConnectionError(str(err) or type(err).__name__) from err
        if not (isinstance(data, dict) and data.get("success")):
            raise DeeperAuthError("login rejected")
        self._logged_in = True

    async def get(self, path: str) -> Any:
        await self.ensure_login()
        return await self._req("GET", path)

    async def post(self, path: str, json: Any = None) -> Any:
        await self.ensure_login()
        return await self._req("POST", path, json or {})

    # --- endpoints (shapes to be confirmed against a real device) ---
    async def device_id(self) -> str:
        try:
            async with self._s.get(self._base + "/api/admin/getDeviceId", ssl=False,
                                   timeout=aiohttp.ClientTimeout(total=15)) as r:
                return (await r.json(content_type=None))["deviceId"]
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise DeeperConnectionError(str(err) or type(err).__name__) from err

    async def tunnels(self) -> Any:
        return await self.get("/api/smartRoute/listTunnels")


    async def refresh_tunnel(self, tunnel_code: str) -> Any:
        # Payload assumed from UI code; UNVERIFIED on hardware.
        return await self.post("/api/smartRoute/refreshTunnel", {"tunnelCode": tunnel_code})

    async def apps(self) -> Any:
        return await self.get("/api/appRelocator/appsData")

    async def set_app_tunnel(self, app: str, tunnel_code: str) -> Any:
        """Relocate an app. 'ZZ' = not set (delApp), 'LL' = direct access, otherwise a tunnel code.

        Request bodies taken from the device's own web UI.
        """
        if tunnel_code == "ZZ":
            resp = await self.post("/api/appRelocator/delApp", {"appName": app})
        else:
            resp = await self.post("/api/appRelocator/addApp", {"appName": app, "tunnelCode": tunnel_code})
        return _check(resp)

    # --- settings (request bodies taken from the device's web UI) ---
    async def set_dpn_mode(self, body: dict) -> Any:
        return _check(await self.post("/api/smartRoute/setDpnMode", body))

    async def set_node_lb_mode(self, mode: str) -> Any:
        return _check(await self.post("/api/smartRoute/nodeLbMode", {"mode": mode}))

    async def set_auto_update(self, on: bool) -> Any:
        return _check(await self.get(f"/api/system-info/set-autoupdate?autoUpdate={1 if on else 0}"))

    async def set_auto_reboot(self, config: dict) -> Any:
        return _check(await self.post("/api/autoReboot/config", config))

    async def set_udp_server(self, on: bool) -> Any:
        return _check(await self.post("/api/security/settings/udpServer", {"enabled": on}))

    async def set_ssl_bypass(self, on: bool) -> Any:
        return _check(await self.post("/api/tproxy/sslBypass", {"enable": on}))

    async def set_youtube_ads(self, on: bool) -> Any:
        return _check(await self.post("/api/tproxy/adsFilter", {"enable": on, "type": "youtube"}))

    CLIENT_ROUTE_MODES = ("smart", "full", "disabled", "blackHole")

    async def set_client_route(self, mac: str, mode: str, region_code: str | None = None) -> Any:
        """Change how one Access Control client is routed.

        The device edits a client with a single call that carries the client's whole record, so the record is
        re-read just before and sent back with only routeMode (and regionCode for 'full') changed, never rebuilt
        from older data. Request shape taken from the device's own web UI; UNVERIFIED on hardware until tested.
        """
        if mode not in self.CLIENT_ROUTE_MODES:
            raise DeeperError(f"unknown client route mode {mode!r}")
        if mode == "full" and not region_code:
            raise DeeperError("full tunnel needs a tunnel code")
        listing = await self.get("/api/accessControl/list")
        mac = mac.lower()
        record = next((c for state in ("online", "offline") for c in (listing or {}).get(state) or []
                       if isinstance(c, dict) and str(c.get("mac", "")).lower() == mac), None)
        if record is None:
            raise DeeperError(f"client {mac} is not in the device's access list")
        body = {**record, "routeMode": mode}
        if mode == "full":
            body["regionCode"] = region_code
        return _check(await self.post("/api/accessControl/setOne", body))

    async def reboot(self) -> Any:
        """Reboot the device.

        Verified on hardware (9 Nov 2026): the device restarts but drops the connection instead of answering, so the
        request times out or is cut. That counts as success. A failed login, an unreachable device (login happens first,
        outside the try), an HTTP error or an explicit refusal still raise.
        """
        await self.ensure_login()
        try:
            return await self.post("/api/admin/reboot")
        except asyncio.TimeoutError:
            pass
        except DeeperConnectionError as err:
            if not isinstance(err.__cause__, (aiohttp.ClientConnectionError, asyncio.TimeoutError)):
                raise
        return {"success": True, "assumed": "connection dropped while the device restarted"}
