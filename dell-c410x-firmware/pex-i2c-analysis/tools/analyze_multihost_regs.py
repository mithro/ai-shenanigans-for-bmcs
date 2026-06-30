#!/usr/bin/env python3
"""Detailed analysis of multi-host register data from fullfw binary.

This script re-interprets the data tables with corrected understanding of the
buffer layout used by the multi-host configuration functions.

Key insight: The PLX I2C command buffer has this layout:
  [0] = station/port byte (set by the function before memcpy)
  [1] = byte_enables | reg_hi | port_lo  (typically 0x3C = all bytes enabled)
  [2] = reg_lo (DWORD index low byte)
  [3-6] = 4-byte register value (little-endian)

But for write_pex8696_register/write_pex8647_register:
  param_3 = command byte (0x03 for write)
  param_4 = pointer to buffer
  The function builds: [param_3] [buf[0]] [buf[1]] ... [buf[6]]
  So the buffer has 7 bytes: [stn/port] [enables|reg_hi] [reg_lo] [val0-3]

For the cfg_multi_host functions, the data is 6 bytes per entry because
byte[0] (stn/port) is NOT part of the memcpy'd data - it's set to a
constant value from the loop counter. Wait, actually looking at the code
more carefully...

Let me re-read the code:
  memcpy(auStack_28, DAT_00036cc8, 0xc);  // copy 12 bytes of ROM data to stack
  *DAT_00036ccc = 0;                       // clear counter at shared location
  for (i = 0; i < 2; i++) {
      memcpy(DAT_00036cd0, auStack_28 + i*6, 6);  // copy 6 bytes to command buffer
      write_pex8696_register(local_11, local_12, local_13, local_18);
  }

DAT_00036cd0 is the command buffer, and it gets 6 bytes from the data.
write_pex8696_register(bus_mux, i2c_addr, cmd, buffer_ptr)
  - bus_mux comes from param_1 (local_11)
  - i2c_addr comes from param_2 (local_12)
  - cmd byte comes from param_3 (local_13)
  - buffer_ptr comes from param_4 (local_18)

Inside write_pex8696_register:
  local_20 = (uint)param_3;                    // byte 0 = cmd (0x03)
  memcpy((int)&local_20 + 1, param_4, 7);      // bytes 1-7 from buffer

So the 8 bytes on the wire are:
  [cmd=0x03] [buf[0]] [buf[1]] [buf[2]] [buf[3]] [buf[4]] [buf[5]] [buf[6]]

But wait - the buffer has 7 bytes starting at DAT_00036cd0, and only 6 are
written by the inner memcpy. So there's a 7th byte that persists from
whatever was previously in the buffer (or from DAT_00036ccc = 0).

Actually, looking at the globals more carefully:
  DAT_00036ccc -> 0x0010B8CD  (this is byte[0] of the command buffer)
  DAT_00036cd0 -> 0x0010B8CE  (this is byte[1] onwards)

So the full 7-byte buffer is at 0x0010B8CD:
  [0x0010B8CD] = station/port byte (set by *DAT_00036ccc = 0, but the code
                  in cfg_multi_host_2 doesn't set it - it's cleared!)
  [0x0010B8CE..0x0010B8D3] = 6 bytes copied from the data table

Wait no, re-reading:
  *DAT_00036ccc = 0;  -- sets the VALUE at the pointer to 0

So DAT_00036ccc is a pointer to a location that gets set to 0.
And DAT_00036cd0 is a pointer to the location that gets the 6-byte memcpy.

From the extraction:
  DAT_00036ccc = 0x0010B8CD
  DAT_00036cd0 = 0x0010B8CE

So 0x0010B8CD = 0 (station/port byte set to 0 = station 0, port 0)
And 0x0010B8CE..0x0010B8D3 gets the 6 bytes.

But wait - who sets the station/port byte for each iteration?
Looking again: the loop copies 6 bytes each time, BUT byte[0] of the 6-byte
entry IS the value at 0x0010B8CE (enables field), NOT the station/port byte.

Actually, I think the structure is:
  0x0010B8CD = command buffer byte[0] = station/port byte
  0x0010B8CE = command buffer byte[1] = enables | reg_hi
  0x0010B8CF = command buffer byte[2] = reg_lo
  0x0010B8D0 = command buffer byte[3] = val[0]
  0x0010B8D1 = command buffer byte[4] = val[1]
  0x0010B8D2 = command buffer byte[5] = val[2]
  0x0010B8D3 = command buffer byte[6] = val[3]

*DAT_00036ccc = 0 means the station/port byte is set to 0 (station 0, port 0)

The 6-byte entries from the data table go into bytes[1..6].

But for pex8696_cfg_multi_host_2, the data entries start with 0x3C which
IS the enables field. So the interpretation is:

Entry format (6 bytes): [enables|reg_hi] [reg_lo] [val0] [val1] [val2] [val3]

Wait, that's only 6 bytes for enables+reg+value. But value is 4 bytes and
enables+reg is 2, so that's exactly 6. But the memcpy copies 6 bytes which
only fills bytes[1..6] of the 7-byte buffer.

Actually no, re-reading: the data at DAT_00036cc8 has entries like:
  3C E1 00 11 10 00
  3C E0 00 00 01 11

These are 6 bytes each. When copied to 0x0010B8CE (bytes[1..6]):
  byte[1] = 0x3C  (enables = all bytes)
  byte[2] = 0xE1  (reg_lo = 0xE1, but wait, bit[7] could be port_lo)
  byte[3] = 0x00  (val[0])
  byte[4] = 0x11  (val[1])
  byte[5] = 0x10  (val[2])
  byte[6] = 0x00  (val[3])

Hmm, but 0xE1 as a DWORD index is too large. Let me reconsider.

Actually the byte numbering in the PLX I2C command is:
  Wire byte[0] = cmd (0x03 for write) -- from param_3
  Wire byte[1] = station/port byte   -- buf[0] at 0x0010B8CD
  Wire byte[2] = enables|reg_hi|port_lo -- buf[1] at 0x0010B8CE
  Wire byte[3] = reg_lo              -- buf[2] at 0x0010B8CF
  Wire byte[4-7] = value             -- buf[3..6] at 0x0010B8D0..D3

So buf[0] = station/port = 0 (from *DAT = 0)
   buf[1] = 0x3C (enables = all bytes)
   buf[2] = 0xE1 (reg_lo)
   buf[3..6] = value

DWORD index = (buf[1] & 0x03) << 8 | buf[2] = (0x3C & 0x03) << 8 | 0xE1
            = 0x00 << 8 | 0xE1 = 0xE1

Register byte address = 0xE1 * 4 = 0x384

OK! NOW it makes sense. Register 0x384 is in the PLX proprietary region.
Let me also note that station/port = 0 means station 0, port 0.
"""

import struct

FULLFW_PATH = "/home/tim/github/mithro/ai-shenanigans-for-bmcs/.worktrees/pex-i2c-re/dell-c410x-firmware/pex-i2c-analysis/analysis/fullfw"
BASE_OFFSET = 0x8000

def read_binary():
    with open(FULLFW_PATH, 'rb') as f:
        return f.read()

def vaddr_to_foffset(vaddr):
    return vaddr - BASE_OFFSET

def read_bytes(data, vaddr, count):
    offset = vaddr_to_foffset(vaddr)
    return data[offset:offset+count]

def read_u32(data, vaddr):
    return struct.unpack_from('<I', data, vaddr_to_foffset(vaddr))[0]

def hex_bytes(b):
    return ' '.join(f'{x:02X}' for x in b)

def decode_plx_write(stn_port, enables, reg_lo, val_bytes):
    """Decode a PLX I2C write command."""
    station = stn_port >> 1
    port_hi = stn_port & 1
    port_lo = (enables >> 7) & 1
    port = (port_hi << 1) | port_lo  # Not right... port_hi is bit from stn_port
    # Actually: byte[1] = (station << 1) | (port >> 1)
    # So station = byte[1] >> 1, and the lower bit of byte[1] is port bit 1 (port >> 1)
    # byte[2] bit 7 = port bit 0 (port & 1)
    station = stn_port >> 1
    port_bit1 = stn_port & 1
    port_bit0 = (enables >> 7) & 1
    port = (port_bit1 << 1) | port_bit0

    byte_enables = (enables >> 2) & 0xF
    reg_hi = enables & 0x03
    dword_idx = (reg_hi << 8) | reg_lo
    byte_addr = dword_idx * 4

    val_u32 = 0
    for i, b in enumerate(val_bytes):
        val_u32 |= (b << (i * 8))

    return {
        'station': station,
        'port': port,
        'global_port': station * 4 + port,
        'byte_enables': byte_enables,
        'dword_idx': dword_idx,
        'byte_addr': byte_addr,
        'value': val_u32,
        'val_bytes': val_bytes,
    }

def print_plx_write(label, stn_port, enables, reg_lo, val_bytes):
    d = decode_plx_write(stn_port, enables, reg_lo, val_bytes)
    print(f"  {label}:")
    print(f"    Target: station {d['station']}, port {d['port']} (global port {d['global_port']})")
    print(f"    Byte enables: 0x{d['byte_enables']:X} ({'all' if d['byte_enables']==0xF else 'partial'})")
    print(f"    Register: DWORD 0x{d['dword_idx']:03X} = byte addr 0x{d['byte_addr']:03X}")
    print(f"    Value: 0x{d['value']:08X} (bytes: {hex_bytes(d['val_bytes'])})")

def main():
    data = read_binary()

    print("=" * 80)
    print("MULTI-HOST REGISTER ANALYSIS")
    print("=" * 80)

    # ================================================================
    # pex8696_cfg_multi_host_2
    # ================================================================
    print("\n" + "=" * 60)
    print("pex8696_cfg_multi_host_2 -- Configure PEX8696 for 2:1 mode")
    print("=" * 60)
    print("\nStation/port byte: 0x00 (station 0, port 0 = global port 0)")
    print("Command byte: 0x03 (PLX write)")
    print("\nThis writes to port 0 on the target PEX8696 switch.")
    print("Port 0 is the upstream/NT port (non-transparent bridge).\n")

    ptr = read_u32(data, 0x36cc8)
    reg_data = read_bytes(data, ptr, 12)

    for i in range(2):
        entry = reg_data[i*6:(i+1)*6]
        # entry[0] = enables|reg_hi, entry[1] = reg_lo, entry[2:6] = value
        stn_port = 0x00  # from *DAT = 0
        enables = entry[0]
        reg_lo = entry[1]
        val_bytes = list(entry[2:6])
        print_plx_write(f"Write {i+1}", stn_port, enables, reg_lo, val_bytes)

    # ================================================================
    # pex8696_cfg_multi_host_4
    # ================================================================
    print("\n" + "=" * 60)
    print("pex8696_cfg_multi_host_4 -- Configure PEX8696 for 4:1 mode")
    print("=" * 60)
    print("\nStation/port byte: 0x00 (station 0, port 0 = global port 0)")
    print("Command byte: 0x03 (PLX write)\n")

    ptr = read_u32(data, 0x36db0)
    reg_data = read_bytes(data, ptr, 12)

    for i in range(2):
        entry = reg_data[i*6:(i+1)*6]
        stn_port = 0x00
        enables = entry[0]
        reg_lo = entry[1]
        val_bytes = list(entry[2:6])
        print_plx_write(f"Write {i+1}", stn_port, enables, reg_lo, val_bytes)

    # ================================================================
    # Comparison: 2:1 vs 4:1 for PEX8696
    # ================================================================
    print("\n" + "=" * 60)
    print("COMPARISON: PEX8696 2:1 vs 4:1 mode register differences")
    print("=" * 60)

    ptr_2 = read_u32(data, 0x36cc8)
    data_2 = read_bytes(data, ptr_2, 12)
    ptr_4 = read_u32(data, 0x36db0)
    data_4 = read_bytes(data, ptr_4, 12)

    for i in range(2):
        e2 = data_2[i*6:(i+1)*6]
        e4 = data_4[i*6:(i+1)*6]
        d2 = decode_plx_write(0, e2[0], e2[1], list(e2[2:6]))
        d4 = decode_plx_write(0, e4[0], e4[1], list(e4[2:6]))

        print(f"\n  Register 0x{d2['byte_addr']:03X} (DWORD 0x{d2['dword_idx']:03X}):")
        if d2['byte_addr'] != d4['byte_addr']:
            print(f"    WARNING: Different registers! 2:1=0x{d2['byte_addr']:03X}, 4:1=0x{d4['byte_addr']:03X}")
        print(f"    2:1 mode value: 0x{d2['value']:08X}")
        print(f"    4:1 mode value: 0x{d4['value']:08X}")
        diff = d2['value'] ^ d4['value']
        if diff:
            print(f"    XOR diff:       0x{diff:08X}")
            for bit in range(32):
                if diff & (1 << bit):
                    byte_pos = bit // 8
                    bit_in_byte = bit % 8
                    print(f"      Bit {bit} (byte {byte_pos}, bit {bit_in_byte}) differs: "
                          f"2:1={'1' if d2['value'] & (1<<bit) else '0'}, "
                          f"4:1={'1' if d4['value'] & (1<<bit) else '0'}")

    # ================================================================
    # pex8647_cfg_multi_host_8
    # ================================================================
    print("\n" + "=" * 60)
    print("pex8647_cfg_multi_host_8 -- Configure PEX8647 for 8:1 mode")
    print("=" * 60)

    ptr = read_u32(data, 0x36ee4)
    reg_data = read_bytes(data, ptr, 18)

    # The function structure:
    # 1. memcpy(auStack_30, data, 0x12)  -- 18 bytes total
    #    auStack_30 is at offset 0: 12 bytes
    #    auStack_24 is at offset 12: 6 bytes (but declared as 11 bytes array)
    #
    # Actually wait. The declarations are:
    #   undefined auStack_30 [12];    // 12 bytes
    #   undefined auStack_24 [11];    // 11 bytes
    # But only 18 bytes are copied. So auStack_24 starts right after auStack_30.
    # On the stack: auStack_30 at fp-0x30, auStack_24 at fp-0x24
    # That's 12 bytes apart. So the 18-byte memcpy fills auStack_30[0..11]
    # and auStack_24[0..5].

    # Step 1: Initial write with counter=4
    # *DAT_00036ee8 = 4;  (sets counter to 4)
    # memcpy(DAT_00036eec, auStack_24, 6);  -- copies 6 bytes from auStack_24
    # write_pex8647_register(...)

    # Step 2: Loop 2 iterations
    # *DAT_00036ee8 = 0;  (sets counter to 0)
    # for i in 0..1:
    #   memcpy(DAT_00036eec, auStack_30 + i*6, 6);
    #   write_pex8647_register(...)
    #   _lx_ThreadSleep(0x14)  -- 20 tick sleep

    # DAT_00036ee8 = 0x0010B8D5 (counter/stn_port byte for PEX8647 command buffer)
    # DAT_00036eec = 0x0010B8D6 (rest of command buffer)

    # PEX8647 command buffer (7 bytes at 0x0010B8D4..0x0010B8DA):
    # Wait, actually looking at write_pex8647_register, the buffer structure
    # is the same as write_pex8696_register. So:
    # buf[0] at DAT_00036ee8 (0x0010B8D5) = station/port byte
    # buf[1..6] at DAT_00036eec (0x0010B8D6) = enables, reg_lo, value

    # Hmm, DAT_00036ee8 = 0x0010B8D5 is the pointer location.
    # The code does: *DAT_00036ee8 = 4 -> writes value 4 to 0x0010B8D5
    # Then: memcpy(DAT_00036eec, src, 6) -> copies to 0x0010B8D6

    # So for the initial write:
    #   buf[0] = 4 (station 2, port 0)
    #   buf[1..6] = auStack_24[0..5] = data[12..17]

    # For loop iteration 0:
    #   buf[0] = 0 (station 0, port 0)
    #   buf[1..6] = auStack_30[0..5] = data[0..5]

    # For loop iteration 1:
    #   buf[0] = 0 (station 0, port 0)
    #   buf[1..6] = auStack_30[6..11] = data[6..11]

    print("\nInitial write (station/port = 4 -> station 2, port 0):")
    entry = reg_data[12:18]
    print_plx_write("Initial", 4, entry[0], entry[1], list(entry[2:6]))

    print("\nLoop writes (station/port = 0 -> station 0, port 0):")
    for i in range(2):
        entry = reg_data[i*6:(i+1)*6]
        print_plx_write(f"Loop {i}", 0, entry[0], entry[1], list(entry[2:6]))

    print("\nDelays: 0x14 = 20 ticks between each loop write")

    # ================================================================
    # pex8647_cfg_multi_host_2_4
    # ================================================================
    print("\n" + "=" * 60)
    print("pex8647_cfg_multi_host_2_4 -- Configure PEX8647 for 2:1 or 4:1 mode")
    print("=" * 60)

    ptr = read_u32(data, 0x37018)
    reg_data = read_bytes(data, ptr, 18)

    print("\nInitial write (station/port = 4 -> station 2, port 0):")
    entry = reg_data[12:18]
    print_plx_write("Initial", 4, entry[0], entry[1], list(entry[2:6]))

    print("\nLoop writes (station/port = 0 -> station 0, port 0):")
    for i in range(2):
        entry = reg_data[i*6:(i+1)*6]
        print_plx_write(f"Loop {i}", 0, entry[0], entry[1], list(entry[2:6]))

    print("\nDelays: 0x14 = 20 ticks between each loop write")

    # ================================================================
    # Comparison: PEX8647 8:1 vs 2:4 mode
    # ================================================================
    print("\n" + "=" * 60)
    print("COMPARISON: PEX8647 8:1 vs 2:4 mode register differences")
    print("=" * 60)

    ptr_8 = read_u32(data, 0x36ee4)
    data_8 = read_bytes(data, ptr_8, 18)
    ptr_24 = read_u32(data, 0x37018)
    data_24 = read_bytes(data, ptr_24, 18)

    print("\nInitial write (to station 2, port 0):")
    e8 = data_8[12:18]
    e24 = data_24[12:18]
    d8 = decode_plx_write(4, e8[0], e8[1], list(e8[2:6]))
    d24 = decode_plx_write(4, e24[0], e24[1], list(e24[2:6]))
    print(f"  Register 0x{d8['byte_addr']:03X}:")
    print(f"    8:1 value: 0x{d8['value']:08X}")
    print(f"    2:4 value: 0x{d24['value']:08X}")
    diff = d8['value'] ^ d24['value']
    if diff:
        print(f"    XOR diff:  0x{diff:08X}")
        for bit in range(32):
            if diff & (1 << bit):
                print(f"      Bit {bit}: 8:1={'1' if d8['value'] & (1<<bit) else '0'}, "
                      f"2:4={'1' if d24['value'] & (1<<bit) else '0'}")

    for i in range(2):
        e8 = data_8[i*6:(i+1)*6]
        e24 = data_24[i*6:(i+1)*6]
        d8 = decode_plx_write(0, e8[0], e8[1], list(e8[2:6]))
        d24 = decode_plx_write(0, e24[0], e24[1], list(e24[2:6]))
        print(f"\n  Loop write {i}:")
        print(f"    8:1 register 0x{d8['byte_addr']:03X}: value 0x{d8['value']:08X}")
        print(f"    2:4 register 0x{d24['byte_addr']:03X}: value 0x{d24['value']:08X}")
        if d8['byte_addr'] == d24['byte_addr']:
            diff = d8['value'] ^ d24['value']
            if diff:
                print(f"    XOR diff:  0x{diff:08X}")
                for bit in range(32):
                    if diff & (1 << bit):
                        print(f"      Bit {bit}: 8:1={'1' if d8['value'] & (1<<bit) else '0'}, "
                              f"2:4={'1' if d24['value'] & (1<<bit) else '0'}")

    # ================================================================
    # pex8696_cfg -- General PEX8696 configuration
    # ================================================================
    print("\n" + "=" * 60)
    print("pex8696_cfg -- General PEX8696 port configuration")
    print("=" * 60)

    # This function iterates over:
    # - I2C addresses: from param_2 (local_12) to 0x36 step 2
    # - Ports: 6 entries from port table [0x00, 0x02, 0x04, 0x06, 0x08, 0x0A]
    # - Registers: 5 entries from register data table
    # For each combination, it writes to write_pex8696_register

    ptr_ports = read_u32(data, 0x37410)
    port_table = read_bytes(data, ptr_ports, 6)

    ptr_regs = read_u32(data, 0x37414)
    reg_table = read_bytes(data, ptr_regs, 30)

    print("\nPort iteration table (station/port bytes):")
    for i, p in enumerate(port_table):
        station = p >> 1
        port = (p & 1) << 1  # This is the high bit, low bit from enables
        print(f"  [{i}] stn/port=0x{p:02X} -> station {station}, port {port} (global port {station*4+port})")

    print("\nRegister writes (for each port on each switch):")
    for i in range(5):
        entry = reg_table[i*6:(i+1)*6]
        enables = entry[0]
        reg_lo = entry[1]
        val = list(entry[2:6])

        # The byte[0] of the buffer is set from port_table, so we use port=0 as placeholder
        port_lo = (enables >> 7) & 1
        byte_enables = (enables >> 2) & 0xF
        reg_hi = enables & 0x03
        dword_idx = (reg_hi << 8) | reg_lo
        byte_addr = dword_idx * 4
        val_u32 = sum(b << (i2*8) for i2, b in enumerate(val))

        # The enables byte is 0x3E for most entries, which means:
        # bit[7] = 0 (port_lo = 0)
        # bits[5:2] = 0b1111 (all bytes enabled)
        # bits[1:0] = 0b10 (reg_hi = 2)
        # So for 0x3E: port_lo=0, enables=0xF, reg_hi=2

        be_str = f"0x{byte_enables:X}" if byte_enables != 0xF else "all"
        print(f"\n  Register {i+1}: DWORD 0x{dword_idx:03X} = byte addr 0x{byte_addr:03X}")
        print(f"    enables=0x{enables:02X} (byte_enables={be_str}, reg_hi={reg_hi}, port_lo={port_lo})")
        print(f"    Value: 0x{val_u32:08X} (bytes: {hex_bytes(val)})")

    # ================================================================
    # pex8696_multi_host_mode_reg_set
    # ================================================================
    print("\n" + "=" * 60)
    print("pex8696_multi_host_mode_reg_set -- Register-level mode setting")
    print("=" * 60)
    print("\nThis function sends queue messages to configure mode-specific registers.")
    print("It only executes when param_2 != 1 (i.e., not in a specific mode).")
    print()

    # Data tables
    ptr_1c = read_u32(data, 0x375a4)  # local_1c init data
    ptr_24 = read_u32(data, 0x375a8)  # local_24 init data
    ptr_2c = read_u32(data, 0x375ac)  # local_2c and auStack_34 init data

    d_1c = read_bytes(data, ptr_1c, 8)
    d_24 = read_bytes(data, ptr_24, 8)
    d_2c = read_bytes(data, ptr_2c, 8)

    print(f"Queue messages (3 total):")
    print(f"\n  Data set 1 (local_1c, 8 bytes): {hex_bytes(d_1c)}")
    print(f"  Data set 2 (local_24, 8 bytes): {hex_bytes(d_24)}")
    print(f"  Data set 3 (local_2c, 8 bytes): {hex_bytes(d_2c)}")

    # The function assembles queue messages by combining bytes from these
    # data sets. The queue message includes the callback function pointer
    # and bus/addr info.

    # The callback is at DAT_000375b0 = 0x00036690
    print(f"\n  Callback function: 0x00036690")
    print(f"  Queue handle: 0x001143E0")

    # Looking at the data:
    # d_1c = 03 07 BC EB 00 00 00 01
    # This looks like a PLX write command!
    # [03] = PLX_CMD_WRITE
    # [07] = station/port byte -> station 3, port 1 (global port 13?)
    #   Actually: station = 0x07 >> 1 = 3, port_bit1 = 0x07 & 1 = 1
    # [BC] = enables|reg_hi|port_lo = 0xBC
    #   port_lo = (0xBC >> 7) & 1 = 1
    #   byte_enables = (0xBC >> 2) & 0xF = 0xF (all)
    #   reg_hi = 0xBC & 0x03 = 0
    #   So port = (port_bit1 << 1) | port_lo = (1 << 1) | 1 = 3
    #   Global port = 3*4 + 3 = 15
    # [EB] = reg_lo = 0xEB
    # DWORD index = 0x000 << 8 | 0xEB = 0xEB = byte addr 0x3AC
    # Value = 00 00 00 01 -> 0x01000000

    print(f"\n  Interpreting data as PLX I2C commands:")
    for name, d in [("d_1c", d_1c), ("d_24", d_24), ("d_2c", d_2c)]:
        if len(d) >= 8:
            cmd = d[0]
            stn_port = d[1]
            enables = d[2]
            reg_lo = d[3]
            val = list(d[4:8])

            station = stn_port >> 1
            port_bit1 = stn_port & 1
            port_bit0 = (enables >> 7) & 1
            port = (port_bit1 << 1) | port_bit0
            byte_enables = (enables >> 2) & 0xF
            reg_hi = enables & 0x03
            dword_idx = (reg_hi << 8) | reg_lo
            byte_addr = dword_idx * 4
            val_u32 = sum(b << (i*8) for i, b in enumerate(val))

            cmd_name = "WRITE" if cmd == 3 else "READ" if cmd == 4 else f"CMD_{cmd:02X}"
            print(f"\n  {name}: {cmd_name}")
            print(f"    Raw: {hex_bytes(d)}")
            print(f"    Station {station}, port {port} (global port {station*4+port})")
            print(f"    Byte enables: 0x{byte_enables:X}")
            print(f"    Register: DWORD 0x{dword_idx:03X} = byte addr 0x{byte_addr:03X}")
            print(f"    Value: 0x{val_u32:08X}")

    # ================================================================
    # Function pointer resolution
    # ================================================================
    print("\n" + "=" * 60)
    print("FUNCTION POINTER RESOLUTION")
    print("=" * 60)

    print("\npex8696_multi_host_mode_cfg handler dispatch:")
    print("  Condition: mode==0 OR is_cfg_multi_host_8() returns 1")
    print(f"    -> calls pex8696_cfg_multi_host_4 at 0x00036CD4")
    print("  Condition: mode!=0 AND NOT 8:1 mode")
    print(f"    -> calls pex8696_cfg_multi_host_2 at 0x00036BEC")
    print()
    print("  IMPORTANT: The function names from Ghidra may be misleading!")
    print("  'multi_host_4' is called for 8:1 mode (and unconfigured)")
    print("  'multi_host_2' is called for non-8:1 mode (i.e., 2:1 or 4:1)")

    print("\npex8647_multi_host_mode_cfg handler dispatch:")
    print("  Condition: is_cfg_multi_host_8() returns 1")
    print(f"    -> calls pex8647_cfg_multi_host_8 at 0x00036DBC")
    print("  Otherwise:")
    print(f"    -> calls pex8647_cfg_multi_host_2_4 at 0x00036EF0")

    # ================================================================
    # is_cfg_multi_host_8 analysis
    # ================================================================
    print("\n" + "=" * 60)
    print("is_cfg_multi_host_8 -- Mode detection function")
    print("=" * 60)

    # From the literal pool at 0x37764:
    # 0x0010B8CB -> points to mode data
    # The data at 0x0010B8CB is: 00 11 00 00 00 D4 D2 04
    # In pex8647_multi_host_mode_cfg, DAT_00037a7c also = 0x0010B8CB
    # And it says: printf(DAT_00037a80, (uint)*DAT_00037a7c);
    # So *0x0010B8CB is a mode byte

    # From the broader context at 0x0010B8C7 (16 bytes):
    # 00 01 00 0C 00 11 00 00 00 D4 D2 04 00 00 00 00
    # DAT_00037928 = 0x0010B8C7 (mode array for 4 PEX8696 switches)
    # So: switch[0]=0x00, switch[1]=0x01, switch[2]=0x00, switch[3]=0x0C

    # And 0x0010B8CB = 0x0010B8C7 + 4 = mode array for PEX8647
    # First PEX8647 mode byte at 0x0010B8CB = 0x00
    # Second at 0x0010B8CC = 0x11

    # Wait, pex8647 iterates with step 2: local_11 = 0, 2
    # is_cfg_multi_host_8(0) and is_cfg_multi_host_8(2)
    # The function at 0x376e8 takes the index and checks a byte array

    # Let me look at the is_cfg_multi_host_8 function body more carefully
    func_bytes = read_bytes(data, 0x376e8, 128)

    # The literal pool reference at 0x37764 points to 0x0010B8CB
    # This is within the mode configuration data area
    # The function likely checks: mode_array[param] == some_value

    print("\nFunction at 0x376e8, size 0x80 (128 bytes)")
    print("Literal pool reference: 0x0010B8CB")
    print(f"Data at 0x0010B8CB: {hex_bytes(read_bytes(data, 0x10B8CB, 8))}")
    print()
    print("The mode data layout at 0x0010B8C7:")
    mode_data = read_bytes(data, 0x10B8C7, 16)
    print(f"  Bytes: {hex_bytes(mode_data)}")
    print(f"  PEX8696 mode array (4 bytes at +0): {hex_bytes(mode_data[0:4])}")
    print(f"    Switch 0: 0x{mode_data[0]:02X}")
    print(f"    Switch 1: 0x{mode_data[1]:02X}")
    print(f"    Switch 2: 0x{mode_data[2]:02X}")
    print(f"    Switch 3: 0x{mode_data[3]:02X}")
    print(f"  PEX8647 mode data (at +4): {hex_bytes(mode_data[4:8])}")
    print()
    print("NOTE: These are runtime-writable values (.bss/.data segment), so")
    print("the values in the binary are just initial/default values.")
    print("The actual mode is set by the user via IPMI commands.")


if __name__ == '__main__':
    main()
