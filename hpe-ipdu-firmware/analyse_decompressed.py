#!/usr/bin/env python3
"""Analyse decompressed HPE iPDU firmware binaries.

Disassembles the big-endian ARM firmware and searches for:
1. GPIO configuration register writes (0x9060_xxxx)
2. BBus peripheral accesses (UART, SPI, I2C, etc.)
3. Memory controller configuration
4. Function prologues and string references
5. Hardware initialisation sequences

The decompressed firmware loads at RAM address 0x00004000.
"""

import os
import re
import struct
import subprocess
import sys
from collections import Counter, defaultdict

EXTRACT_DIR = "extracted"
BASE_ADDR = 0x00004000  # RAM load address from bootHdr

# NS9360 BBus peripheral addresses
BBUS_REGIONS = {
    (0x90000000, 0x901FFFFF): "BBus DMA",
    (0x90200000, 0x9020003F): "SER Port B",
    (0x90200040, 0x9020007F): "SER Port A",
    (0x90300000, 0x9030003F): "SER Port C",
    (0x90300040, 0x9030007F): "SER Port D",
    (0x90400000, 0x904FFFFF): "IEEE 1284",
    (0x90500000, 0x905FFFFF): "I2C",
    (0x90600000, 0x906FFFFF): "BBus Utility (GPIO)",
    (0x90700000, 0x907FFFFF): "RTC",
    (0x90800000, 0x908FFFFF): "USB Host",
    (0x90900000, 0x909FFFFF): "USB Device",
    (0xA0400000, 0xA04FFFFF): "BBus-to-AHB Bridge",
    (0xA0600000, 0xA06FFFFF): "Ethernet",
    (0xA0700000, 0xA07FFFFF): "Memory Controller",
    (0xA0800000, 0xA08FFFFF): "LCD Controller",
    (0xA0900000, 0xA09FFFFF): "System Control",
}

# GPIO configuration register specifics
GPIO_REGS = {
    0x90600010: "GPIO Config #1 (gpio[0]-gpio[7])",
    0x90600014: "GPIO Config #2 (gpio[8]-gpio[15])",
    0x90600018: "GPIO Config #3 (gpio[16]-gpio[23])",
    0x9060001C: "GPIO Config #4 (gpio[24]-gpio[31])",
    0x90600020: "GPIO Config #5 (gpio[32]-gpio[39])",
    0x90600024: "GPIO Config #6 (gpio[40]-gpio[47])",
    0x90600028: "GPIO Config #7 (gpio[48]-gpio[49])",
    0x90600030: "GPIO Control #1 (gpio[0]-gpio[31])",
    0x90600034: "GPIO Control #2 (gpio[32]-gpio[49])",
    0x90600040: "GPIO Status #1 (gpio[0]-gpio[31])",
    0x90600044: "GPIO Status #2 (gpio[32]-gpio[49])",
    0x90600100: "GPIO Config #8 (gpio[50]-gpio[57])",
    0x90600104: "GPIO Config #9 (gpio[58]-gpio[65])",
    0x90600108: "GPIO Config #10 (gpio[66]-gpio[72])",
    0x90600120: "GPIO Control #3 (gpio[50]-gpio[72])",
    0x90600130: "GPIO Status #3 (gpio[50]-gpio[72])",
}

# Serial port register offsets (within each serial port base)
SER_REGS = {
    0x00: "CTRL_A",
    0x04: "CTRL_B",
    0x08: "STATUS_A",
    0x0C: "BITRATE",
    0x10: "FIFO",
    0x14: "RX_BUF_TIMER",
    0x18: "RX_CHAR_TIMER",
    0x1C: "RX_MATCH",
    0x20: "RX_MATCH_MASK",
    0x24: "CTRL_C",
    0x28: "STATUS_B",
    0x2C: "STATUS_C",
    0x30: "FIFO_LAST",
}


def decode_gpio_config(reg_addr, value):
    """Decode a GPIO configuration register value into per-pin settings."""
    reg_name = GPIO_REGS.get(reg_addr, f"0x{reg_addr:08X}")
    # Determine which GPIO pins this register covers
    if reg_addr == 0x90600010:
        start_pin = 0
    elif reg_addr == 0x90600014:
        start_pin = 8
    elif reg_addr == 0x90600018:
        start_pin = 16
    elif reg_addr == 0x9060001C:
        start_pin = 24
    elif reg_addr == 0x90600020:
        start_pin = 32
    elif reg_addr == 0x90600024:
        start_pin = 40
    elif reg_addr == 0x90600028:
        start_pin = 48
    elif reg_addr == 0x90600100:
        start_pin = 50
    elif reg_addr == 0x90600104:
        start_pin = 58
    elif reg_addr == 0x90600108:
        start_pin = 66
    else:
        return []

    pins = []
    for i in range(8):
        nibble = (value >> (i * 4)) & 0xF
        pin_num = start_pin + i
        func = nibble & 0x3
        inv = (nibble >> 2) & 1
        direction = (nibble >> 3) & 1

        func_names = {0: "Mux0 (peripheral)", 1: "Mux1", 2: "Mux2", 3: "GPIO"}
        dir_names = {0: "input", 1: "output"}

        pins.append({
            'pin': pin_num,
            'func': func,
            'func_name': func_names[func],
            'inv': inv,
            'dir': direction,
            'dir_name': dir_names[direction] if func == 3 else "N/A",
        })
    return pins


def disassemble_full(bin_path, base_addr, output_path):
    """Full disassembly of a big-endian ARM binary."""
    cmd = [
        "arm-linux-gnueabi-objdump",
        "-D",
        "-b", "binary",
        "-m", "arm",
        "-EB",
        "--adjust-vma", hex(base_addr),
        bin_path,
    ]
    print(f"  Running objdump (this may take a while for ~8MB binary)...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        print(f"  objdump failed: {result.stderr}")
        return None

    with open(output_path, 'w') as f:
        f.write(result.stdout)
    print(f"  Saved full disassembly to {output_path} ({len(result.stdout):,} bytes)")
    return result.stdout


def find_mmio_accesses(disasm_text):
    """Find all references to memory-mapped I/O addresses in disassembly.

    ARM code typically uses two patterns to load 32-bit constants:
    1. MOV + ORR (or MOVW + MOVT on ARMv6T2+):
       mov r0, #0x90600000
       orr r0, r0, #0x10

    2. LDR from literal pool:
       ldr r0, [pc, #offset]
       ; literal pool contains 0x90600010

    We search for both patterns by looking for known address constants
    appearing in the instruction operands or data words.
    """
    results = defaultdict(list)
    lines = disasm_text.split('\n')

    # Pattern 1: Look for hex constants in instruction operands
    hex_pattern = re.compile(r'0x([0-9a-f]{7,8})', re.IGNORECASE)

    for i, line in enumerate(lines):
        if ':' not in line or '\t' not in line:
            continue

        matches = hex_pattern.findall(line)
        for match in matches:
            try:
                addr = int(match, 16)
            except ValueError:
                continue

            # Check if this address falls in a known peripheral region
            for (start, end), name in BBUS_REGIONS.items():
                if start <= addr <= end:
                    results[name].append((line.strip(), addr))
                    break

            # Also check for specific GPIO register addresses
            if addr in GPIO_REGS:
                results[f"GPIO: {GPIO_REGS[addr]}"].append((line.strip(), addr))

    return results


def find_string_refs(data, base_addr):
    """Find interesting strings in the binary and their addresses."""
    strings_of_interest = [
        b'NS9360',
        b'Brookline',
        b'Brooklyn',
        b'GPIO',
        b'gpio',
        b'SPI',
        b'UART',
        b'uart',
        b'serial',
        b'Serial',
        b'baud',
        b'Baud',
        b'MAXQ',
        b'maxq',
        b'I2C',
        b'i2c',
        b'SNMP',
        b'HTTP',
        b'Telnet',
        b'telnet',
        b'FTP',
        b'flash',
        b'Flash',
        b'FLASH',
        b'NET+OS',
        b'NET+ARM',
        b'ThreadX',
        b'RomPager',
        b'Allegro',
        b'Copyright',
        b'version',
        b'Version',
        b'iPDU',
        b'HPPDU',
        b'boot',
        b'Boot',
        b'BOOT',
        b'init',
        b'Init',
        b'PLC',
        b'Ethernet',
        b'ethernet',
        b'PHY',
        b'phy',
        b'DHCP',
        b'dhcp',
        b'SSL',
        b'ssl',
        b'TLS',
        b'password',
        b'Password',
        b'login',
        b'Login',
        b'admin',
        b'Admin',
    ]

    found = {}
    for marker in strings_of_interest:
        pos = 0
        locations = []
        while True:
            pos = data.find(marker, pos)
            if pos == -1:
                break
            # Extract context (null-terminated string around this location)
            # Find start of string (scan back for null or non-printable)
            str_start = pos
            while str_start > 0 and data[str_start - 1] >= 32 and data[str_start - 1] < 127:
                str_start -= 1
            # Find end of string
            str_end = pos + len(marker)
            while str_end < len(data) and data[str_end] >= 32 and data[str_end] < 127:
                str_end += 1

            context = data[str_start:str_end].decode('ascii', errors='replace')
            locations.append((base_addr + pos, context))
            pos += 1

        if locations:
            found[marker.decode('ascii', errors='replace')] = locations

    return found


def extract_literal_pool_constants(data, base_addr):
    """Extract 32-bit constants from the binary that look like MMIO addresses.

    In ARM code, literal pools contain 32-bit constants loaded via LDR Rn, [PC, #offset].
    We scan all 4-byte aligned words and collect those in interesting address ranges.
    """
    mmio_refs = defaultdict(list)
    for offset in range(0, len(data) - 3, 4):
        word = struct.unpack_from('>I', data, offset)[0]  # Big-endian

        # Check BBus region
        for (start, end), name in BBUS_REGIONS.items():
            if start <= word <= end:
                mmio_refs[name].append((base_addr + offset, word))
                break

        # Check specific GPIO registers
        if word in GPIO_REGS:
            reg_name = GPIO_REGS[word]
            mmio_refs[f"GPIO: {reg_name}"].append((base_addr + offset, word))

    return mmio_refs


def analyse_vector_table(data, base_addr):
    """Analyse the ARM exception vector table at the start of the binary."""
    print(f"\n  ARM Exception Vector Table (at 0x{base_addr:08X}):")
    vec_names = ['Reset', 'Undef', 'SWI', 'PAbort', 'DAbort', 'Reserved', 'IRQ', 'FIQ']

    for i in range(8):
        word = struct.unpack_from('>I', data, i * 4)[0]
        addr = base_addr + i * 4

        # Decode instruction
        if word == 0xE1A00000:
            desc = "NOP (MOV R0, R0)"
        elif (word & 0x0F000000) == 0x0A000000:
            offset = word & 0x00FFFFFF
            if offset & 0x800000:
                offset -= 0x1000000
            target = addr + 8 + (offset << 2)
            link = "BL" if word & 0x01000000 else "B"
            desc = f"{link} 0x{target:08X}"
        elif (word & 0xFFFF0000) == 0xE59F0000:
            # LDR Rn, [PC, #offset]
            rd = (word >> 12) & 0xF
            imm = word & 0xFFF
            pool_addr = addr + 8 + imm
            pool_offset = pool_addr - base_addr
            if pool_offset < len(data) - 3:
                target = struct.unpack_from('>I', data, pool_offset)[0]
                desc = f"LDR R{rd}, [PC, #0x{imm:X}] → 0x{target:08X}"
            else:
                desc = f"LDR R{rd}, [PC, #0x{imm:X}]"
        else:
            desc = f"0x{word:08X}"

        print(f"    [{i}] {vec_names[i]:8s} @ 0x{addr:08X}: {desc}")

    # Also dump the literal pool that follows
    print(f"\n  Literal pool (0x{base_addr + 0x40:08X} - 0x{base_addr + 0x80:08X}):")
    for i in range(0x40, min(0x80, len(data)), 4):
        word = struct.unpack_from('>I', data, i)[0]
        print(f"    0x{base_addr + i:08X}: 0x{word:08X}")


def find_init_functions(disasm_text, data, base_addr):
    """Find likely hardware initialisation functions.

    Look for functions that write to GPIO config registers, serial port
    registers, or memory controller registers early in the code.
    """
    # Parse disassembly into addressable lines
    lines = disasm_text.split('\n')
    addr_pattern = re.compile(r'^\s*([0-9a-f]+):\s+([0-9a-f]+)\s+(.*)', re.IGNORECASE)

    # Find all STR instructions that reference BBus addresses
    # In ARM, STR patterns to MMIO typically look like:
    #   ldr r0, =0x90600010    ; or mov+orr sequence
    #   ldr r1, =0x00330033    ; value
    #   str r1, [r0]           ; write
    #
    # We look for clusters of LDR + STR targeting BBus addresses.

    store_instructions = []
    for i, line in enumerate(lines):
        m = addr_pattern.match(line)
        if not m:
            continue
        addr_str, opcode_str, asm = m.groups()
        asm_lower = asm.lower().strip()

        # Check for STR instructions
        if asm_lower.startswith('str'):
            store_instructions.append((int(addr_str, 16), asm.strip(), i))

    return store_instructions


def main():
    os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__))))

    # Use the latest firmware version
    fw_name = "2.0.51.12_Z7550-02475"
    bin_path = os.path.join(EXTRACT_DIR, f"{fw_name}_decompressed.bin")

    if not os.path.exists(bin_path):
        print(f"Error: {bin_path} not found. Run decompress_firmware.py first.")
        sys.exit(1)

    with open(bin_path, 'rb') as f:
        data = f.read()

    print(f"Firmware: {bin_path} ({len(data):,} bytes)")
    print(f"Load address: 0x{BASE_ADDR:08X}")

    # 1. Analyse vector table
    analyse_vector_table(data, BASE_ADDR)

    # 2. Find interesting strings
    print(f"\n{'='*70}")
    print(f"  String Analysis")
    print(f"{'='*70}")
    strings = find_string_refs(data, BASE_ADDR)
    for marker, locations in sorted(strings.items()):
        print(f"\n  \"{marker}\" ({len(locations)} occurrences):")
        for addr, context in locations[:5]:
            # Truncate long contexts
            if len(context) > 80:
                context = context[:77] + "..."
            print(f"    0x{addr:08X}: \"{context}\"")
        if len(locations) > 5:
            print(f"    ... ({len(locations)} total)")

    # 3. Scan for MMIO address constants in literal pools
    print(f"\n{'='*70}")
    print(f"  Memory-Mapped I/O References (literal pool scan)")
    print(f"{'='*70}")
    mmio_refs = extract_literal_pool_constants(data, BASE_ADDR)
    for name, refs in sorted(mmio_refs.items()):
        print(f"\n  {name} ({len(refs)} references):")
        # Group by target address
        by_target = defaultdict(list)
        for pool_addr, target_addr in refs:
            by_target[target_addr].append(pool_addr)
        for target_addr, pool_addrs in sorted(by_target.items()):
            reg_info = GPIO_REGS.get(target_addr, "")
            if reg_info:
                reg_info = f" ({reg_info})"
            print(f"    0x{target_addr:08X}{reg_info}: referenced from {len(pool_addrs)} literal pool entries")
            for pa in pool_addrs[:3]:
                print(f"      pool @ 0x{pa:08X}")
            if len(pool_addrs) > 3:
                print(f"      ... ({len(pool_addrs)} total)")

    # 4. Full disassembly (save to file)
    print(f"\n{'='*70}")
    print(f"  Full Disassembly")
    print(f"{'='*70}")
    disasm_path = os.path.join(EXTRACT_DIR, f"{fw_name}_full_disasm.txt")
    if os.path.exists(disasm_path):
        print(f"  Loading existing disassembly from {disasm_path}")
        with open(disasm_path, 'r') as f:
            disasm_text = f.read()
    else:
        disasm_text = disassemble_full(bin_path, BASE_ADDR, disasm_path)
        if disasm_text is None:
            print("  Disassembly failed, skipping analysis")
            return

    # 5. Find MMIO accesses in disassembly
    print(f"\n{'='*70}")
    print(f"  MMIO Access Analysis (from disassembly)")
    print(f"{'='*70}")
    mmio_access = find_mmio_accesses(disasm_text)
    for name, refs in sorted(mmio_access.items()):
        print(f"\n  {name} ({len(refs)} references):")
        for line, addr in refs[:10]:
            print(f"    {line}")
        if len(refs) > 10:
            print(f"    ... ({len(refs)} total)")

    # 6. Look for GPIO configuration writes
    print(f"\n{'='*70}")
    print(f"  GPIO Configuration Analysis")
    print(f"{'='*70}")

    # Scan the binary for GPIO config register addresses in literal pools,
    # then look at nearby code for the values being written
    gpio_config_addrs = [
        0x90600010, 0x90600014, 0x90600018, 0x9060001C,
        0x90600020, 0x90600024, 0x90600028,
        0x90600100, 0x90600104, 0x90600108,
    ]

    for gpio_addr in gpio_config_addrs:
        # Search for this address as a big-endian 32-bit word in the binary
        needle = struct.pack('>I', gpio_addr)
        pos = 0
        locations = []
        while True:
            pos = data.find(needle, pos)
            if pos == -1:
                break
            locations.append(BASE_ADDR + pos)
            pos += 4  # Move past this occurrence

        if locations:
            reg_name = GPIO_REGS.get(gpio_addr, f"0x{gpio_addr:08X}")
            print(f"\n  {reg_name} (0x{gpio_addr:08X}):")
            print(f"    Found at {len(locations)} literal pool locations:")
            for loc in locations[:5]:
                print(f"      0x{loc:08X}")

                # Look for nearby code context - find the LDR that references this pool entry
                # The LDR instruction would be at some earlier address:
                # LDR Rn, [PC, #offset] where PC+8+offset = loc
                # So the LDR is at (loc - 8 - offset) for various offsets
                # We can search the disassembly for this address
                loc_hex = f"{loc:x}"
                # Find lines in disassembly referencing this address
                for line in disasm_text.split('\n'):
                    if loc_hex in line and '.word' in line:
                        print(f"        {line.strip()}")
                        break

            if len(locations) > 5:
                print(f"      ... ({len(locations)} total)")

    # 7. Extract function that likely does GPIO init
    # Search for the earliest code that references GPIO config registers
    print(f"\n{'='*70}")
    print(f"  Early Code Analysis (first 4KB after vector table)")
    print(f"{'='*70}")

    # Disassemble just the first 4KB for detailed analysis
    lines = disasm_text.split('\n')
    print(f"\n  First 50 instructions after vector table:")
    count = 0
    for line in lines:
        if ':' not in line or '\t' not in line:
            continue
        # Parse address
        try:
            addr_str = line.strip().split(':')[0].strip()
            addr = int(addr_str, 16)
        except (ValueError, IndexError):
            continue

        if addr >= BASE_ADDR + 0x40:  # After literal pool
            print(f"    {line.strip()}")
            count += 1
            if count >= 50:
                break

    print(f"\n  Done. Full disassembly saved to {disasm_path}")


if __name__ == '__main__':
    main()
