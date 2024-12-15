import logging
from typing import Any

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector, config_entry_flow
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.exceptions import HomeAssistantError

import voluptuous as vol
from homeassistant.const import CONF_HOST, CONF_SCAN_INTERVAL
from . import RuntimeData
from .const import DOMAIN, CONF_NEW_DEVICE_SCAN_INTERVAL_DEFAULT
from .leshan_client import LeshanClient, Lwm2mClient

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(
            CONF_HOST,
        ): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.URL),
        ),
        vol.Required(
            CONF_SCAN_INTERVAL,
            default=CONF_NEW_DEVICE_SCAN_INTERVAL_DEFAULT,
        ): int,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    leshan_client = LeshanClient(
        host=data[CONF_HOST], session=async_create_clientsession(hass)
    )

    try:
        await leshan_client.test_server()
    except Exception as e:
        _LOGGER.error(f"Cannot connect to the server: {e}")
        raise CannotConnect from e

    return {"title": f"Leshan LwM2M Server - ({data[CONF_HOST]})"}


class LeshanLwm2mConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Leshan LWM2M config flow."""

    VERSION = 1
    MINOR_VERSION = 0

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            # Check if the server URI is valid by getting
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                _LOGGER.error("Cannot connect to the server")
                errors["base"] = "cannot_connect"
            except Exception as e:
                _LOGGER.error(f"Unexpected exception: {e}")
                errors["base"] = "unknown"
            else:
                # validation was successful, create the entry
                await self.async_set_unique_id(info.get("title"))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_discovery(self, discovery_info):
        """Test discovery step."""
        return self.async_show_form(step_id="discovery_confirm")

    async def async_step_discovery_confirm(self, discovery_info):
        """Test discovery confirm step."""
        return self.async_create_entry(title="Test Title", data={"token": "abcd"})

    # async def async_step_finish(
    #     self, discovered_client: Lwm2mClient
    # ) -> config_entries.FlowResult:
    #     """Finish the config flow."""
    #     _LOGGER.info(f"Discovered client {discovered_client.endpoint}, finishing")
    #     return self.async_create_entry(
    #         title=discovered_client.endpoint,
    #         data={CONF_HOST: discovered_client.host},
    #     )


# async def _async_new_clients_available(hass: HomeAssistant) -> bool:
#     """Check if there are new clients available."""
#     # get config entry
#     config_entries = hass.config_entries.async_entries(DOMAIN)
#     _LOGGER.debug(f"Checking for new clients for {len(config_entries)} config entries")

#     for config_entry in config_entries:
#         _LOGGER.debug(f"Checking for new clients for config entry {config_entry.entry_id}")
#         runtime_data: RuntimeData = hass.data[DOMAIN][config_entry.entry_id]
#         coordinator = runtime_data.coordinator
#         known_clients = runtime_data.known_clients

#         all_clients = await coordinator.async_get_all_clients()

#         new_clients = [client for client in all_clients if client not in known_clients]
#         if new_clients:
#             return True

# config_entry_flow.register_discovery_flow(
#     DOMAIN,
#     "Discovered LwM2M clients",
#     _async_new_clients_available,
# )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""

    pass
