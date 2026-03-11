# SELFA Inverter

Home Assistant custom integration and data bridge for SELFA SFH hybrid inverters. Communicates locally with the inverter's WiFi dongle over Modbus RTU/TCP — no cloud required.

> **Disclaimer:** This integration is an independent community project and is **not associated with, endorsed by, or supported by Selfa-PV** in any way. Use at your own risk. The author takes **no responsibility for any damage** to your inverter, battery, electrical installation, or any other equipment resulting from the use of this integration.

---

## Home Assistant Integration (HACS)

### Installation via HACS

1. In HACS, go to **Integrations** → ⋮ → **Custom repositories**
2. Add `https://github.com/btaczala/selfa-inverter-query` with category **Integration**
3. Install **SELFA Inverter** from HACS
4. Restart Home Assistant
5. Go to **Settings → Devices & Services → Add Integration** → search **SELFA**
6. Enter your inverter dongle's local IP, port (`5743`), and slave address (`252`)

### What it provides

All sensors appear under a single **SELFA Inverter** device:

| Entity | Type | Unit | Description |
|--------|------|------|-------------|
| Home Power | Sensor | kW | Actual home consumption (PV + Battery − Grid) |
| Inverter AC Power | Sensor | kW | Total AC output power of the inverter |
| PV Input Power | Sensor | kW | Combined PV input |
| PV1 / PV2 Power | Sensor | kW | Per-string PV power |
| PV1 / PV2 Voltage | Sensor | V | Per-string PV voltage |
| Grid Meter Power | Sensor | kW | Positive = export, negative = import |
| Grid Frequency | Sensor | Hz | |
| L1 / L2 / L3 Voltage | Sensor | V | Per-phase grid voltage |
| L1 / L2 / L3 Current | Sensor | A | Per-phase grid current |
| Battery Power | Sensor | kW | Positive = discharging, negative = charging |
| Battery Voltage / Current | Sensor | V / A | |
| Battery SOC / SOH | Sensor | % | State of charge / health |
| BMS Temperature | Sensor | °C | |
| Inverter Temperature | Sensor | °C | |
| Daily / Total energy | Sensor | kWh | PV, grid injection/purchase, battery charge/discharge, load |
| Working Mode | Select | — | Switch operating mode — **[Expert Mode only](#expert-mode)** |
| Export Limit | Switch | — | Enable/disable grid export limiting — **[Expert Mode only](#expert-mode)** |
| Export Limit Value | Number | kW | Maximum power exported to the grid — **[Expert Mode only](#expert-mode)** |
| Import Limit | Switch | — | Enable/disable grid import limiting — **[Expert Mode only](#expert-mode)** |
| Import Limit Value | Number | kVA | Maximum power drawn from the grid — **[Expert Mode only](#expert-mode)** |

### Working Modes

The inverter supports several operating modes, selectable via the app or via Home Assistant in [Expert Mode](#expert-mode):

| Mode | Description |
|------|-------------|
| **General** | Default on-grid mode. Maximises PV self-consumption. Battery charges from surplus PV and discharges to cover home load. Grid used as backup. |
| **Economic** | Time-of-use optimisation. Battery charges during cheap-rate periods and discharges during peak-rate periods to minimise grid cost. |
| **UPS** | Priority is to keep the battery charged. Battery discharges only during a grid outage to power backup loads. |
| **Off-grid** | Inverter disconnects from the grid entirely. Home is powered only from PV and battery. |

### Expert Mode

Expert mode unlocks advanced control entities that write directly to the inverter:

| Entity | Type | Description |
|--------|------|-------------|
| Working Mode | Select | Switch operating mode (General, Economic, UPS, Off-grid) |
| Export Limit | Switch + Number | Enable/disable and set the maximum power exported to the grid (kW) |
| Import Limit | Switch + Number | Enable/disable and set the maximum power drawn from the grid (kVA) |

> **Warning:** These controls write directly to the inverter over Modbus. Incorrect settings may affect your installation, battery, or grid connection. Only enable Expert Mode if you understand what each setting does. The author takes no responsibility for any resulting damage.

Changes made in the SELFA app are reflected in Home Assistant automatically within the next poll cycle (default: 5 seconds).

To enable:
1. Go to **Settings → Devices & Services → SELFA Inverter → Configure**
2. Toggle **Expert Mode** on and click **Submit**
3. The integration reloads and the expert entities become available under the SELFA Inverter device

To disable, repeat the steps above and toggle Expert Mode off. The entities will be removed on reload.

### Protocol

The dongle communicates over **Modbus RTU over TCP** (raw RTU framing with CRC, not standard Modbus TCP). Default: `192.168.1.1:5743`, slave address `252` (`0xFC`).

---
