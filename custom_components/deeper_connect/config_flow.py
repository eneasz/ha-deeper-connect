"""Config flow."""
from __future__ import annotations

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

from .api import DeeperAuthError, DeeperClient, DeeperConnectionError
from .const import DEFAULT_HOST, DOMAIN


class DeeperConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input:
            session = aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True))
            try:
                client = DeeperClient(session, user_input[CONF_HOST], user_input[CONF_USERNAME],
                                      user_input[CONF_PASSWORD])
                device_id = await client.device_id()
                await client.login()
            except DeeperAuthError:
                errors["base"] = "invalid_auth"
            except DeeperConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            finally:
                await session.close()
            if not errors:
                await self.async_set_unique_id(device_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=f"Deeper {user_input[CONF_HOST]}", data=user_input)
        schema = vol.Schema({
            vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
            vol.Required(CONF_USERNAME, default="admin"): str,
            vol.Required(CONF_PASSWORD): str,
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
