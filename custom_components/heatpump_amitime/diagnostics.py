"""Diagnostics support for the AmiTime Heat Pump integration."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry (cookie is redacted)."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    store = coordinator.data
    device_info = data["device_info"]

    # Redact the session cookie before exposing the entry data.
    safe_entry = dict(entry.data)
    cookie = safe_entry.get("cookie")
    if cookie:
        safe_entry["cookie"] = cookie[:6] + "***"

    return {
        "entry": safe_entry,
        "has_cloud": data["has_cloud"],
        "device": {
            "name": device_info.name,
            "manufacturer": device_info.manufacturer,
            "model": device_info.model,
            "sw_version": device_info.sw_version,
        },
        "connection": {
            "connected": bool(store.connected) if store else False,
            "last_update_success": coordinator.last_update_success,
            "packet_count": store.packet_count if store else 0,
            "last_packet_cmd": store.last_packet_cmd if store else None,
            "last_update": (
                store.last_update.isoformat()
                if store and store.last_update
                else None
            ),
        },
        "fields": dict(store.fields) if store else {},
    }
