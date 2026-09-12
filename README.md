# AmiTime Heat Pump — Home Assistant Custom Integration

A native Home Assistant custom integration that reads data **directly** from an
AmiTime / compatible Wi‑Fi adapter (e.g. the **usr‑c210**) over a local TCP
socket — **no AppDaemon and no MQTT broker required**.

- Opens a persistent TCP connection to the adapter (default port `8899`).
- Decodes the pushed packets:
  - `0x01` → **0143** real‑time sensor data
  - `0x02` → **01B3** setpoints / settings
- Exposes the decoded values as native Home Assistant entities (sensors, binary
  sensors).
- Optionally sends **controls** (power, mode, setpoints, delta‑T, heating curve)
  to the vendor cloud API when you provide the session credentials.

> ⚠️ **Disclaimer** — You are responsible for your own account/cookie usage and
> equipment. Use at your own risk. Not affiliated with any manufacturer.

## Credits & Acknowledgements

This integration is a native Home Assistant port of the original AmiTime heat
pump bridge. The protocol details — packet structure, field offsets, and the
cloud API — were reverse‑engineered and documented in the original project by
**AndresL71**: <https://github.com/AndresL71/AmiTime-HeatPump-HA>.

Thanks to AndresL71 for the original work that made this possible.

---

## What you get

**Always (read‑only, no credentials needed):**

| Type | Entities |
|------|----------|
| Temperature sensors | Outdoor, DHW, Cooling water, Outlet, Inlet, Room, Outdoor ambient, Outdoor coil, Gas discharge, Gas suction |
| Electrical sensors | Voltage, Current, Compressor frequency, Compressor frequency limit |
| Pressure sensors | Low pressure, High pressure |
| Misc sensors | Delta‑T compressor speed, Outdoor unit mode, Priority / working‑time settings |
| Binary sensors | DHW working, Heating working, Cooling working, Defrost, Heating‑curve enabled |

**Additionally, when cloud credentials are set (controls):**

| Type | Entities |
|------|----------|
| Switch | Power, Low‑noise mode |
| Select | Mode (Cooling / DHW / Heating) |
| Number | Heating / Cooling / DHW temperature, Heating / Cooling delta‑T, Heating‑curve ambient & water points |

When cloud credentials are **not** set, the setpoints, delta‑T and mode are
still exposed — as read‑only sensors / binary sensors instead of controls — so
you never lose data.

---

## Prerequisites

- The heat pump's Wi‑Fi adapter configured as a **TCP server** (socket A) on a
  known port (default `8899`).
- Home Assistant (2024.8 or newer recommended).
- For controls only: a valid **raw session cookie** plus the `mn` and `devid`
  values from your cloud website account.

---

## Installation

### Option A — HACS (recommended)

1. Add this repository as a HACS *repository*.
2. Open the integration in HACS and click **Download**.
3. Restart Home Assistant.

### Option B — Manual

1. Copy the `custom_components/heatpump_amitime/` folder into your HA config:
   ```
   /config/custom_components/heatpump_amitime/
   ```
2. Restart Home Assistant.

### Configure

1. **Settings → Devices & Services → Add Integration → "AmiTime Heat Pump"**.
2. Enter the adapter **IP** and **port** (the form tests the connection first).
3. Optionally set device name / manufacturer / model.
4. Optionally fill in the **cloud** fields (`mn`, `devid`, `cookie`) to enable
   the control entities. Leave them empty for a read‑only integration.
5. Submit. The device and its sensors appear.

> The connection is resilient: if the adapter drops, the integration
> automatically reconnects with exponential backoff and entities show as
> *unavailable* while offline.

### Enabling / changing controls later

Use **Settings → Devices & Services → (your device) → Configure** to add or
remove the cloud credentials at any time. The entry reloads automatically.

---

## Testing the connection from the command line

`test_heatpump.py` (repo root) connects to the adapter and decodes packets
using the **same code** as the integration — a fast way to verify your adapter
is reachable and streaming before/after installing. It only needs Python 3 and
the standard library (no Home Assistant required).

```bash
# quick connectivity check (exits after one of each packet type)
python3 test_heatpump.py --host 192.168.0.50 --once

# monitor (default: keeps running until Ctrl+C)
python3 test_heatpump.py --host 192.168.0.50

# monitor for 60 seconds (Ctrl+C to stop early)
python3 test_heatpump.py --host 192.168.0.50 --port 8899 --duration 60

# machine-readable (one JSON line per packet, for scripting)
python3 test_heatpump.py --host 192.168.0.50 --json

# show every decoded field and unknown packet types
python3 test_heatpump.py --host 192.168.0.50 --verbose
```

Exit codes: `0` = data received, `1` = could not connect, `2` = connected but
no data. If it connects but shows no values, confirm the adapter is set as a
**TCP server** on the given port (socket A) and that you're on the right subnet.

---

## Configuration reference

| Field | Required | Description |
|-------|----------|-------------|
| `host` | yes | Adapter IP address |
| `port` | no (default `8899`) | Adapter TCP port |
| `device_name` | no | Name shown in HA |
| `manufacturer` | no (default `AmiTime`) | Device manufacturer |
| `model` | no (default `usr-c210`) | Device model |
| `mn` | for controls | Cloud account `mn` (from your cookie) |
| `devid` | for controls | Cloud device id |
| `cookie` | for controls | Raw session cookie string (`k=v; k=v`) |
| `cloud_url` | no | Cloud API endpoint (default `https://www.myheatpump.com/a/amt/setdata/update`) |

---

## How it works

```
adapter --TCP--> Home Assistant (custom_components/heatpump_amitime)
```

- Entities are created **natively** (no MQTT discovery / state topics).
- The TCP reader runs as an **async task** inside HA (no extra process/thread).
- Data flows through a `DataUpdateCoordinator`; entities update when packets
  arrive (push‑based, with a light throttle to avoid excessive state writes).
- Controls call the cloud API directly via HA's `aiohttp` client.

## Notes

- The **heating‑curve** number entities reuse the `par` mapping from the
  original bridge (ambient `par85`–`par89`, water `par86`–`par90`). If your
  unit behaves unexpectedly on the curve, verify/adjust those `par` numbers in
  `const.py`.
- Only the first **4** heating‑curve points are read back from the `01B3`
  packet (as in the original); all **5** are controllable.
- The session cookie is stored with the config entry (locally, in
  `.storage/core.config_entries`). Treat it like any other credential.
- **Diagnostics**: from the device page use *⋮ → Download diagnostics* to get
  the connection status, packet count and all decoded field values (the
  cookie is redacted) — useful for confirming the socket is receiving data.
- **Working modes** (`Working Mode` sensor / `Mode` select): `1` = DHW,
  `2` = Heating, `3` = Cooling, `5` = Heating + DHW (combined, set from the
  physical panel). Mode `5` is *shown* but is not a selectable option in HA —
  the select offers only Cooling / DHW / Heating (written as `par2` 0/1/2).

## Repository layout

```
.
├── README.md
├── LICENSE                          # MIT
├── test_heatpump.py                 # standalone connection test tool
└── custom_components/
    └── heatpump_amitime/
        ├── __init__.py              # setup/unload, wires connection + coordinator
        ├── config_flow.py           # UI config + options flow
        ├── const.py                 # offsets & entity definitions
        ├── data.py                  # HeatpumpData + packet decoders
        ├── connection.py            # async TCP reader (reconnect w/ backoff)
        ├── coordinator.py           # DataUpdateCoordinator fed by the connection
        ├── api.py                   # optional cloud API client
        ├── diagnostics.py           # diagnostics export (cookie redacted)
        ├── sensor.py                # temperature/electrical/pressure sensors
        ├── binary_sensor.py         # state flags
        ├── number.py                # setpoint controls (cloud)
        ├── switch.py                # power/low-noise controls (cloud)
        ├── select.py                # mode control (cloud)
        ├── manifest.json
        ├── strings.json
        └── translations/
            └── en.json
```

## License

Released under the [MIT License](./LICENSE).

Protocol knowledge was reverse‑engineered from the original project by
[AndresL71](https://github.com/AndresL71/AmiTime-HeatPump-HA) — see the
[Credits & Acknowledgements](#credits--acknowledgements) section.
