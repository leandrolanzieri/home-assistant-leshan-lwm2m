from __future__ import annotations
import logging
import asyncio

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorEntityDescription
from .leshan_client import LeshanClient, Lwm2mResourceValue

from .const import (
    DOMAIN,
    LWM2M_DEVICE_OBJECT_ID,
    LWM2M_DEVICE_MANUFACTURER_RESOURCE_ID,
    LWM2M_DEVICE_FIRMWARE_VERSION_RESOURCE_ID,
    LWM2M_IPSO_ON_OFF_SWITCH_OBJECT_ID,
    LWM2M_IPSO_ON_OFF_SWITCH_DIGITAL_INPUT_STATE_RESOURCE_ID,
    LWM2M_IPSO_ON_OFF_SWITCH_APPLICATION_TYPE_RESOURCE_ID,
)
from homeassistant.helpers.device_registry import DeviceInfo

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the sensor platform."""
    leshan_client: LeshanClient = hass.data[DOMAIN][entry.entry_id]

    devices = await leshan_client.list_clients()

    switch_entities = []
    _LOGGER.debug(devices)

    for device in devices:
        endpoint = device.endpoint
        for instance in device.object_instances:
            if instance.object_id == LWM2M_IPSO_ON_OFF_SWITCH_OBJECT_ID:
                try:
                    name = (await leshan_client.read(
                        endpoint=endpoint,
                        object_id=instance.object_id,
                        instance_id=instance.instance_id,
                        resource_id=LWM2M_IPSO_ON_OFF_SWITCH_APPLICATION_TYPE_RESOURCE_ID
                    ))[0].value
                except:
                    name = f"{endpoint} {instance.instance_id}"

                # TODO: do this once per device
                try:
                    device = await leshan_client.read(
                        endpoint=endpoint,
                        object_id=LWM2M_DEVICE_OBJECT_ID,
                        instance_id=0
                    )

                    for resource in device:
                        if resource.resource_id == LWM2M_DEVICE_MANUFACTURER_RESOURCE_ID:
                            device_manufacturer = resource.value
                        if resource.resource_id == LWM2M_DEVICE_FIRMWARE_VERSION_RESOURCE_ID:
                            firmware_version = resource.value
                except:
                    _LOGGER.error(f"Failed to read device information for {endpoint}")

                switch_entities.append(
                    LeshanLwm2mSwitch(
                        leshan_client=leshan_client,
                        endpoint=endpoint,
                        object_id=instance.object_id,
                        instance_id=instance.instance_id,
                        manufacturer=device_manufacturer,
                        firmware_version=firmware_version,
                        entity_description=BinarySensorEntityDescription(
                            key=f"{endpoint}_{instance.object_id}_{instance.instance_id}",
                            name=name,
                            icon="mdi:light-switch",
                        )
                    )
                )

    async_add_entities(switch_entities)

class LeshanLwm2mSwitch(BinarySensorEntity):
    should_poll = False

    def __init__(
            self,
            leshan_client: LeshanClient,
            endpoint: str,
            object_id: int,
            instance_id: int,
            entity_description: BinarySensorEntityDescription,
            manufacturer: str = "Unknown",
            firmware_version: str = "Unknown",
    ) -> None:
        super().__init__()
        self._loop = asyncio.get_event_loop()
        self._switch_state = False
        self._endpoint = endpoint
        self._object_id = object_id
        self._instance_id = instance_id
        self._leshan_client = leshan_client
        self._manufacturer = manufacturer
        self._firmware_version = firmware_version
        self.entity_description = entity_description

    async def async_added_to_hass(self) -> None:
        """Run when this Entity has been added to HA."""
        # Importantly for a push integration, the module that will be getting updates
        # needs to notify HA of changes. The dummy device has a registercallback
        # method, so to this we add the 'self.async_write_ha_state' method, to be
        # called where ever there are changes.
        # The call back registration is done once this entity is registered with HA
        # (rather than in the __init__)
        await self._leshan_client.observe(
            endpoint=self._endpoint,
            object_id=self._object_id,
            instance_id=self._instance_id,
            resource_id=LWM2M_IPSO_ON_OFF_SWITCH_DIGITAL_INPUT_STATE_RESOURCE_ID,
            callback=self._async_observe_callback
        )

        await self._update()

    async def _async_observe_callback(self, value: Lwm2mResourceValue) -> None:
        """Handle value updates."""
        if value.resource_id == LWM2M_IPSO_ON_OFF_SWITCH_DIGITAL_INPUT_STATE_RESOURCE_ID:
            self._switch_state = value.value

        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self.unique_id)
            },
            name=self.name,
            manufacturer=self._manufacturer,
            sw_version=self._firmware_version,
        )

    @property
    def unique_id(self) -> str:
        return f"{self._endpoint}_{self._object_id}_{self._instance_id}"

    @property
    def is_on(self) -> bool:
        return self._switch_state

    async def _update(self):
        values = await self._leshan_client.read(
            endpoint=self._endpoint,
            object_id=self._object_id,
            instance_id=self._instance_id,
            resource_id=None
        )

        for value in values:
            if value.resource_id == LWM2M_IPSO_ON_OFF_SWITCH_DIGITAL_INPUT_STATE_RESOURCE_ID:
                self._switch_state = value.value

        value = values[0].value
        self._switch_state = value
