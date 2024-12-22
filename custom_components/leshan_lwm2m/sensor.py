"""Support for LWM2M sensors."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorEntityDescription,
)
from homeassistant.components.sensor.const import SensorDeviceClass
from homeassistant.core import HomeAssistant, callback

from .const import (
    DOMAIN,
    LWM2M_IPSO_BAROMETER_OBJECT_ID,
    LWM2M_IPSO_CURRENT_OBJECT_ID,
    LWM2M_IPSO_HUMIDITY_OBJECT_ID,
    LWM2M_IPSO_ILLUMINANCE_OBJECT_ID,
    LWM2M_IPSO_SENSOR_UNITS_RESOURCE_ID,
    LWM2M_IPSO_SENSOR_VALUE_RESOURCE_ID,
    LWM2M_IPSO_TEMPERATURE_OBJECT_ID,
    LWM2M_IPSO_VOLTAGE_OBJECT_ID,
)
from .leshan_lwm2m_entity import LeshanLwm2mEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .leshan_client import Lwm2mClient, Lwm2mObjectInstance, Lwm2mResourceValue
    from .leshan_lwm2m_coordinator import LeshanLwm2mCoordinator

_LOGGER = logging.getLogger(__name__)

SENSOR_MAPPING = {
    LWM2M_IPSO_TEMPERATURE_OBJECT_ID: SensorDeviceClass.TEMPERATURE,
    LWM2M_IPSO_CURRENT_OBJECT_ID: SensorDeviceClass.CURRENT,
    LWM2M_IPSO_BAROMETER_OBJECT_ID: SensorDeviceClass.PRESSURE,
    LWM2M_IPSO_ILLUMINANCE_OBJECT_ID: SensorDeviceClass.ILLUMINANCE,
    LWM2M_IPSO_HUMIDITY_OBJECT_ID: SensorDeviceClass.HUMIDITY,
    LWM2M_IPSO_VOLTAGE_OBJECT_ID: SensorDeviceClass.VOLTAGE,
}


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
            if instance.object_id in SENSOR_MAPPING:
                switch = LeshanLwm2mSensor(
                    client=client,
                    instance=instance,
                    coordinator=coordinator,
                    server_name=config_entry.title,
                    device_class=SENSOR_MAPPING[instance.object_id],
                )
                await switch.async_update_device_info()

                switch_entities.append(switch)

    async_add_entities(switch_entities)


class LeshanLwm2mSensor(LeshanLwm2mEntity, RestoreSensor):
    """Representation of a LWM2M binary sensor."""

    def __init__(
        self,
        client: Lwm2mClient,
        instance: Lwm2mObjectInstance,
        coordinator: LeshanLwm2mCoordinator,
        server_name: str,
        device_class: SensorDeviceClass,
    ) -> None:
        """Initialize the LWM2M binary sensor."""
        super().__init__(
            client=client,
            instance=instance,
            coordinator=coordinator,
            server_name=server_name,
        )

        self._name: str | None = None
        self._attr_device_class = device_class
        self._value = None
        self._attr_native_unit_of_measurement = None

    async def async_added_to_hass(self) -> None:
        """Observe the value resource when entity added to HASS."""
        await self.coordinator.leshan_client.observe(
            client=self.client,
            object_instance=self.instance,
            resource_id=LWM2M_IPSO_SENSOR_VALUE_RESOURCE_ID,
            callback=self._handle_digital_input_update,
        )

    async def async_will_remove_from_hass(self) -> None:
        """Remove the observation when the entity is removed from HASS."""
        await self.coordinator.leshan_client.cancel_observe(
            client=self.client,
            object_instance=self.instance,
            resource_id=LWM2M_IPSO_SENSOR_VALUE_RESOURCE_ID,
        )

    async def async_update_device_info(self) -> None:
        """Update the device info."""
        await super().async_update_device_info()
        await self.read_sensor_info()

        self.entity_description = SensorEntityDescription(
            key=f"{self.client.endpoint}_{self.instance.object_id}_{self.instance.instance_id}",
            name=f"{self._name}",
            device_class=self._attr_device_class,
        )

    async def read_sensor_info(self) -> None:
        """Read the sensor value and info."""
        try:
            units = await self.coordinator.leshan_client.read(
                client=self.client,
                object_instance=self.instance,
                resource_id=LWM2M_IPSO_SENSOR_UNITS_RESOURCE_ID,
            )

            if len(units) != 1:
                msg = f"Expected 1 resource, got {len(units)}"
                _LOGGER.error(msg)
            self._attr_native_unit_of_measurement = str(units[0].value)

        except Exception as e:
            msg = f"Failed to read sensor units for {self.client.endpoint}: {e}"
            _LOGGER.exception(msg)
            return

        try:
            sensor = await self.coordinator.leshan_client.read(
                client=self.client,
                object_instance=self.instance,
                resource_id=LWM2M_IPSO_SENSOR_VALUE_RESOURCE_ID,
            )

            if len(sensor) != 1:
                msg = f"Expected 1 resource, got {len(sensor)}"
                _LOGGER.error(msg)
            self._value = float(sensor[0].value)

        except Exception as e:
            msg = f"Failed to read sensor value for {self.client.endpoint}: {e}"
            _LOGGER.exception(msg)
            return

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return self._value

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self.client.endpoint

    @callback
    async def _handle_digital_input_update(
        self,
        _: Lwm2mClient,
        __: Lwm2mObjectInstance,
        resource_value: Lwm2mResourceValue,
    ) -> None:
        self._value = float(resource_value.value)
        msg = f"Updated sensor value to {self._value}"
        _LOGGER.debug(msg)
        self.async_write_ha_state()
