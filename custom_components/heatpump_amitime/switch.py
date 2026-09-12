"""Switch platform (power controls) for the AmiTime Heat Pump integration."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SWITCHES, SwitchDef


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    if not data["has_cloud"]:
        return
    coordinator = data["coordinator"]
    api = data["api"]
    device_info: DeviceInfo = data["device_info"]

    async_add_entities(
        [
            HeatpumpSwitch(coordinator, api, sdef, device_info)
            for sdef in SWITCHES
        ]
    )


class HeatpumpSwitch(CoordinatorEntity, SwitchEntity):
    """A on/off control. Shows the live state and sends changes to the cloud."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        coordinator,
        api,
        sdef: SwitchDef,
        device_info: DeviceInfo,
    ) -> None:
        super().__init__(coordinator)
        self._api = api
        self._par = sdef.par
        self._key = sdef.key
        self._attr_name = sdef.name
        self._attr_unique_id = (
            f"{coordinator.config_entry.unique_id}_{sdef.par}"
        )
        self._attr_device_class = sdef.device_class
        self._attr_device_info = device_info

    @property
    def is_on(self) -> bool | None:
        if not self.coordinator.last_update_success:
            return None
        data = self.coordinator.data
        if data is None:
            return None
        return bool(data.get(self._key))

    async def async_turn_on(self) -> None:
        await self._api.async_set_field(self._par, "1")

    async def async_turn_off(self) -> None:
        await self._api.async_set_field(self._par, "0")
