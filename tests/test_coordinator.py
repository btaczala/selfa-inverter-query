"""Tests for the Modbus coordinator — no HA instance needed."""
import struct
from unittest.mock import MagicMock

import pytest

from custom_components.selfa.coordinator import _crc16, _read_registers, _decode, REGISTER_BATCHES
from homeassistant.helpers.update_coordinator import UpdateFailed

from .conftest import modbus_response, modbus_exception, make_mock_socket


# ---------------------------------------------------------------------------
# _crc16
# ---------------------------------------------------------------------------

def test_crc16_known_value():
    # FC03 request: slave=0xFC, reg=10000, count=8 → CRC must be 0x5A90 (little-endian in frame)
    req = struct.pack(">BBHH", 0xFC, 0x03, 10000, 8)
    assert _crc16(req) == 0x905A  # stored little-endian in frame as 5A 90


def test_crc16_empty():
    assert _crc16(b"") == 0xFFFF


# ---------------------------------------------------------------------------
# _read_registers
# ---------------------------------------------------------------------------

def test_read_registers_success():
    sock = make_mock_socket([modbus_response(0xFC, [100, 200, 300])])
    result = _read_registers(sock, 0xFC, 11000, 3)
    assert result == [100, 200, 300]


def test_read_registers_modbus_exception():
    exc = modbus_exception(0xFC, 0x02)
    sock = make_mock_socket([exc])
    with pytest.raises(UpdateFailed, match="Modbus exception .* code 0x2"):
        _read_registers(sock, 0xFC, 60000, 1)


def test_read_registers_short_response():
    # A partial header is read on until the inverter closes the connection.
    sock = MagicMock()
    sock.recv.side_effect = [b"\xFC\x03", b""]
    with pytest.raises(UpdateFailed, match="Connection closed"):
        _read_registers(sock, 0xFC, 11000, 1)


# ---------------------------------------------------------------------------
# _decode
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("reg,data_type,expected", [
    (11000, "uint16", 1234),
    (11000, "int16",  1234),
    (11000, "int16",  -1),          # 0xFFFF → -1
    (11028, "uint32", 4523),        # high=0, low=4523
    (30258, "int32",  -3668),       # 0xFFFFF1AC
])
def test_decode(reg, data_type, expected):
    reg_map = {}
    if data_type == "uint16":
        reg_map[reg] = 1234
    elif data_type == "int16" and expected == 1234:
        reg_map[reg] = 1234
    elif data_type == "int16" and expected == -1:
        reg_map[reg] = 0xFFFF
    elif data_type == "uint32":
        reg_map[reg] = 0
        reg_map[reg + 1] = 4523
    elif data_type == "int32":
        reg_map[reg] = 0xFFFF
        reg_map[reg + 1] = 0xF1AC

    result = _decode([], reg_map, reg, data_type)
    assert result == expected


def test_decode_missing_register():
    with pytest.raises((KeyError, ValueError)):
        _decode([], {}, 11000, "uint16")


# ---------------------------------------------------------------------------
# SelfaCoordinator._fetch  (integration-level, no HA needed)
# ---------------------------------------------------------------------------

def _build_full_responses(slave: int = 0xFC) -> list:
    """Build responses for all REGISTER_BATCHES + SN + FW reads."""
    from .conftest import SN_REGISTERS, FW_REGISTERS

    responses = [
        modbus_response(slave, SN_REGISTERS),       # serial number
        modbus_response(slave, FW_REGISTERS),        # firmware
    ]
    for start, count in REGISTER_BATCHES:
        responses.append(modbus_response(slave, [0] * count))
    return responses


def test_fetch_returns_all_sensor_keys(mock_socket):
    from custom_components.selfa.coordinator import SelfaCoordinator
    from custom_components.selfa.const import SENSORS

    responses = _build_full_responses()
    sock = make_mock_socket(responses)
    mock_socket.return_value = sock

    coord = SelfaCoordinator.__new__(SelfaCoordinator)
    coord.host = "192.168.1.1"
    coord.port = 5743
    coord.slave = 0xFC
    coord.serial_number = "unknown"
    coord.firmware_version = "unknown"
    coord.logger = __import__("logging").getLogger("test")

    result = coord._fetch()

    for sensor in SENSORS:
        assert sensor.key in result


def test_fetch_pv_power(mock_socket):
    from custom_components.selfa.coordinator import SelfaCoordinator
    from .conftest import SN_REGISTERS, FW_REGISTERS

    # Build responses: all zeros except PV batch (11000+42 regs)
    # PV total power is at 11028-11029 → offset 28,29 within that batch
    pv_regs = [0] * 42
    pv_regs[28] = 0       # high word
    pv_regs[29] = 4523    # low word  → 4.523 kW

    responses = [
        modbus_response(0xFC, SN_REGISTERS),
        modbus_response(0xFC, FW_REGISTERS),
        modbus_response(0xFC, [0]),          # 10105 inverter status
        modbus_response(0xFC, pv_regs),      # 11000..11041
        modbus_response(0xFC, [0] * 4),      # 11062..11065
        modbus_response(0xFC, [0] * 6),      # 30254..30259
        modbus_response(0xFC, [0] * 9),      # 31000..31008
        modbus_response(0xFC, [0] * 18),     # 31102..31119
        modbus_response(0xFC, [0] * 4),      # 33000..33003
    ]
    sock = make_mock_socket(responses)
    mock_socket.return_value = sock

    coord = SelfaCoordinator.__new__(SelfaCoordinator)
    coord.host = "192.168.1.1"
    coord.port = 5743
    coord.slave = 0xFC
    coord.serial_number = "unknown"
    coord.firmware_version = "unknown"
    coord.logger = __import__("logging").getLogger("test")

    result = coord._fetch()

    assert result["pv_input_power"] == pytest.approx(4.523)


def test_fetch_battery_soc(mock_socket):
    from custom_components.selfa.coordinator import SelfaCoordinator
    from .conftest import SN_REGISTERS, FW_REGISTERS

    soc_regs = [5300, 9800, 0, 250]  # SOC=53.00%, SOH=98.00%, status, BMS temp=25.0°C

    responses = [
        modbus_response(0xFC, SN_REGISTERS),
        modbus_response(0xFC, FW_REGISTERS),
        modbus_response(0xFC, [0]),          # 10105
        modbus_response(0xFC, [0] * 42),     # 11000..11041
        modbus_response(0xFC, [0] * 4),      # 11062..11065
        modbus_response(0xFC, [0] * 6),      # 30254..30259
        modbus_response(0xFC, [0] * 9),      # 31000..31008
        modbus_response(0xFC, [0] * 18),     # 31102..31119
        modbus_response(0xFC, soc_regs),     # 33000..33003
    ]
    sock = make_mock_socket(responses)
    mock_socket.return_value = sock

    coord = SelfaCoordinator.__new__(SelfaCoordinator)
    coord.host = "192.168.1.1"
    coord.port = 5743
    coord.slave = 0xFC
    coord.serial_number = "unknown"
    coord.firmware_version = "unknown"
    coord.logger = __import__("logging").getLogger("test")

    result = coord._fetch()

    assert result["battery_soc"] == pytest.approx(53.0)
    assert result["battery_soh"] == pytest.approx(98.0)
    assert result["bms_temperature"] == pytest.approx(25.0)


def test_fetch_serial_number(mock_socket):
    from custom_components.selfa.coordinator import SelfaCoordinator
    from .conftest import SN_REGISTERS, FW_REGISTERS, EXPECTED_SERIAL

    responses = [
        modbus_response(0xFC, SN_REGISTERS),
        modbus_response(0xFC, FW_REGISTERS),
    ] + [modbus_response(0xFC, [0] * count) for _, count in REGISTER_BATCHES]

    sock = make_mock_socket(responses)
    mock_socket.return_value = sock

    coord = SelfaCoordinator.__new__(SelfaCoordinator)
    coord.host = "192.168.1.1"
    coord.port = 5743
    coord.slave = 0xFC
    coord.serial_number = "unknown"
    coord.firmware_version = "unknown"
    coord.logger = __import__("logging").getLogger("test")

    coord._fetch()

    assert coord.serial_number == EXPECTED_SERIAL


def test_fetch_skips_failed_batch(mock_socket):
    """A Modbus exception on one batch should not abort the whole fetch."""
    from custom_components.selfa.coordinator import SelfaCoordinator
    from .conftest import SN_REGISTERS, FW_REGISTERS

    soc_regs = [7500, 9900, 0, 300]
    responses = [
        modbus_response(0xFC, SN_REGISTERS),
        modbus_response(0xFC, FW_REGISTERS),
        modbus_response(0xFC, [2]),          # 10105 status=2 (on-grid)
        modbus_exception(0xFC, 0x02),        # 11000 batch fails
        modbus_response(0xFC, [0] * 4),      # 11062
        modbus_response(0xFC, [0] * 6),      # 30254
        modbus_response(0xFC, [0] * 9),      # 31000
        modbus_response(0xFC, [0] * 18),     # 31102
        modbus_response(0xFC, soc_regs),     # 33000
    ]
    sock = make_mock_socket(responses)
    mock_socket.return_value = sock

    coord = SelfaCoordinator.__new__(SelfaCoordinator)
    coord.host = "192.168.1.1"
    coord.port = 5743
    coord.slave = 0xFC
    coord.serial_number = "unknown"
    coord.firmware_version = "unknown"
    coord.logger = __import__("logging").getLogger("test")

    result = coord._fetch()

    # Sensors from the failed batch are None
    assert result["grid_meter_power"] is None
    # Sensors from successful batches still have values
    assert result["battery_soc"] == pytest.approx(75.0)
    assert result["inverter_status"] == 2


# ---------------------------------------------------------------------------
# Desync: a reply that doesn't belong to the request (2026-10-05)
# ---------------------------------------------------------------------------

def test_read_registers_rejects_reply_of_wrong_length():
    """A stale 6-register reply must not be decoded as a 9-register batch."""
    from custom_components.selfa.coordinator import _DesyncError

    sock = make_mock_socket([modbus_response(0xFC, [5400, 17, 0, 0, 0, 935])])
    with pytest.raises(_DesyncError, match="doesn't match"):
        _read_registers(sock, 0xFC, 31000, 9)


def test_read_registers_rejects_reply_from_other_slave():
    from custom_components.selfa.coordinator import _DesyncError

    sock = make_mock_socket([modbus_response(0x01, [1, 2, 3])])
    with pytest.raises(_DesyncError, match="slave"):
        _read_registers(sock, 0xFC, 11000, 3)


def test_read_registers_timeout_is_desync():
    from custom_components.selfa.coordinator import _DesyncError

    sock = MagicMock()
    sock.recv.side_effect = TimeoutError("timed out")
    with pytest.raises(_DesyncError):
        _read_registers(sock, 0xFC, 11000, 3)


def test_fetch_reconnects_after_desync(mock_socket):
    """After a mismatched reply the rest of the poll uses a new connection."""
    from custom_components.selfa.coordinator import SelfaCoordinator

    batches = [count for _, count in REGISTER_BATCHES]
    first = make_mock_socket([
        modbus_response(0xFC, [2]),          # 10105
        modbus_response(0xFC, [0] * 5),      # 11000: wrong length
    ])
    second = make_mock_socket(
        [modbus_response(0xFC, [0] * n) for n in batches[2:6]]
        + [modbus_response(0xFC, [0] * 4)]   # 25100
        + [modbus_response(0xFC, [7500, 9900, 0, 300])]  # 33000
        + [modbus_response(0xFC, [0] * n) for n in batches[8:]])
    mock_socket.side_effect = [first, second]

    coord = SelfaCoordinator.__new__(SelfaCoordinator)
    coord.host = "192.168.1.1"
    coord.port = 5743
    coord.slave = 0xFC
    coord.serial_number = "already read"
    coord.crc_error_count = 0
    coord.breaker_type = "16A"
    coord.max_import_kva = 0.0

    result = coord._fetch()

    assert mock_socket.call_count == 2
    first.close.assert_called()
    second.close.assert_called()
    assert result["inverter_status"] == 2
    assert result["grid_meter_power"] is None   # the skipped batch
    assert result["battery_soc"] == pytest.approx(75.0)


# ---------------------------------------------------------------------------
# Energy counters: rate bound instead of the two-poll gate
# ---------------------------------------------------------------------------

def _filter_coordinator():
    from custom_components.selfa.coordinator import SelfaCoordinator

    coord = SelfaCoordinator.__new__(SelfaCoordinator)
    coord._last_data = {}
    coord._pending = {}
    coord._accepted_at = {}
    coord._dropping = set()
    coord._last_poll_at = None
    coord.crc_error_count = 0
    return coord


def _poll(coord, values: list[float], monkeypatch, start: float = 1000.0) -> list[float]:
    """Feed total_grid_purchase readings 5 s apart from `start`, return what's
    reported."""
    import asyncio
    import types

    from custom_components.selfa import coordinator as module

    clock = [start]
    monkeypatch.setattr(module, "time", types.SimpleNamespace(monotonic=lambda: clock[0]))
    reported = []
    for value in values:
        async def submit(priority, func, *args, value=value):
            return {"total_grid_purchase": value}
        coord._submit = submit
        reported.append(asyncio.run(coord._async_update_data())["total_grid_purchase"])
        clock[0] += 5
    return reported


def test_energy_counter_rejects_repeated_misread(monkeypatch):
    """The 2026-10-05 misread, repeated over several polls, never gets in,
    so the real readings after it aren't rejected as drops."""
    coord = _filter_coordinator()
    reported = _poll(coord, [1604.2, 1604.3, 19671.7, 19671.7, 19671.7, 1604.3, 1604.4],
                     monkeypatch)
    assert reported == [1604.2, 1604.3, 1604.3, 1604.3, 1604.3, 1604.3, 1604.4]


def test_energy_counter_never_goes_backwards(monkeypatch):
    coord = _filter_coordinator()
    assert _poll(coord, [10.0, 9.0, 10.1], monkeypatch) == [10.0, 10.0, 10.1]


def test_energy_counter_catches_up_after_outage(monkeypatch):
    """A counter that wasn't read for an hour may have grown by kWh."""
    coord = _filter_coordinator()
    _poll(coord, [10.0, 10.1], monkeypatch)
    assert _poll(coord, [18.1], monkeypatch, start=1005.0 + 3600) == [18.1]
