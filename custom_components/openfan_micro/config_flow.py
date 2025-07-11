import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME

from ._api import test_connection
from .const import DOMAIN


class OpenFANMicroConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST]

            is_valid = await self.hass.async_add_executor_job(test_connection, host)

            if is_valid:
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME) or f"OpenFAN Micro ({host})",
                    data=user_input,
                )
            else:
                errors["base"] = "cannot_connect"

        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Optional(CONF_NAME, default=""): str,
            }
        )

        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)
