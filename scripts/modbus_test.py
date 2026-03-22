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

# Export limit
export_grp = parser.add_argument_group("export limit")
export_grp.add_argument("--export-limit-on",  action="store_true", help="Enable export limit")
export_grp.add_argument("--export-limit-off", action="store_true", help="Disable export limit")
export_grp.add_argument("--set-export-limit", type=float, metavar="PCT",
                        help="Set export limit percentage (0–100)")

# Import limit
import_grp = parser.add_argument_group("import limit")
import_grp.add_argument("--import-limit-on",  action="store_true", help="Enable import limit")
import_grp.add_argument("--import-limit-off", action="store_true", help="Disable import limit")
import_grp.add_argument("--set-import-limit", type=float, metavar="PCT",
                        help="Set import limit percentage (0–100)")

args = parser.parse_args()

HOST = args.ip
PORT = 5743
SLAVE = 0xFC

# Known limit registers
REG_EXPORT_ENABLE = 25100
REG_EXPORT_VALUE  = 25103
REG_IMPORT_VALUE  = 50009   # Max Grid Power / import limit (kVA, scale 0.1)
REG_IMPORT_ENABLE = 50007   # confirmed: 1=ON, 0=OFF


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
    pv_regs           = read_registers(sock, 11028, 2)
    grid_regs         = read_registers(sock, 11000, 2)
    ac_regs           = read_registers(sock, 11016, 2)
    energy_total_regs = read_registers(sock, 11020, 2)
    phase_regs        = read_registers(sock, 11009, 6)
    battery_regs      = read_registers(sock, 30258, 2)
    battery_brand_regs = read_registers(sock, 52500, 2)
    working_mode_regs = read_registers(sock, 50000, 1)
    batt_power_sched_regs = read_registers(sock, 50207, 1)
    bms_status_regs = read_registers(sock, 53508, 1)

    # Export limit area (confirmed)
    limit_regs  = read_registers(sock, 25100, 20)   # 25100–25119
    # Import limit area — 50009 is the value; scan nearby for enable toggle
    import_regs = read_registers(sock, 50005, 10)   # 50005–50014

    # --- writes ---
    if args.set_mode:
        new_value = WORKING_MODES[args.set_mode]
        write_register(sock, 50000, new_value)
        print(f"Set working mode to {args.set_mode} ({new_value:#06x})")
        working_mode_regs = read_registers(sock, 50000, 1)

    if args.export_limit_on:
        write_register(sock, REG_EXPORT_ENABLE, 1)
        print("Export limit: enabled")
    if args.export_limit_off:
        write_register(sock, REG_EXPORT_ENABLE, 0)
        print("Export limit: disabled")
    if args.set_export_limit is not None:
        raw = int(args.set_export_limit * 1000)
        write_register(sock, REG_EXPORT_VALUE, raw)
        print(f"Export limit value set to {args.set_export_limit:.1f}%")

    if args.import_limit_on:
        write_register(sock, REG_IMPORT_ENABLE, 1)
        print(f"Import limit: enabled  (reg {REG_IMPORT_ENABLE} — unconfirmed)")
    if args.import_limit_off:
        write_register(sock, REG_IMPORT_ENABLE, 0)
        print(f"Import limit: disabled  (reg {REG_IMPORT_ENABLE} — unconfirmed)")
    if args.set_import_limit is not None:
        raw = int(args.set_import_limit * 10)   # kVA, scale 0.1
        write_register(sock, REG_IMPORT_VALUE, raw)
        print(f"Import limit value set to {args.set_import_limit:.1f} kVA  (reg {REG_IMPORT_VALUE})")

    # re-read after any writes
    if any([args.export_limit_on, args.export_limit_off, args.set_export_limit,
            args.import_limit_on, args.import_limit_off, args.set_import_limit]):
        limit_regs  = read_registers(sock, 25100, 20)
        import_regs = read_registers(sock, 50005, 10)

# --- decode ---
pv_kw  = u32(pv_regs) / 1000
grid_kw = i32(grid_regs) / 1000
ac_kw  = i32(ac_regs) / 1000
energy_total_kwh = u32(energy_total_regs) / 10
battery_kw = i32(battery_regs) / 1000
home_kw = pv_kw + battery_kw - grid_kw

l1_v, l1_a = phase_regs[0] / 10, phase_regs[1] / 10
l2_v, l2_a = phase_regs[2] / 10, phase_regs[3] / 10
l3_v, l3_a = phase_regs[4] / 10, phase_regs[5] / 10

WORKING_MODES_DISPLAY = {v: k.title() for k, v in WORKING_MODES.items()}
working_mode_raw = working_mode_regs[0]
working_mode = WORKING_MODES_DISPLAY.get(working_mode_raw, f"Unknown ({working_mode_raw:#06x})")

battery_brand    = battery_brand_regs[0]
battery_protocol = battery_brand_regs[1]
batt_power_sched_kw = i16(batt_power_sched_regs[0]) / 100
bms_status_raw = bms_status_regs[0]
bms_discharge_ongrid  = bool(bms_status_raw & (1 << 9))
bms_discharge_offgrid = bool(bms_status_raw & (1 << 8))
bms_charge_cmd        = bool(bms_status_raw & (1 << 10))
bms_force_charge      = bool(bms_status_raw & (1 << 11))
bms_running_status    = bms_status_raw & 0xFF

export_enable = limit_regs[REG_EXPORT_ENABLE - 25100]
export_value  = limit_regs[REG_EXPORT_VALUE  - 25100] / 10     # kW
IMPORT_BASE   = 50005
import_enable = import_regs[REG_IMPORT_ENABLE - IMPORT_BASE]
import_value  = import_regs[REG_IMPORT_VALUE  - IMPORT_BASE] / 10   # kVA, scale 0.1

# --- output ---
print(f"PV Input:         {pv_kw:.3f} kW")
print(f"Grid Meter:       {grid_kw:+.3f} kW  ({'export' if grid_kw > 0 else 'import'})")
print(f"Battery:          {battery_kw:+.3f} kW  ({'discharge' if battery_kw > 0 else 'charge'})")
print(f"Inverter AC:      {ac_kw:.3f} kW  (11016, P_AC)")
print(f"Home Power:       {home_kw:.3f} kW  (PV + Bat - Grid)")
print(f"Energy Total:     {energy_total_kwh:.1f} kWh  (11020)")
print(f"L1:               {l1_v:.1f} V  {l1_a:.1f} A")
print(f"L2:               {l2_v:.1f} V  {l2_a:.1f} A")
print(f"L3:               {l3_v:.1f} V  {l3_a:.1f} A")
print(f"Working Mode:     {working_mode}")
print(f"Export Limit:     {'ON' if export_enable else 'OFF'}  {export_value:.1f} kW"
      f"  (enable={REG_EXPORT_ENABLE}, value={REG_EXPORT_VALUE})")
print(f"Import Limit:     {'ON' if import_enable else 'OFF'}  {import_value:.1f} kVA"
      f"  (enable={REG_IMPORT_ENABLE}?, value={REG_IMPORT_VALUE})")
print(f"Battery Brand:    {battery_brand}")
print(f"Battery Protocol: {battery_protocol}")
print(f"Batt Pwr Sched:   {batt_power_sched_kw:+.2f} kW  (50207, +discharge/-charge)")
BMS_RUNNING = {0: "Sleep", 1: "Charge", 2: "Discharge", 3: "Standby", 4: "Fault"}
print(f"BMS Status:       0x{bms_status_raw:04x}  (53508)"
      f"  discharge_ongrid={int(bms_discharge_ongrid)}"
      f"  discharge_offgrid={int(bms_discharge_offgrid)}"
      f"  charge={int(bms_charge_cmd)}"
      f"  force_charge={int(bms_force_charge)}"
      f"  running={BMS_RUNNING.get(bms_running_status, bms_running_status)}")

