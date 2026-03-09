import logging
import socket
import struct
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SENSORS, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

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

    return [
        struct.unpack(">H", payload[i : i + 2])[0]
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

    async def _async_update_data(self) -> dict:
        return await self.hass.async_add_executor_job(self._fetch)

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
                except UpdateFailed as e:
                    _LOGGER.debug("Skipping batch starting at %d: %s", start, e)

        result: dict = {"serial_number": self.serial_number}
        for sensor in SENSORS:
            if sensor.register == 0:
                continue
            try:
                raw = _decode([], reg_map, sensor.register, sensor.data_type)
                result[sensor.key] = round(raw * sensor.scale, 6) if sensor.scale != 1.0 else raw
            except (KeyError, Exception) as e:
                _LOGGER.debug("Failed to decode %s: %s", sensor.key, e)
                result[sensor.key] = None

        return result
