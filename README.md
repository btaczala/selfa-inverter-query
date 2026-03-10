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

| Sensor | Unit | Description |
|--------|------|-------------|
| Home Power | kW | Actual home consumption (PV + Battery − Grid) |
| Inverter AC Power | kW | Total AC output power of the inverter |
| PV Input Power | kW | Combined PV input |
| PV1 / PV2 Power | kW | Per-string PV power |
| PV1 / PV2 Voltage | V | Per-string PV voltage |
| Grid Meter Power | kW | Positive = export, negative = import |
| Grid Frequency | Hz | |
| L1 / L2 / L3 Voltage | V | Per-phase grid voltage |
| L1 / L2 / L3 Current | A | Per-phase grid current |
| Battery Power | kW | Positive = discharging, negative = charging |
| Battery Voltage / Current | V / A | |
| Battery SOC / SOH | % | State of charge / health |
| BMS Temperature | °C | |
| Inverter Temperature | °C | |
| Daily / Total energy | kWh | PV, grid injection/purchase, battery charge/discharge, load |

### Working Modes

The inverter supports several operating modes, selectable via the app or via Home Assistant in [Expert Mode](#expert-mode):

| Mode | Description |
|------|-------------|
| **General** | Default on-grid mode. Maximises PV self-consumption. Battery charges from surplus PV and discharges to cover home load. Grid used as backup. |
| **Economic** | Time-of-use optimisation. Battery charges during cheap-rate periods and discharges during peak-rate periods to minimise grid cost. |
| **UPS** | Priority is to keep the battery charged. Battery discharges only during a grid outage to power backup loads. |
| **Off-grid** | Inverter disconnects from the grid entirely. Home is powered only from PV and battery. |

### Expert Mode

Expert mode unlocks a **Working Mode** select entity in Home Assistant that lets you switch the inverter's operating mode directly from HA (e.g. via automations or the dashboard).

> **Warning:** Changing the working mode writes directly to the inverter over Modbus. Selecting an incorrect mode (e.g. Off-grid while the grid is connected) may affect your installation. Only enable this if you understand what each mode does.

To enable:
1. Go to **Settings → Devices & Services → SELFA Inverter → Configure**
2. Toggle **Expert Mode** on and click **Submit**
3. The integration reloads and a **Working Mode** select entity becomes available under the SELFA Inverter device

To disable, repeat the steps above and toggle Expert Mode off. The select entity will be removed on reload.

### Protocol

The dongle communicates over **Modbus RTU over TCP** (raw RTU framing with CRC, not standard Modbus TCP). Default: `192.168.1.1:5743`, slave address `252` (`0xFC`).

---
