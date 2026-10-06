# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

A Home Assistant custom integration for **SELFA SFH hybrid inverters**. Communicates locally with the inverter's WiFi dongle using **Modbus RTU over TCP** (no cloud). Exposes 50+ sensors and expert-mode controls for export/import limits, working modes, and battery parameters.

Default inverter address: `192.168.1.1:5743`, slave address `252` (0xFC).

Actual inverter IP on local network: `192.168.20.188`.

## Commands

```bash
# Run all tests
pytest tests/

# Run a single test file
pytest tests/test_coordinator.py -v

# Lint
ruff check custom_components/

# Manual Modbus testing
uv run scripts/modbus_test.py --ip 192.168.20.188
uv run scripts/modbus_test.py --ip 192.168.20.188 --help
```

CI runs `ruff check` and validates the manifest on every PR.

## Architecture

The integration lives entirely in `custom_components/selfa/`.

**Data flow**:
1. `coordinator.py` — `SelfaCoordinator` polls Modbus registers every 5s in batches, decodes values, applies spike-gate filtering, and injects computed fields (`home_power`, `serial_number`, `firmware_version`).
2. Entity platforms (`sensor.py`, `select.py`, `switch.py`, `number.py`) are `CoordinatorEntity` subclasses that read from `coordinator.data`.
3. `config_flow.py` captures host/port/slave on setup; the **Options Flow** toggles Expert Mode and Breaker Type (affects `max_import_kva`).
4. `const.py` is the single source of truth for all sensor definitions (`SENSORS` tuple) and working mode mappings.

**Expert Mode** (disabled by default): when enabled, registers SELECT, SWITCH, and NUMBER entities that can write Modbus registers via `coordinator.async_write_register()`. Requires integration reload to take effect.

**Spike gate**: large value changes require 2 consecutive matching polls before being accepted. Thresholds are unit-based (kW, kWh, %, V, A, °C, Hz). Energy counters (`TOTAL_INCREASING`) skip the gate: they never go backwards, and an increase faster than `_MAX_ENERGY_RATE_KW` over the time since the counter last moved is rejected. A two-poll check isn't enough for them -- a misread that repeats passes it, and a counter that's once wrongly high would reject every real reading as a drop until the integration is reloaded (2026-10-05).

**Modbus protocol details**:
- Raw RTU framing over a plain TCP socket (not Modbus TCP)
- FC03 for reads, FC06 for single-register writes
- CRC-16 (poly 0xA001, init 0xFFFF); `CrcError` increments a diagnostic counter and skips the batch
- No transaction id: a reply is only checked against its request by slave, function code and byte count. Any `_DesyncError` (bad CRC, mismatched reply, short read, timeout) skips the batch and reconnects, since a stale frame left in the socket would otherwise be decoded as the next batch's registers
- 10s socket timeout; on failure the coordinator retains last known values

**Register reference**: `SFH_SELFA Hybrid Inverter MODBUS RTU Protocol.pdf` (repo root) contains the full register map and protocol specification.

**Register layout** (key addresses):
- `10000–10012`: Device info (SN, firmware)
- `10105`: Inverter status
- `11000–11065`: Grid, AC, temperatures, PV strings
- `25100`: Export limit enable
- `30254–30259`: Battery voltage/current/mode/power
- `50000`: Working mode
- `50007`: Import limit enable
- `50207`: Battery power scheduling
- `52502`: Battery low SOC protection

**Working modes** (register 50000):
- `0x0101` General, `0x0102` Economic, `0x0103` UPS, `0x0200` Off-grid, `0x0301–0x0404` EMS variants

