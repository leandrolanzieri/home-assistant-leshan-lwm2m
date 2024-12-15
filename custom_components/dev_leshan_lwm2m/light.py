from __future__ import annotations
import logging

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    LightEntity,
    LightEntityDescription,
    ColorMode,
)
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.color import value_to_brightness, brightness_to_value

from .const import (
    DOMAIN,
    LWM2M_IPSO_LIGHT_CONTROL_OBJECT_ID,
    LWM2M_IPSO_LIGHT_CONTROL_DIMMER_RESOURCE_ID,
    LWM2M_IPSO_LIGHT_CONTROL_ON_OFF_RESOURCE_ID,
    LWM2M_IPSO_LIGHT_CONTROL_APPLICATION_TYPE_RESOURCE_ID,
)

from .leshan_client import (
    Lwm2mClient,
    Lwm2mObjectInstance,
    Lwm2mResourceValue,
    Lwm2mResourceValueType,
)
from .leshan_lwm2m_entity import LeshanLwm2mEntity
from .leshan_lwm2m_coordinator import LeshanLwm2mCoordinator


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up the light platform."""
    # this gets the leshan lwm2m data coordinator specified in __init__.py
    coordinator: LeshanLwm2mCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ].coordinator

    light_entities = []
    clients = coordinator.data.clients
    for client in clients:
        for instance in client.object_instances:
            if instance.object_id == LWM2M_IPSO_LIGHT_CONTROL_OBJECT_ID:
                _LOGGER.debug(
                    f"Found light control object on LwM2M client {client.endpoint}"
                )
                light = LeshanLwm2mLight(
                    client=client,
                    instance=instance,
                    coordinator=coordinator,
                    server_name=config_entry.title,
                )
                await light.observe_resources()
                await light.async_update_device_info()
                light_entities.append(light)

    async_add_entities(light_entities)


class LeshanLwm2mLight(LeshanLwm2mEntity, LightEntity):
    BRIGHTNESS_SCALE = (1, 100)

    def __init__(
        self,
        client: Lwm2mClient,
        instance: Lwm2mObjectInstance,
        coordinator: LeshanLwm2mCoordinator,
        server_name: str,
    ) -> None:
        super().__init__(
            client=client,
            instance=instance,
            coordinator=coordinator,
            server_name=server_name,
        )

        self._color_mode = ColorMode.BRIGHTNESS
        self._light_control_status = False
        self._brightness: int = 0
        self._name: str | None = None

    async def observe_resources(self):
        await self.coordinator.leshan_client.observe(
            client=self.client,
            instance=self.instance,
            resource_id=LWM2M_IPSO_LIGHT_CONTROL_ON_OFF_RESOURCE_ID,
            callback=self._handle_on_off_update,
        )

        await self.coordinator.leshan_client.observe(
            client=self.client,
            instance=self.instance,
            resource_id=LWM2M_IPSO_LIGHT_CONTROL_DIMMER_RESOURCE_ID,
            callback=self._handle_dimmer_update,
        )

    async def _handle_on_off_update(
        self,
        client: Lwm2mClient,
        instance: Lwm2mObjectInstance,
        value: Lwm2mResourceValue,
    ) -> None:
        """Handle value updates."""
        self._light_control_status = value.value
        self.async_write_ha_state()

    async def _handle_dimmer_update(
        self,
        client: Lwm2mClient,
        instance: Lwm2mObjectInstance,
        value: Lwm2mResourceValue,
    ) -> None:
        """Handle value updates."""
        self._brightness = value.value
        self.async_write_ha_state()

    async def async_update_device_info(self):
        await super().async_update_device_info()
        await self.read_light_info()

        self.entity_description = LightEntityDescription(
            key=f"{self.client.endpoint}_{self.instance.object_id}_{self.instance.instance_id}",
            name=self._name,
            icon="mdi:lightbulb-variant-outline",
        )

    async def read_light_info(self) -> None:
        """
        Read the light state from the device object.

        This sets the light name.
        """
        try:
            light = await self.coordinator.leshan_client.read(
                client=self.client,
                object_instance=self.instance,
                resource_id=LWM2M_IPSO_LIGHT_CONTROL_APPLICATION_TYPE_RESOURCE_ID,
            )
            assert len(light) == 1
            self._name = light[0].value
        except Exception as e:
            _LOGGER.error(
                f"Failed to read light information for {self.client.endpoint}: {e}"
            )
            return

        try:
            light = await self.coordinator.leshan_client.read(
                client=self.client,
                object_instance=self.instance,
                resource_id=LWM2M_IPSO_LIGHT_CONTROL_ON_OFF_RESOURCE_ID,
            )
            assert len(light) == 1
            self._light_control_status = light[0].value
        except Exception as e:
            _LOGGER.error(
                f"Failed to read light status for {self.client.endpoint}: {e}"
            )
            return

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
        return set([ColorMode.BRIGHTNESS])

    @property
    def color_mode(self) -> ColorMode | None:
        return self._color_mode

    async def async_turn_on(self, **kwargs: any) -> None:
        values = [
            Lwm2mResourceValue(
                resource_id=LWM2M_IPSO_LIGHT_CONTROL_ON_OFF_RESOURCE_ID,
                type=Lwm2mResourceValueType.BOOLEAN,
                value=True,
            )
        ]
        # check if ATTR_BRIGHTNESS is in kwargs
        if ATTR_BRIGHTNESS in kwargs:
            brightness_in_range = brightness_to_value(
                self.BRIGHTNESS_SCALE, kwargs[ATTR_BRIGHTNESS]
            )
            values.append(
                Lwm2mResourceValue(
                    resource_id=LWM2M_IPSO_LIGHT_CONTROL_DIMMER_RESOURCE_ID,
                    type=Lwm2mResourceValueType.INTEGER,
                    value=brightness_in_range,
                )
            )
            self._brightness = brightness_in_range

        await self.coordinator.leshan_client.write(
            client=self.client,
            object_instance=self.instance,
            values=values,
        )

        self._light_control_status = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: any) -> None:
        """Turn the light off."""
        value = Lwm2mResourceValue(
            resource_id=LWM2M_IPSO_LIGHT_CONTROL_ON_OFF_RESOURCE_ID,
            type=Lwm2mResourceValueType.BOOLEAN,
            value=False,
        )
        await self.coordinator.leshan_client.write(
            client=self.client,
            object_instance=self.instance,
            values=[value],
        )

        self._light_control_status = False
        self.async_write_ha_state()
