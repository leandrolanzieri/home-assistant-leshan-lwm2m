"""Leshan LWM2M coordinator for the Home Assistant integration."""

import logging
from dataclasses import dataclass, field
from datetime import timedelta
from typing import ClassVar

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_SCAN_INTERVAL
from homeassistant.core import DOMAIN, HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .leshan_client import (
    LeshanClient,
    Lwm2mClient,
    Lwm2mObjectInstance,
    Lwm2mResourceValue,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class LeshanLwm2mCoordinatorPollListEntry:
    """Entry for the poll list."""

    client: Lwm2mClient
    """The client to poll."""

    instances: list[Lwm2mObjectInstance] = field(default_factory=list)
    """The instances to poll."""


@dataclass
class LeshanLwm2mPollResult:
    """The result of a poll."""

    client: Lwm2mClient
    """The client that was polled."""

    instance: Lwm2mObjectInstance
    """The instance that was polled."""

    resources: list[Lwm2mResourceValue] = field(default_factory=list)
    """The resources of the instance that was polled"""


@dataclass
class LeshanLwm2mCoordinatorData:
    """Data for the Leshan LWM2M coordinator."""

    clients: list[Lwm2mClient]
    """The clients connected to the server."""

    poll_results: list[LeshanLwm2mPollResult] = field(default_factory=list)
    """The results of the polling."""


class LeshanLwm2mCoordinator(DataUpdateCoordinator):
    """A coordinator for Leshan LWM2M integration."""

    data: LeshanLwm2mCoordinatorData
    _poll_list: ClassVar[list[LeshanLwm2mCoordinatorPollListEntry]] = []

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the Leshan LWM2M coordinator."""
        # set variables from the config flow
        self.host: str = config_entry.data[CONF_HOST]
        self.scan_interval: int = config_entry.data[CONF_SCAN_INTERVAL]

        # initialize the coordinator
        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"{DOMAIN} ({config_entry.unique_id})",
            update_interval=timedelta(seconds=self.scan_interval),
            update_method=self.async_update_data,
        )

        # initialize the leshan client
        self.leshan_client = LeshanClient(
            host=self.host, session=async_create_clientsession(hass)
        )

    def add_to_poll_list(
        self, client: Lwm2mClient, instances: list[Lwm2mObjectInstance]
    ) -> None:
        """Add a client and its instances to the poll list."""
        self._poll_list.append(
            LeshanLwm2mCoordinatorPollListEntry(client=client, instances=instances)
        )

    async def async_update_data(self) -> LeshanLwm2mCoordinatorData:
        """Fetch data from Leshan server."""
        try:
            clients = await self.leshan_client.get_clients()
            poll_results = []
            for poll_entry in self._poll_list:
                for instance in poll_entry.instances:
                    resources = await self.leshan_client.read(
                        client=poll_entry.client,
                        object_instance=instance,
                    )
                    poll_results.append(
                        LeshanLwm2mPollResult(
                            client=poll_entry.client,
                            instance=instance,
                            resources=resources,
                        )
                    )
        except Exception as e:
            msg = f"Error fetching data: {e}"
            raise UpdateFailed(msg) from e

        return LeshanLwm2mCoordinatorData(clients=clients, poll_results=poll_results)

    async def async_get_all_clients(self) -> list[Lwm2mClient]:
        """Get all clients."""
        return await self.leshan_client.get_clients()
