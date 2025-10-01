from typing import Any
import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.helpers.httpx_client import get_async_client
from httpx import HTTPError

from ._device import Device
from .const import DOMAIN


class OpenFANMicroConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST]

            device = Device(get_async_client(self.hass), host)
            try:
                await device.fetch_status()
                return self.async_create_entry(
                    title=device.hostname or f"OpenFAN Micro ({host})",
                    data=user_input,
                )
            except (HTTPError, ValueError):
                errors["base"] = "cannot_connect"

        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Optional(CONF_NAME, default=""): str,
            }
        )

        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors = {}
        reconfigure_entry = self._get_reconfigure_entry()
        host = reconfigure_entry.data[CONF_HOST]
        name = reconfigure_entry.data.get(CONF_NAME, "")

        if user_input is not None:
            host = user_input[CONF_HOST]
            name = user_input[CONF_NAME]

            device = Device(get_async_client(self.hass), host)
            try:
                await device.fetch_status()
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data_updates={
                        CONF_HOST: host,
                        CONF_NAME: name,
                    },
                )
            except (HTTPError, ValueError):
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=host): str,
                    vol.Optional(CONF_NAME, default=name): str,
                }
            ),
            description_placeholders={"device_name": reconfigure_entry.title},
            errors=errors,
        )
