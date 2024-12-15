"""Support for LwM2M lights."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ColorMode,
    LightEntity,
    LightEntityDescription,
)
from homeassistant.util.color import brightness_to_value, value_to_brightness

from .const import (
    DOMAIN,
    LWM2M_IPSO_LIGHT_CONTROL_APPLICATION_TYPE_RESOURCE_ID,
    LWM2M_IPSO_LIGHT_CONTROL_DIMMER_RESOURCE_ID,
    LWM2M_IPSO_LIGHT_CONTROL_OBJECT_ID,
    LWM2M_IPSO_LIGHT_CONTROL_ON_OFF_RESOURCE_ID,
)
from .leshan_client import (
    Lwm2mClient,
    Lwm2mObjectInstance,
    Lwm2mResourceValue,
    Lwm2mResourceValueType,
)
from .leshan_client.exceptions import (
    LeshanClientConnectionError,
    LeshanClientConnectionTimeoutError,
    LeshanClientEmptyResponseError,
    LeshanClientError,
)
from .leshan_lwm2m_entity import LeshanLwm2mEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .leshan_lwm2m_coordinator import LeshanLwm2mCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
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
                    "Found light control object on LwM2M client",
                    extra={"endpoint": client.endpoint},
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
    """
    Representation of a LWM2M light.

    Args:
        client (Lwm2mClient): The LWM2M client that this entity belongs to.
        instance (Lwm2mObjectInstance): The LWM2M object instance that this entity
        belongs to.
        coordinator (LeshanLwm2mCoordinator): The coordinator for the LWM2M entities.
        server_name (str): The name of the LWM2M server that this entity belongs to.

    """

    BRIGHTNESS_SCALE = (1, 100)

    def __init__(
        self,
        client: Lwm2mClient,
        instance: Lwm2mObjectInstance,
        coordinator: LeshanLwm2mCoordinator,
        server_name: str,
    ) -> None:
        """Initialize the LWM2M light."""
        super().__init__(
            client=client,
            instance=instance,
            coordinator=coordinator,
            server_name=server_name,
        )

        self._light_control_status: bool = False
        self._brightness: int = 0
        self._name: str = "Unknown Light"

    async def observe_resources(self) -> None:
        """Observe the light control resources."""
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
        _: Lwm2mClient,
        __: Lwm2mObjectInstance,
        value: Lwm2mResourceValue,
    ) -> None:
        """Handle value updates."""
        self._light_control_status = bool(value.value)
        self.async_write_ha_state()

    async def _handle_dimmer_update(
        self,
        _: Lwm2mClient,
        __: Lwm2mObjectInstance,
        value: Lwm2mResourceValue,
    ) -> None:
        """Handle value updates."""
        self._brightness = int(value.value)
        self.async_write_ha_state()

    async def async_update_device_info(self) -> None:
        """Update the device info."""
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

            if len(light) != 1:
                msg = f"Expected 1 resource, got {len(light)}"
                _LOGGER.error(msg)
            self._name = str(light[0].value)

        except (
            LeshanClientError,
            LeshanClientConnectionError,
            LeshanClientConnectionTimeoutError,
            LeshanClientEmptyResponseError,
        ) as e:
            msg = f"Failed to read light information for {self.client.endpoint}: {e}"
            _LOGGER.exception(msg)
            return

        try:
            light = await self.coordinator.leshan_client.read(
                client=self.client,
                object_instance=self.instance,
                resource_id=LWM2M_IPSO_LIGHT_CONTROL_ON_OFF_RESOURCE_ID,
            )

            if len(light) != 1:
                msg = f"Expected 1 resource, got {len(light)}"
                _LOGGER.error(msg)
            self._light_control_status = bool(light[0].value)
        except (
            LeshanClientError,
            LeshanClientConnectionError,
            LeshanClientConnectionTimeoutError,
            LeshanClientEmptyResponseError,
        ) as e:
            msg = f"Failed to read light status for {self.client.endpoint}: {e}"
            _LOGGER.exception(msg)
            return

    @property
    def is_on(self) -> bool:
        """Return the state of the light."""
        return self._light_control_status

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light."""
        # TODO: Check capabilities
        # convert from 0-100 to 0-255
        return value_to_brightness(self.BRIGHTNESS_SCALE, self._brightness)

    @property
    def supported_color_modes(self) -> set[ColorMode] | None:
        """Flag supported color modes."""
        return {ColorMode.BRIGHTNESS}

    @property
    def color_mode(self) -> ColorMode | None:
        """Return the color mode of the light."""
        return ColorMode.BRIGHTNESS

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
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
            self._brightness = int(brightness_in_range)

        await self.coordinator.leshan_client.write(
            client=self.client,
            object_instance=self.instance,
            values=values,
        )

        self._light_control_status = True
        self.async_write_ha_state()

    async def async_turn_off(self, **_: Any) -> None:
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
