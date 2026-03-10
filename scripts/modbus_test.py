import argparse
import socket
import struct

WORKING_MODES = {
    "general":      0x0101,
    "economic":     0x0102,
    "ups":          0x0103,
    "off-grid":     0x0200,
    "ems-ac":       0x0301,
    "ems-general":  0x0302,
    "ems-battery":  0x0303,
    "ems-offgrid":  0x0404,
}

parser = argparse.ArgumentParser()
parser.add_argument("--ip", default="192.168.1.1")
parser.add_argument("--set-mode", choices=WORKING_MODES.keys(), metavar="MODE",
                    help=f"Set working mode. Choices: {', '.join(WORKING_MODES)}")
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


def write_register(sock: socket.socket, register: int, value: int) -> None:
    req = struct.pack(">BBHH", SLAVE, 0x06, register, value)
    req += struct.pack("<H", crc16(req))
    sock.sendall(req)
    resp = sock.recv(256)
    if resp[1] == 0x86:
        raise RuntimeError(f"Modbus write exception: code {resp[2]:#x}")


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
    ac_regs = read_registers(sock, 11016, 2)       # P_AC: inverter AC output
    energy_total_regs = read_registers(sock, 11020, 2)  # Energy-total (kWh, not power)
    phase_regs = read_registers(sock, 11009, 6)   # 11009-11014: L1-L3 V+I
    battery_regs = read_registers(sock, 30258, 2)
    battery_brand_regs = read_registers(sock, 52500, 2)
    export_limit_regs = read_registers(sock, 25100, 4)  # 25100: switch, 25103: limit %
    max_grid_regs = read_registers(sock, 50009, 1)      # max grid power (kVA)
    working_mode_regs = read_registers(sock, 50000, 1)  # working mode
    if args.set_mode:
        new_value = WORKING_MODES[args.set_mode]
        write_register(sock, 50000, new_value)
        print(f"Set working mode to {args.set_mode} ({new_value:#06x})")
        working_mode_regs = read_registers(sock, 50000, 1)  # re-read to confirm

pv_kw = u32(pv_regs) / 1000
grid_kw = i32(grid_regs) / 1000
ac_kw = i32(ac_regs) / 1000
energy_total_kwh = u32(energy_total_regs) / 10
battery_kw = i32(battery_regs) / 1000
home_kw = pv_kw + battery_kw - grid_kw

l1_v = phase_regs[0] / 10
l1_a = phase_regs[1] / 10
l2_v = phase_regs[2] / 10
l2_a = phase_regs[3] / 10
l3_v = phase_regs[4] / 10
l3_a = phase_regs[5] / 10

WORKING_MODES_DISPLAY = {v: k.title() for k, v in WORKING_MODES.items()}
working_mode_raw = working_mode_regs[0]
working_mode = WORKING_MODES_DISPLAY.get(working_mode_raw, f"Unknown ({working_mode_raw:#06x})")

export_limit_on = export_limit_regs[0]           # 25100: 0=OFF, 1=ON
export_limit_pct = export_limit_regs[3] / 1000   # 25103: 0.0-100.0%
max_grid_kva = max_grid_regs[0] / 10             # 50009: kVA

battery_brand = battery_brand_regs[0]
battery_protocol = battery_brand_regs[1]

print(f"PV Input:         {pv_kw:.3f} kW")
print(f"Grid Meter:       {grid_kw:+.3f} kW  ({'export' if grid_kw > 0 else 'import'})")
print(f"Battery:          {battery_kw:+.3f} kW  ({'discharge' if battery_kw > 0 else 'charge'})")
print(f"Inverter AC:      {ac_kw:.3f} kW  (11016, P_AC)")
print(f"Home Power:       {home_kw:.3f} kW  (PV + Bat - Grid)")
print(f"Energy Total:     {energy_total_kwh:.1f} kWh  (11020, lifetime counter — not power)")
print(f"L1:               {l1_v:.1f} V  {l1_a:.1f} A")
print(f"L2:               {l2_v:.1f} V  {l2_a:.1f} A")
print(f"L3:               {l3_v:.1f} V  {l3_a:.1f} A")
print(f"Working Mode:     {working_mode}")
print(f"Export Limit:     {'ON' if export_limit_on else 'OFF'}  {export_limit_pct:.1f}%  (25100/25103)")
print(f"Max Grid Power:   {max_grid_kva:.1f} kVA  (50009)")
print(f"Battery Brand:    {battery_brand}")
print(f"Battery Protocol: {battery_protocol}")
