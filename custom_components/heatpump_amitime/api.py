"""Client for the optional vendor cloud API used to send control commands."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)


def parse_cookie(cookie_str: str) -> dict[str, str]:
    """Parse a raw ``key=value; key=value`` cookie string into a dict."""
    cookies: dict[str, str] = {}
    if not cookie_str:
        return cookies
    for part in cookie_str.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        key, value = part.split("=", 1)
        cookies[key.strip()] = value.strip()
    return cookies


class HeatpumpAPI:
    """Sends write commands to the vendor cloud API.

    This mirrors the write path of the original AppDaemon bridge: a POST to
    the cloud ``setdata/update`` endpoint carrying the field name/value plus
    the account ``mn``/``devid`` and the session cookies.
    """

    def __init__(
        self,
        session,
        mn: str,
        devid: str,
        cookie: str,
        cloud_url: str,
    ) -> None:
        self._session = session
        self._mn = mn
        self._devid = devid
        self._cookies = parse_cookie(cookie)
        self._cloud_url = cloud_url

    async def async_set_field(self, par: str, value: Any) -> None:
        """Send a single field/value pair to the cloud API."""
        payload = {
            "id": "",
            "mn": self._mn,
            "devid": self._devid,
            par: str(value),
            "fieldName": par,
            "fieldValue": str(value),
        }
        try:
            resp = await self._session.post(
                self._cloud_url,
                data=payload,
                cookies=self._cookies,
                timeout=aiohttp.ClientTimeout(total=10),
            )
            resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            raise HomeAssistantError(
                f"Cloud API request for '{par}' failed: {exc}"
            ) from exc
        try:
            res = await resp.json()
        except Exception:  # noqa: BLE001
            res = {}
        if str(res.get("result", "")).lower() != "true":
            raise HomeAssistantError(f"Cloud API rejected '{par}': {res}")
        _LOGGER.debug("Cloud API accepted %s=%s", par, value)
