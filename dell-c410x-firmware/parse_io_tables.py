#!/usr/bin/env python3
"""Parse the raw IO table binary files from Dell C410X BMC firmware.

Cross-checks I2C addresses, bus assignments, and sensor mappings
against the device tree and documentation.
"""

import os
import struct
import sys

BASE = "extracted/rootfs/etc/default/ipmi/evb"


def parse_is_fl_bin():
    """Parse IS_fl.bin - the sensor table."""
    path = os.path.join(BASE, "IS_fl.bin")
    with open(path, 'rb') as f:
        data = f.read()

    print(f"IS_fl.bin: {len(data)} bytes")

    # Header
    version = data[0]
    analog_count = data[2]
    discrete_count = data[3]
    total = analog_count + discrete_count
    print(f"  Version: {version}")
    print(f"  Analog sensors: {analog_count}")
    print(f"  Discrete sensors: {discrete_count}")
    print(f"  Total: {total}")
    print()

    # Parse each 22-byte entry
    print("  --- Analog Sensors (threshold-based readings) ---")
    print(f"  {'#':>3s} {'Sensor':>6s} {'Flags':>5s} {'DevAddr':>7s} {'Bus':>4s} {'Reg/Mux':>7s} {'IOSAPI':>10s}  Notes")
    print(f"  {'':->3s} {'':->6s} {'':->5s} {'':->7s} {'':->4s} {'':->7s} {'':->10s}  {'':->40s}")

    for i in range(total):
        offset = 4 + i * 22
        entry = data[offset:offset + 22]
        if len(entry) < 22:
            break

        sensor_num = entry[0]
        sensor_flags = entry[1]

        # Bytes 14-15: I2C device address (low) + bus ID (high)
        dev_addr = entry[14]
        bus_id = entry[15]

        # Byte 16: register or mux index
        reg_mux = entry[16]

        # Bytes 18-21: IOSAPI driver pointer
        iosapi = struct.unpack_from('<I', entry, 18)[0]

        # Classify the sensor
        notes = ""
        if iosapi == 0x000fcc0c:
            notes = f"INA219 Power (7-bit=0x{dev_addr >> 1:02X})" if dev_addr > 0x7F else f"INA219 Power"
        elif iosapi == 0x000fcbcc:
            notes = f"ADT7462 Temp (mux_sel=0x{reg_mux:02X})"
        elif iosapi == 0x000fcbdc:
            notes = f"ADT7462 Fan (mux_sel=0x{reg_mux:02X})"
        elif iosapi == 0x000fcbfc:
            notes = f"TMP100 Temp (mux_ch=0x{reg_mux:02X})"
        elif iosapi == 0x000fc344:
            notes = f"FB Temp (7-bit=0x{dev_addr >> 1:02X})" if dev_addr > 0x7F else "FB Temp"
        elif iosapi == 0x000fc3d4:
            notes = f"PMBus PSU"
        elif iosapi == 0x0010a5a8:
            notes = "PCIe Presence (GPIO)"
        elif iosapi == 0x0010a5b0:
            notes = "PSU Presence (GPIO)"
        elif iosapi == 0x0010a5b8:
            notes = "Sys Power Monitor (GPIO)"

        # Determine if address is 7-bit or 8-bit
        addr_str = f"0x{dev_addr:02X}"
        if dev_addr > 0x7F:
            addr_str += f" (7b=0x{dev_addr >> 1:02X})"

        category = "A" if i < analog_count else "D"
        print(f"  {i:3d} 0x{sensor_num:02X}  0x{sensor_flags:02X} {addr_str:>15s} 0x{bus_id:02X} 0x{reg_mux:02X}    0x{iosapi:08X}  {notes}")

    print()


def parse_io_fl_bin():
    """Parse IO_fl.bin - the master hardware IO table."""
    path = os.path.join(BASE, "IO_fl.bin")
    with open(path, 'rb') as f:
        data = f.read()

    print(f"IO_fl.bin: {len(data)} bytes")

    # Header
    version = data[0]
    hint_count = struct.unpack_from('<H', data, 2)[0]
    print(f"  Version: {version}")
    print(f"  Entry count hint: {hint_count}")

    # Dispatch table: 37 slots, 4 bytes each, starting at offset 4
    print("\n  Dispatch Table:")
    print(f"  {'Type':>4s} {'Count':>5s} {'Start':>5s}")
    for t in range(37):
        off = 4 + t * 4
        count = struct.unpack_from('<H', data, off)[0]
        start = struct.unpack_from('<H', data, off + 2)[0]
        if count > 0:
            print(f"  {t:4d} {count:5d} {start:5d}")

    # Entry table: starts at offset 152 (4 + 37*4), 12 bytes each
    entry_start = 4 + 37 * 4
    num_entries = (len(data) - entry_start) // 12
    print(f"\n  Entry table: {num_entries} entries (12 bytes each)")

    # Print specific entries of interest

    # Type 9 (EEPROM/FRU) - check EEPROM bus and address
    print("\n  --- Type 9: EEPROM/FRU ---")
    # Find dispatch for type 9
    off9 = 4 + 9 * 4
    count9 = struct.unpack_from('<H', data, off9)[0]
    start9 = struct.unpack_from('<H', data, off9 + 2)[0]
    for i in range(count9):
        idx = start9 + i
        eoff = entry_start + idx * 12
        entry = data[eoff:eoff + 12]
        addr_mask = struct.unpack_from('<H', entry, 0)[0]
        reg_bus = struct.unpack_from('<H', entry, 2)[0]
        port_cfg = struct.unpack_from('<H', entry, 4)[0]
        driver = struct.unpack_from('<I', entry, 6)[0]
        dev_id = struct.unpack_from('<H', entry, 10)[0]
        print(f"    Entry {idx}: addr=0x{addr_mask:04X} reg=0x{reg_bus:04X} port=0x{port_cfg:04X} drv=0x{driver:08X} id=0x{dev_id:04X}")

    # Type 13 (ADT7462)
    print("\n  --- Type 13: ADT7462 Fan/Temp ---")
    off13 = 4 + 13 * 4
    count13 = struct.unpack_from('<H', data, off13)[0]
    start13 = struct.unpack_from('<H', data, off13 + 2)[0]
    for i in range(count13):
        idx = start13 + i
        eoff = entry_start + idx * 12
        entry = data[eoff:eoff + 12]
        addr_mask = struct.unpack_from('<H', entry, 0)[0]
        reg_bus = struct.unpack_from('<H', entry, 2)[0]
        port_cfg = struct.unpack_from('<H', entry, 4)[0]
        driver = struct.unpack_from('<I', entry, 6)[0]
        dev_id = struct.unpack_from('<H', entry, 10)[0]
        print(f"    Entry {idx}: addr=0x{addr_mask:04X} reg=0x{reg_bus:04X} port=0x{port_cfg:04X} drv=0x{driver:08X} id=0x{dev_id:04X}")

    # Type 14 (GPIO) - first few and PCA9555 entries
    print("\n  --- Type 14: Sensor/GPIO (first 10 + PCA9555 entries) ---")
    off14 = 4 + 14 * 4
    count14 = struct.unpack_from('<H', data, off14)[0]
    start14 = struct.unpack_from('<H', data, off14 + 2)[0]
    for i in range(count14):
        idx = start14 + i
        eoff = entry_start + idx * 12
        entry = data[eoff:eoff + 12]
        addr_mask = struct.unpack_from('<H', entry, 0)[0]
        reg_bus = struct.unpack_from('<H', entry, 2)[0]
        port_cfg = struct.unpack_from('<H', entry, 4)[0]
        driver = struct.unpack_from('<I', entry, 6)[0]
        dev_id = struct.unpack_from('<H', entry, 10)[0]
        # Only print PCA9555 entries (driver pointer for PCA9555 GPIO)
        if i < 10 or driver != struct.unpack_from('<I', data, entry_start + (start14) * 12 + 6)[0]:
            if i < 10 or i >= count14 - 10:
                label = ""
                # Identify on-chip vs PCA9555 by checking port_cfg
                if port_cfg in (0x4000, 0x4002, 0x4004, 0x4006):
                    label = "ON-CHIP GPIO"
                else:
                    label = f"PCA9555 (bus byte=0x{(port_cfg >> 8) & 0xFF:02X}, addr byte=0x{port_cfg & 0xFF:02X})"
                print(f"    Entry {idx} [gpio#{i}]: mask=0x{addr_mask:04X} reg=0x{reg_bus:04X} port=0x{port_cfg:04X} drv=0x{driver:08X} id=0x{dev_id:04X}  {label}")

    # Let's specifically look for PCA9555 entries to understand the address format
    print("\n  --- Type 14: All PCA9555 GPIO entries ---")
    pca9555_entries = []
    for i in range(count14):
        idx = start14 + i
        eoff = entry_start + idx * 12
        entry = data[eoff:eoff + 12]
        port_cfg = struct.unpack_from('<H', entry, 4)[0]
        driver = struct.unpack_from('<I', entry, 6)[0]
        # PCA9555 entries have non-0x40xx port_cfg values
        if port_cfg not in (0x4000, 0x4002, 0x4004, 0x4006):
            addr_mask = struct.unpack_from('<H', entry, 0)[0]
            reg_bus = struct.unpack_from('<H', entry, 2)[0]
            dev_id = struct.unpack_from('<H', entry, 10)[0]
            bus_byte = (port_cfg >> 8) & 0xFF
            addr_byte = port_cfg & 0xFF
            pca9555_entries.append((i, idx, addr_mask, reg_bus, port_cfg, driver, dev_id, bus_byte, addr_byte))

    # Summarize PCA9555 entries by bus/address
    by_bus_addr = {}
    for i, idx, addr_mask, reg_bus, port_cfg, driver, dev_id, bus_byte, addr_byte in pca9555_entries:
        key = (bus_byte, addr_byte)
        if key not in by_bus_addr:
            by_bus_addr[key] = []
        by_bus_addr[key].append((i, idx, addr_mask, reg_bus, dev_id))

    for (bus, addr), entries in sorted(by_bus_addr.items()):
        print(f"\n    PCA9555 on bus=0x{bus:02X}, 8-bit-addr=0x{addr:02X} (7-bit=0x{addr >> 1:02X}): {len(entries)} entries")
        for i, idx, mask, reg, devid in entries[:4]:
            print(f"      gpio#{i} entry#{idx}: mask=0x{mask:04X} reg=0x{reg:04X} devid=0x{devid:04X}")
        if len(entries) > 4:
            print(f"      ... and {len(entries) - 4} more")

    # Type 20 (PCA9544A mux)
    print("\n  --- Type 20: PCA9544A I2C Mux ---")
    off20 = 4 + 20 * 4
    count20 = struct.unpack_from('<H', data, off20)[0]
    start20 = struct.unpack_from('<H', data, off20 + 2)[0]
    for i in range(count20):
        idx = start20 + i
        eoff = entry_start + idx * 12
        entry = data[eoff:eoff + 12]
        fields = [struct.unpack_from('<H', entry, j)[0] for j in range(0, 12, 2)]
        driver = struct.unpack_from('<I', entry, 6)[0]
        print(f"    Entry {idx}: {' '.join(f'0x{f:04X}' for f in fields[:3])} drv=0x{driver:08X} id=0x{fields[5]:04X}")

    # Type 31 (PMBus PSU)
    print("\n  --- Type 31: PMBus PSU ---")
    off31 = 4 + 31 * 4
    if off31 + 4 <= 4 + 37 * 4:
        count31 = struct.unpack_from('<H', data, off31)[0]
        start31 = struct.unpack_from('<H', data, off31 + 2)[0]
        for i in range(count31):
            idx = start31 + i
            eoff = entry_start + idx * 12
            entry = data[eoff:eoff + 12]
            # Dump all bytes
            hex_dump = ' '.join(f'{b:02X}' for b in entry)
            fields = [struct.unpack_from('<H', entry, j)[0] for j in range(0, 12, 2)]
            print(f"    Entry {idx}: [{hex_dump}]")
            print(f"      word0=0x{fields[0]:04X} word1=0x{fields[1]:04X} word2=0x{fields[2]:04X} drv=0x{struct.unpack_from('<I', entry, 6)[0]:08X} id=0x{fields[5]:04X}")


def parse_bmcsetting():
    """Parse bmcsetting file for bus/address configuration."""
    path = os.path.join(BASE, "bmcsetting")
    with open(path, 'rb') as f:
        content = f.read()
    print(f"\nbmcsetting: {len(content)} bytes")
    # It's typically a text file
    try:
        text = content.decode('ascii', errors='replace')
        print(text)
    except Exception:
        print("  (binary, dumping hex)")
        for i in range(0, min(256, len(content)), 16):
            hex_part = ' '.join(f'{b:02X}' for b in content[i:i + 16])
            print(f"  {i:04X}: {hex_part}")


def parse_id_devid():
    """Parse ID_devid.bin for device identification."""
    path = os.path.join(BASE, "ID_devid.bin")
    with open(path, 'rb') as f:
        data = f.read()
    print(f"\nID_devid.bin: {len(data)} bytes")
    hex_dump = ' '.join(f'{b:02X}' for b in data)
    print(f"  Raw: {hex_dump}")
    if len(data) >= 15:
        print(f"  Device ID: 0x{data[0]:02X}")
        print(f"  Device Revision: 0x{data[1]:02X}")
        print(f"  Firmware Major: {data[2] & 0x7F}")
        print(f"  Firmware Minor: 0x{data[3]:02X} (BCD={data[3]:02X})")
        print(f"  IPMI Version: {(data[4] & 0xF0) >> 4}.{data[4] & 0x0F}")
        print(f"  Additional Device Support: 0x{data[5]:02X}")
        mfr_id = data[6] | (data[7] << 8) | (data[8] << 16)
        print(f"  Manufacturer ID: 0x{mfr_id:06X}")
        prod_id = data[9] | (data[10] << 8)
        print(f"  Product ID: 0x{prod_id:04X}")


def parse_sdr():
    """Parse SDR file for sensor names and thresholds."""
    path = os.path.join(BASE, "NVRAM_SDR00.dat")
    with open(path, 'rb') as f:
        data = f.read()
    print(f"\nNVRAM_SDR00.dat: {len(data)} bytes")

    # SDR records start after a header
    # Each record: record ID (2), version (1), record type (1), length (1), data...
    offset = 0
    record_count = 0

    # Simple SDR parsing - look for Full Sensor Records (type 0x01)
    while offset + 5 <= len(data):
        rec_id = struct.unpack_from('<H', data, offset)[0]
        sdr_ver = data[offset + 2]
        rec_type = data[offset + 3]
        rec_len = data[offset + 4]

        if rec_len == 0 or rec_len > 64 or offset + 5 + rec_len > len(data):
            break

        if rec_type == 0x01 and rec_len >= 43:
            # Full Sensor Record
            rec_data = data[offset + 5:offset + 5 + rec_len]
            sensor_num = rec_data[2]
            entity_id = rec_data[3]
            entity_instance = rec_data[4]
            sensor_type = rec_data[7]
            # Name is at the end, length in bits 4:0 of last control byte
            name_len = rec_data[42] & 0x1F
            name_offset = 43
            if name_offset + name_len <= len(rec_data):
                name = rec_data[name_offset:name_offset + name_len]
                try:
                    name_str = name.decode('ascii', errors='replace').strip()
                except Exception:
                    name_str = repr(name)
            else:
                name_str = "?"

            # Thresholds
            if rec_len >= 36:
                uc = rec_data[31]  # upper critical
                unc = rec_data[30]  # upper non-critical
                lnc = rec_data[33]  # lower non-critical
                lc = rec_data[34]   # lower critical
                thresh_str = f"UC={uc} UNC={unc} LNC={lnc} LC={lc}"
            else:
                thresh_str = ""

            print(f"  Sensor 0x{sensor_num:02X}: type=0x{sensor_type:02X} entity={entity_id}.{entity_instance} name='{name_str}' {thresh_str}")
            record_count += 1

        elif rec_type == 0x02 and rec_len >= 21:
            # Compact Sensor Record
            rec_data = data[offset + 5:offset + 5 + rec_len]
            sensor_num = rec_data[2]
            entity_id = rec_data[3]
            entity_instance = rec_data[4]
            sensor_type = rec_data[7]
            name_len = rec_data[20] & 0x1F
            name_offset = 21
            if name_offset + name_len <= len(rec_data):
                name_str = rec_data[name_offset:name_offset + name_len].decode('ascii', errors='replace').strip()
            else:
                name_str = "?"
            print(f"  Sensor 0x{sensor_num:02X}: type=0x{sensor_type:02X} entity={entity_id}.{entity_instance} name='{name_str}' [compact]")
            record_count += 1

        offset += 5 + rec_len

    print(f"  Total sensor records: {record_count}")


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    parse_is_fl_bin()
    parse_io_fl_bin()
    parse_bmcsetting()
    parse_id_devid()
    parse_sdr()


if __name__ == '__main__':
    main()
