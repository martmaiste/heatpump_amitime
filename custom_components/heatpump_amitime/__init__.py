"""The AmiTime Heat Pump integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo

from .api import HeatpumpAPI
from .const import (
    CONF_CLOUD_URL,
    CONF_COOKIE,
    CONF_DEVID,
    CONF_DEVICE_NAME,
    CONF_MANUFACTURER,
    CONF_MN,
    CONF_MODEL,
    DEFAULT_CLOUD_URL,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DOMAIN,
    MANUFACTURER_DEFAULT,
    MODEL_DEFAULT,
    SW_VERSION,
)
from .connection import HeatpumpConnection
from .coordinator import HeatpumpCoordinator
from .data import HeatpumpData

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SWITCH,
    Platform.SELECT,
]

HeatpumpConfigEntry = ConfigEntry


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the integration (no YAML configuration needed)."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: HeatpumpConfigEntry) -> bool:
    """Set up a config entry from the UI."""
    data = entry.data
    host = data[CONF_HOST]
    port = int(data.get(CONF_PORT, DEFAULT_PORT))
    device_name = data.get(CONF_DEVICE_NAME, DEFAULT_NAME)
    manufacturer = data.get(CONF_MANUFACTURER, MANUFACTURER_DEFAULT)
    model = data.get(CONF_MODEL, MODEL_DEFAULT)

    store = HeatpumpData()
    coordinator = HeatpumpCoordinator(hass, config_entry=entry, store=store)

    def on_change(success: bool) -> None:
        if success:
            coordinator.notify_success()
        else:
            coordinator.notify_failure()

    connection = HeatpumpConnection(host, port, store, on_change)

    # Optional cloud controls. Only enabled when mn, devid and a cookie are
    # all provided; otherwise the integration is read-only.
    has_cloud = bool(
        data.get(CONF_MN) and data.get(CONF_DEVID) and data.get(CONF_COOKIE)
    )
    api = None
    if has_cloud:
        api = HeatpumpAPI(
            async_get_clientsession(hass),
            data[CONF_MN],
            data[CONF_DEVID],
            data[CONF_COOKIE],
            data.get(CONF_CLOUD_URL, DEFAULT_CLOUD_URL),
        )

    device_info = DeviceInfo(
        identifiers={(DOMAIN, entry.unique_id)},
        name=device_name,
        manufacturer=manufacturer,
        model=model,
        sw_version=SW_VERSION,
    )

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "connection": connection,
        "api": api,
        "device_info": device_info,
        "has_cloud": has_cloud,
    }

    await connection.start()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.info(
        "Set up AmiTime Heat Pump at %s:%s (cloud controls: %s)",
        host,
        port,
        "enabled" if has_cloud else "disabled",
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HeatpumpConfigEntry) -> bool:
    """Unload a config entry."""
    data = hass.data[DOMAIN].get(entry.entry_id)
    if data and data.get("connection"):
        await data["connection"].stop()
    if await hass.config_entries.async_unload(entry.entry_id):
        hass.data[DOMAIN].pop(entry.entry_id, None)
        return True
    return False
