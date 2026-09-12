"""In-memory data model and packet decoding for the heat pump."""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .const import (
    REALTIME_FLAG_KEYS,
    REALTIME_OFFSETS,
    REALTIME_U8_KEYS,
    SETPOINT_FLAG_KEYS,
    SETPOINT_OFFSETS,
)


@dataclass
class HeatpumpData:
    """Holds the latest decoded values from the heat pump.

    This object is mutated in place by the connection task and read by the
    entities. It is intentionally a single shared instance per config entry.
    """

    fields: dict[str, Any] = field(default_factory=dict)
    connected: bool = False
    last_packet_cmd: int | None = None
    last_update: datetime | None = None
    packet_count: int = 0

    def get(self, key: str, default: Any = None) -> Any:
        """Return the latest value for ``key`` or ``default``."""
        return self.fields.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Store a decoded value."""
        self.fields[key] = value


def _f32(buf: bytes, off: int) -> float | None:
    """Decode a little-endian 32-bit float at ``off`` (or None)."""
    if off + 4 <= len(buf):
        try:
            return struct.unpack("<f", buf[off : off + 4])[0]
        except struct.error:
            return None
    return None


def _u8(buf: bytes, off: int) -> int | None:
    """Decode a single unsigned byte at ``off`` (or None)."""
    if 0 <= off < len(buf):
        return buf[off]
    return None


def decode_realtime(params: bytes, store: HeatpumpData) -> None:
    """Decode a 0143 (real-time) packet payload into ``store``."""
    for key, off in REALTIME_OFFSETS.items():
        if key in REALTIME_FLAG_KEYS:
            value = _f32(params, off)
            if value is not None:
                store.set(key, value == 1.0)
        elif key in REALTIME_U8_KEYS:
            value = _u8(params, off)
            if value is not None:
                store.set(key, value)
        else:
            value = _f32(params, off)
            if value is not None:
                store.set(key, round(value, 2))


def decode_setpoints(params: bytes, store: HeatpumpData) -> None:
    """Decode a 01B3 (setpoints) packet payload into ``store``."""
    for key, off in SETPOINT_OFFSETS.items():
        if key in SETPOINT_FLAG_KEYS:
            value = _f32(params, off)
            if value is not None:
                store.set(key, value == 1.0)
        elif key == "working_mode":
            value = _f32(params, off)
            if value is not None:
                store.set(key, int(value))
        else:
            value = _f32(params, off)
            if value is not None:
                store.set(key, round(value, 2))
