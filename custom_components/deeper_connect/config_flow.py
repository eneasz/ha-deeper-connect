"""Config flow."""
from __future__ import annotations

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback

from .api import DeeperAuthError, DeeperClient, DeeperConnectionError
from .const import CONF_GEO_LOOKUP, CONF_SCAN_INTERVAL, DEFAULT_HOST, DEFAULT_SCAN_INTERVAL, DOMAIN, MIN_SCAN_INTERVAL


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
    VERSION = 1

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
    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        cur = self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        return self.async_show_form(step_id="init", data_schema=vol.Schema({
            vol.Required(CONF_SCAN_INTERVAL, default=cur): vol.All(int, vol.Range(min=MIN_SCAN_INTERVAL, max=3600)),
            vol.Required(CONF_GEO_LOOKUP, default=self.config_entry.options.get(CONF_GEO_LOOKUP, False)): bool}))
