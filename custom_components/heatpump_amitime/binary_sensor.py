"""Binary sensor platform for the AmiTime Heat Pump integration."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    BINARY_SENSORS,
    DOMAIN,
    FALLBACK_BINARY,
    BinaryDef,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    device_info: DeviceInfo = data["device_info"]
    has_cloud: bool = data["has_cloud"]

    entities: list[HeatpumpBinarySensor] = [
        HeatpumpBinarySensor(coordinator, bdef, device_info)
        for bdef in BINARY_SENSORS
    ]
    # When cloud controls are disabled, the power / low-noise values become
    # read-only binary sensors instead of switches.
    if not has_cloud:
        entities += [
            HeatpumpBinarySensor(coordinator, bdef, device_info)
            for bdef in FALLBACK_BINARY
        ]
    async_add_entities(entities)


class HeatpumpBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """A boolean state flag fed by the coordinator."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        coordinator,
        bdef: BinaryDef,
        device_info: DeviceInfo,
    ) -> None:
        super().__init__(coordinator)
        self._key = bdef.key
        self._attr_name = bdef.name
        self._attr_unique_id = (
            f"{coordinator.config_entry.unique_id}_{bdef.key}"
        )
        self._attr_device_class = bdef.device_class
        self._attr_device_info = device_info

    @property
    def is_on(self) -> bool | None:
        if not self.coordinator.last_update_success:
            return None
        data = self.coordinator.data
        if data is None:
            return None
        return bool(data.get(self._key))
