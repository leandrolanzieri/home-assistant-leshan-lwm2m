from __future__ import annotations
import logging
import asyncio

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    LightEntity,
    LightEntityDescription,
    ColorMode
)
from homeassistant.util.color import value_to_brightness, brightness_to_value

from .const import (
    DOMAIN,
    LWM2M_IPSO_LIGHT_CONTROL_OBJECT_ID,
    LWM2M_IPSO_LIGHT_CONTROL_DIMMER_RESOURCE_ID,
    LWM2M_IPSO_LIGHT_CONTROL_ON_OFF_RESOURCE_ID,
    LWM2M_IPSO_LIGHT_CONTROL_APPLICATION_TYPE_RESOURCE_ID,
    LWM2M_DEVICE_OBJECT_ID,
    LWM2M_DEVICE_MANUFACTURER_RESOURCE_ID,
    LWM2M_DEVICE_FIRMWARE_VERSION_RESOURCE_ID,
)
from .leshan_client import LeshanClient, Lwm2mResourceValue, Lwm2mResourceValueType
from homeassistant.helpers.device_registry import DeviceInfo

from aiohttp_sse_client import client as sse_client

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the sensor platform."""
    leshan_client: LeshanClient = hass.data[DOMAIN][entry.entry_id]

    devices = await leshan_client.list_clients()

    light_entities = []
    _LOGGER.debug(devices)

    for device in devices:
        endpoint = device.endpoint
        for instance in device.object_instances:
            if instance.object_id == LWM2M_IPSO_LIGHT_CONTROL_OBJECT_ID:
                try:
                    name = (await leshan_client.read(
                        endpoint=endpoint,
                        object_id=instance.object_id,
                        instance_id=instance.instance_id,
                        resource_id=LWM2M_IPSO_LIGHT_CONTROL_APPLICATION_TYPE_RESOURCE_ID
                    ))[0].value
                except:
                    name = f"{endpoint} {instance.instance_id}"

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

                light_entities.append(
                    LeshanLwm2mLight(
                        leshan_client=leshan_client,
                        endpoint=endpoint,
                        object_id=instance.object_id,
                        instance_id=instance.instance_id,
                        manufacturer=device_manufacturer,
                        firmware_version=firmware_version,
                        entity_description=LightEntityDescription(
                            key=f"{endpoint}_{instance.object_id}_{instance.instance_id}",
                            name=name,
                            icon="mdi:lightbulb-variant-outline",
                        )
                    )
                )

    async_add_entities(light_entities)

class LeshanLwm2mLight(LightEntity):
    BRIGHTNESS_SCALE = (1, 100)
    should_poll = False

    def __init__(
            self,
            leshan_client: LeshanClient,
            endpoint: str,
            object_id: int,
            instance_id: int,
            entity_description: LightEntityDescription,
            manufacturer: str = "Unknown",
            firmware_version: str = "Unknown",
    ) -> None:
        super().__init__()
        self._color_mode = ColorMode.BRIGHTNESS
        self._loop = asyncio.get_event_loop()
        self._light_control_status = False
        self._brightness = 0
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
            resource_id=LWM2M_IPSO_LIGHT_CONTROL_ON_OFF_RESOURCE_ID,
            callback=self._async_observe_callback
        )

        await self._leshan_client.observe(
            endpoint=self._endpoint,
            object_id=self._object_id,
            instance_id=self._instance_id,
            resource_id=LWM2M_IPSO_LIGHT_CONTROL_DIMMER_RESOURCE_ID,
            callback=self._async_observe_callback
        )

        await self._update()

    async def _async_observe_callback(self, value: Lwm2mResourceValue) -> None:
        """Handle value updates."""
        if value.resource_id == LWM2M_IPSO_LIGHT_CONTROL_ON_OFF_RESOURCE_ID:
            self._light_control_status = value.value
        elif value.resource_id == LWM2M_IPSO_LIGHT_CONTROL_DIMMER_RESOURCE_ID:
            self._brightness = value.value
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
        return self._light_control_status

    @property
    def brightness(self) -> int | None:
        # TODO: Check capabilities
        # convert from 0-100 to 0-255
        return value_to_brightness(self.BRIGHTNESS_SCALE, self._brightness)

    @property
    def supported_color_modes(self) -> set[ColorMode] | None:
        return set([
            ColorMode.BRIGHTNESS
        ])

    @property
    def color_mode(self) -> ColorMode | None:
        return self._color_mode

    async def _update(self):
        values = await self._leshan_client.read(
            endpoint=self._endpoint,
            object_id=self._object_id,
            instance_id=self._instance_id,
            resource_id=None
        )

        for value in values:
            if value.resource_id == LWM2M_IPSO_LIGHT_CONTROL_ON_OFF_RESOURCE_ID:
                self._light_control_status = value.value
            elif value.resource_id == LWM2M_IPSO_LIGHT_CONTROL_DIMMER_RESOURCE_ID:
                self._brightness = value.value

        value = values[0].value
        self._light_control_status = value

    async def async_turn_on(self, **kwargs: any) -> None:
        values = [
            Lwm2mResourceValue(
                resource_id=LWM2M_IPSO_LIGHT_CONTROL_ON_OFF_RESOURCE_ID,
                type=Lwm2mResourceValueType.BOOLEAN,
                value=True
            )
        ]
        # check if ATTR_BRIGHTNESS is in kwargs
        if ATTR_BRIGHTNESS in kwargs:
            brightness_in_range = brightness_to_value(self.BRIGHTNESS_SCALE, kwargs[ATTR_BRIGHTNESS])
            values.append(
                Lwm2mResourceValue(
                    resource_id=LWM2M_IPSO_LIGHT_CONTROL_DIMMER_RESOURCE_ID,
                    type=Lwm2mResourceValueType.INTEGER,
                    value=brightness_in_range
                )
            )

        await self._leshan_client.write(
            endpoint=self._endpoint,
            object_id=self._object_id,
            instance_id=self._instance_id,
            values=values
        )

    async def async_turn_off(self, **kwargs: any) -> None:
        value = Lwm2mResourceValue(
            resource_id=LWM2M_IPSO_LIGHT_CONTROL_ON_OFF_RESOURCE_ID,
            type=Lwm2mResourceValueType.BOOLEAN,
            value=False
        )
        await self._leshan_client.write(
            endpoint=self._endpoint,
            object_id=self._object_id,
            instance_id=self._instance_id,
            values=[value]
        )
