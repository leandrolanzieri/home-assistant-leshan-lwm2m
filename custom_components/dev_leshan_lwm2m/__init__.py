"""
The Leshan LWM2M integration.
"""

from __future__ import annotations

from datetime import timedelta
import logging
from dataclasses import dataclass, field
from collections.abc import Callable

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.const import Platform
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers import discovery_flow

from .const import DOMAIN
from .leshan_lwm2m_coordinator import LeshanLwm2mCoordinator
from .leshan_client import Lwm2mClient

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.LIGHT,
    Platform.BINARY_SENSOR,
]

DISCOVERY_INTERVAL = timedelta(minutes=15)


@dataclass
class RuntimeData:
    """Holds the runtime data for the integration."""

    coordinator: LeshanLwm2mCoordinator
    cancel_update_listener: Callable
    known_clients: list[Lwm2mClient] = field(default_factory=list)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # initialize the coordinator that fetches data from the Leshan server
    coordinator = LeshanLwm2mCoordinator(hass, config_entry)

    # perform a first load from the server
    await coordinator.async_config_entry_first_refresh()

    # initialize a listener for changes in the config flow options
    cancel_update_listener = config_entry.add_update_listener(_async_update_listener)

    # @callback
    # async def _async_handle_client_registration(client: Lwm2mClient):
    #     _LOGGER.info(f"Client {client.endpoint} registered")
    #     runtime_data = hass.data[DOMAIN][config_entry.entry_id]

    #     if client.endpoint not in runtime_data.known_clients:
    #         _LOGGER.info(f"Client {client.endpoint} is new")
    #         discovery_flow.async_create_flow(
    #             hass,
    #             DOMAIN,
    #             context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
    #             data=client,
    #         )

    #     else:
    #         _LOGGER.info(f"Client {client.endpoint} is known")

    # hass.async_create_task(
    #     target=coordinator.leshan_client.listen_registrations(_async_handle_client_registration),
    #     name="leshan_client_listen_registrations"
    # )

    # await coordinator.leshan_client.listen_registrations(_async_handle_client_registration)

    # add the coordinator to the entry
    hass.data[DOMAIN][config_entry.entry_id] = RuntimeData(
        coordinator=coordinator,
        cancel_update_listener=cancel_update_listener,
    )

    # setup platforms, this calls async_setup_entry for each platform
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    # all went well
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # remove the config options update listener
    hass.data[DOMAIN][config_entry.entry_id].cancel_update_listener()

    # unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    # remove the config entry from hass data object
    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok


async def _async_update_listener(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Handle updates in the config flow options."""
    # reload the integration when options change
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Delete a device if selected from the UI."""
    return True
