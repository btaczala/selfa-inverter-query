import argparse
import socket
import struct

parser = argparse.ArgumentParser()
parser.add_argument("--ip", default="192.168.1.1")
args = parser.parse_args()

HOST = args.ip
PORT = 5743
SLAVE = 0xFC


def crc16(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def read_registers(sock: socket.socket, start: int, count: int) -> list[int]:
    req = struct.pack(">BBHH", SLAVE, 0x03, start, count)
    req += struct.pack("<H", crc16(req))
    sock.sendall(req)

    resp = sock.recv(256)
    if resp[1] == 0x83:
        raise RuntimeError(f"Modbus exception: code {resp[2]:#x}")

    byte_count = resp[2]
    return [struct.unpack(">H", resp[3 + i * 2 : 5 + i * 2])[0] for i in range(byte_count // 2)]


def u32(regs: list[int]) -> int:
    return (regs[0] << 16) | regs[1]


def i32(regs: list[int]) -> int:
    val = u32(regs)
    return val if val < 0x80000000 else val - 0x100000000


def i16(reg: int) -> int:
    return reg if reg < 0x8000 else reg - 0x10000


with socket.create_connection((HOST, PORT), timeout=5) as sock:
    pv_regs = read_registers(sock, 11028, 2)
    grid_regs = read_registers(sock, 11000, 2)
    phase_regs = read_registers(sock, 11009, 6)   # 11009-11014: L1-L3 V+I
    battery_regs = read_registers(sock, 30258, 2)
    battery_brand_regs = read_registers(sock, 52500, 2)

pv_kw = u32(pv_regs) / 1000
grid_kw = i32(grid_regs) / 1000
battery_kw = i32(battery_regs) / 1000
home_kw = pv_kw + battery_kw - grid_kw

l1_v = phase_regs[0] / 10
l1_a = phase_regs[1] / 10
l2_v = phase_regs[2] / 10
l2_a = phase_regs[3] / 10
l3_v = phase_regs[4] / 10
l3_a = phase_regs[5] / 10

battery_brand = battery_brand_regs[0]
battery_protocol = battery_brand_regs[1]

print(f"PV Input:         {pv_kw:.3f} kW")
print(f"Grid Meter:       {grid_kw:+.3f} kW  ({'export' if grid_kw > 0 else 'import'})")
print(f"Battery:          {battery_kw:+.3f} kW  ({'discharge' if battery_kw > 0 else 'charge'})")
print(f"Home Power:       {home_kw:.3f} kW  (PV + Bat - Grid)")
print(f"L1:               {l1_v:.1f} V  {l1_a:.1f} A")
print(f"L2:               {l2_v:.1f} V  {l2_a:.1f} A")
print(f"L3:               {l3_v:.1f} V  {l3_a:.1f} A")
print(f"Battery Brand:    {battery_brand}")
print(f"Battery Protocol: {battery_protocol}")
