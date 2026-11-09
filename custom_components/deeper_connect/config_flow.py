"""Config flow."""
from __future__ import annotations

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.selector import (SelectOptionDict, SelectSelector, SelectSelectorConfig,
                                            SelectSelectorMode)

from .features import enabled_features
from .util import all_clients, app_title, client_title, customised_apps, pinned_clients

from .api import DeeperAuthError, DeeperClient, DeeperConnectionError
from .const import (ALL_FEATURES, CONFIG_VERSION, CONF_APPS, CONF_CLIENTS, CONF_FEATURES, CONF_GEO_LOOKUP, CONF_SCAN_INTERVAL, DEFAULT_HOST,
                    DEFAULT_SCAN_INTERVAL, DOMAIN, FEATURE_ACCESS, FEATURE_APPS, MIN_SCAN_INTERVAL)


async def _validate(data: dict) -> tuple[str | None, str | None]:
    """Return (device_id, error)."""
    session = aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True))
    try:
        client = DeeperClient(session, data[CONF_HOST], data[CONF_USERNAME], data[CONF_PASSWORD])
        device_id = await client.device_id()
        await client.login()
        return device_id, None
    except DeeperAuthError:
        return None, "invalid_auth"
    except DeeperConnectionError:
        return None, "cannot_connect"
    except Exception:  # noqa: BLE001
        return None, "unknown"
    finally:
        await session.close()


class DeeperConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = CONFIG_VERSION

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> OptionsFlow:
        return DeeperOptionsFlow()

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input:
            device_id, err = await _validate(user_input)
            if err:
                errors["base"] = err
            else:
                await self.async_set_unique_id(device_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=f"Deeper {user_input[CONF_HOST]}", data=user_input)
        schema = vol.Schema({
            vol.Required(CONF_HOST, default=(user_input or {}).get(CONF_HOST, DEFAULT_HOST)): str,
            vol.Required(CONF_USERNAME, default=(user_input or {}).get(CONF_USERNAME, "admin")): str,
            vol.Required(CONF_PASSWORD): str,
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reauth(self, entry_data):
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        entry = self._get_reauth_entry()
        errors = {}
        if user_input:
            data = {**entry.data, CONF_PASSWORD: user_input[CONF_PASSWORD]}
            _, err = await _validate(data)
            if not err:
                return self.async_update_reload_and_abort(entry, data=data)
            errors["base"] = err
        return self.async_show_form(step_id="reauth_confirm", errors=errors,
                                    data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}))


class DeeperOptionsFlow(OptionsFlow):
    """Step 1: polling + feature flags. Then one step per enabled feature that has something to pick."""

    def __init__(self) -> None:
        self._opts: dict = {}

    def _data(self) -> dict:
        coordinator = getattr(self.config_entry, "runtime_data", None)
        return (coordinator.data if coordinator is not None and coordinator.data else {})

    async def async_step_init(self, user_input=None):
        entry_opts = self.config_entry.options
        if user_input is not None:
            self._opts = {**entry_opts, **user_input}
            return await self._next("init")
        cur = entry_opts.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        return self.async_show_form(step_id="init", data_schema=vol.Schema({
            vol.Required(CONF_SCAN_INTERVAL, default=cur): vol.All(int, vol.Range(min=MIN_SCAN_INTERVAL, max=3600)),
            vol.Required(CONF_FEATURES, default=sorted(enabled_features(entry_opts))): SelectSelector(SelectSelectorConfig(
                options=[SelectOptionDict(value=f, label=f) for f in ALL_FEATURES], multiple=True,
                mode=SelectSelectorMode.LIST, translation_key="features")),
            vol.Required(CONF_GEO_LOOKUP, default=entry_opts.get(CONF_GEO_LOOKUP, False)): bool}))

    async def _next(self, after: str):
        feats = enabled_features(self._opts)
        if after == "init" and FEATURE_APPS in feats:
            return await self.async_step_apps()
        if after in ("init", "apps") and FEATURE_ACCESS in feats:
            return await self.async_step_clients()
        return self.async_create_entry(data=self._opts)

    async def async_step_apps(self, user_input=None):
        if user_input is not None:
            self._opts[CONF_APPS] = user_input[CONF_APPS]
            return await self._next("apps")
        known = self._data().get("apps") or {}
        saved = self.config_entry.options.get(CONF_APPS)
        chosen = list(saved) if saved is not None else customised_apps(known)
        options = [SelectOptionDict(value=k, label=app_title(k)) for k in sorted(known, key=str.lower)]
        options += [SelectOptionDict(value=k, label=app_title(k)) for k in chosen if k not in known]
        return self.async_show_form(step_id="apps", data_schema=vol.Schema({
            vol.Optional(CONF_APPS, default=chosen): SelectSelector(SelectSelectorConfig(
                options=options, multiple=True, mode=SelectSelectorMode.DROPDOWN))}))

    async def async_step_clients(self, user_input=None):
        if user_input is not None:
            self._opts[CONF_CLIENTS] = user_input[CONF_CLIENTS]
            return await self._next("clients")
        known = all_clients(self._data())
        saved = self.config_entry.options.get(CONF_CLIENTS)
        chosen = [m.lower() for m in saved] if saved is not None else pinned_clients(self._data())
        options = [SelectOptionDict(value=m, label=f"{client_title(c)} ({m})")
                   for m, c in sorted(known.items(), key=lambda kv: client_title(kv[1]).lower())]
        options += [SelectOptionDict(value=m, label=m) for m in chosen if m not in known]
        return self.async_show_form(step_id="clients", data_schema=vol.Schema({
            vol.Optional(CONF_CLIENTS, default=chosen): SelectSelector(SelectSelectorConfig(
                options=options, multiple=True, mode=SelectSelectorMode.DROPDOWN))}))
