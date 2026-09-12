"""Config and options flow for the AmiTime Heat Pump integration."""
from __future__ import annotations

import asyncio
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

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
    HEADER_LEN,
    MANUFACTURER_DEFAULT,
    MODEL_DEFAULT,
)


class HeatpumpConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow for adding a heat pump."""

    VERSION = 1

    def _schema(self, data: dict[str, Any] | None = None) -> vol.Schema:
        data = data or {}
        return vol.Schema(
            {
                vol.Required(CONF_HOST, default=data.get(CONF_HOST)): str,
                vol.Required(
                    CONF_PORT, default=data.get(CONF_PORT, DEFAULT_PORT)
                ): vol.Coerce(int),
                vol.Optional(
                    CONF_DEVICE_NAME, default=data.get(CONF_DEVICE_NAME, DEFAULT_NAME)
                ): str,
                vol.Optional(
                    CONF_MANUFACTURER,
                    default=data.get(CONF_MANUFACTURER, MANUFACTURER_DEFAULT),
                ): str,
                vol.Optional(
                    CONF_MODEL, default=data.get(CONF_MODEL, MODEL_DEFAULT)
                ): str,
                vol.Optional(CONF_MN, default=data.get(CONF_MN, "")): str,
                vol.Optional(CONF_DEVID, default=data.get(CONF_DEVID, "")): str,
                vol.Optional(CONF_COOKIE, default=data.get(CONF_COOKIE, "")): str,
                vol.Optional(
                    CONF_CLOUD_URL, default=data.get(CONF_CLOUD_URL, DEFAULT_CLOUD_URL)
                ): str,
            }
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            port = int(user_input[CONF_PORT])
            if not await _test_connection(self.hass, host, port):
                errors["base"] = "cannot_connect"
            else:
                unique_id = f"amitime_{host}_{port}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input.get(CONF_DEVICE_NAME, DEFAULT_NAME),
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self._schema(),
            errors=errors,
        )


class HeatpumpOptionsFlow(OptionsFlow):
    """Handle the options flow (cloud control credentials)."""

    def _schema(self, data: dict[str, Any]) -> vol.Schema:
        return vol.Schema(
            {
                vol.Optional(CONF_MN, default=data.get(CONF_MN, "")): str,
                vol.Optional(CONF_DEVID, default=data.get(CONF_DEVID, "")): str,
                vol.Optional(CONF_COOKIE, default=data.get(CONF_COOKIE, "")): str,
                vol.Optional(
                    CONF_CLOUD_URL, default=data.get(CONF_CLOUD_URL, DEFAULT_CLOUD_URL)
                ): str,
            }
        )

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            entry = self.config_entry
            updated = dict(entry.data)
            updated[CONF_MN] = user_input.get(CONF_MN, "")
            updated[CONF_DEVID] = user_input.get(CONF_DEVID, "")
            updated[CONF_COOKIE] = user_input.get(CONF_COOKIE, "")
            updated[CONF_CLOUD_URL] = user_input.get(
                CONF_CLOUD_URL, DEFAULT_CLOUD_URL
            )
            entry.async_update_entry(data=updated)
            # Toggling the cloud credentials changes which entities exist, so
            # reload the entry to apply the change.
            await self.hass.config_entries.async_reload(entry.entry_id)
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="init",
            data_schema=self._schema(dict(self.config_entry.data)),
        )


async def _test_connection(hass: HomeAssistant, host: str, port: int) -> bool:
    """Try to connect to the adapter and read a packet header."""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=5
        )
    except Exception:  # noqa: BLE001
        return False
    try:
        data = await asyncio.wait_for(reader.read(HEADER_LEN), timeout=5)
        return len(data) >= HEADER_LEN
    except Exception:  # noqa: BLE001
        return False
    finally:
        writer.close()
