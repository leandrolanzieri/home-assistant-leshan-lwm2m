from dataclasses import dataclass, field
from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant, DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.const import (
    CONF_HOST,
    CONF_SCAN_INTERVAL
)

from .leshan_client import LeshanClient, Lwm2mClient, Lwm2mObjectInstance, Lwm2mResourceValue

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
    _poll_list: list[LeshanLwm2mCoordinatorPollListEntry] = []

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry):
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
            host=self.host,
            session=async_create_clientsession(hass)
        )

    def add_to_poll_list(self, client: Lwm2mClient, instances: list[Lwm2mObjectInstance]):
        self._poll_list.append(LeshanLwm2mCoordinatorPollListEntry(client=client, instances=instances))

    async def async_update_data(self):
        """Fetch data from Leshan server."""
        try:
            clients = await self.leshan_client.get_clients()
            poll_results = []
            for poll_entry in self._poll_list:
                for instance in poll_entry.instances:
                    resources = await self.leshan_client.read(
                        endpoint=poll_entry.client.endpoint,
                        object_id=instance.object_id,
                        instance_id=instance.instance_id
                    )
                    poll_results.append(LeshanLwm2mPollResult(client=poll_entry.client, instance=instance, resources=resources))
        except Exception as e:
            raise UpdateFailed(f"Error fetching data: {e}") from e

        return LeshanLwm2mCoordinatorData(clients=clients, poll_results=poll_results)

    async def async_get_all_clients(self):
        """Get all clients."""
        return await self.leshan_client.get_clients()
