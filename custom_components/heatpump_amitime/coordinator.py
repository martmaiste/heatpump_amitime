"""Data coordinator driven by the live TCP connection."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .data import HeatpumpData

_LOGGER = logging.getLogger(__name__)


class HeatpumpCoordinator(DataUpdateCoordinator[HeatpumpData]):
    """Coordinator whose data is fed by push updates from the connection.

    The TCP connection keeps the shared :class:`HeatpumpData` store up to
    date. Instead of polling, the connection calls :meth:`notify_success` /
    :meth:`notify_failure` after each update, which refreshes the listeners
    (the entities) exactly like a normal coordinator update would.
    """

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        config_entry: ConfigEntry,
        store: HeatpumpData,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"AmiTime Heat Pump {config_entry.title}",
            update_interval=None,  # push-based, no periodic polling
        )
        self._store = store
        self.data = store
        self.last_update_success = store.connected

    def notify_success(self) -> None:
        """Mark the data as fresh and notify listeners."""
        self.async_set_updated_data(self._store)

    def notify_failure(self) -> None:
        """Mark the connection as down and notify listeners."""
        self.last_update_success = False
        self.async_update_listeners()

    async def _async_update_data(self) -> HeatpumpData:
        """Return the current store (the connection keeps it fresh)."""
        return self._store
