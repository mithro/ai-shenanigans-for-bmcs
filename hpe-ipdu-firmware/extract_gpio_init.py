#!/usr/bin/env python3
"""Extract GPIO initialisation code from the decompressed firmware.

Finds functions that write to GPIO configuration registers and extracts
the values being written, to determine the actual GPIO pin assignments
used by the HPE iPDU board.

Strategy:
1. Find literal pool entries containing GPIO config register addresses
2. Find LDR instructions that reference those pool entries
3. Trace the surrounding code to find what values are STR'd to those registers
4. Decode the GPIO configuration values into per-pin settings
"""

import os
import re
import struct
import subprocess
import sys
from collections import defaultdict

EXTRACT_DIR = "extracted"
BASE_ADDR = 0x00004000

# GPIO configuration registers
GPIO_CONFIG_REGS = {
    0x90600010: ("GPIO Config #1", 0, 7),
    0x90600014: ("GPIO Config #2", 8, 15),
    0x90600018: ("GPIO Config #3", 16, 23),
    0x9060001C: ("GPIO Config #4", 24, 31),
    0x90600020: ("GPIO Config #5", 32, 39),
    0x90600024: ("GPIO Config #6", 40, 47),
    0x90600028: ("GPIO Config #7", 48, 49),
    0x90600100: ("GPIO Config #8", 50, 57),
    0x90600104: ("GPIO Config #9", 58, 65),
    0x90600108: ("GPIO Config #10", 66, 72),
}

GPIO_CONTROL_REGS = {
    0x90600030: ("GPIO Control #1", 0, 31),
    0x90600034: ("GPIO Control #2", 32, 49),
    0x90600120: ("GPIO Control #3", 50, 72),
}

# Pin mux functions from NS9360 datasheet
PIN_MUX = {
    0: {  # gpio[0]
        0: "Ser B TXData / SPI B dout",
        1: "LCD d[10]",
        2: "IEEE 1284 Data[2]",
        3: "GPIO",
    },
    1: {0: "Ser B RXData / SPI B din", 1: "LCD d[11]", 2: "1284 Data[3]", 3: "GPIO"},
    2: {0: "Ser B RTS", 1: "LCD d[12]", 2: "1284 Data[4]", 3: "GPIO"},
    3: {0: "Ser B CTS", 1: "LCD d[13]", 2: "1284 Data[5]", 3: "GPIO"},
    4: {0: "Ser B DTR", 1: "LCD d[14]", 2: "1284 Data[6]", 3: "GPIO"},
    5: {0: "Ser B DSR", 1: "LCD d[15]", 2: "1284 Data[7]", 3: "GPIO"},
    6: {0: "Ser B RI / SPI B clk", 1: "LCD d[16]", 2: "1284 nFault", 3: "GPIO"},
    7: {0: "Ser B DCD / SPI B enable", 1: "LCD d[17]", 2: "1284 nAck", 3: "GPIO"},
    8: {0: "Ser A TXData / SPI A dout", 1: "LCD d[2]", 2: "1284 nSel", 3: "GPIO"},
    9: {0: "Ser A RXData / SPI A din", 1: "LCD d[3]", 2: "1284 PE", 3: "GPIO"},
    10: {0: "Ser A RTS", 1: "LCD d[4]", 2: "1284 nError", 3: "GPIO"},
    11: {0: "Ser A CTS", 1: "LCD d[5]", 2: "1284 Busy", 3: "GPIO"},
    12: {0: "Ser A DTR", 1: "LCD d[6]", 2: "USB OC", 3: "GPIO"},
    13: {0: "Ser A DSR", 1: "LCD d[7]", 2: "USB PWR EN", 3: "GPIO"},
    14: {0: "Ser A RI / SPI A clk", 1: "LCD d[8]", 2: "1284 nInit", 3: "GPIO"},
    15: {0: "Ser A DCD / SPI A enable", 1: "LCD d[9]", 2: "1284 nAutoFd", 3: "GPIO"},
    16: {0: "Ext IRQ[0]", 1: "DMA Ack 1", 3: "GPIO"},
    17: {0: "Ext IRQ[1]", 1: "DMA Done 1", 3: "GPIO"},
    18: {0: "Ext IRQ[2]", 1: "timer_clk[0]", 3: "GPIO"},
    19: {0: "Ext IRQ[3]", 1: "timer_clk[1]", 3: "GPIO"},
    20: {0: "Ser C DTR", 1: "timer_clk[2]", 3: "GPIO"},
    21: {0: "Ser C DSR", 1: "timer_clk[3]", 3: "GPIO"},
    22: {0: "Ser C RI / SPI C clk", 1: "DMA Done 0", 3: "GPIO"},
    23: {0: "Ser C DCD / SPI C enable", 1: "DMA Ack 0", 3: "GPIO"},
    24: {0: "LCD A[0]", 1: "BIST Done", 3: "GPIO"},
    25: {0: "LCD pclk", 3: "GPIO"},
    26: {0: "LCD lp", 3: "GPIO"},
    27: {0: "LCD fp", 3: "GPIO"},
    28: {0: "LCD ac_bias", 3: "GPIO"},
    29: {0: "LCD d[0]", 3: "GPIO"},
    30: {0: "LCD d[1]", 3: "GPIO"},
    31: {0: "1284 Data[0]", 1: "nBLE[0]", 3: "GPIO"},
    32: {0: "1284 Data[1]", 1: "nBLE[1]", 3: "GPIO"},
    33: {0: "1284 nStrobe", 1: "nBLE[2]", 3: "GPIO"},
    34: {0: "iic_scl", 1: "nBLE[3]", 3: "GPIO"},
    35: {0: "iic_sda", 1: "nCS[4]", 3: "GPIO"},
    36: {0: "nCS[5]", 1: "ext_irq[2]", 3: "GPIO"},
    37: {0: "nCS[6]", 1: "ext_irq[3]", 3: "GPIO"},
    38: {0: "nCS[7]", 1: "ext_irq[1]", 3: "GPIO"},
    39: {0: "DRQ[1]", 1: "ext_irq[0]", 3: "GPIO"},
    40: {0: "Ser C TXData / SPI C dout", 3: "GPIO"},
    41: {0: "Ser C RXData / SPI C din", 3: "GPIO"},
    42: {0: "Ser C RTS", 3: "GPIO"},
    43: {0: "Ser C CTS", 3: "GPIO"},
    44: {0: "Ser D TXData / SPI D dout", 3: "GPIO"},
    45: {0: "Ser D RXData / SPI D din", 3: "GPIO"},
    46: {0: "Ser D RTS", 3: "GPIO"},
    47: {0: "Ser D CTS", 3: "GPIO"},
    48: {0: "Ser D DTR", 3: "GPIO"},
    49: {0: "Ser D DSR", 3: "GPIO"},
    50: {0: "MDIO", 3: "GPIO"},
    51: {0: "rx_dv", 3: "GPIO"},
    52: {0: "rx_er", 3: "GPIO"},
    53: {0: "rxd[0]", 3: "GPIO"},
    54: {0: "rxd[1]", 3: "GPIO"},
    55: {0: "rxd[2]", 3: "GPIO"},
    56: {0: "rxd[3]", 3: "GPIO"},
    57: {0: "tx_en", 3: "GPIO"},
    58: {0: "tx_er", 3: "GPIO"},
    59: {0: "txd[0]", 3: "GPIO"},
    60: {0: "txd[1]", 3: "GPIO"},
    61: {0: "txd[2]", 3: "GPIO"},
    62: {0: "txd[3]", 3: "GPIO"},
    63: {0: "collision", 3: "GPIO"},
    64: {0: "carrier sense", 3: "GPIO"},
    65: {0: "enet_phy_int_n", 3: "GPIO"},
    66: {0: "MDC", 3: "GPIO"},
    67: {0: "rx_clk", 3: "GPIO"},
    68: {0: "tx_clk", 3: "GPIO"},
    69: {0: "DRQ[0]", 1: "nCS[3]", 3: "GPIO"},
    70: {0: "1284 nSelect/nAddr Strobe", 1: "DMA Done 0", 3: "GPIO"},
    71: {0: "USB host overcurrent", 1: "DMA Ack 0", 3: "GPIO"},
    72: {0: "USB host power enable", 1: "DMA Done 1", 3: "GPIO"},
}


def decode_gpio_config_value(reg_addr, value):
    """Decode a GPIO config register value into per-pin settings."""
    if reg_addr not in GPIO_CONFIG_REGS:
        return []

    name, start_pin, end_pin = GPIO_CONFIG_REGS[reg_addr]
    pins = []

    for i in range(min(8, end_pin - start_pin + 1)):
        nibble = (value >> (i * 4)) & 0xF
        pin_num = start_pin + i
        func = nibble & 0x3
        inv = (nibble >> 2) & 1
        direction = (nibble >> 3) & 1

        func_name = PIN_MUX.get(pin_num, {}).get(func, f"Mux{func}")
        dir_str = "output" if direction else "input"
        inv_str = " (inverted)" if inv else ""

        if func == 3:
            mode = f"GPIO {dir_str}{inv_str}"
        else:
            mode = func_name

        pins.append({
            'pin': pin_num,
            'nibble': nibble,
            'func': func,
            'mode': mode,
            'dir': direction,
            'inv': inv,
        })

    return pins


def find_gpio_init_regions(data):
    """Find regions in the binary where GPIO config register addresses cluster.

    These regions are the GPIO init functions -- they contain literal pool
    entries for multiple GPIO config register addresses near each other.
    """
    # Find all occurrences of GPIO config register addresses as BE 32-bit words
    all_gpio_addrs = {}
    all_gpio_addrs.update(GPIO_CONFIG_REGS)

    gpio_pool_locations = defaultdict(list)  # reg_addr -> [file_offsets]

    for reg_addr in all_gpio_addrs:
        needle = struct.pack('>I', reg_addr)
        pos = 0
        while True:
            pos = data.find(needle, pos)
            if pos == -1:
                break
            gpio_pool_locations[reg_addr].append(pos)
            pos += 4

    # Group pool entries by proximity to find GPIO init functions
    # Collect all pool entries with their file offsets
    all_entries = []
    for reg_addr, offsets in gpio_pool_locations.items():
        for off in offsets:
            all_entries.append((off, reg_addr))

    all_entries.sort()

    # Cluster entries within 256 bytes of each other
    clusters = []
    current_cluster = []
    for off, reg_addr in all_entries:
        if current_cluster and off - current_cluster[-1][0] > 256:
            if len(current_cluster) >= 3:  # At least 3 different GPIO regs
                clusters.append(current_cluster)
            current_cluster = []
        current_cluster.append((off, reg_addr))
    if current_cluster and len(current_cluster) >= 3:
        clusters.append(current_cluster)

    return clusters


def disassemble_region(bin_path, start_offset, size, base_addr):
    """Disassemble a specific region of the binary."""
    with open(bin_path, 'rb') as f:
        f.seek(start_offset)
        region_data = f.read(size)

    # Write to temp file
    tmp_path = os.path.join(EXTRACT_DIR, "tmp_region.bin")
    with open(tmp_path, 'wb') as f:
        f.write(region_data)

    vma = base_addr + start_offset
    cmd = [
        "arm-linux-gnueabi-objdump",
        "-D",
        "-b", "binary",
        "-m", "arm",
        "-EB",
        "--adjust-vma", hex(vma),
        tmp_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    os.remove(tmp_path)

    if result.returncode != 0:
        return ""
    return result.stdout


def find_config_values_near_pool(data, pool_offsets, search_range=512):
    """Search around GPIO config register pool entries for likely config values.

    In ARM code, the GPIO init pattern is typically:
        LDR R0, =0x90600010    ; GPIO Config register address
        LDR R1, =0x33003300    ; Value to write
        STR R1, [R0]           ; Write config

    The value to write is also usually in the literal pool nearby.
    We look for 32-bit values near the register address that look like
    valid GPIO config values (nibble patterns with 0x0-0xF per pin).
    """
    values = []
    for off in pool_offsets:
        # Scan the literal pool area around this entry
        search_start = max(0, off - search_range)
        search_end = min(len(data), off + search_range)

        for pos in range(search_start, search_end, 4):
            word = struct.unpack_from('>I', data, pos)[0]
            # Skip if this is a known register address
            if word in GPIO_CONFIG_REGS or word in GPIO_CONTROL_REGS:
                continue
            # Skip if this looks like code (ARM instruction)
            if (word & 0xF0000000) == 0xE0000000:  # Unconditional ARM
                continue
            if word == 0:
                continue
            # Skip addresses that look like they're in the code/data region
            if 0x00004000 <= word <= 0x007FFFFF:
                continue
            # Skip BBus addresses
            if 0x90000000 <= word <= 0xA0FFFFFF:
                continue

            values.append((pos, word))

    return values


def extract_gpio_data_table(data):
    """Look for a contiguous table of GPIO config values.

    NET+OS BSP typically has a data structure with all GPIO config values
    stored sequentially. Look for sequences of 10 words (one per GPIO config
    register) that decode to valid pin configurations.
    """
    results = []

    # GPIO config registers are accessed sequentially in the BSP
    # The values for all 10 registers might be stored as a table
    # Each config register holds 8 nibbles (4 bits each), total 32 bits

    # Look for patterns where 10 consecutive 32-bit words could be
    # GPIO config values. A valid config value has nibbles 0x0-0xF,
    # and we expect most pins to be in mux-0 (0x0) or GPIO mode (0x3/0xB/0xF).

    for offset in range(0, len(data) - 40, 4):
        words = [struct.unpack_from('>I', data, offset + i * 4)[0] for i in range(10)]

        # Check if these look like GPIO config values
        # Heuristic: most nibbles should be 0x0 (default peripheral),
        # 0x3 (GPIO input), or 0xB (GPIO output)
        valid_nibble_count = 0
        total_nibbles = 0
        for word in words:
            for j in range(8):
                nibble = (word >> (j * 4)) & 0xF
                total_nibbles += 1
                if nibble in (0x0, 0x3, 0x7, 0xB, 0xF):
                    valid_nibble_count += 1

        # Need at least 70% valid nibbles and not all zeros
        if (valid_nibble_count > total_nibbles * 0.7 and
                any(w != 0 for w in words) and
                not any(0x90000000 <= w <= 0xFFFFFFFF for w in words)):
            results.append((offset, words))

    return results


def main():
    os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__))))

    fw_name = "2.0.51.12_Z7550-02475"
    bin_path = os.path.join(EXTRACT_DIR, f"{fw_name}_decompressed.bin")

    if not os.path.exists(bin_path):
        print(f"Error: {bin_path} not found")
        sys.exit(1)

    with open(bin_path, 'rb') as f:
        data = f.read()

    print(f"Firmware: {bin_path} ({len(data):,} bytes)")
    print(f"Load address: 0x{BASE_ADDR:08X}")

    # 1. Find GPIO init function clusters
    print(f"\n{'='*70}")
    print(f"  GPIO Init Function Clusters (literal pool analysis)")
    print(f"{'='*70}")

    clusters = find_gpio_init_regions(data)
    for i, cluster in enumerate(clusters):
        start_off = cluster[0][0]
        end_off = cluster[-1][0]
        regs_in_cluster = set(addr for _, addr in cluster)

        print(f"\n  Cluster {i+1}: offsets 0x{start_off:X}-0x{end_off:X} "
              f"(addresses 0x{BASE_ADDR+start_off:08X}-0x{BASE_ADDR+end_off:08X})")
        print(f"  Contains {len(cluster)} GPIO register references "
              f"({len(regs_in_cluster)} unique registers):")
        for reg_addr in sorted(regs_in_cluster):
            name = GPIO_CONFIG_REGS.get(reg_addr, (f"0x{reg_addr:08X}",))[0]
            pool_offs = [off for off, ra in cluster if ra == reg_addr]
            print(f"    {name}: pool @ {', '.join(f'0x{o:X}' for o in pool_offs)}")

        # Disassemble the region before the literal pool (the actual code)
        # The code is typically 256-1024 bytes before the literal pool
        code_start = max(0, start_off - 1024)
        code_end = end_off + 64
        print(f"\n  Disassembling 0x{BASE_ADDR+code_start:08X}-0x{BASE_ADDR+code_end:08X}:")

        disasm = disassemble_region(bin_path, code_start, code_end - code_start, BASE_ADDR)
        if disasm:
            lines = disasm.split('\n')
            # Find STR instructions and LDR instructions referencing GPIO regs
            interesting = []
            for line in lines:
                if ':' not in line or '\t' not in line:
                    continue
                lower = line.lower()
                # Show STR, LDR, and branch instructions
                for pattern in ['str\t', 'str ', 'ldr\t', 'ldr ', 'bl\t', 'bl ',
                                '.word\t0x9060', '.word\t0x0']:
                    if pattern in lower:
                        interesting.append(line.strip())
                        break

            for line in interesting[:80]:
                print(f"      {line}")
            if len(interesting) > 80:
                print(f"      ... ({len(interesting)} total interesting instructions)")

    # 2. Extract actual GPIO config values from the init function
    print(f"\n{'='*70}")
    print(f"  GPIO Configuration Value Extraction")
    print(f"{'='*70}")

    # Focus on the first cluster (0x000A97xx) which is likely the BSP init
    # The pattern in NET+OS is typically:
    #   - A table of (register_address, value) pairs
    #   - Or sequential LDR/STR pairs

    # Let's look for the data table approach - scan for contiguous config values
    for cluster in clusters:
        start_off = cluster[0][0]
        end_off = cluster[-1][0]

        # Look at the literal pool entries adjacent to GPIO register addresses
        # These are likely the values being written
        print(f"\n  Examining cluster at 0x{BASE_ADDR+start_off:08X}:")

        # Dump the literal pool region as 32-bit words
        pool_start = start_off - (start_off % 4)
        pool_end = end_off + 64
        print(f"  Literal pool dump (0x{BASE_ADDR+pool_start:08X} - 0x{BASE_ADDR+pool_end:08X}):")

        for pos in range(pool_start, min(pool_end, len(data) - 3), 4):
            word = struct.unpack_from('>I', data, pos)[0]
            annotation = ""
            if word in GPIO_CONFIG_REGS:
                annotation = f"  <-- {GPIO_CONFIG_REGS[word][0]}"
            elif word in GPIO_CONTROL_REGS:
                annotation = f"  <-- {GPIO_CONTROL_REGS[word][0]}"
            elif 0x90600000 <= word <= 0x906FFFFF:
                annotation = f"  <-- BBus GPIO (unknown reg)"
            print(f"    0x{BASE_ADDR+pos:08X}: 0x{word:08X}{annotation}")

    # 3. Direct approach: look for the GPIO init data table
    print(f"\n{'='*70}")
    print(f"  GPIO Data Table Search")
    print(f"{'='*70}")

    # In NET+OS BSPs for the NS9360, the GPIO config is typically stored as a
    # structure in the bsp_gpio_pins.c file. Let's search for a table that
    # has 10 entries (one per GPIO config register).

    # Actually, let's try a simpler approach: for each GPIO config register
    # pool entry, look at the value stored 4 bytes before or after it
    # (common pattern in literal pools).

    print(f"\n  Looking for (address, value) pairs in literal pools:")
    for reg_addr, (name, start_pin, end_pin) in sorted(GPIO_CONFIG_REGS.items()):
        needle = struct.pack('>I', reg_addr)
        pos = 0
        while True:
            pos = data.find(needle, pos)
            if pos == -1:
                break

            # Look at surrounding words for potential config values
            print(f"\n  {name} (0x{reg_addr:08X}) at pool offset 0x{pos:X}:")
            # Dump 8 words before and after
            for delta in range(-32, 36, 4):
                check_pos = pos + delta
                if 0 <= check_pos <= len(data) - 4:
                    word = struct.unpack_from('>I', data, check_pos)[0]
                    marker = " <-- THIS" if delta == 0 else ""
                    addr_annotation = ""
                    if word in GPIO_CONFIG_REGS:
                        addr_annotation = f" ({GPIO_CONFIG_REGS[word][0]})"
                    elif word in GPIO_CONTROL_REGS:
                        addr_annotation = f" ({GPIO_CONTROL_REGS[word][0]})"
                    elif 0x90600000 <= word <= 0x906FFFFF:
                        addr_annotation = " (BBus GPIO)"
                    print(f"    [{delta:+4d}] 0x{BASE_ADDR+check_pos:08X}: "
                          f"0x{word:08X}{addr_annotation}{marker}")

            # Try to decode the value at common offsets
            for delta_name, delta in [("before (-4)", -4), ("after (+4)", +4),
                                       ("before (-8)", -8), ("after (+8)", +8)]:
                val_pos = pos + delta
                if 0 <= val_pos <= len(data) - 4:
                    val = struct.unpack_from('>I', data, val_pos)[0]
                    # Try to decode as GPIO config
                    pins = decode_gpio_config_value(reg_addr, val)
                    if pins:
                        # Check if it looks plausible
                        valid = sum(1 for p in pins if p['nibble'] in
                                    (0x0, 0x3, 0x7, 0xB, 0xF))
                        if valid >= len(pins) // 2:
                            print(f"\n    Candidate value ({delta_name}): 0x{val:08X}")
                            for p in pins:
                                print(f"      gpio[{p['pin']:2d}]: 0x{p['nibble']:X} = {p['mode']}")

            pos += 4
            break  # Just show first occurrence per register

    # 4. Alternative: search the full disassembly for the pattern
    print(f"\n{'='*70}")
    print(f"  Searching for GPIO init code patterns in disassembly")
    print(f"{'='*70}")

    # Load the full disassembly if it exists
    disasm_path = os.path.join(EXTRACT_DIR, f"{fw_name}_full_disasm.txt")
    if os.path.exists(disasm_path):
        with open(disasm_path, 'r') as f:
            disasm = f.read()

        # Search for .word entries that are GPIO register addresses
        # and extract the surrounding code
        lines = disasm.split('\n')
        for reg_addr, (name, start_pin, end_pin) in sorted(GPIO_CONFIG_REGS.items()):
            hex_pattern = f".word\t0x{reg_addr:08x}"
            for i, line in enumerate(lines):
                if hex_pattern in line:
                    # Found the literal pool entry. Now find the LDR that references it.
                    pool_addr_str = line.strip().split(':')[0].strip()
                    pool_addr = int(pool_addr_str, 16)

                    print(f"\n  {name} (0x{reg_addr:08X}) pool at 0x{pool_addr:08X}:")

                    # Search backwards for LDR instruction referencing this pool
                    # LDR Rn, [PC, #offset] where PC+8+offset = pool_addr
                    found_ldr = False
                    for j in range(max(0, i-200), i):
                        if 'ldr' in lines[j].lower() and pool_addr_str in lines[j]:
                            print(f"    LDR: {lines[j].strip()}")
                            found_ldr = True

                            # Show context: 10 instructions around the LDR
                            print(f"    Context (10 instructions before/after):")
                            for k in range(max(0, j-10), min(len(lines), j+11)):
                                if ':' in lines[k] and '\t' in lines[k]:
                                    marker = " <<<" if k == j else ""
                                    print(f"      {lines[k].strip()}{marker}")
                            break

                    if not found_ldr:
                        # Also check for the address pattern in comments
                        for j in range(max(0, i-300), i):
                            lower = lines[j].lower()
                            if ('ldr' in lower and
                                    (f'{pool_addr:x}' in lower or
                                     f'{pool_addr:08x}' in lower)):
                                print(f"    LDR (alt): {lines[j].strip()}")
                                found_ldr = True
                                break

                    if not found_ldr:
                        print(f"    (LDR instruction not found in nearby code)")
                    break  # Just first occurrence

    else:
        print("  Full disassembly not available - run analyse_decompressed.py first")


if __name__ == '__main__':
    main()
