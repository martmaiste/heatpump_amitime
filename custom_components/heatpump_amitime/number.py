"""Number platform (setpoint controls) for the AmiTime Heat Pump integration."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NUMBERS, NumberDef


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    if not data["has_cloud"]:
        return  # numbers only make sense when the cloud API is configured
    coordinator = data["coordinator"]
    api = data["api"]
    device_info: DeviceInfo = data["device_info"]

    async_add_entities(
        [
            HeatpumpNumber(coordinator, api, ndef, device_info)
            for ndef in NUMBERS
        ]
    )


class HeatpumpNumber(CoordinatorEntity, NumberEntity):
    """A setpoint control. Shows the live value and sends changes to the cloud."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        coordinator,
        api,
        ndef: NumberDef,
        device_info: DeviceInfo,
    ) -> None:
        super().__init__(coordinator)
        self._api = api
        self._par = ndef.par
        self._key = ndef.key
        self._attr_name = ndef.name
        self._attr_unique_id = (
            f"{coordinator.config_entry.unique_id}_{ndef.par}"
        )
        self._attr_native_min_value = ndef.min_value
        self._attr_native_max_value = ndef.max_value
        self._attr_native_step = ndef.step
        self._attr_native_unit_of_measurement = ndef.unit
        self._attr_device_class = ndef.device_class
        self._attr_device_info = device_info

    @property
    def native_value(self):
        if self._key is None or not self.coordinator.last_update_success:
            return None
        data = self.coordinator.data
        if data is None:
            return None
        return data.get(self._key)

    async def async_set_native_value(self, value: float) -> None:
        await self._api.async_set_field(self._par, value)
