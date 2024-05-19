from homeassistant import config_entries
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_create_clientsession

import voluptuous as vol
from .const import DOMAIN, CONF_SERVER_URI
from .leshan_client import LeshanClient

class LeshanLwm2mConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Leshan LWM2M config flow."""
    VERSION = 1
    MINOR_VERSION = 0

    async def async_step_user(self, user_input: dict | None = None) -> config_entries.FlowResult:
        errors = {}

        if user_input is not None:
            # Check if the server URI is valid by getting
            try:
                await self._test_server(user_input[CONF_SERVER_URI])
            except Exception as e:
                # TODO: Handle exceptions
                errors["base"] = "connection"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_SERVER_URI],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SERVER_URI,
                        default=(user_input or {}).get(CONF_SERVER_URI),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.URL
                        ),
                    ),
                }
            ),
            errors=errors,
        )

    async def _test_server(self, server_uri: str) -> None:
        leshan_client = LeshanClient(
            host=server_uri,
            session=async_create_clientsession(self.hass)
        )

        await leshan_client.list_clients()

