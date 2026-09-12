"""Select platform (mode control) for the AmiTime Heat Pump integration."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SELECTS, SelectDef


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
            HeatpumpSelect(coordinator, api, sdef, device_info)
            for sdef in SELECTS
        ]
    )


class HeatpumpSelect(CoordinatorEntity, SelectEntity):
    """The working-mode select. Shows the live mode and sends to the cloud."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        coordinator,
        api,
        sdef: SelectDef,
        device_info: DeviceInfo,
    ) -> None:
        super().__init__(coordinator)
        self._api = api
        self._par = sdef.par
        self._key = sdef.key
        self._read_map = sdef.read_map
        self._write_map = sdef.write_map
        self._attr_name = sdef.name
        self._attr_unique_id = (
            f"{coordinator.config_entry.unique_id}_{sdef.par}"
        )
        self._attr_options = list(sdef.options)
        self._attr_device_info = device_info

    @property
    def current_option(self) -> str | None:
        if not self.coordinator.last_update_success:
            return None
        data = self.coordinator.data
        if data is None:
            return None
        raw = data.get(self._key)
        if raw is None:
            return None
        return self._read_map.get(raw)

    async def async_select_option(self, option: str) -> None:
        await self._api.async_set_field(self._par, self._write_map[option])
