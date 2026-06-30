#!/usr/bin/env python3
"""Deep binary analysis of HPE iPDU firmware.

This script performs deeper analysis that goes beyond string searching:
1. GPIO configuration register value extraction (pattern matching)
2. SPI port-to-MAXQ3180 mapping (via DMA channel cross-reference)
3. I2C device address scanning
4. Serial port baud rate register analysis
5. Interrupt handler mapping
"""

import os
import struct
from collections import defaultdict

EXTRACT_DIR = "extracted"
RAM_BASE = 0x00004000

# ============================================================================
# NS9360 Register Definitions
# ============================================================================

# GPIO Configuration Registers (each controls 8 pins via 4-bit nibbles)
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

# GPIO Control Registers (read/write pin states)
GPIO_CONTROL_REGS = {
    0x90600030: ("GPIO Control #1", 0, 31),
    0x90600034: ("GPIO Control #2", 32, 49),
    0x90600120: ("GPIO Control #3", 50, 72),
}

# Serial Port Base Addresses
SERIAL_PORTS = {
    0x90200000: "Port B",
    0x90200040: "Port A",
    0x90300000: "Port C",
    0x90300040: "Port D",
}

# Serial port register offsets
SER_REG_OFFSETS = {
    0x00: "Ctrl A",
    0x04: "Ctrl B",
    0x08: "Status A",
    0x0C: "Bit Rate",
    0x10: "RX Buf Gap Timer",
    0x14: "RX Char Timer",
    0x18: "RX Match",
    0x1C: "RX Match Mask",
    0x20: "FIFO",
    0x24: "Flow Control",
    0x28: "Flow Force",
}

# I2C Register Base
I2C_BASE = 0x90500000
I2C_REGS = {
    0x90500000: "I2C Slave Address",
    0x90500004: "I2C Data",
    0x90500008: "I2C Status",
    0x9050000C: "I2C Master Address",
    0x90500010: "I2C Configuration",
}

# DMA Channel Control Registers
DMA_BASE = 0xA0700000
DMA_CHANNEL_SPACING = 0x20

# Ethernet MAC
ETH_BASE = 0xA0600000

# Pin MUX table (from NS9360 datasheet, Table 11)
PIN_MUX = {
    0: {0: "Ser B TXData / SPI B dout", 1: "LCD d[10]", 2: "1284 Data[2]", 3: "GPIO"},
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


def decode_gpio_config(reg_addr, value):
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
        if func == 3:
            dir_str = "output" if direction else "input"
            inv_str = " (inv)" if inv else ""
            mode = f"GPIO {dir_str}{inv_str}"
        else:
            mode = func_name
        pins.append((pin_num, nibble, mode))
    return pins


def find_all_mmio_refs(data, base_addr_prefix):
    """Find all big-endian 32-bit values matching a base address prefix.

    E.g., base_addr_prefix=0x9060 finds all references to 0x9060xxxx addresses.
    """
    prefix_bytes = struct.pack('>H', base_addr_prefix)
    results = []
    pos = 0
    while pos < len(data) - 3:
        pos = data.find(prefix_bytes, pos)
        if pos == -1:
            break
        if pos % 4 == 0:  # Aligned to 4 bytes (likely a literal pool entry)
            word = struct.unpack_from('>I', data, pos)[0]
            results.append((pos, word))
        pos += 1
    return results


def analyse_gpio_config_values(data):
    """Extract GPIO configuration values using pattern-matched literal pool analysis.

    Strategy: Find each GPIO config register address in the literal pool, then look
    at nearby words that could be the configuration values. Use structural analysis
    of the literal pool to identify (address, value) pairs.
    """
    print("\n  Searching for GPIO config register literal pool entries...")

    # For each GPIO config register, find its literal pool entries
    gpio_pool_entries = {}
    for reg_addr in sorted(GPIO_CONFIG_REGS.keys()):
        needle = struct.pack('>I', reg_addr)
        positions = []
        pos = 0
        while True:
            pos = data.find(needle, pos)
            if pos < 0:
                break
            positions.append(pos)
            pos += 4
        gpio_pool_entries[reg_addr] = positions

    # Group by cluster (entries within 256 bytes of each other)
    all_entries = []
    for reg_addr, positions in gpio_pool_entries.items():
        for pos in positions:
            all_entries.append((pos, reg_addr))
    all_entries.sort()

    clusters = []
    current = []
    for pos, reg_addr in all_entries:
        if current and pos - current[-1][0] > 512:
            if len(current) >= 3:
                clusters.append(current)
            current = []
        current.append((pos, reg_addr))
    if current and len(current) >= 3:
        clusters.append(current)

    print(f"    Found {len(clusters)} GPIO init clusters")

    for ci, cluster in enumerate(clusters):
        regs = set(r for _, r in cluster)
        first_off = cluster[0][0]
        last_off = cluster[-1][0]
        print(f"\n    Cluster {ci+1}: 0x{first_off + RAM_BASE:08X}-0x{last_off + RAM_BASE:08X} "
              f"({len(regs)} unique GPIO config registers)")

        # Dump the literal pool region to identify value patterns
        # In ARM big-endian code, literal pool entries are 4-byte aligned words
        # Look for a pattern where GPIO register addresses alternate with values

        pool_start = first_off - (first_off % 4)
        pool_end = last_off + 64

        print(f"\n    Literal pool dump:")
        prev_was_gpio_addr = False
        for pos in range(pool_start, min(pool_end, len(data) - 3), 4):
            word = struct.unpack_from('>I', data, pos)[0]
            annotation = ""
            is_gpio_addr = False

            if word in GPIO_CONFIG_REGS:
                name, start_pin, end_pin = GPIO_CONFIG_REGS[word]
                annotation = f"  <-- {name} (pins {start_pin}-{end_pin})"
                is_gpio_addr = True
            elif word in GPIO_CONTROL_REGS:
                annotation = f"  <-- {GPIO_CONTROL_REGS[word][0]}"
                is_gpio_addr = True
            elif 0x90600000 <= word <= 0x906FFFFF:
                annotation = "  <-- BBus GPIO (other)"
                is_gpio_addr = True
            elif prev_was_gpio_addr and not (0x90000000 <= word <= 0xFFFFFFFF):
                # This word follows a GPIO address -- might be a config value
                # Try to decode it as a GPIO config value for the previous register
                for prev_pos_check in range(pos - 8, pos, 4):
                    if prev_pos_check >= 0:
                        prev_word = struct.unpack_from('>I', data, prev_pos_check)[0]
                        if prev_word in GPIO_CONFIG_REGS:
                            pins = decode_gpio_config(prev_word, word)
                            if pins:
                                pin_strs = [f"g{p}={m}" for p, _, m in pins]
                                annotation = f"  <-- VALUE? [{', '.join(pin_strs[:4])}...]"
                            break

            print(f"      0x{pos + RAM_BASE:08X}: 0x{word:08X}{annotation}")
            prev_was_gpio_addr = is_gpio_addr


def analyse_serial_port_config(data):
    """Analyse serial port Control A register values to determine UART vs SPI mode.

    NS9360 serial port Control A register bits:
    - Bits [1:0] (WLS): Word Length Select
    - Bits [3:2]: Number of stop bits
    - Bit [4]: Parity enable
    - etc.
    For SPI mode, specific bit patterns indicate SPI operation.
    """
    print("\n  Searching for serial port Control A register values...")

    for port_base, port_name in sorted(SERIAL_PORTS.items()):
        ctrl_a_addr = port_base + 0x00  # Control A register
        ctrl_b_addr = port_base + 0x04  # Control B register
        baud_addr = port_base + 0x0C    # Bit Rate register

        # Find Control A address in literal pool
        ctrl_a_refs = []
        needle = struct.pack('>I', ctrl_a_addr)
        pos = 0
        while True:
            pos = data.find(needle, pos)
            if pos < 0:
                break
            ctrl_a_refs.append(pos)
            pos += 4

        # Find Bit Rate address in literal pool
        baud_refs = []
        needle = struct.pack('>I', baud_addr)
        pos = 0
        while True:
            pos = data.find(needle, pos)
            if pos < 0:
                break
            baud_refs.append(pos)
            pos += 4

        # Count all register references for this port
        total_refs = 0
        reg_types = set()
        for reg_off, reg_name in SER_REG_OFFSETS.items():
            reg_addr = port_base + reg_off
            needle = struct.pack('>I', reg_addr)
            count = 0
            pos = 0
            while True:
                pos = data.find(needle, pos)
                if pos < 0:
                    break
                count += 1
                pos += 4
            if count > 0:
                total_refs += count
                reg_types.add(reg_name)

        print(f"\n    {port_name} (0x{port_base:08X}):")
        print(f"      Total register references: {total_refs}")
        print(f"      Register types referenced: {', '.join(sorted(reg_types))}")
        print(f"      Ctrl A refs: {len(ctrl_a_refs)}, Baud Rate refs: {len(baud_refs)}")

        # Look for baud rate divisor values near the Bit Rate register address
        # 115200 baud with 29.4912 MHz crystal:
        #   divisor = (clock / (baud * 16)) - 1
        #   For NS9360: BBus clock = SysClk/2 = ~88.5 MHz
        #   divisor_115200 = (88473600 / (115200 * 16)) - 1 ≈ 47 (0x2F) or 23 (0x17)
        #   divisor_9600 = (88473600 / (9600 * 16)) - 1 ≈ 575 (0x23F) or 287 (0x11F)

        # The actual BBus clock depends on PLL settings but common divisors:
        known_divisors = {
            0x00000017: "115200 baud (div=23, BBus=44.2MHz)",
            0x0000002F: "115200 baud (div=47, BBus=88.5MHz)",
            0x0000011F: "9600 baud (div=287, BBus=44.2MHz)",
            0x0000023F: "9600 baud (div=575, BBus=88.5MHz)",
        }

        for baud_off in baud_refs:
            # Look at words near the baud rate register reference
            print(f"      Baud Rate pool ref at 0x{baud_off + RAM_BASE:08X}:")
            for delta in range(-16, 20, 4):
                check_pos = baud_off + delta
                if 0 <= check_pos <= len(data) - 4:
                    word = struct.unpack_from('>I', data, check_pos)[0]
                    annotation = ""
                    if word in known_divisors:
                        annotation = f"  <-- {known_divisors[word]}"
                    elif word == port_base + 0x0C:
                        annotation = "  <-- Bit Rate register addr"
                    print(f"        [{delta:+3d}] 0x{word:08X}{annotation}")


def analyse_i2c_bus(data):
    """Search for I2C device addresses and bus configuration.

    Common I2C device addresses used with PDU hardware:
    - 0x50-0x57: EEPROM (AT24Cxx)
    - 0x48-0x4F: Temperature sensors (LM75, TMP102)
    - 0x68-0x6F: RTC (DS1307, PCF8563)
    - 0x20-0x27: I/O expanders (PCF8574, MCP23008)
    - 0x40-0x47: INA219/226 current/power monitors
    """
    print("\n  Searching for I2C register references...")

    # Find I2C base register references
    for reg_addr, reg_name in sorted(I2C_REGS.items()):
        needle = struct.pack('>I', reg_addr)
        count = 0
        positions = []
        pos = 0
        while True:
            pos = data.find(needle, pos)
            if pos < 0:
                break
            count += 1
            positions.append(pos)
            pos += 4

        if count > 0:
            print(f"    {reg_name} (0x{reg_addr:08X}): {count} references")
            # For slave address register, look at nearby values for I2C addresses
            if "Slave" in reg_name or "Master" in reg_name:
                for p in positions[:3]:
                    print(f"      Pool at 0x{p + RAM_BASE:08X}, nearby values:")
                    for delta in range(-16, 20, 4):
                        check_pos = p + delta
                        if 0 <= check_pos <= len(data) - 4:
                            word = struct.unpack_from('>I', data, check_pos)[0]
                            annotation = ""
                            if word == reg_addr:
                                annotation = "  <-- THIS REG"
                            elif 0x00 < word <= 0x7F:
                                # Could be an I2C 7-bit address
                                annotation = f"  (I2C addr 0x{word:02X}?)"
                            print(f"        [{delta:+3d}] 0x{word:08X}{annotation}")

    # Search for I2C-related strings
    print("\n  Searching for I2C-related strings...")
    i2c_strings = [b'i2c', b'I2C', b'iic', b'IIC', b'EEPROM', b'eeprom',
                   b'AT24', b'LM75', b'TMP10', b'DS1307', b'PCF85']

    for keyword in i2c_strings:
        pos = 0
        found = []
        while True:
            pos = data.find(keyword, pos)
            if pos < 0:
                break
            # Extract containing string
            start = pos
            while start > 0 and 0x20 <= data[start - 1] < 0x7F:
                start -= 1
            end = pos + len(keyword)
            while end < len(data) and 0x20 <= data[end] < 0x7F:
                end += 1
            s = data[start:end].decode('ascii', errors='replace')
            if len(s) >= 3 and (start + RAM_BASE, s) not in found:
                found.append((start + RAM_BASE, s))
            pos += 1

        if found:
            print(f"\n    '{keyword.decode()}' ({len(found)} matches):")
            seen = set()
            for addr, s in found:
                if s not in seen:
                    print(f"      0x{addr:08X}: {s[:150]}")
                    seen.add(s)
                    if len(seen) >= 10:
                        break


def analyse_dma_channel_mapping(data):
    """Analyse DMA channel configuration to map serial ports to DMA channels.

    The previous serial port analysis found a DMA descriptor table at ~0x757130
    mapping Port B and C to DMA channels. Let's find and decode it.
    """
    print("\n  Searching for DMA descriptor tables...")

    # NS9360 DMA channel registers start at 0xA0700000
    # Each channel has registers at offset channel * 0x20
    # Channel assignments for serial ports:
    #   Port A RX: typically channel 0
    #   Port A TX: typically channel 1
    #   Port B RX: typically channel 2
    #   Port B TX: typically channel 3
    #   Port C RX: typically channel 4
    #   Port C TX: typically channel 5
    #   Port D RX: typically channel 6
    #   Port D TX: typically channel 7

    # Find DMA base address references
    dma_refs = []
    for channel in range(16):
        ch_addr = DMA_BASE + (channel * DMA_CHANNEL_SPACING)
        needle = struct.pack('>I', ch_addr)
        pos = 0
        while True:
            pos = data.find(needle, pos)
            if pos < 0:
                break
            dma_refs.append((pos, channel, ch_addr))
            pos += 4

    if dma_refs:
        print(f"    Found {len(dma_refs)} DMA channel register references:")
        channels_used = defaultdict(int)
        for pos, channel, addr in dma_refs:
            channels_used[channel] += 1
        for ch in sorted(channels_used.keys()):
            print(f"      DMA Channel {ch} (0x{DMA_BASE + ch * DMA_CHANNEL_SPACING:08X}): "
                  f"{channels_used[ch]} refs")

    # Look for DMA descriptor table (array of structures with serial port FIFO
    # addresses and DMA channel addresses)
    print("\n  Searching for DMA descriptor structures...")

    # A DMA descriptor for a serial port typically contains:
    # - Serial port FIFO address (e.g., 0x90200020 for Port B FIFO)
    # - DMA channel address
    # - Buffer pointer
    # - Transfer size/flags

    for port_base, port_name in sorted(SERIAL_PORTS.items()):
        fifo_addr = port_base + 0x20  # FIFO register
        needle = struct.pack('>I', fifo_addr)
        pos = 0
        fifo_refs = []
        while True:
            pos = data.find(needle, pos)
            if pos < 0:
                break
            fifo_refs.append(pos)
            pos += 4

        if fifo_refs:
            print(f"\n    {port_name} FIFO (0x{fifo_addr:08X}): {len(fifo_refs)} refs")
            for fpos in fifo_refs[:3]:
                # Look for DMA channel addresses nearby
                print(f"      Pool at 0x{fpos + RAM_BASE:08X}, nearby:")
                for delta in range(-32, 36, 4):
                    check_pos = fpos + delta
                    if 0 <= check_pos <= len(data) - 4:
                        word = struct.unpack_from('>I', data, check_pos)[0]
                        annotation = ""
                        if word == fifo_addr:
                            annotation = f"  <-- {port_name} FIFO"
                        elif 0xA0700000 <= word <= 0xA07FFFFF:
                            ch = (word - DMA_BASE) // DMA_CHANNEL_SPACING
                            annotation = f"  <-- DMA Channel {ch}"
                        elif word in SERIAL_PORTS:
                            annotation = f"  <-- {SERIAL_PORTS[word]} base"
                        elif any(word == base + off for base in SERIAL_PORTS
                                 for off in SER_REG_OFFSETS):
                            for base in SERIAL_PORTS:
                                for off, name in SER_REG_OFFSETS.items():
                                    if word == base + off:
                                        annotation = f"  <-- {SERIAL_PORTS[base]} {name}"
                        print(f"        [{delta:+3d}] 0x{word:08X}{annotation}")


def analyse_spi_mode_indicators(data):
    """Search for indicators of which serial port is configured as SPI.

    In NS9360, SPI mode is selected by:
    1. Setting GPIO mux to SPI function (mux=0 for the SPI-capable pins)
    2. Configuring the serial port Control A register for SPI mode

    The SPI-capable ports are:
    - Port A: gpio[8-15] (SPI A clk=gpio[14], enable=gpio[15], dout=gpio[8], din=gpio[9])
    - Port B: gpio[0-7] (SPI B clk=gpio[6], enable=gpio[7], dout=gpio[0], din=gpio[1])
    - Port C: gpio[40-43] (SPI C clk=gpio[22], enable=gpio[23], dout=gpio[40], din=gpio[41])
    - Port D: gpio[44-49] (SPI D dout=gpio[44], din=gpio[45])
    """
    print("\n  Analysing SPI mode indicators...")

    # The key evidence from firmware:
    # 1. "spi tx DMA Cache error" / "spi rx DMA Cache error" -- SPI with DMA
    # 2. Port B has 14 refs (primary, DMA) -- likely UART to Display Unit
    # 3. Port C has 4 refs (DMA) -- likely UART for daisy-chain
    # 4. Port A has 1 ref (no DMA) -- confirmed Debug UART (J25)
    # 5. Port D has 1 ref (no DMA) -- minimal use
    #
    # MAXQ3180 needs SPI. Since Ports B and C are heavily used for UART,
    # the SPI port for MAXQ3180 is most likely Port D (or possibly A if
    # the debug UART uses Port A in UART mode and A can be reconfigured).
    #
    # But wait: the "spi slave" strings suggest an SPI slave mode too,
    # which is a different port than the MAXQ3180 master mode.
    #
    # Let's check which SPI function strings appear in the firmware

    # Search for SPI-specific strings with port indicators
    spi_keywords = [
        b'spi_a', b'SPI_A', b'spiA', b'SPIA',
        b'spi_b', b'SPI_B', b'spiB', b'SPIB',
        b'spi_c', b'SPI_C', b'spiC', b'SPIC',
        b'spi_d', b'SPI_D', b'spiD', b'SPID',
        b'spi port', b'SPI port', b'SPI Port',
        b'spi_port', b'SPI_PORT',
        b'spi_master', b'SPI_MASTER', b'spi_slave', b'SPI_SLAVE',
        b'spi_init', b'SPI_init', b'spi_open', b'SPI_open',
        b'NSSerialSPIConfig',  # NET+OS SPI API
        b'NSSPIConfig',
        b'SPIClkMode',
    ]

    for keyword in spi_keywords:
        pos = 0
        found = []
        while True:
            pos = data.find(keyword, pos)
            if pos < 0:
                break
            start = pos
            while start > 0 and 0x20 <= data[start - 1] < 0x7F:
                start -= 1
            end = pos + len(keyword)
            while end < len(data) and 0x20 <= data[end] < 0x7F:
                end += 1
            s = data[start:end].decode('ascii', errors='replace')
            if len(s) >= 3 and s not in [f[1] for f in found]:
                found.append((start + RAM_BASE, s))
            pos += 1

        if found:
            print(f"\n    '{keyword.decode()}' ({len(found)} matches):")
            for addr, s in found[:5]:
                print(f"      0x{addr:08X}: {s[:150]}")


def analyse_interrupt_vectors(data):
    """Analyse the interrupt vector table and handler addresses."""
    print("\n  Analysing interrupt vector table...")

    # ARM vector table at start of image (offset 0, i.e., RAM address 0x4000)
    # Standard ARM vectors:
    vectors = [
        (0x00, "Reset"),
        (0x04, "Undefined Instruction"),
        (0x08, "Software Interrupt (SWI)"),
        (0x0C, "Prefetch Abort"),
        (0x10, "Data Abort"),
        (0x14, "Reserved"),
        (0x18, "IRQ"),
        (0x1C, "FIQ"),
    ]

    print(f"    ARM Exception Vectors (at 0x{RAM_BASE:08X}):")
    for offset, name in vectors:
        if offset + 3 < len(data):
            word = struct.unpack_from('>I', data, offset)[0]
            # Decode ARM instruction
            if (word & 0x0F000000) == 0x0A000000:
                # Branch instruction
                off = word & 0x00FFFFFF
                if off & 0x800000:
                    off |= 0xFF000000  # Sign extend
                target = RAM_BASE + offset + 8 + (off * 4)
                print(f"      0x{offset:02X} ({name:24s}): B 0x{target:08X}")
            elif (word & 0x0F7FF000) == 0x059FF000:
                # LDR PC, [PC, #offset]
                ldr_offset = word & 0xFFF
                pool_addr = offset + 8 + ldr_offset
                if pool_addr + 3 < len(data):
                    handler = struct.unpack_from('>I', data, pool_addr)[0]
                    print(f"      0x{offset:02X} ({name:24s}): LDR PC, =0x{handler:08X}")
                else:
                    print(f"      0x{offset:02X} ({name:24s}): LDR PC, [PC, #0x{ldr_offset:X}]")
            else:
                print(f"      0x{offset:02X} ({name:24s}): 0x{word:08X}")


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    decomp_file = "2.0.51.12_Z7550-02475_decompressed.bin"
    decomp_path = os.path.join(EXTRACT_DIR, decomp_file)

    if not os.path.exists(decomp_path):
        print(f"ERROR: {decomp_path} not found")
        return

    with open(decomp_path, 'rb') as f:
        data = f.read()

    print(f"  Loaded {decomp_file}: {len(data):,} bytes")

    print(f"\n{'='*70}")
    print(f"  Deep Binary Analysis -- GPIO, SPI, I2C, DMA")
    print(f"{'='*70}")

    analyse_interrupt_vectors(data)
    analyse_gpio_config_values(data)
    analyse_serial_port_config(data)
    analyse_spi_mode_indicators(data)
    analyse_i2c_bus(data)
    analyse_dma_channel_mapping(data)

    print(f"\n{'='*70}")
    print(f"  Summary")
    print(f"{'='*70}")


if __name__ == '__main__':
    main()
