"""Support for LWM2M binary sensors."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback

from .const import (
    DOMAIN,
    LWM2M_IPSO_ON_OFF_SWITCH_APPLICATION_TYPE_RESOURCE_ID,
    LWM2M_IPSO_ON_OFF_SWITCH_DIGITAL_INPUT_STATE_RESOURCE_ID,
    LWM2M_IPSO_ON_OFF_SWITCH_OBJECT_ID,
)
from .leshan_lwm2m_entity import LeshanLwm2mEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .leshan_client import Lwm2mClient, Lwm2mObjectInstance, Lwm2mResourceValue
    from .leshan_lwm2m_coordinator import LeshanLwm2mCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    # this gets the leshan lwm2m data coordinator specified in __init__.py
    coordinator: LeshanLwm2mCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ].coordinator

    switch_entities = []
    clients: list[Lwm2mClient] = coordinator.data.clients
    for client in clients:
        for instance in client.object_instances:
            if instance.object_id == LWM2M_IPSO_ON_OFF_SWITCH_OBJECT_ID:
                switch = LeshanLwm2mSwitch(
                    client=client,
                    instance=instance,
                    coordinator=coordinator,
                    server_name=config_entry.title,
                )
                await switch.observe_resource()
                await switch.async_update_device_info()

                switch_entities.append(switch)

    async_add_entities(switch_entities)


class LeshanLwm2mSwitch(LeshanLwm2mEntity, BinarySensorEntity):
    """Representation of a LWM2M binary sensor."""

    def __init__(
        self,
        client: Lwm2mClient,
        instance: Lwm2mObjectInstance,
        coordinator: LeshanLwm2mCoordinator,
        server_name: str,
    ) -> None:
        """Initialize the LWM2M binary sensor."""
        super().__init__(
            client=client,
            instance=instance,
            coordinator=coordinator,
            server_name=server_name,
        )

        self._switch_state: bool | None = None
        self._name: str | None = None

    async def observe_resource(self) -> None:
        """Observe the digital input state resource."""
        await self.coordinator.leshan_client.observe(
            client=self.client,
            instance=self.instance,
            resource_id=LWM2M_IPSO_ON_OFF_SWITCH_DIGITAL_INPUT_STATE_RESOURCE_ID,
            callback=self._handle_digital_input_update,
        )

    async def async_update_device_info(self) -> None:
        """Update the device info."""
        await super().async_update_device_info()
        await self.read_switch_info()

        self.entity_description = BinarySensorEntityDescription(
            key=f"{self.client.endpoint}_{self.instance.object_id}_{self.instance.instance_id}",
            name=f"{self._name}",
            icon="mdi:light-switch",
        )

    async def read_switch_info(self) -> None:
        """
        Read the switch state from the device object.

        This sets the switch name.
        """
        try:
            switch = await self.coordinator.leshan_client.read(
                client=self.client,
                object_instance=self.instance,
                resource_id=LWM2M_IPSO_ON_OFF_SWITCH_APPLICATION_TYPE_RESOURCE_ID,
            )

            if len(switch) != 1:
                msg = f"Expected 1 resource, got {len(switch)}"
                _LOGGER.error(msg)
            self._name = str(switch[0].value)

        except Exception as e:
            msg = f"Failed to read switch information for {self.client.endpoint}: {e}"
            _LOGGER.exception(msg)
            return

        try:
            switch = await self.coordinator.leshan_client.read(
                client=self.client,
                object_instance=self.instance,
                resource_id=LWM2M_IPSO_ON_OFF_SWITCH_DIGITAL_INPUT_STATE_RESOURCE_ID,
            )

            if len(switch) != 1:
                msg = f"Expected 1 resource, got {len(switch)}"
                _LOGGER.error(msg)
            self._switch_state = bool(switch[0].value)

        except Exception as e:
            msg = f"Failed to read switch status for {self.client.endpoint}: {e}"
            _LOGGER.exception(msg)
            return

    @property
    def is_on(self) -> bool:
        """Return the state of the switch."""
        return self._switch_state is not None and self._switch_state

    @property
    def name(self) -> str:
        """Return the name of the switch."""
        return self._name or "Unknown Switch"

    @callback
    async def _handle_digital_input_update(
        self,
        _: Lwm2mClient,
        __: Lwm2mObjectInstance,
        resource_value: Lwm2mResourceValue,
    ) -> None:
        self._switch_state = bool(resource_value.value)
        msg = f"Updated switch state to {self._switch_state}"
        _LOGGER.debug(msg)
        self.async_write_ha_state()
