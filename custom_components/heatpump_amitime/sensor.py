"""Sensor platform for the AmiTime Heat Pump integration."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, READ_SENSORS, SETPOINT_SENSORS, SensorDef


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    device_info: DeviceInfo = data["device_info"]
    has_cloud: bool = data["has_cloud"]

    entities: list[HeatpumpSensor] = [
        HeatpumpSensor(coordinator, sdef, device_info) for sdef in READ_SENSORS
    ]
    # When cloud controls are disabled, expose the setpoint values as plain
    # sensors (they would otherwise be reachable only via the number controls).
    if not has_cloud:
        entities += [
            HeatpumpSensor(coordinator, sdef, device_info)
            for sdef in SETPOINT_SENSORS
        ]
    async_add_entities(entities)


class HeatpumpSensor(CoordinatorEntity, SensorEntity):
    """A single real-time or setpoint sensor fed by the coordinator."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        coordinator,
        sdef: SensorDef,
        device_info: DeviceInfo,
    ) -> None:
        super().__init__(coordinator)
        self._key = sdef.key
        self._value_map = sdef.value_map
        self._attr_name = sdef.name
        self._attr_unique_id = (
            f"{coordinator.config_entry.unique_id}_{sdef.key}"
        )
        self._attr_native_unit_of_measurement = sdef.unit
        self._attr_device_class = sdef.device_class
        self._attr_state_class = sdef.state_class
        self._attr_device_info = device_info

    @property
    def native_value(self):
        if not self.coordinator.last_update_success:
            return None
        data = self.coordinator.data
        if data is None:
            return None
        raw = data.get(self._key)
        if raw is None:
            return None
        if self._value_map:
            return self._value_map.get(raw, raw)
        return raw
