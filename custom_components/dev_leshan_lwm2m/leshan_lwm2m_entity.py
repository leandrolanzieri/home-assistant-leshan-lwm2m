"""Base class for Leshan LWM2M entities."""

import logging

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    LWM2M_DEVICE_FIRMWARE_VERSION_RESOURCE_ID,
    LWM2M_DEVICE_HARDWARE_VERSION_RESOURCE_ID,
    LWM2M_DEVICE_MANUFACTURER_RESOURCE_ID,
    LWM2M_DEVICE_OBJECT_ID,
)
from .leshan_client import Lwm2mClient, Lwm2mObjectInstance
from .leshan_client.exceptions import (
    LeshanClientConnectionError,
    LeshanClientConnectionTimeoutError,
    LeshanClientEmptyResponseError,
    LeshanClientError,
)
from .leshan_lwm2m_coordinator import LeshanLwm2mCoordinator

_LOGGER = logging.getLogger(__name__)


class LeshanLwm2mEntity(CoordinatorEntity):
    """
    Base class for Leshan LWM2M entities.

    Args:
        client: The LWM2M client that this entity belongs to.
        instance: The LWM2M object instance that this entity belongs to.
        coordinator: The coordinator for the LWM2M entities.
        server_name: The name of the LWM2M server that this entity belongs to.

    """

    _attr_should_poll = False

    def __init__(
        self,
        client: Lwm2mClient,
        instance: Lwm2mObjectInstance,
        coordinator: LeshanLwm2mCoordinator,
        server_name: str,
    ) -> None:
        """Initialize the LWM2M entity."""
        super().__init__(coordinator)
        self.client = client
        """The LWM2M client that this entity belongs to."""

        self.instance = instance
        """The LWM2M object instance that this entity belongs to."""

        self.coordinator = coordinator
        """The coordinator for the LWM2M entities."""

        self.server_name = server_name
        """The name of the LWM2M server that this entity belongs to."""

        self.manufacturer = None
        """The manufacturer of the device."""

        self.hardware_version = None
        """The hardware version of the device."""

        self.firmware_version = None
        """The firmware version of the device."""

    async def async_update_device_info(self) -> None:
        """Update the device information."""
        await self.read_device_info()

    async def read_device_info(self) -> None:
        """
        Read device information from the device object.

        This sets the manufacturer and firmware version of the device.
        """
        try:
            instance = Lwm2mObjectInstance(
                object_id=LWM2M_DEVICE_OBJECT_ID, instance_id=0
            )
            device = await self.coordinator.leshan_client.read(
                client=self.client, object_instance=instance
            )
        except (
            LeshanClientError,
            LeshanClientConnectionError,
            LeshanClientConnectionTimeoutError,
            LeshanClientEmptyResponseError,
        ) as e:
            msg = f"Failed to read device information for {self.client.endpoint}: {e}"
            _LOGGER.exception(msg)
            return

        for resource in device:
            if resource.resource_id == LWM2M_DEVICE_MANUFACTURER_RESOURCE_ID:
                self.manufacturer = str(resource.value)
            if resource.resource_id == LWM2M_DEVICE_FIRMWARE_VERSION_RESOURCE_ID:
                self.firmware_version = str(resource.value)
            if resource.resource_id == LWM2M_DEVICE_HARDWARE_VERSION_RESOURCE_ID:
                self.hardware_version = str(resource.value)

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.client.endpoint)},
            name=self.client.endpoint,
            manufacturer=self.manufacturer,
            sw_version=self.firmware_version,
            hw_version=self.hardware_version,
            via_device=(DOMAIN, self.server_name),
        )

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the entity."""
        id_value = f"{self.client.endpoint}"
        id_value += f"_{self.instance.object_id}"
        id_value += f"_{self.instance.instance_id}"
        return id_value
