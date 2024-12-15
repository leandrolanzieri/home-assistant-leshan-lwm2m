"""Config flow for Leshan LWM2M integration."""

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.typing import DiscoveryInfoType

from .const import CONF_NEW_DEVICE_SCAN_INTERVAL_DEFAULT, DOMAIN
from .leshan_client import LeshanClient

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
    """
    Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    leshan_client = LeshanClient(
        host=data[CONF_HOST], session=async_create_clientsession(hass)
    )

    try:
        await leshan_client.test_server()
    except Exception as e:
        _LOGGER.exception("Cannot connect to the server", exc_info=e)
        raise CannotConnectError from e

    return {"title": f"Leshan LwM2M Server - ({data[CONF_HOST]})"}


class LeshanLwm2mConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Leshan LWM2M config flow."""

    VERSION = 1
    MINOR_VERSION = 0

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Check if the server URI is valid by getting
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnectError:
                _LOGGER.exception("Cannot connect to the server")
                errors["base"] = "cannot_connect"
            except Exception as e:
                _LOGGER.exception("Unexpected exception", exc_info=e)
                errors["base"] = "unknown"
            else:
                # validation was successful, create the entry
                await self.async_set_unique_id(user_input[CONF_HOST])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_integration_discovery(
        self, discovery_info: DiscoveryInfoType
    ) -> ConfigFlowResult:
        """Handle integration discovery."""
        entry_id = discovery_info["entry_id"]

        _LOGGER.debug(
            "Lwm2m client discovered from integration discovery",
            extra={"info": discovery_info},
        )
        self.hass.config_entries.async_schedule_reload(entry_id)
        return self.async_abort(reason="already_configured")


class CannotConnectError(HomeAssistantError):
    """Error to indicate we cannot connect."""
