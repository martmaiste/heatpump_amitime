#!/usr/bin/env python3
"""Command-line test tool for the AmiTime Heat Pump integration.

This connects to the heat pump's Wi-Fi adapter (usr-c210) over a local TCP
socket and decodes the pushed packets using the *exact same* decoding logic
as the Home Assistant custom integration (``custom_components/heatpump_amitime``).
It is a quick way to verify that your adapter is reachable and streaming data
without needing Home Assistant to be running.

It only uses the Python standard library. The integration's own ``const.py``
(offsets) and ``data.py`` (decoders) are loaded directly, so what you see here
is exactly what the integration will report.

Examples
--------
Quick connectivity check (exits after one of each packet type):

    python3 test_heatpump.py --host 192.168.0.50 --once

Monitor (default: keeps running until Ctrl+C):

    python3 test_heatpump.py --host 192.168.0.50

Monitor for 60 seconds (Ctrl+C to stop early):

    python3 test_heatpump.py --host 192.168.0.50 --port 8899 --duration 60

Machine-readable output (one JSON line per packet):

    python3 test_heatpump.py --host 192.168.0.50 --json

Show every decoded field plus unknown packet types:

    python3 test_heatpump.py --host 192.168.0.50 --verbose
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import socket
import sys
import time
import types

MODE_NAMES = {1: "DHW", 2: "Heating", 3: "Cooling", 5: "Heating + DHW"}

# ---------------------------------------------------------------------------
# Field display specs: (store key, short label)
# ---------------------------------------------------------------------------
RT_TEMPS = [
    ("outdoor_temp", "outdoor"),
    ("dhw_temp", "dhw"),
    ("cooling_water_temp", "cool_water"),
    ("outlet_temp", "outlet"),
    ("inlet_temp", "inlet"),
    ("room_temp", "room"),
    ("outdoor_ambient", "ambient"),
    ("outdoor_coil_temp", "coil"),
    ("gas_discharge_temp", "gas_disch"),
    ("gas_suction_temp", "gas_suct"),
]
RT_ELEC = [
    ("voltage", "V"),
    ("current", "A"),
    ("compressor_freq", "freq"),
    ("compressor_freq_limit", "freq_lim"),
]
RT_PRESS = [("low_pressure", "low"), ("high_pressure", "high")]
RT_STATES = [
    ("dhw_state", "dhw"),
    ("heating_state", "heating"),
    ("cooling_state", "cooling"),
    ("defrost_state", "defrost"),
]

SP_SETS = [
    ("heating_set_temp", "heating"),
    ("cooling_set_temp", "cooling"),
    ("dhw_set_temp", "dhw"),
]
SP_DELTA = [
    ("delta_t_compressor_speed", "compressor"),
    ("heating_delta_t", "heating"),
    ("cooling_delta_t", "cooling"),
    ("dhw_delta_t", "dhw"),
]
SP_CURVE = [
    ("heating_curve_ambient_temp_1", "amb1"),
    ("heating_curve_water_temp_1", "water1"),
    ("heating_curve_ambient_temp_2", "amb2"),
    ("heating_curve_water_temp_2", "water2"),
    ("heating_curve_ambient_temp_3", "amb3"),
    ("heating_curve_water_temp_3", "water3"),
    ("heating_curve_ambient_temp_4", "amb4"),
    ("heating_curve_water_temp_4", "water4"),
]
SP_PRIO = [
    ("dhw_priority_min_time", "dhw_min"),
    ("priority_ambient_start_temp", "amb_start"),
    ("priority_heating_delta_t", "heat_delta"),
    ("priority_heating_working_time", "heat_time"),
]


# ---------------------------------------------------------------------------
# Load the integration's const.py / data.py without running its __init__.py
# (which needs the full Home Assistant runtime).
# ---------------------------------------------------------------------------
def _install_ha_stubs() -> None:
    """Provide the minimal homeassistant names that const.py imports."""

    def mod(name: str) -> types.ModuleType:
        m = types.ModuleType(name)
        sys.modules[name] = m
        return m

    ha = mod("homeassistant")

    const = mod("homeassistant.const")
    for name, attrs in [
        ("UnitOfTemperature", {"CELSIUS": "°C", "KELVIN": "K", "FAHRENHEIT": "°F"}),
        ("UnitOfVoltage", {"VOLT": "V"}),
        ("UnitOfElectricCurrent", {"AMPERE": "A"}),
        ("UnitOfFrequency", {"HERTZ": "Hz"}),
        ("UnitOfPressure", {"BAR": "bar"}),
        ("UnitOfTime", {"MINUTES": "min", "SECONDS": "s", "HOURS": "h"}),
    ]:
        setattr(const, name, type(name, (), attrs))
    ha.const = const

    components = mod("homeassistant.components")
    ha.components = components

    sensor = mod("homeassistant.components.sensor")
    sensor.SensorDeviceClass = type(
        "SensorDeviceClass",
        (),
        {
            "TEMPERATURE": "temperature",
            "VOLTAGE": "voltage",
            "CURRENT": "current",
            "PRESSURE": "pressure",
            "POWER": "power",
        },
    )
    sensor.SensorStateClass = type("SensorStateClass", (), {"MEASUREMENT": "measurement"})
    components.sensor = sensor

    binary_sensor = mod("homeassistant.components.binary_sensor")
    binary_sensor.BinarySensorDeviceClass = type(
        "BinarySensorDeviceClass",
        (),
        {
            "HEAT": "heat",
            "COOL": "cool",
            "RUNNING": "running",
            "POWER": "power",
            "BATTERY": "battery",
        },
    )
    components.binary_sensor = binary_sensor


def _ensure_ha() -> None:
    """Use the real homeassistant package when present, else install stubs."""
    try:
        import homeassistant  # noqa: F401
    except ImportError:
        _install_ha_stubs()


def _load_integration(integration_dir: str) -> tuple:
    """Import const.py and data.py as a throw-away package (no __init__ run)."""
    _ensure_ha()
    if not os.path.isdir(integration_dir):
        raise FileNotFoundError(
            f"integration directory not found: {integration_dir}\n"
            "Pass --integration-dir to point at custom_components/heatpump_amitime"
        )
    pkg_name = "_heatpump_amitime_under_test"
    if pkg_name not in sys.modules:
        pkg = types.ModuleType(pkg_name)
        pkg.__path__ = [integration_dir]
        sys.modules[pkg_name] = pkg
    const = importlib.import_module(f"{pkg_name}.const")
    data = importlib.import_module(f"{pkg_name}.data")
    return const, data


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------
def _pair(items, store) -> str:
    parts = []
    for key, label in items:
        value = store.get(key)
        if value is None or isinstance(value, bool):
            continue
        parts.append(f"{label}={value:g}")
    return "  ".join(parts)


def _flag(items, store) -> str:
    parts = []
    for key, label in items:
        value = store.get(key)
        if isinstance(value, bool):
            parts.append(f"{label}={'ON' if value else 'OFF'}")
    return "  ".join(parts)


def _block(title: str, packet_no: int, raw_len: int, lines, verbose: bool, store) -> str:
    out = [f"[{title}] packet #{packet_no} ({raw_len} bytes)"]
    for label, content in lines:
        if content:
            out.append(f"    {label:<10} {content}")
    if verbose:
        out.append("    all fields:")
        for key in sorted(store.fields):
            out.append(f"      {key} = {store.fields[key]}")
    return "\n".join(out)


def format_realtime(store, packet_no: int, raw_len: int, verbose: bool) -> str:
    states = _flag(RT_STATES, store)
    mode = store.get("outdoor_unit_mode")
    if mode is not None:
        states = (states + "  " if states else "") + f"outdoor_mode={mode:g}"
    lines = [
        ("temps", _pair(RT_TEMPS, store)),
        ("electrical", _pair(RT_ELEC, store)),
        ("pressure", _pair(RT_PRESS, store)),
        ("states", states),
    ]
    return _block("0143 realtime", packet_no, raw_len, lines, verbose, store)


def format_setpoints(store, packet_no: int, raw_len: int, verbose: bool) -> str:
    unit = _flag(
        [("unit_on_off", "on"), ("low_noise_mode", "low_noise"), ("heating_curve_enabled", "curve")],
        store,
    )
    mode = store.get("working_mode")
    if mode is not None:
        unit = (unit + "  " if unit else "") + f"mode={MODE_NAMES.get(mode, mode)}"
    lines = [
        ("unit", unit),
        ("setpoints", _pair(SP_SETS, store)),
        ("delta T", _pair(SP_DELTA, store)),
        ("curve", _pair(SP_CURVE, store)),
        ("priority", _pair(SP_PRIO, store)),
    ]
    return _block("01B3 setpoints", packet_no, raw_len, lines, verbose, store)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    default_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "custom_components",
        "heatpump_amitime",
    )
    parser = argparse.ArgumentParser(
        description="Test the AmiTime heat pump adapter connection from the command line.",
        epilog="Exit codes: 0 = data received, 1 = could not connect, 2 = connected but no data.",
    )
    parser.add_argument("--host", required=True, help="Adapter IP address")
    parser.add_argument("--port", type=int, default=8899, help="Adapter TCP port (default 8899)")
    parser.add_argument(
        "--duration",
        type=float,
        default=0,
        help="Seconds to listen. Default 0 = keep running until Ctrl+C.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Exit after receiving one 0143 and one 01B3 packet (quick check)",
    )
    parser.add_argument(
        "--timeout", type=float, default=10, help="Connect timeout in seconds (default 10)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Emit one JSON line per packet (diagnostics go to stderr)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print every decoded field and unknown packet types",
    )
    parser.add_argument(
        "--integration-dir",
        default=default_dir,
        help="Path to custom_components/heatpump_amitime (default: auto-detected)",
    )
    return parser


def log(msg: str, as_json: bool) -> None:
    print(msg, file=sys.stderr if as_json else sys.stdout, flush=True)


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    try:
        const, data_mod = _load_integration(args.integration_dir)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print_or_err = lambda msg: log(msg, args.as_json)  # noqa: E731

    print_or_err(f"Connecting to {args.host}:{args.port} ...")
    try:
        sock = socket.create_connection((args.host, args.port), timeout=args.timeout)
    except (OSError, socket.timeout) as exc:
        print_or_err(f"ERROR: could not connect to {args.host}:{args.port}: {exc}")
        print_or_err(
            "Hint: the adapter must be configured as a TCP server (socket A) on this port."
        )
        return 1

    if args.duration <= 0:
        listen_desc = "Listening (Ctrl+C to stop)"
    else:
        listen_desc = f"Listening for up to {args.duration:g}s (Ctrl+C to stop)"
    print_or_err(
        f"Connected. {listen_desc}"
        + ("  [JSON mode]" if args.as_json else "")
    )

    store = data_mod.HeatpumpData()
    counts = {"0143": 0, "01B3": 0, "other": 0}
    seen = {"0143": False, "01B3": False}
    packet_no = 0
    start = time.monotonic()
    deadline = None if args.duration <= 0 else start + args.duration
    sock.settimeout(1.0)  # stay responsive to Ctrl+C / duration

    try:
        while True:
            if args.once and seen["0143"] and seen["01B3"]:
                break
            if deadline is not None and time.monotonic() >= deadline:
                break

            try:
                buf = sock.recv(1024)
            except socket.timeout:
                continue
            except (ConnectionResetError, BrokenPipeError, OSError) as exc:
                print_or_err(f"connection lost: {exc}")
                break
            if not buf:
                print_or_err("connection closed by peer")
                break
            if len(buf) < const.HEADER_LEN:
                continue

            cmd = buf[const.HEADER_LEN - 1]
            params = buf[const.HEADER_LEN :]
            packet_no += 1

            if cmd == const.CMD_REALTIME:
                data_mod.decode_realtime(params, store)
                counts["0143"] += 1
                seen["0143"] = True
                if args.as_json:
                    print(_json_line(packet_no, "0143", store), flush=True)
                else:
                    print(format_realtime(store, packet_no, len(buf), args.verbose), flush=True)
            elif cmd == const.CMD_SETPOINTS:
                data_mod.decode_setpoints(params, store)
                counts["01B3"] += 1
                seen["01B3"] = True
                if args.as_json:
                    print(_json_line(packet_no, "01B3", store), flush=True)
                else:
                    print(format_setpoints(store, packet_no, len(buf), args.verbose), flush=True)
            else:
                counts["other"] += 1
                if args.verbose:
                    print_or_err(f"unknown packet 0x{cmd:02X} ({len(buf)} bytes)")
    except KeyboardInterrupt:
        print_or_err("\nstopped (Ctrl+C)")
    finally:
        try:
            sock.close()
        except OSError:
            pass

    elapsed = time.monotonic() - start
    got_data = counts["0143"] + counts["01B3"] > 0
    if not args.as_json:
        print("\n" + "=" * 46)
        print(f"Summary  ({elapsed:.1f}s)")
        print(f"  0143 realtime packets : {counts['0143']}")
        print(f"  01B3 setpoint packets : {counts['01B3']}")
        print(f"  other/unknown packets : {counts['other']}")
        if got_data:
            print("  Result: OK — adapter is streaming data.")
        else:
            print("  Result: no decoded data received.")
            print("  Check the IP/port, and that the adapter is a TCP server (socket A).")

    if not got_data:
        return 2
    return 0


def _json_line(packet_no: int, ptype: str, store) -> str:
    return json.dumps(
        {
            "ts": round(time.time(), 3),
            "packet": packet_no,
            "type": ptype,
            "fields": dict(store.fields),
        },
        ensure_ascii=False,
    )


if __name__ == "__main__":
    sys.exit(main())
