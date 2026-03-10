import logging
import socket
import struct
from datetime import timedelta

from homeassistant.components.sensor import SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SENSORS, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

# A large change in any of these units triggers the confirmation gate.
# The value must appear in TWO consecutive polls before being accepted.
_CONFIRM_THRESHOLD_BY_UNIT: dict[str, float] = {
    "kW":  5.0,
    "kWh": 0.5,
    "%":   5.0,
    "V":  20.0,
    "A":  10.0,
    "°C":  5.0,
    "Hz":  2.0,
}

# Contiguous register ranges to fetch in one request: (start, count)
REGISTER_BATCHES = [
    (10105, 1),    # inverter status
    (11000, 42),   # grid, AC power, daily/total energy, temps, PV1/2 V+I (11000-11041)
    (11062, 4),    # PV1/2 power (11062-11065)
    (30254, 6),    # battery V, I, mode, power (30254-30259)
    (31000, 9),    # daily energy (31000-31008)
    (31102, 18),   # total energy (31102-31119)
    (33000, 4),    # SOC, SOH, BMS status, BMS temp (33000-33003)
    (50000, 1),    # working mode (50000)
    (52500, 1),    # battery brand (52500)
]


class _CrcError(UpdateFailed):
    """Raised when a Modbus response has a bad CRC."""


# Lookup for confirmation-gate logic keyed by sensor key
_SENSOR_MAP = {s.key: s for s in SENSORS}


def _crc16(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def _read_registers(sock: socket.socket, slave: int, start: int, count: int) -> list[int]:
    req = struct.pack(">BBHH", slave, 0x03, start, count)
    req += struct.pack("<H", _crc16(req))
    sock.sendall(req)

    header = sock.recv(3)
    if len(header) < 3:
        raise UpdateFailed("Short response from inverter")
    if header[1] == 0x83:
        exc = sock.recv(3)
        raise UpdateFailed(f"Modbus exception at reg {start}: code {exc[0]:#x}")

    byte_count = header[2]
    payload = b""
    while len(payload) < byte_count + 2:  # +2 for CRC
        chunk = sock.recv(byte_count + 2 - len(payload))
        if not chunk:
            raise UpdateFailed("Connection closed by inverter")
        payload += chunk

    data_bytes = payload[:byte_count]
    received_crc = struct.unpack("<H", payload[byte_count : byte_count + 2])[0]
    expected_crc = _crc16(header + data_bytes)
    if received_crc != expected_crc:
        _LOGGER.warning(
            "CRC mismatch at reg %d: got %#06x, expected %#06x"
            " (likely collision with another Modbus client)",
            start, received_crc, expected_crc,
        )
        raise _CrcError(f"CRC mismatch at reg {start}")

    return [
        struct.unpack(">H", data_bytes[i : i + 2])[0]
        for i in range(0, byte_count, 2)
    ]


def _decode(regs: list[int], reg_map: dict[int, int], address: int, data_type: str) -> float | int:
    idx = address - min(reg_map.keys())  # relative index into the batch
    raw = reg_map[address]

    if data_type == "uint16":
        return raw
    if data_type == "int16":
        return raw if raw < 0x8000 else raw - 0x10000
    if data_type in ("uint32", "int32"):
        high = reg_map[address]
        low = reg_map[address + 1]
        val = (high << 16) | low
        if data_type == "int32" and val >= 0x80000000:
            val -= 0x100000000
        return val
    return raw


class SelfaCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, host: str, port: int, slave: int) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.host = host
        self.port = port
        self.slave = slave
        self.serial_number: str = "unknown"
        self.firmware_version: str = "unknown"
        self._last_data: dict = {}
        self._pending: dict = {}  # values waiting for confirmation (spike gate)
        self.crc_error_count: int = 0

    async def async_write_register(self, register: int, value: int) -> None:
        await self.hass.async_add_executor_job(self._write_register, register, value)

    def _write_register(self, register: int, value: int) -> None:
        with socket.create_connection((self.host, self.port), timeout=10) as sock:
            req = struct.pack(">BBHH", self.slave, 0x06, register, value)
            req += struct.pack("<H", _crc16(req))
            sock.sendall(req)
            resp = sock.recv(8)
            if resp[1] == 0x86:
                raise RuntimeError(f"Modbus write exception at reg {register}: code {resp[2]:#x}")

    async def _async_update_data(self) -> dict:
        try:
            result = await self.hass.async_add_executor_job(self._fetch)
        except Exception as e:
            if self._last_data:
                _LOGGER.warning("Inverter unreachable, retaining last known values: %s", e)
                return {**self._last_data, "crc_error_count": self.crc_error_count}
            raise

        if self._last_data:
            for key, val in result.items():
                last = self._last_data.get(key)

                # Keep last known value when current read returned None
                if val is None and last is not None:
                    result[key] = last
                    self._pending.pop(key, None)
                    continue

                if val is None or last is None:
                    self._pending.pop(key, None)
                    continue

                sensor = _SENSOR_MAP.get(key)
                if sensor is None:
                    continue

                threshold = _CONFIRM_THRESHOLD_BY_UNIT.get(sensor.native_unit_of_measurement)
                if threshold is None:
                    continue

                # Energy counters must never go backwards (no confirmation needed)
                if sensor.state_class == SensorStateClass.TOTAL_INCREASING and val < last:
                    _LOGGER.debug("Spike filter: %s dropped %.3f → %.3f, keeping last", key, last, val)
                    result[key] = last
                    self._pending.pop(key, None)
                    continue

                delta = abs(val - last)
                if delta <= threshold:
                    # Normal change — clear any pending candidate
                    self._pending.pop(key, None)
                    continue

                # Large change: require a second consecutive matching reading
                pending = self._pending.get(key)
                if pending is not None and abs(val - pending) <= threshold:
                    # Confirmed over two polls — accept and clear
                    _LOGGER.debug("Spike gate: %s confirmed %.3f → %.3f", key, last, val)
                    self._pending.pop(key, None)
                else:
                    # First sighting of a large change — hold it, keep last value
                    _LOGGER.warning(
                        "Spike gate: %s changed %.3f → %.3f (Δ%.3f > %.3f %s), holding for confirmation",
                        key, last, val, delta, threshold, sensor.native_unit_of_measurement,
                    )
                    self._pending[key] = val
                    result[key] = last

        self._last_data = result
        return result

    def _fetch(self) -> dict:
        reg_map: dict[int, int] = {}

        with socket.create_connection((self.host, self.port), timeout=10) as sock:
            # Read device info once (serial + firmware)
            if self.serial_number == "unknown":
                try:
                    sn_regs = _read_registers(sock, self.slave, 10000, 8)
                    raw = b"".join(struct.pack(">H", r) for r in sn_regs)
                    self.serial_number = raw.decode("ascii", errors="replace").rstrip("\x00")
                    fw_regs = _read_registers(sock, self.slave, 10011, 2)
                    fw = (fw_regs[0] << 16) | fw_regs[1]
                    self.firmware_version = "v{:02d}.{:02d}.{:02d}.{:02d}".format(
                        (fw >> 24) & 0xFF, (fw >> 16) & 0xFF, (fw >> 8) & 0xFF, fw & 0xFF
                    )
                except Exception:
                    pass

            for start, count in REGISTER_BATCHES:
                try:
                    regs = _read_registers(sock, self.slave, start, count)
                    for i, val in enumerate(regs):
                        reg_map[start + i] = val
                except _CrcError as e:
                    self.crc_error_count += 1
                    _LOGGER.debug("Skipping batch starting at %d: %s", start, e)
                except (UpdateFailed, OSError) as e:
                    _LOGGER.debug("Skipping batch starting at %d: %s", start, e)

        _SENTINEL = {
            "uint16": 0xFFFF,
            "int16":  0xFFFF,
            "uint32": 0xFFFFFFFF,
            "int32":  0xFFFFFFFF,
        }

        result: dict = {"serial_number": self.serial_number, "crc_error_count": self.crc_error_count}
        for sensor in SENSORS:
            if sensor.register == 0:
                continue
            try:
                raw = _decode([], reg_map, sensor.register, sensor.data_type)
                if raw == _SENTINEL.get(sensor.data_type):
                    _LOGGER.debug("Sentinel value for %s, treating as unavailable", sensor.key)
                    result[sensor.key] = None
                else:
                    result[sensor.key] = round(raw * sensor.scale, 6) if sensor.scale != 1.0 else raw
            except (KeyError, Exception) as e:
                _LOGGER.debug("Failed to decode %s: %s", sensor.key, e)
                result[sensor.key] = None

        # Compute home power: P_load = P_pv + P_bat - P_grid_meter
        pv = result.get("pv_input_power")
        bat = result.get("battery_power")
        grid = result.get("grid_meter_power")
        if pv is not None and bat is not None and grid is not None:
            result["home_power"] = round(pv + bat - grid, 6)
        else:
            result["home_power"] = None

        return result
