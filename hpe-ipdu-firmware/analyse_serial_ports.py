#!/usr/bin/env python3
"""Analyse serial port configuration from the decompressed firmware.

The NS9360 has 4 serial ports (A-D), each configurable as UART or SPI.
This script finds serial port register references in the firmware and
extracts baud rate divisors, mode settings, and identifies which port
connects to which peripheral.

NS9360 Serial Port Register Map (from HW Reference Manual):
- Port B: 0x9020_0000
- Port A: 0x9020_0040
- Port C: 0x9030_0000
- Port D: 0x9030_0040

Key registers per port (offset from port base):
  0x00: RX/TX FIFO (data)
  0x04: Control A (bit rate, protocol)
  0x08: Control B (interrupts, flow control)
  0x0C: Status A (flags)
  0x10: Bit Rate (divisor)
  0x14: RX Buffer Timer
  0x18: RX Character Timer
  0x1C: RX Match
  0x20: RX Match Mask
  0x24: Control C (gap timer, RX idle)
"""

import os
import re
import struct
import subprocess
from collections import defaultdict

EXTRACT_DIR = "extracted"
BASE_ADDR = 0x00004000

# NS9360 serial port base addresses
SERIAL_PORTS = {
    0x90200000: "Port B",
    0x90200040: "Port A",
    0x90300000: "Port C",
    0x90300040: "Port D",
}

# Serial port register offsets
SERIAL_REGS = {
    0x00: "RX/TX FIFO",
    0x04: "Control A",
    0x08: "Control B",
    0x0C: "Status A",
    0x10: "Bit Rate",
    0x14: "RX Buffer Timer",
    0x18: "RX Char Timer",
    0x1C: "RX Match",
    0x20: "RX Match Mask",
    0x24: "Control C",
}

# BBus clock frequency (system clock / 4)
# With 29.4912 MHz crystal at full PLL: 176.9472 / 4 = 44.2368 MHz
BBUS_CLOCK_HZ = 44_236_800


def decode_control_a(value):
    """Decode Control A register fields."""
    fields = {}
    # Bit 31: CE (clock enable)
    fields["clock_enable"] = bool(value & (1 << 31))
    # Bit 30: BRG (baud rate gen mode): 0=internal, 1=external
    fields["baud_ext"] = bool(value & (1 << 30))
    # Bits 29-28: Mode: 00=UART, 01=HDLC, 10=SPI, 11=reserved
    mode = (value >> 28) & 0x3
    fields["mode"] = {0: "UART", 1: "HDLC", 2: "SPI", 3: "reserved"}[mode]
    # Bit 27: LOOP (loopback)
    fields["loopback"] = bool(value & (1 << 27))
    # Bit 26: WLS (word length select for UART): 0=7bit, 1=8bit
    fields["data_bits"] = 8 if (value & (1 << 26)) else 7
    # Bit 25: STB (stop bits): 0=1 stop, 1=2 stop
    fields["stop_bits"] = 2 if (value & (1 << 25)) else 1
    # Bits 24-23: PEN, EPS (parity)
    pen = bool(value & (1 << 24))
    eps = bool(value & (1 << 23))
    if not pen:
        fields["parity"] = "none"
    elif eps:
        fields["parity"] = "even"
    else:
        fields["parity"] = "odd"
    # Bits 22-20: DTR mode
    fields["dtr_mode"] = (value >> 20) & 0x7
    # Bit 19: RTS auto
    fields["rts_auto"] = bool(value & (1 << 19))
    # Bit 18: CTS auto
    fields["cts_auto"] = bool(value & (1 << 18))
    # Bit 17: RxIMask (RX interrupt mask)
    fields["rx_int_mask"] = bool(value & (1 << 17))
    # Bit 16: TxIMask (TX interrupt mask)
    fields["tx_int_mask"] = bool(value & (1 << 16))
    fields["raw"] = f"0x{value:08X}"
    return fields


def baud_from_divisor(divisor):
    """Calculate baud rate from the bit rate divisor register.

    NS9360 baud rate formula:
    Baud = BBus_clock / (16 * (N + 1))
    where N is the 16-bit value in the Bit Rate register.
    """
    if divisor == 0:
        return BBUS_CLOCK_HZ // 16
    n = divisor & 0xFFFF
    return BBUS_CLOCK_HZ // (16 * (n + 1))


def divisor_for_baud(baud):
    """Calculate the expected divisor for a target baud rate."""
    n = (BBUS_CLOCK_HZ // (16 * baud)) - 1
    return n


def find_serial_register_refs(data, base_addr):
    """Find all references to serial port registers in literal pools.

    Scans the firmware for 32-bit values that match serial port register
    addresses. Returns a dict keyed by (port_name, register_name) with
    lists of firmware addresses where each is referenced.
    """
    refs = defaultdict(list)

    for offset in range(0, len(data) - 3, 4):
        word = struct.unpack_from('>I', data, offset)[0]

        for port_base, port_name in SERIAL_PORTS.items():
            for reg_offset, reg_name in SERIAL_REGS.items():
                reg_addr = port_base + reg_offset
                if word == reg_addr:
                    fw_addr = base_addr + offset
                    refs[(port_name, reg_name, reg_addr)].append(fw_addr)

    return refs


def find_baud_rate_values(data, base_addr):
    """Search for common baud rate divisor values stored as 32-bit words.

    Calculate expected divisors and search for them.
    """
    common_bauds = [300, 1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200,
                    230400, 460800]

    print(f"\n  Expected baud rate divisors (BBus clock = {BBUS_CLOCK_HZ:,} Hz):")
    divisor_to_baud = {}
    for baud in common_bauds:
        n = divisor_for_baud(baud)
        actual_baud = baud_from_divisor(n)
        error_pct = abs(actual_baud - baud) / baud * 100
        print(f"    {baud:>7d} baud: N={n:5d} (0x{n:04X}), actual={actual_baud:>7d}, error={error_pct:.2f}%")
        divisor_to_baud[n] = baud

    return divisor_to_baud


def find_serial_init_strings(data, base_addr):
    """Find strings that reference serial port names, baud rates, etc."""
    patterns = [
        rb'[Ss]erial [Pp]ort [ABCD]',
        rb'[Ss]er[A-D]',
        rb'UART',
        rb'uart',
        rb'[Bb]aud',
        rb'[Ss]erial [Cc]onsole',
        rb'[Dd]ebug.*[Ss]erial',
        rb'[Dd]ebug.*[Oo]utput',
        rb'RS-?232',
        rb'SPI [Mm]aster',
        rb'SPI [Ss]lave',
        rb'MAXQ',
        rb'[Dd]isplay',
        rb'[Dd]aisy',
        rb'[Mm]odem',
        rb'NS9360.*[Bb]oard',
        rb'Brookline',
    ]

    print(f"\n  Serial-related strings:")
    found_strings = []
    for pat in patterns:
        regex = re.compile(pat)
        for m in regex.finditer(data):
            start = m.start()
            # Expand to full null-terminated string
            # Find start of string (walk back to null or non-printable)
            str_start = start
            while str_start > 0 and data[str_start - 1] >= 0x20 and data[str_start - 1] < 0x7F:
                str_start -= 1
            # Find end
            str_end = data.find(b'\x00', start)
            if str_end == -1 or str_end - str_start > 512:
                continue
            s = data[str_start:str_end].decode('ascii', errors='replace')
            addr = base_addr + str_start
            if len(s) >= 5:
                found_strings.append((addr, s))

    # Deduplicate
    seen = set()
    for addr, s in sorted(found_strings):
        if s not in seen:
            print(f"    0x{addr:08X}: \"{s}\"")
            seen.add(s)

    return found_strings


def disasm_region(bin_path, file_offset, size, base_addr=BASE_ADDR):
    """Disassemble a specific region as big-endian ARM."""
    with open(bin_path, 'rb') as f:
        f.seek(file_offset)
        region = f.read(size)

    # Use a project-local tmp file, not /tmp
    tmp = os.path.join(EXTRACT_DIR, "tmp_serial_region.bin")
    with open(tmp, 'wb') as f:
        f.write(region)

    vma = base_addr + file_offset
    cmd = [
        "arm-linux-gnueabi-objdump", "-D",
        "-b", "binary", "-m", "arm", "-EB",
        "--adjust-vma", hex(vma),
        tmp,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    os.remove(tmp)
    return result.stdout if result.returncode == 0 else ""


def analyse_serial_init_functions(data, bin_path, base_addr, port_refs):
    """Disassemble code around serial port register references to find init sequences."""
    print(f"\n  Serial port init function analysis:")

    for (port_name, reg_name, reg_addr), ref_addrs in sorted(port_refs.items()):
        if reg_name != "Control A":
            continue  # Focus on Control A (mode/config) references

        print(f"\n    {port_name} {reg_name} (0x{reg_addr:08X}):")
        for ref_addr in ref_addrs:
            file_offset = ref_addr - base_addr
            # Disassemble 64 bytes before the literal pool entry to find the function
            # that uses it. The LDR instruction is typically 4-64 bytes before the
            # literal pool entry.
            func_start = max(0, file_offset - 256)
            func_size = 512
            disasm = disasm_region(bin_path, func_start, func_size, base_addr)
            if not disasm:
                continue

            # Find instructions that reference this pool entry
            lines = disasm.split('\n')
            relevant_lines = []
            for i, line in enumerate(lines):
                if ':' not in line or '\t' not in line:
                    continue
                # Look for STR instructions near LDR of this register
                if f'0x{ref_addr:x}' in line.lower() or f'0x{reg_addr:08x}' in line.lower():
                    # Show context: 10 instructions before and 5 after
                    code_lines = [l for l in lines if ':' in l and '\t' in l]
                    try:
                        idx = code_lines.index(line)
                    except ValueError:
                        continue
                    start_idx = max(0, idx - 10)
                    end_idx = min(len(code_lines), idx + 6)
                    for cl in code_lines[start_idx:end_idx]:
                        relevant_lines.append(cl.strip())

            if relevant_lines:
                print(f"      Referenced at 0x{ref_addr:08X}:")
                for rl in relevant_lines:
                    print(f"        {rl}")


def search_baud_config_table(data, base_addr):
    """Search for a table of baud rate configurations.

    Many NET+OS BSPs have a baud rate configuration table that maps
    user-selectable baud rates to divisor values. Look for arrays
    of common baud rate integers (9600, 19200, 38400, etc.)
    """
    common_bauds_be = [
        struct.pack('>I', b) for b in
        [1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200]
    ]

    print(f"\n  Searching for baud rate configuration tables...")
    # Search for 9600 followed by 19200 within 16 bytes (typical table stride)
    needle_9600 = struct.pack('>I', 9600)
    needle_19200 = struct.pack('>I', 19200)

    pos = 0
    tables_found = []
    while True:
        pos = data.find(needle_9600, pos)
        if pos == -1:
            break

        # Check if 19200 follows within a reasonable stride
        for stride in [4, 8, 12, 16, 20, 24]:
            check_pos = pos + stride
            if check_pos + 4 <= len(data):
                next_val = struct.unpack_from('>I', data, check_pos)[0]
                if next_val == 19200:
                    # Found 9600 followed by 19200!
                    tables_found.append((pos, stride))
                    break
        pos += 4

    for tbl_pos, stride in tables_found:
        addr = base_addr + tbl_pos
        print(f"\n    Possible baud table at 0x{addr:08X} (stride {stride}):")
        # Read entries before and after
        start = max(0, tbl_pos - stride * 4)
        for i in range(12):
            entry_pos = start + i * stride
            if entry_pos + 4 > len(data):
                break
            val = struct.unpack_from('>I', data, entry_pos)[0]
            entry_addr = base_addr + entry_pos
            marker = " <<<" if entry_pos == tbl_pos else ""
            if val in [300, 600, 1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200, 230400, 460800]:
                print(f"      0x{entry_addr:08X}: {val:>10d} = {val} baud{marker}")
            else:
                print(f"      0x{entry_addr:08X}: {val:>10d} (0x{val:08X}){marker}")


def search_debug_serial_string(data, base_addr):
    """Find the Brookline board debug serial port string and trace its reference."""
    marker = b"NS9360 Brookline Board Debug Output Serial port"
    pos = data.find(marker)
    if pos == -1:
        print("\n  Brookline debug serial string not found!")
        return

    str_addr = base_addr + pos
    print(f"\n  Board debug string at 0x{str_addr:08X}")

    # Find what references this string address (look for it in literal pools)
    str_addr_bytes = struct.pack('>I', str_addr)
    ref_pos = 0
    refs = []
    while True:
        ref_pos = data.find(str_addr_bytes, ref_pos)
        if ref_pos == -1:
            break
        refs.append(base_addr + ref_pos)
        ref_pos += 4

    if refs:
        print(f"  Referenced from literal pools at:")
        for ref in refs:
            print(f"    0x{ref:08X}")

    # Dump 128 bytes before and after the string to find nearby port config
    dump_start = max(0, pos - 128)
    dump_end = min(len(data), pos + len(marker) + 128)
    print(f"\n  Context around debug serial string:")
    for i in range(dump_start, dump_end, 16):
        hex_part = ' '.join(f'{data[j]:02X}' for j in range(i, min(i + 16, dump_end)))
        ascii_part = ''.join(
            chr(data[j]) if 32 <= data[j] < 127 else '.'
            for j in range(i, min(i + 16, dump_end))
        )
        marker_flag = ""
        if i <= pos < i + 16:
            marker_flag = " <<<"
        print(f"    {base_addr+i:08X}: {hex_part:<48s} {ascii_part}{marker_flag}")


def count_port_references(port_refs):
    """Count total references per port to estimate which are most active."""
    port_totals = defaultdict(int)
    port_regs = defaultdict(set)

    for (port_name, reg_name, reg_addr), ref_addrs in port_refs.items():
        count = len(ref_addrs)
        port_totals[port_name] += count
        port_regs[port_name].add(reg_name)

    print(f"\n  Port reference summary:")
    for port_name in ["Port A", "Port B", "Port C", "Port D"]:
        total = port_totals[port_name]
        regs = port_regs[port_name]
        print(f"    {port_name}: {total:3d} references across {len(regs)} register types")
        if regs:
            for reg in sorted(regs):
                key = next(k for k in port_refs.keys() if k[0] == port_name and k[1] == reg)
                count = len(port_refs[key])
                print(f"      {reg}: {count} refs")


def main():
    os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__))))

    fw_name = "2.0.51.12_Z7550-02475"
    bin_path = os.path.join(EXTRACT_DIR, f"{fw_name}_decompressed.bin")

    with open(bin_path, 'rb') as f:
        data = f.read()

    print(f"Firmware: {bin_path} ({len(data):,} bytes)")

    # 1. Find all serial port register references
    print(f"\n{'='*70}")
    print(f"  Serial Port Register References")
    print(f"{'='*70}")
    port_refs = find_serial_register_refs(data, BASE_ADDR)

    for (port_name, reg_name, reg_addr), ref_addrs in sorted(port_refs.items()):
        print(f"\n  {port_name} {reg_name} (0x{reg_addr:08X}): {len(ref_addrs)} references")
        for addr in ref_addrs[:5]:
            print(f"    0x{addr:08X}")
        if len(ref_addrs) > 5:
            print(f"    ... ({len(ref_addrs)} total)")

    # 2. Port reference summary
    print(f"\n{'='*70}")
    print(f"  Port Usage Summary")
    print(f"{'='*70}")
    count_port_references(port_refs)

    # 3. Find baud rate divisors
    print(f"\n{'='*70}")
    print(f"  Baud Rate Analysis")
    print(f"{'='*70}")
    divisor_to_baud = find_baud_rate_values(data, BASE_ADDR)

    # Search for divisor values in the binary
    print(f"\n  Searching for baud rate divisor values in firmware...")
    for divisor, baud in sorted(divisor_to_baud.items()):
        if divisor < 0 or divisor > 0xFFFF:
            continue
        # Search as 32-bit big-endian values
        needle32 = struct.pack('>I', divisor)
        count = 0
        pos = 0
        locations = []
        while True:
            pos = data.find(needle32, pos)
            if pos == -1:
                break
            locations.append(BASE_ADDR + pos)
            count += 1
            pos += 4
        if count > 0 and count < 50:
            print(f"    Divisor {divisor} ({baud} baud): {count} occurrences")
            for loc in locations[:5]:
                print(f"      0x{loc:08X}")

    # 4. Search for baud rate config tables
    print(f"\n{'='*70}")
    print(f"  Baud Rate Configuration Tables")
    print(f"{'='*70}")
    search_baud_config_table(data, BASE_ADDR)

    # 5. Find serial-related strings
    print(f"\n{'='*70}")
    print(f"  Serial-Related Strings")
    print(f"{'='*70}")
    find_serial_init_strings(data, BASE_ADDR)

    # 6. Trace the debug serial port string
    print(f"\n{'='*70}")
    print(f"  Debug Serial Port Configuration")
    print(f"{'='*70}")
    search_debug_serial_string(data, BASE_ADDR)

    # 7. Analyse serial init functions
    print(f"\n{'='*70}")
    print(f"  Serial Init Function Disassembly")
    print(f"{'='*70}")
    analyse_serial_init_functions(data, bin_path, BASE_ADDR, port_refs)


if __name__ == '__main__':
    main()
