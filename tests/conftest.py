import struct
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest


def _crc16(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def modbus_response(slave: int, registers: list[int]) -> bytes:
    """Build a valid Modbus RTU FC03 response for the given register values."""
    data = b"".join(struct.pack(">H", r) for r in registers)
    body = struct.pack("BBB", slave, 0x03, len(data)) + data
    crc = struct.pack("<H", _crc16(body))
    return body + crc


def modbus_exception(slave: int, exc_code: int = 0x02) -> bytes:
    """Build a Modbus RTU exception response (e.g. illegal address)."""
    body = struct.pack("BBB", slave, 0x83, exc_code)
    crc = struct.pack("<H", _crc16(body))
    return body + crc


# Serial number "B112400101230134" encoded as 8 registers (ASCII pairs)
SN_REGISTERS = [
    (ord("B") << 8) | ord("1"),
    (ord("1") << 8) | ord("2"),
    (ord("4") << 8) | ord("0"),
    (ord("0") << 8) | ord("1"),
    (ord("0") << 8) | ord("1"),
    (ord("2") << 8) | ord("3"),
    (ord("0") << 8) | ord("1"),
    (ord("3") << 8) | ord("4"),
]
EXPECTED_SERIAL = "B112400101230134"
FW_REGISTERS = [0x0006, 0xC303]  # arbitrary firmware version


def make_mock_socket(responses: list[bytes]) -> MagicMock:
    """
    Create a socket mock that streams the given response bytes.
    Each recv() call returns the next chunk from the current response.
    Responses are consumed in order — one per _read_registers() call.
    """
    sock = MagicMock()
    # We simulate recv() by splitting each response into header (3 bytes) + rest
    chunks = []
    for resp in responses:
        chunks.append(resp[:3])   # header: addr + fc + byte_count
        chunks.append(resp[3:])   # payload + CRC
    sock.recv.side_effect = chunks
    return sock


@pytest.fixture
def mock_socket() -> Generator:
    """Patch socket.create_connection for all coordinator tests."""
    with patch("custom_components.selfa.coordinator.socket.create_connection") as mock_conn:
        yield mock_conn
