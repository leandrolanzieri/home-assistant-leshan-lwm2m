"""
The "hello world" custom component.

This component implements the bare minimum that a component should implement.

Configuration:

To use the hello_world component you will need to add the following to your
configuration.yaml file.

leshan_lwm2m:
"""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import DOMAIN, CONF_SERVER_URI
from .leshan_client import LeshanClient

PLATFORMS = [
    Platform.LIGHT,
    Platform.BINARY_SENSOR,
    # Platform.SWITCH,
]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    hass.data.setdefault(DOMAIN, {})
    leshan_client = LeshanClient(
        host=entry.data[CONF_SERVER_URI],
        session=async_create_clientsession(hass)
    )

    hass.data[DOMAIN][entry.entry_id] = leshan_client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
