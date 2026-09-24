"""Constants and entity definitions for the AmiTime Heat Pump integration."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfFrequency,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
)

try:
    from homeassistant.const import UnitOfElectricPotential
except ImportError:  # HA < 2026 called the voltage unit UnitOfVoltage
    from homeassistant.const import UnitOfVoltage as UnitOfElectricPotential

DOMAIN = "heatpump_amitime"

DEFAULT_NAME = "AmiTime Heat Pump"
DEFAULT_PORT = 8899
DEFAULT_CLOUD_URL = "https://www.myheatpump.com/a/amt/setdata/update"
MANUFACTURER_DEFAULT = "AmiTime"
MODEL_DEFAULT = "usr-c210"
SW_VERSION = "1.0.1"

CONF_DEVICE_NAME = "device_name"
CONF_MANUFACTURER = "manufacturer"
CONF_MODEL = "model"
CONF_MN = "mn"
CONF_DEVID = "devid"
CONF_COOKIE = "cookie"
CONF_CLOUD_URL = "cloud_url"

# ---------------------------------------------------------------------------
# Packet layout
#
# The Wi-Fi adapter (usr-c210) acts as a TCP server. When a client connects it
# continuously pushes packets. Each packet has a 13-byte header; byte index 12
# is the command byte and everything from index 13 onwards is the payload.
# ---------------------------------------------------------------------------
HEADER_LEN = 13
CMD_REALTIME = 0x01  # 0143 packet (real-time sensor data)
CMD_SETPOINTS = 0x02  # 01B3 packet (setpoints / settings)

# Offsets are relative to the payload (packet[HEADER_LEN:]).
REALTIME_OFFSETS: dict[str, int] = {
    # Temperatures
    "outdoor_temp": 10,
    "dhw_temp": 14,
    "cooling_water_temp": 18,
    "outlet_temp": 22,
    "inlet_temp": 26,
    "room_temp": 54,
    "outdoor_ambient": 254,
    "outdoor_coil_temp": 258,
    "gas_discharge_temp": 262,
    "gas_suction_temp": 266,
    # Electrical
    "voltage": 214,
    "current": 218,
    "compressor_freq_limit": 222,
    "compressor_freq": 226,
    # Pressure
    "low_pressure": 278,
    "high_pressure": 282,
    # Status flags (stored as float 1.0 / 0.0)
    "dhw_state": 174,
    "heating_state": 178,
    "cooling_state": 182,
    "defrost_state": 286,
    # Outdoor unit operating mode (single byte)
    "outdoor_unit_mode": 186,
}

SETPOINT_OFFSETS: dict[str, int] = {
    "unit_on_off": 2,
    "working_mode": 6,
    "delta_t_compressor_speed": 18,
    "low_noise_mode": 66,
    "dhw_set_temp": 166,
    "dhw_delta_t": 170,
    "dhw_priority_min_time": 190,
    "heating_set_temp": 246,
    "heating_delta_t": 250,
    "priority_ambient_start_temp": 306,
    "priority_heating_delta_t": 314,
    "priority_heating_working_time": 318,
    "heating_curve_enabled": 330,
    "heating_curve_ambient_temp_1": 338,
    "heating_curve_water_temp_1": 342,
    "heating_curve_ambient_temp_2": 346,
    "heating_curve_water_temp_2": 350,
    "heating_curve_ambient_temp_3": 354,
    "heating_curve_water_temp_3": 358,
    "heating_curve_ambient_temp_4": 362,
    "heating_curve_water_temp_4": 366,
    "cooling_set_temp": 378,
    "cooling_delta_t": 382,
}

# Keys that are boolean flags (decoded from a raw float of 1.0 / 0.0).
REALTIME_FLAG_KEYS = {"dhw_state", "heating_state", "cooling_state", "defrost_state"}
REALTIME_U8_KEYS = {"outdoor_unit_mode"}
SETPOINT_FLAG_KEYS = {"unit_on_off", "low_noise_mode", "heating_curve_enabled"}


# ---------------------------------------------------------------------------
# Entity definitions (data-driven so the platform modules stay small)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SensorDef:
    key: str
    name: str
    unit: str | None = None
    device_class: Any = None
    state_class: Any = None
    value_map: dict | None = None


@dataclass(frozen=True)
class BinaryDef:
    key: str
    name: str
    device_class: Any = None


@dataclass(frozen=True)
class NumberDef:
    key: str | None  # read key for the current value (None if not readable)
    par: str  # cloud API field used to send a command
    name: str
    unit: str | None = None
    min_value: float = 0.0
    max_value: float = 100.0
    step: float = 1.0
    device_class: Any = None


@dataclass(frozen=True)
class SwitchDef:
    key: str
    par: str
    name: str
    device_class: Any = None


@dataclass(frozen=True)
class SelectDef:
    key: str
    par: str
    name: str
    options: tuple[str, ...] = ()
    read_map: dict = field(default_factory=dict)  # raw value -> option
    write_map: dict = field(default_factory=dict)  # option -> par value


# Read-only sensors (always present).
READ_SENSORS: list[SensorDef] = [
    SensorDef("outdoor_temp", "Outdoor Temperature", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT),
    SensorDef("dhw_temp", "DHW Temperature", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT),
    SensorDef("cooling_water_temp", "Cooling Water Temperature", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT),
    SensorDef("outlet_temp", "Outlet Temperature", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT),
    SensorDef("inlet_temp", "Inlet Temperature", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT),
    SensorDef("room_temp", "Room Temperature", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT),
    SensorDef("outdoor_ambient", "Outdoor Ambient", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT),
    SensorDef("outdoor_coil_temp", "Outdoor Coil Temperature", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT),
    SensorDef("gas_discharge_temp", "Gas Discharge Temperature", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT),
    SensorDef("gas_suction_temp", "Gas Suction Temperature", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT),
    SensorDef("voltage", "Voltage", UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT),
    SensorDef("current", "Current", UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT),
    SensorDef("compressor_freq", "Compressor Frequency", UnitOfFrequency.HERTZ, None, SensorStateClass.MEASUREMENT),
    SensorDef("compressor_freq_limit", "Compressor Frequency Limit", UnitOfFrequency.HERTZ, None, SensorStateClass.MEASUREMENT),
    SensorDef("low_pressure", "Low Pressure", UnitOfPressure.BAR, SensorDeviceClass.PRESSURE, SensorStateClass.MEASUREMENT),
    SensorDef("high_pressure", "High Pressure", UnitOfPressure.BAR, SensorDeviceClass.PRESSURE, SensorStateClass.MEASUREMENT),
    SensorDef("delta_t_compressor_speed", "Delta T Compressor Speed", UnitOfTemperature.CELSIUS, None, SensorStateClass.MEASUREMENT),
    SensorDef("outdoor_unit_mode", "Outdoor Unit Mode", None, None, None),
    SensorDef("dhw_priority_min_time", "DHW Minimum Working Time", UnitOfTime.MINUTES, None, SensorStateClass.MEASUREMENT),
    SensorDef("priority_ambient_start_temp", "Priority Ambient Start Temp", UnitOfTemperature.CELSIUS, None, SensorStateClass.MEASUREMENT),
    SensorDef("priority_heating_delta_t", "Priority Heating Delta Temp", UnitOfTemperature.CELSIUS, None, SensorStateClass.MEASUREMENT),
    SensorDef("priority_heating_working_time", "Heating Working Time", UnitOfTime.MINUTES, None, SensorStateClass.MEASUREMENT),
]

# Read-only setpoint sensors. Only created when cloud controls are NOT
# enabled (otherwise these values are exposed through the number/select
# controls instead, to avoid duplicate entities).
SETPOINT_SENSORS: list[SensorDef] = [
    SensorDef("heating_set_temp", "Heating Set Temperature", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT),
    SensorDef("cooling_set_temp", "Cooling Set Temperature", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT),
    SensorDef("dhw_set_temp", "DHW Set Temperature", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT),
    SensorDef("heating_delta_t", "Heating Delta T", UnitOfTemperature.KELVIN, None, SensorStateClass.MEASUREMENT),
    SensorDef("cooling_delta_t", "Cooling Delta T", UnitOfTemperature.KELVIN, None, SensorStateClass.MEASUREMENT),
    SensorDef("working_mode", "Working Mode", None, None, None, value_map={1: "DHW", 2: "Heating", 3: "Cooling", 5: "Heating + DHW", 6: "Cooling + DHW"}),
]

# Read-only binary sensors (always present).
BINARY_SENSORS: list[BinaryDef] = [
    BinaryDef("dhw_state", "DHW Working State", BinarySensorDeviceClass.RUNNING),
    BinaryDef("heating_state", "Heating Working State", BinarySensorDeviceClass.RUNNING),
    BinaryDef("cooling_state", "Cooling Working State", BinarySensorDeviceClass.RUNNING),
    BinaryDef("defrost_state", "Defrost State", BinarySensorDeviceClass.RUNNING),
    BinaryDef("heating_curve_enabled", "Heating Curve Enabled", None),
]

# Read-only binary fallback for the values that become switches when cloud
# controls are enabled.
FALLBACK_BINARY: list[BinaryDef] = [
    BinaryDef("unit_on_off", "Unit On/Off", BinarySensorDeviceClass.POWER),
    BinaryDef("low_noise_mode", "Low Noise Mode", BinarySensorDeviceClass.BATTERY),
]

# Number controls (only created when cloud controls are enabled).
NUMBERS: list[NumberDef] = [
    NumberDef("heating_set_temp", "par62", "Heating Temperature", UnitOfTemperature.CELSIUS, 20, 60, 1),
    NumberDef("cooling_set_temp", "par95", "Cooling Temperature", UnitOfTemperature.CELSIUS, 10, 30, 1),
    NumberDef("dhw_set_temp", "par42", "DHW Temperature", UnitOfTemperature.CELSIUS, 30, 70, 1),
    NumberDef("heating_delta_t", "par63", "Heating Delta T", UnitOfTemperature.KELVIN, 1, 10, 1),
    NumberDef("cooling_delta_t", "par96", "Cooling Delta T", UnitOfTemperature.KELVIN, 1, 10, 1),
]

# Heating curve points. The par mapping is faithful to the original bridge.
for _i in range(1, 6):
    NUMBERS.append(
        NumberDef(
            f"heating_curve_ambient_temp_{_i}" if _i <= 4 else None,
            f"par{84 + _i}",
            f"Heating Curve Ambient {_i}",
            UnitOfTemperature.CELSIUS,
            -20,
            20,
            1,
        )
    )
    NUMBERS.append(
        NumberDef(
            f"heating_curve_water_temp_{_i}" if _i <= 4 else None,
            f"par{85 + _i}",
            f"Heating Curve Water {_i}",
            UnitOfTemperature.CELSIUS,
            20,
            70,
            1,
        )
    )

# Switch controls (only created when cloud controls are enabled).
SWITCHES: list[SwitchDef] = [
    SwitchDef("unit_on_off", "par1", "Power"),
    SwitchDef("low_noise_mode", "par17", "Low Noise Mode"),
]

# Select controls (only created when cloud controls are enabled).
SELECTS: list[SelectDef] = [
    SelectDef(
        "working_mode",
        "par2",
        "Mode",
        options=("Cooling", "DHW", "Heating"),
        read_map={1: "DHW", 2: "Heating", 3: "Cooling", 5: "Heating + DHW", 6: "Cooling + DHW"},
        write_map={"Cooling": "0", "DHW": "1", "Heating": "2"},
    ),
]
