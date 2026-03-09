# SELFA Inverter

Home Assistant custom integration and data bridge for SELFA SFH hybrid inverters. Communicates locally with the inverter's WiFi dongle over Modbus RTU/TCP — no cloud required.

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
| Inverter AC Power | kW | Total AC output power |
| PV Input Power | kW | Combined PV input |
| PV1 / PV2 Power | kW | Per-string PV power |
| PV1 / PV2 Voltage | V | Per-string PV voltage |
| Grid Meter Power | kW | Negative = export, positive = import |
| Grid Voltage / Frequency | V / Hz | |
| Battery Power | kW | Negative = charging, positive = discharging |
| Battery Voltage / Current | V / A | |
| Battery SOC / SOH | % | State of charge / health |
| BMS Temperature | °C | |
| Inverter Temperature | °C | |
| Daily / Total energy | kWh | PV, grid injection/purchase, battery charge/discharge, load |

### Protocol

The dongle communicates over **Modbus RTU over TCP** (raw RTU framing with CRC, not standard Modbus TCP). Default: `192.168.1.1:5743`, slave address `252` (`0xFC`).

---
