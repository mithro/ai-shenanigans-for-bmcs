#!/usr/bin/env python3
"""Cross-check DTS values against raw firmware binary data.

This script parses the raw IO table binaries and compares them
against the device tree source to find discrepancies.
"""

import os
import struct

BASE = "extracted/rootfs/etc/default/ipmi/evb"


def read_file(name):
    path = os.path.join(BASE, name)
    with open(path, 'rb') as f:
        return f.read()


def analyze_i2c_address_convention():
    """Determine whether IS_fl.bin uses 7-bit or 8-bit I2C addresses."""
    data = read_file("IS_fl.bin")
    print("=" * 72)
    print("I2C ADDRESS CONVENTION ANALYSIS")
    print("=" * 72)
    print()

    # Parse all entries and check address byte values
    for i in range(72):
        offset = 4 + i * 22
        entry = data[offset:offset + 22]
        sensor_num = entry[0]
        dev_addr = entry[14]
        bus_id = entry[15]
        iosapi = struct.unpack_from('<I', entry, 18)[0]

        if dev_addr == 0 and bus_id == 0:
            continue  # Skip entries with no bus/address

        is_8bit = dev_addr > 0x7F
        addr_7bit = dev_addr >> 1 if is_8bit else dev_addr

        # Known device identifications
        known = {
            0x000FCC0C: ("INA219", "0x40-0x4F"),
            0x000FCBCC: ("ADT7462-temp", "0x58 or 0x5C"),
            0x000FCBDC: ("ADT7462-fan", "0x58 or 0x5C"),
            0x000FCBFC: ("TMP100", "0x48-0x4F"),
            0x000FC344: ("FB-temp", "0x48-0x4F"),
        }

        chip_name, expected_range = known.get(iosapi, ("unknown", "?"))

        if dev_addr != 0:
            format_str = "8-bit" if is_8bit else "AMBIGUOUS (<0x80)"
            print(f"  Sensor 0x{sensor_num:02X} ({chip_name:14s}): "
                  f"raw=0x{dev_addr:02X} bus=0x{bus_id:02X} "
                  f"format={format_str:16s} → 7-bit=0x{addr_7bit:02X} "
                  f"(expected {expected_range})")

    print()
    print("CONCLUSION:")
    print("  Entries > 0x7F are definitively 8-bit (INA219: 0x80-0x9E, ADT7462: 0xB0/0xB8, FB: 0x9E)")
    print("  TMP100 entry 0x5C is < 0x80 - could be 7-bit (0x5C) or 8-bit (→ 0x2E)")
    print("  If 8-bit: 0x5C → 7-bit 0x2E (no known temp sensor uses this address)")
    print("  If 7-bit: 0x5C is non-standard for TMP100/LM75 family (normally 0x48-0x4F)")
    print()


def analyze_pca9555_addresses():
    """Parse IO_fl.bin to extract PCA9555 bus and address info."""
    data = read_file("IO_fl.bin")
    print("=" * 72)
    print("PCA9555 GPIO EXPANDER BUS/ADDRESS ANALYSIS (from IO_fl.bin)")
    print("=" * 72)
    print()

    # Dispatch table for type 14 (GPIO)
    off14 = 4 + 14 * 4
    count14 = struct.unpack_from('<H', data, off14)[0]
    start14 = struct.unpack_from('<H', data, off14 + 2)[0]
    entry_start = 4 + 37 * 4

    # Find unique driver pointers in type 14
    drivers = {}
    for i in range(count14):
        idx = start14 + i
        eoff = entry_start + idx * 12
        entry = data[eoff:eoff + 12]
        driver = struct.unpack_from('<I', entry, 6)[0]
        if driver not in drivers:
            drivers[driver] = []
        drivers[driver].append(i)

    print("  Driver pointers in type 14 GPIO entries:")
    for drv, indices in sorted(drivers.items()):
        print(f"    0x{drv:08X}: {len(indices)} entries (gpio #{indices[0]}-#{indices[-1]})")
    print()

    # Assume the driver with 80 entries is PCA9555, 38 entries is on-chip
    for drv, indices in sorted(drivers.items()):
        if len(indices) >= 70:  # PCA9555
            print(f"  PCA9555 driver (0x{drv:08X}): {len(indices)} entries")
            # Group by dev_id field which encodes bus+address
            by_devid = {}
            for gpio_idx in indices:
                idx = start14 + gpio_idx
                eoff = entry_start + idx * 12
                entry = data[eoff:eoff + 12]
                mask = struct.unpack_from('<H', entry, 0)[0]
                reg = struct.unpack_from('<H', entry, 2)[0]
                port = struct.unpack_from('<H', entry, 4)[0]
                dev_id = struct.unpack_from('<H', entry, 10)[0]
                key = dev_id
                if key not in by_devid:
                    by_devid[key] = []
                by_devid[key].append((gpio_idx, mask, reg, port))

            for devid, entries in sorted(by_devid.items()):
                bus_byte = (devid >> 8) & 0xFF
                addr_byte = devid & 0xFF
                addr_7bit = addr_byte >> 1
                print(f"\n    dev_id=0x{devid:04X}: bus=0x{bus_byte:02X} "
                      f"8-bit-addr=0x{addr_byte:02X} "
                      f"(7-bit=0x{addr_7bit:02X}) "
                      f"→ {len(entries)} pins")
                for gpio_idx, mask, reg, port in entries[:3]:
                    print(f"      gpio#{gpio_idx}: mask=0x{mask:04X} reg=0x{reg:04X} port=0x{port:04X}")
                if len(entries) > 3:
                    print(f"      ... and {len(entries) - 3} more")

    print()


def analyze_uboot_env():
    """Search firmware image for U-Boot environment variables."""
    print("=" * 72)
    print("U-BOOT ENVIRONMENT ANALYSIS")
    print("=" * 72)
    print()

    import zipfile
    with zipfile.ZipFile("backup/c410xbmc135.zip", 'r') as zf:
        for name in zf.namelist():
            if name.endswith('.pec'):
                data = zf.read(name)
                break

    # Search for bootargs (the key variable for console and memory)
    for marker in [b'bootargs=', b'console=ttyS', b'mem=']:
        pos = 0
        while True:
            pos = data.find(marker, pos)
            if pos == -1:
                break
            # Extract surrounding null-terminated string
            start = pos
            while start > 0 and data[start - 1] != 0:
                start -= 1
            end = pos
            while end < len(data) and data[end] != 0:
                end += 1
            string = data[start:end].decode('ascii', errors='replace')
            print(f"  Found at 0x{pos:08X}: '{string}'")
            pos = end + 1

    # Also search for memory-related strings
    print()
    for marker in [b'DRAM:', b'Total memory:', b'DDR', b'sdram', b'SDRAM']:
        pos = 0
        found = False
        while True:
            pos = data.find(marker, pos)
            if pos == -1:
                break
            start = max(0, pos - 32)
            end = min(len(data), pos + 64)
            context = data[start:end]
            # Only show printable contexts
            try:
                text = context.decode('ascii', errors='replace')
                printable = ''.join(c if 32 <= ord(c) < 127 else '.' for c in text)
                print(f"  '{marker.decode()}' at 0x{pos:08X}: ...{printable}...")
                found = True
            except Exception:
                pass
            pos += len(marker)
        if not found:
            print(f"  '{marker.decode()}' not found")

    print()


def analyze_flash_layout():
    """Extract flash partition information from U-Boot env."""
    print("=" * 72)
    print("FLASH PARTITION LAYOUT (from U-Boot environment)")
    print("=" * 72)
    print()

    import zipfile
    with zipfile.ZipFile("backup/c410xbmc135.zip", 'r') as zf:
        for name in zf.namelist():
            if name.endswith('.pec'):
                data = zf.read(name)
                break

    # Find all U-Boot env variables
    # Look for the env block (null-terminated strings ending with double null)
    env_vars = {}
    for marker in [b'bootcmd=', b'bootargs=']:
        pos = data.find(marker)
        if pos == -1:
            continue
        # Scan backward to find start of env block
        start = pos
        while start > 0 and (data[start - 1] != 0 or data[start - 2:start] == b'\x00'):
            start -= 1
            # Limit backtrack
            if pos - start > 4096:
                break

        # Actually, env block starts with CRC32 (4 bytes) then strings
        # Let's just scan forward from a known variable
        env_data = data[pos:]
        strings = []
        off = 0
        while off < len(env_data) and off < 8192:
            end = env_data.find(b'\x00', off)
            if end == -1:
                break
            s = env_data[off:end]
            if not s:
                break  # Double null = end of env
            try:
                decoded = s.decode('ascii')
                if '=' in decoded:
                    key, val = decoded.split('=', 1)
                    env_vars[key] = val
                    strings.append(decoded)
            except UnicodeDecodeError:
                break
            off = end + 1

    print("  Relevant U-Boot environment variables:")
    for key in sorted(env_vars.keys()):
        if any(x in key.lower() for x in ['boot', 'flash', 'mem', 'console',
                                            'baud', 'mac', 'eth', 'kernel',
                                            'rootfs', 'mtd', 'intf']):
            print(f"    {key}={env_vars[key]}")

    print()

    # Check bootargs specifically
    if 'bootargs' in env_vars:
        args = env_vars['bootargs']
        print(f"  bootargs analysis:")
        for part in args.split():
            print(f"    {part}")
    else:
        print("  WARNING: bootargs not found in env block near bootcmd")
        # Search more broadly
        pos = data.find(b'bootargs=')
        if pos != -1:
            end = data.find(b'\x00', pos)
            if end != -1:
                print(f"  Found bootargs at 0x{pos:08X}: {data[pos:end].decode('ascii', errors='replace')}")

    print()


def analyze_pca9548_mux():
    """Check if we can determine PCA9548 mux I2C addresses."""
    print("=" * 72)
    print("PCA9548 MUX ADDRESS ANALYSIS")
    print("=" * 72)
    print()

    # The TMP100 sensors are on bus 0xF4 behind PCA9548 muxes.
    # The mux addresses aren't directly in IS_fl.bin since the mux
    # is transparent to the sensor IOSAPI driver. Let's check if
    # the fullfw binary references specific PCA9548 addresses.

    import zipfile
    with zipfile.ZipFile("backup/c410xbmc135.zip", 'r') as zf:
        for name in zf.namelist():
            if name.endswith('.pec'):
                pec_data = zf.read(name)
                break

    # The TMP100 IOSAPI driver is at 0x000FCBFC. But the PCA9548 mux
    # driver is accessed by the TMP100 driver internally. Let's search
    # for PCA9548 I2C addresses in the binary.
    #
    # Common PCA9548 7-bit addresses: 0x70-0x77 (set by A0-A2 pins)
    # 8-bit write addresses: 0xE0-0xEE
    #
    # Let's look at IO_fl.bin for any PCA9548-related entries
    io_data = read_file("IO_fl.bin")

    # The FT_fl.bin config byte 21 = 0xBE is for PCA9548 channel mask
    ft_data = read_file("FT_fl.bin")
    print(f"  FT_fl.bin byte 21 (PCA9548 channel mask): 0x{ft_data[2+21]:02X}")
    mask = ft_data[2 + 21]
    enabled = [i for i in range(8) if mask & (1 << i)]
    disabled = [i for i in range(8) if not (mask & (1 << i))]
    print(f"    Enabled channels: {enabled}")
    print(f"    Disabled channels: {disabled}")
    print()

    # Search the PEC image for the string "PCA9548" or common mux addresses
    # near the TMP100 driver code area
    search_area = pec_data
    for pattern_name, pattern in [
        ("PCA9548", b"PCA9548"),
        ("pca9548", b"pca9548"),
        ("0xE0 bytes (mux addr)", bytes([0xE0])),
        ("0xE2 bytes (mux addr)", bytes([0xE2])),
    ]:
        if pattern_name.startswith("PCA"):
            count = search_area.count(pattern)
            if count > 0:
                pos = search_area.find(pattern)
                print(f"  String '{pattern_name}' found {count} time(s), first at 0x{pos:08X}")

    # Check around the TMP100 IOSAPI code area for hardcoded mux addresses
    # The IOSAPI driver at 0x000FCBFC would be in the fullfw binary
    # which is within the SquashFS. Let's check if we extracted it.
    fullfw_path = "extracted/rootfs/sbin/fullfw"
    if os.path.exists(fullfw_path):
        with open(fullfw_path, 'rb') as f:
            fullfw = f.read()
        print(f"\n  fullfw binary: {len(fullfw)} bytes")
        # Search for PCA9548 addresses near TMP100 code
        # 0xE0 (PCA9548 at 0x70) and 0xE2 (PCA9548 at 0x71)
        for addr_8bit in [0xE0, 0xE2, 0xE4, 0xE6]:
            # Search for the byte in instruction-like contexts
            count = fullfw.count(bytes([addr_8bit]))
            print(f"    Byte 0x{addr_8bit:02X} (PCA9548 @ 7-bit 0x{addr_8bit>>1:02X}) appears {count} times in fullfw")
    else:
        print("  fullfw not extracted (would need full SquashFS extraction)")

    print()


def analyze_pmbus_psu():
    """Analyze PMBus PSU entries to determine I2C bus."""
    print("=" * 72)
    print("PMBus PSU BUS ANALYSIS")
    print("=" * 72)
    print()

    io_data = read_file("IO_fl.bin")
    entry_start = 4 + 37 * 4

    # Type 31 entries
    off31 = 4 + 31 * 4
    count31 = struct.unpack_from('<H', io_data, off31)[0]
    start31 = struct.unpack_from('<H', io_data, off31 + 2)[0]

    print(f"  PMBus PSU entries (type 31): {count31} entries starting at index {start31}")
    for i in range(count31):
        idx = start31 + i
        eoff = entry_start + idx * 12
        entry = io_data[eoff:eoff + 12]
        hex_dump = ' '.join(f'{entry[j]:02X}' for j in range(12))
        print(f"    Entry {idx}: {hex_dump}")

        # Parse
        word0 = struct.unpack_from('<H', entry, 0)[0]
        word1 = struct.unpack_from('<H', entry, 2)[0]
        word2 = struct.unpack_from('<H', entry, 4)[0]
        driver = struct.unpack_from('<I', entry, 6)[0]
        dev_id = struct.unpack_from('<H', entry, 10)[0]

        print(f"      capabilities=0x{word0:04X} config1=0x{word1:04X} config2=0x{word2:04X}")
        print(f"      driver=0x{driver:08X} dev_id=0x{dev_id:04X}")
        # dev_id seems to encode PSU unit number in high nibble
        print(f"      dev_id high byte=0x{(dev_id >> 8) & 0xFF:02X} low byte=0x{dev_id & 0xFF:02X}")

    # Check IS_fl.bin PSU entries
    is_data = read_file("IS_fl.bin")
    print("\n  IS_fl.bin PSU Power entries (sensors 0x60-0x63):")
    for i in range(72):
        offset = 4 + i * 22
        entry = is_data[offset:offset + 22]
        sensor_num = entry[0]
        if sensor_num in (0x60, 0x61, 0x62, 0x63):
            hex_dump = ' '.join(f'{entry[j]:02X}' for j in range(22))
            print(f"    Sensor 0x{sensor_num:02X}: {hex_dump}")
            # Check bytes 2-13 for potential bus info
            cat = entry[6]
            print(f"      Category byte (offset 6): 0x{cat:02X} (decimal {cat})")
            # Dump bytes 2-17 individually
            for j in range(2, 18):
                print(f"      byte[{j}] = 0x{entry[j]:02X}", end="")
                if j == 14:
                    print(" (device address)", end="")
                elif j == 15:
                    print(" (bus ID)", end="")
                elif j == 16:
                    print(" (reg/mux)", end="")
                print()
    print()


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    analyze_i2c_address_convention()
    analyze_pca9555_addresses()
    analyze_uboot_env()
    analyze_flash_layout()
    analyze_pca9548_mux()
    analyze_pmbus_psu()


if __name__ == '__main__':
    main()
