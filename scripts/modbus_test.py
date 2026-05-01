import argparse
import socket
import struct
import time

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

parser.add_argument("--set-batt-sched", type=float, metavar="KW",
                    help="Set battery power schedule in kW (+discharge/-charge, 0=off)")
parser.add_argument("--set-pv-sched", type=float, metavar="KW",
                    help="Set PV power schedule in kW (0=curtail, EMS Battery mode only)")

args = parser.parse_args()

HOST = args.ip
PORT = 5743
SLAVE = 0xFC

# Known limit registers
REG_EXPORT_ENABLE    = 25100
REG_EXPORT_VALUE     = 25103
REG_IMPORT_VALUE     = 50009   # Max Grid Power / import limit (kVA, scale 0.1)
REG_IMPORT_ENABLE    = 50007   # confirmed: 1=ON, 0=OFF
REG_LOW_SOC_ENABLE   = 52502   # On-grid SOC protection: 0=OFF, 1=ON
REG_LOW_SOC_VALUE    = 52503   # On-grid Battery End SOC (%, raw × 0.1, accuracy 1000)


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


def recvall(sock: socket.socket, n: int) -> bytes:
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise RuntimeError("Connection closed before all bytes received")
        data += chunk
    return data


def read_registers(sock: socket.socket, start: int, count: int) -> list[int]:
    req = struct.pack(">BBHH", SLAVE, 0x03, start, count)
    req += struct.pack("<H", crc16(req))
    sock.sendall(req)

    header = recvall(sock, 3)  # slave + fc + byte_count
    if header[1] == 0x83:
        code = recvall(sock, 1)[0]
        raise RuntimeError(f"Modbus exception: code {code:#x}")

    byte_count = header[2]
    payload = recvall(sock, byte_count + 2)  # data + 2 CRC bytes
    time.sleep(0.05)
    return [struct.unpack(">H", payload[i * 2 : i * 2 + 2])[0] for i in range(byte_count // 2)]


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
    pv_power_sched_regs = read_registers(sock, 50211, 1)
    bms_status_regs = read_registers(sock, 53508, 1)
    low_soc_regs    = read_registers(sock, REG_LOW_SOC_ENABLE, 2)  # 52502–52503

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

    if args.set_batt_sched is not None:
        raw = int(args.set_batt_sched * 100) & 0xFFFF  # signed i16, scale 0.01 kW
        write_register(sock, 50207, raw)
        print(f"Battery schedule set to {args.set_batt_sched:+.2f} kW  (reg 50207 = {raw})")
        batt_power_sched_regs = read_registers(sock, 50207, 1)

    if args.set_pv_sched is not None:
        raw = int(args.set_pv_sched * 100)
        write_register(sock, 50211, raw)
        print(f"PV schedule set to {args.set_pv_sched:.2f} kW  (reg 50211 = {raw})")
        pv_power_sched_regs = read_registers(sock, 50211, 1)

    # re-read after any writes
    if any([args.export_limit_on, args.export_limit_off, args.set_export_limit,
            args.import_limit_on, args.import_limit_off, args.set_import_limit]):
        limit_regs  = read_registers(sock, 25100, 20)
        import_regs = read_registers(sock, 50005, 10)
        low_soc_regs = read_registers(sock, REG_LOW_SOC_ENABLE, 2)

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
pv_power_sched_kw   = pv_power_sched_regs[0] / 100
bms_status_raw = bms_status_regs[0]
bms_discharge_ongrid  = bool(bms_status_raw & (1 << 9))
bms_discharge_offgrid = bool(bms_status_raw & (1 << 8))
bms_charge_cmd        = bool(bms_status_raw & (1 << 10))
bms_force_charge      = bool(bms_status_raw & (1 << 11))
bms_running_status    = bms_status_raw & 0xFF

low_soc_enable = bool(low_soc_regs[0])
low_soc_value  = low_soc_regs[1] * 0.1   # %, raw × 0.1

export_enable = limit_regs[REG_EXPORT_ENABLE - 25100]
export_value  = limit_regs[REG_EXPORT_VALUE  - 25100] / 10     # kW
IMPORT_BASE   = 50005
import_enable = import_regs[REG_IMPORT_ENABLE - IMPORT_BASE]
import_value  = import_regs[REG_IMPORT_VALUE  - IMPORT_BASE] / 10   # kVA, scale 0.1

BMS_RUNNING = {0: "Sleep", 1: "Charge", 2: "Discharge", 3: "Standby", 4: "Fault"}
bms_running_label = BMS_RUNNING.get(bms_running_status, str(bms_running_status))
if bms_force_charge:
    bms_running_label += " [force charge]"

# --- colours & helpers ---
R = "\033[0m"
BOLD = "\033[1m"
DIM  = "\033[2m"

BLACK  = "\033[30m"
RED    = "\033[31m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
BLUE   = "\033[34m"
CYAN   = "\033[36m"

BRED   = "\033[91m"
BGREEN = "\033[92m"
BYELLOW= "\033[93m"
BBLUE  = "\033[94m"
BMAGENTA="\033[95m"
BCYAN  = "\033[96m"
BWHITE = "\033[97m"

BAR_FULL  = "█"
BAR_EMPTY = "░"
BAR_W = 24


def bar(value: float, max_val: float, color: str, width: int = BAR_W) -> str:
    filled = round(min(abs(value) / max_val, 1.0) * width)
    return color + BAR_FULL * filled + DIM + BAR_EMPTY * (width - filled) + R


def on_off(flag: bool) -> str:
    return f"{BGREEN}ON {R}" if flag else f"{DIM}OFF{R}"


def section(title: str) -> None:
    line = f"{'─' * (44 - len(title))}"
    print(f"\n{BOLD}{BCYAN}── {title} {line}{R}")


def volt_color(v: float) -> str:
    # EN 50160: 230V ±10% → 207–253V is normal
    if 207 <= v <= 253:
        return BGREEN
    if 195 <= v <= 260:
        return BYELLOW
    return BRED


# --- output ---
section("Power Flow")
PV_MAX   = 12.0
BAT_MAX  =  5.0
GRID_MAX =  8.0
HOME_MAX = 10.0

print(f"  {BYELLOW}PV      {R} {bar(pv_kw,   PV_MAX,   BYELLOW)}  {BYELLOW}{pv_kw:>6.3f} kW{R}")

bat_color = BCYAN if battery_kw < 0 else BYELLOW
bat_label = "charge" if battery_kw < 0 else "discharge"
print(f"  {bat_color}Battery {R} {bar(battery_kw, BAT_MAX, bat_color)}  {bat_color}{abs(battery_kw):>6.3f} kW  {bat_label}{R}")

grid_color = BRED if grid_kw < 0 else BGREEN
grid_label = "import" if grid_kw < 0 else "export"
print(f"  {grid_color}Grid    {R} {bar(grid_kw,  GRID_MAX, grid_color)}  {grid_color}{abs(grid_kw):>6.3f} kW  {grid_label}{R}")

print(f"  {BWHITE}Home    {R} {bar(home_kw, HOME_MAX, BWHITE)}  {BWHITE}{home_kw:>6.3f} kW{R}")
print(f"  {DIM}Inv AC  {R} {DIM}{bar(ac_kw,   HOME_MAX, '')}  {ac_kw:>6.3f} kW{R}")

section("Grid Phases")
CURR_MAX = 16.0
for label, v, a in [("L1", l1_v, l1_a), ("L2", l2_v, l2_a), ("L3", l3_v, l3_a)]:
    vc = volt_color(v)
    print(f"  {BOLD}{label}{R}  {vc}{v:>5.1f} V{R}  {bar(a, CURR_MAX, BBLUE, 16)}  {BBLUE}{a:>4.1f} A{R}")

section("Mode & Controls")
print(f"  Working Mode   {BOLD}{BCYAN}{working_mode}{R}")
print(f"  Export Limit   {on_off(export_enable)}  {export_value:.1f} kW")
print(f"  Import Limit   {on_off(import_enable)}  {import_value:.1f} kVA")
print(f"  Low SOC Limit  {on_off(low_soc_enable)}  {low_soc_value:.0f} %")
if working_mode_raw == WORKING_MODES["ems-battery"]:
    sched_color = BYELLOW if batt_power_sched_kw > 0 else BCYAN
    print(f"  Batt Sched     {sched_color}{batt_power_sched_kw:>+7.2f} kW{R}  (+discharge / -charge)")
    print(f"  PV Sched       {BYELLOW}{pv_power_sched_kw:>7.2f} kW{R}  (0 = curtailed)")

section("Diagnostics")
bms_color = BGREEN if bms_running_status in (1, 2, 3) else DIM
print(f"  BMS Status     {bms_color}{bms_running_label}{R}")
print(f"  Energy Total   {energy_total_kwh:.1f} kWh")
print(f"  {DIM}Battery Brand  {battery_brand}  Protocol {battery_protocol}{R}")
print()

