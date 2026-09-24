"""Asynchronous TCP connection to the heat pump Wi-Fi adapter."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Callable

from .const import CMD_REALTIME, CMD_SETPOINTS, HEADER_LEN
from .data import HeatpumpData, decode_realtime, decode_setpoints

_LOGGER = logging.getLogger(__name__)

# At most this often do we push a state update, to avoid hammering HA with
# state writes if the adapter emits packets very frequently.
_MIN_NOTIFY_INTERVAL = 0.5

# The adapter streams packets continuously and re-sends the setpoint (01B3)
# packet immediately when setpoints change. If no packet arrives for this
# long, the link is dead (adapter reboot / reconfiguration / network
# hiccup) - reconnect instead of waiting on a half-open socket forever.
_READ_TIMEOUT = 120.0


class HeatpumpConnection:
    """Maintains the persistent TCP connection and decodes incoming packets.

    The adapter is a push-based server: once connected it streams packets
    continuously, so there is nothing to poll. This task reconnects with
    exponential backoff if the connection drops or goes silent.
    """

    def __init__(
        self,
        host: str,
        port: int,
        store: HeatpumpData,
        on_change: Callable[[bool], None],
    ) -> None:
        self._host = host
        self._port = port
        self._store = store
        self._on_change = on_change
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._last_notify = 0.0

    async def start(self) -> None:
        """Start the background connection task (no-op if already running)."""
        if self._task is not None:
            return
        self._stop.clear()
        self._task = asyncio.create_task(
            self._run(), name=f"heatpump_amitime_{self._host}_{self._port}"
        )

    async def stop(self) -> None:
        """Stop the task and close the connection."""
        self._stop.set()
        self._close_writer()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
            self._task = None

    def _close_writer(self) -> None:
        if self._writer is not None:
            try:
                self._writer.close()
            except Exception:  # noqa: BLE001
                pass
            self._writer = None
            self._reader = None

    def _notify(self, success: bool, force: bool = False) -> None:
        now = time.monotonic()
        if not force and (now - self._last_notify) < _MIN_NOTIFY_INTERVAL:
            return
        self._last_notify = now
        self._on_change(success)

    async def _run(self) -> None:
        backoff = 2
        while not self._stop.is_set():
            try:
                self._reader, self._writer = await asyncio.wait_for(
                    asyncio.open_connection(self._host, self._port), timeout=15
                )
                self._store.connected = True
                backoff = 2
                _LOGGER.info(
                    "Connected to heat pump adapter %s:%s", self._host, self._port
                )
                self._notify(True, force=True)
                while not self._stop.is_set():
                    try:
                        data = await asyncio.wait_for(
                            self._reader.read(1024), timeout=_READ_TIMEOUT
                        )
                    except asyncio.TimeoutError as exc:
                        raise ConnectionError(
                            f"no data from adapter for {_READ_TIMEOUT:.0f}s"
                        ) from exc
                    if not data:
                        raise ConnectionError("connection closed by peer")
                    if len(data) < HEADER_LEN:
                        continue
                    cmd = data[12]
                    params = data[13:]
                    if cmd == CMD_REALTIME:
                        decode_realtime(params, self._store)
                        self._store.last_packet_cmd = CMD_REALTIME
                    elif cmd == CMD_SETPOINTS:
                        decode_setpoints(params, self._store)
                        self._store.last_packet_cmd = CMD_SETPOINTS
                    else:
                        _LOGGER.debug("Ignoring packet type 0x%02X", cmd)
                        continue
                    self._store.packet_count += 1
                    self._notify(True)
            except asyncio.CancelledError:
                self._store.connected = False
                self._notify(False, force=True)
                raise
            except Exception as exc:  # noqa: BLE001
                self._store.connected = False
                _LOGGER.warning(
                    "Heat pump connection error: %s (retry in %ss)", exc, backoff
                )
                self._notify(False, force=True)
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=backoff)
                except asyncio.TimeoutError:
                    pass
                backoff = min(backoff * 2, 60)
            finally:
                self._close_writer()
