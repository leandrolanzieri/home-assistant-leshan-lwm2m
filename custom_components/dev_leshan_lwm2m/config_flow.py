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

from custom_components.dev_leshan_lwm2m.leshan_client.lwm2m_client import Lwm2mClient

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

    # async def _async_handle_discovery(self) -> ConfigFlowResult:
    #     """Handle any discovery."""
    #     _LOGGER.debug("_async_handle_discovery")
    #     client = self._discovered_client
    #     await self.async_set_unique_id(client.endpoint)

    #     for entry in self._async_current_entries(include_ignore=False):
    #         _LOGGER.debug("Checking entry", extra={"entry": entry})
    #         if entry.unique_id == client.endpoint:
    #             self.hass.config_entries.async_schedule_reload(entry.entry_id)
    #             return self.async_abort(reason="already_configured")

    #     if self.hass.config_entries.flow.async_has_matching_flow(self):
    #         _LOGGER.debug("Already in progress")
    #         return self.async_abort(reason="already_in_progress")
    #     # Handled ignored case since _async_current_entries
    #     # is called with include_ignore=False
    #     self._abort_if_unique_id_configured()
    #     return await self.async_step_discovery_confirm()

    # async def async_step_discovery_confirm(
    #     self, _: dict[str, Any] | None = None
    # ) -> ConfigFlowResult:
    #     """Confirm discovery."""
    #     _LOGGER.debug("async_step_discovery_confirm")
    #     self.context["title_placeholders"] = _placeholders_from_client(
    #         self._discovered_client
    #     )
    #     return await self.async_step_discovered_connection()

    # async def async_step_discovered_connection(
    #     self, _: dict[str, Any] | None = None
    # ) -> ConfigFlowResult:
    #     """Handle connecting the device when we have a discovery."""
    #     _LOGGER.debug("async_step_discovered_connection")
    #     errors: dict[str, str] | None = {}
    #     client = self._discovered_client

    #     return self.async_show_form(
    #         step_id="discovered_client",
    #         errors=errors,
    #         description_placeholders=_placeholders_from_client(client),
    #     )


def _placeholders_from_client(client: Lwm2mClient) -> dict[str, str]:
    return {"endpoint": client.endpoint}


class CannotConnectError(HomeAssistantError):
    """Error to indicate we cannot connect."""
