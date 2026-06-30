#!/usr/bin/env python3
"""Extract data tables referenced by multi-host configuration functions from fullfw binary.

The fullfw ELF binary is loaded at base address 0x8000.
Virtual address = file offset + 0x8000.
File offset = virtual address - 0x8000.
"""

import struct
import sys

FULLFW_PATH = "/home/tim/github/mithro/ai-shenanigans-for-bmcs/.worktrees/pex-i2c-re/dell-c410x-firmware/pex-i2c-analysis/analysis/fullfw"

# Base address offset: virtual_addr - file_offset = 0x8000
BASE_OFFSET = 0x8000

def vaddr_to_foffset(vaddr):
    return vaddr - BASE_OFFSET

def read_bytes(data, vaddr, count):
    offset = vaddr_to_foffset(vaddr)
    return data[offset:offset+count]

def read_u32(data, vaddr):
    offset = vaddr_to_foffset(vaddr)
    return struct.unpack_from('<I', data, offset)[0]

def hex_bytes(b):
    return ' '.join(f'{x:02X}' for x in b)

def main():
    with open(FULLFW_PATH, 'rb') as f:
        data = f.read()

    print("=" * 80)
    print("MULTI-HOST CONFIGURATION DATA EXTRACTION")
    print("=" * 80)

    # First, read pointer values from the DAT_ references
    # These are ARM code that references data via PC-relative loads

    # ================================================================
    # pex8696_cfg_multi_host_2 at 0x00036bec (220 bytes)
    # References:
    #   DAT_00036cc8 - pointer to 12 bytes of register data
    #   DAT_00036ccc - pointer to counter/flag
    #   DAT_00036cd0 - pointer to command buffer (write destination)
    # ================================================================
    print("\n--- pex8696_cfg_multi_host_2 (0x36bec) ---")
    # DAT_00036cc8 contains a pointer to the 12-byte data table
    ptr_36cc8 = read_u32(data, 0x36cc8)
    print(f"DAT_00036cc8 = 0x{ptr_36cc8:08X} (pointer to 12-byte register data)")
    if ptr_36cc8 > BASE_OFFSET and ptr_36cc8 < len(data) + BASE_OFFSET:
        reg_data_2 = read_bytes(data, ptr_36cc8, 12)
        print(f"  Data (12 bytes): {hex_bytes(reg_data_2)}")
        # These 12 bytes are 2 entries of 6 bytes each
        for i in range(2):
            entry = reg_data_2[i*6:(i+1)*6]
            print(f"  Entry {i}: {hex_bytes(entry)}")
            # Interpret as PLX command: [stn/port] [enables|reg_hi] [reg_lo] [val0] [val1] [val2]
            if len(entry) >= 3:
                stn_port = entry[0]
                enables_reg_hi = entry[1]
                reg_lo = entry[2]
                dword_idx = ((enables_reg_hi & 0x03) << 8) | reg_lo
                byte_addr = dword_idx * 4
                print(f"    stn/port=0x{stn_port:02X}, enables=0x{enables_reg_hi:02X}, reg_lo=0x{reg_lo:02X}")
                print(f"    DWORD index=0x{dword_idx:03X}, byte addr=0x{byte_addr:03X}")
                if len(entry) >= 6:
                    val = entry[3:6]
                    print(f"    Value bytes: {hex_bytes(val)}")

    # DAT_00036ccc - pointer to where counter is stored
    ptr_36ccc = read_u32(data, 0x36ccc)
    print(f"DAT_00036ccc = 0x{ptr_36ccc:08X} (counter location)")

    # DAT_00036cd0 - pointer to command buffer
    ptr_36cd0 = read_u32(data, 0x36cd0)
    print(f"DAT_00036cd0 = 0x{ptr_36cd0:08X} (command buffer for memcpy dest)")

    # ================================================================
    # pex8696_cfg_multi_host_4 at 0x00036cd4 (220 bytes)
    # References:
    #   DAT_00036db0 - pointer to 12 bytes of register data
    #   DAT_00036db4 - pointer to counter
    #   DAT_00036db8 - pointer to command buffer
    # ================================================================
    print("\n--- pex8696_cfg_multi_host_4 (0x36cd4) ---")
    ptr_36db0 = read_u32(data, 0x36db0)
    print(f"DAT_00036db0 = 0x{ptr_36db0:08X} (pointer to 12-byte register data)")
    if ptr_36db0 > BASE_OFFSET and ptr_36db0 < len(data) + BASE_OFFSET:
        reg_data_4 = read_bytes(data, ptr_36db0, 12)
        print(f"  Data (12 bytes): {hex_bytes(reg_data_4)}")
        for i in range(2):
            entry = reg_data_4[i*6:(i+1)*6]
            print(f"  Entry {i}: {hex_bytes(entry)}")
            if len(entry) >= 3:
                stn_port = entry[0]
                enables_reg_hi = entry[1]
                reg_lo = entry[2]
                dword_idx = ((enables_reg_hi & 0x03) << 8) | reg_lo
                byte_addr = dword_idx * 4
                print(f"    stn/port=0x{stn_port:02X}, enables=0x{enables_reg_hi:02X}, reg_lo=0x{reg_lo:02X}")
                print(f"    DWORD index=0x{dword_idx:03X}, byte addr=0x{byte_addr:03X}")
                if len(entry) >= 6:
                    val = entry[3:6]
                    print(f"    Value bytes: {hex_bytes(val)}")

    ptr_36db4 = read_u32(data, 0x36db4)
    print(f"DAT_00036db4 = 0x{ptr_36db4:08X} (counter location)")
    ptr_36db8 = read_u32(data, 0x36db8)
    print(f"DAT_00036db8 = 0x{ptr_36db8:08X} (command buffer)")

    # ================================================================
    # pex8647_cfg_multi_host_8 at 0x00036dbc (296 bytes)
    # References:
    #   DAT_00036ee4 - pointer to 18 bytes of data
    #   DAT_00036ee8 - pointer to counter
    #   DAT_00036eec - pointer to command buffer
    # ================================================================
    print("\n--- pex8647_cfg_multi_host_8 (0x36dbc) ---")
    ptr_36ee4 = read_u32(data, 0x36ee4)
    print(f"DAT_00036ee4 = 0x{ptr_36ee4:08X} (pointer to 18-byte data)")
    if ptr_36ee4 > BASE_OFFSET and ptr_36ee4 < len(data) + BASE_OFFSET:
        reg_data_8647_8 = read_bytes(data, ptr_36ee4, 18)
        print(f"  Data (18 bytes): {hex_bytes(reg_data_8647_8)}")
        # First 12 bytes are auStack_30 (2 entries of 6 bytes)
        # Next 6 bytes are auStack_24 (1 entry of 6 bytes, written first with counter=4)
        print("  auStack_30 (loop entries, 2x6 bytes):")
        for i in range(2):
            entry = reg_data_8647_8[i*6:(i+1)*6]
            print(f"    Entry {i}: {hex_bytes(entry)}")
            if len(entry) >= 3:
                stn_port = entry[0]
                enables_reg_hi = entry[1]
                reg_lo = entry[2]
                dword_idx = ((enables_reg_hi & 0x03) << 8) | reg_lo
                byte_addr = dword_idx * 4
                print(f"      stn/port=0x{stn_port:02X}, enables=0x{enables_reg_hi:02X}, reg_lo=0x{reg_lo:02X}")
                print(f"      DWORD index=0x{dword_idx:03X}, byte addr=0x{byte_addr:03X}")
                if len(entry) >= 6:
                    val = entry[3:6]
                    print(f"      Value bytes: {hex_bytes(val)}")
        print("  auStack_24 (initial write with counter=4, 6 bytes):")
        entry = reg_data_8647_8[12:18]
        print(f"    Entry: {hex_bytes(entry)}")
        if len(entry) >= 3:
            stn_port = entry[0]
            enables_reg_hi = entry[1]
            reg_lo = entry[2]
            dword_idx = ((enables_reg_hi & 0x03) << 8) | reg_lo
            byte_addr = dword_idx * 4
            print(f"      stn/port=0x{stn_port:02X}, enables=0x{enables_reg_hi:02X}, reg_lo=0x{reg_lo:02X}")
            print(f"      DWORD index=0x{dword_idx:03X}, byte addr=0x{byte_addr:03X}")
            if len(entry) >= 6:
                val = entry[3:6]
                print(f"      Value bytes: {hex_bytes(val)}")

    ptr_36ee8 = read_u32(data, 0x36ee8)
    print(f"DAT_00036ee8 = 0x{ptr_36ee8:08X} (counter location)")
    ptr_36eec = read_u32(data, 0x36eec)
    print(f"DAT_00036eec = 0x{ptr_36eec:08X} (command buffer)")

    # ================================================================
    # pex8647_cfg_multi_host_2_4 at 0x00036ef0 (296 bytes)
    # References:
    #   DAT_00037018 - pointer to 18 bytes of data
    #   DAT_0003701c - pointer to counter
    #   DAT_00037020 - pointer to command buffer
    # ================================================================
    print("\n--- pex8647_cfg_multi_host_2_4 (0x36ef0) ---")
    ptr_37018 = read_u32(data, 0x37018)
    print(f"DAT_00037018 = 0x{ptr_37018:08X} (pointer to 18-byte data)")
    if ptr_37018 > BASE_OFFSET and ptr_37018 < len(data) + BASE_OFFSET:
        reg_data_8647_24 = read_bytes(data, ptr_37018, 18)
        print(f"  Data (18 bytes): {hex_bytes(reg_data_8647_24)}")
        print("  auStack_30 (loop entries, 2x6 bytes):")
        for i in range(2):
            entry = reg_data_8647_24[i*6:(i+1)*6]
            print(f"    Entry {i}: {hex_bytes(entry)}")
            if len(entry) >= 3:
                stn_port = entry[0]
                enables_reg_hi = entry[1]
                reg_lo = entry[2]
                dword_idx = ((enables_reg_hi & 0x03) << 8) | reg_lo
                byte_addr = dword_idx * 4
                print(f"      stn/port=0x{stn_port:02X}, enables=0x{enables_reg_hi:02X}, reg_lo=0x{reg_lo:02X}")
                print(f"      DWORD index=0x{dword_idx:03X}, byte addr=0x{byte_addr:03X}")
                if len(entry) >= 6:
                    val = entry[3:6]
                    print(f"      Value bytes: {hex_bytes(val)}")
        print("  auStack_24 (initial write with counter=4, 6 bytes):")
        entry = reg_data_8647_24[12:18]
        print(f"    Entry: {hex_bytes(entry)}")
        if len(entry) >= 3:
            stn_port = entry[0]
            enables_reg_hi = entry[1]
            reg_lo = entry[2]
            dword_idx = ((enables_reg_hi & 0x03) << 8) | reg_lo
            byte_addr = dword_idx * 4
            print(f"      stn/port=0x{stn_port:02X}, enables=0x{enables_reg_hi:02X}, reg_lo=0x{reg_lo:02X}")
            print(f"      DWORD index=0x{dword_idx:03X}, byte addr=0x{byte_addr:03X}")
            if len(entry) >= 6:
                val = entry[3:6]
                print(f"      Value bytes: {hex_bytes(val)}")

    ptr_3701c = read_u32(data, 0x3701c)
    print(f"DAT_0003701c = 0x{ptr_3701c:08X} (counter location)")
    ptr_37020 = read_u32(data, 0x37020)
    print(f"DAT_00037020 = 0x{ptr_37020:08X} (command buffer)")

    # ================================================================
    # pex8696_cfg at 0x000372ac (356 bytes)
    # References:
    #   DAT_00037410 - pointer to 6-byte port table
    #   DAT_00037414 - pointer to 30-byte (0x1E) register data
    #   DAT_00037418 - command buffer byte 0
    #   DAT_0003741c - command buffer (6-byte memcpy dest)
    # ================================================================
    print("\n--- pex8696_cfg (0x372ac) ---")
    ptr_37410 = read_u32(data, 0x37410)
    print(f"DAT_00037410 = 0x{ptr_37410:08X} (pointer to 6-byte port table)")
    if ptr_37410 > BASE_OFFSET and ptr_37410 < len(data) + BASE_OFFSET:
        port_table = read_bytes(data, ptr_37410, 6)
        print(f"  Port table (6 bytes): {hex_bytes(port_table)}")
        for i, p in enumerate(port_table):
            station = p >> 1
            port_lo = (p & 1) << 7
            print(f"    Port[{i}]: 0x{p:02X} -> station={station}, port_hi_bit={p & 1}")

    ptr_37414 = read_u32(data, 0x37414)
    print(f"DAT_00037414 = 0x{ptr_37414:08X} (pointer to 30-byte register data)")
    if ptr_37414 > BASE_OFFSET and ptr_37414 < len(data) + BASE_OFFSET:
        reg_data_cfg = read_bytes(data, ptr_37414, 30)
        print(f"  Register data (30 bytes = 5 x 6 byte entries): {hex_bytes(reg_data_cfg)}")
        for i in range(5):
            entry = reg_data_cfg[i*6:(i+1)*6]
            print(f"  Entry {i}: {hex_bytes(entry)}")
            if len(entry) >= 3:
                enables_reg_hi = entry[0]
                reg_lo = entry[1]
                dword_idx = ((enables_reg_hi & 0x03) << 8) | reg_lo
                byte_addr = dword_idx * 4
                print(f"    enables|reg_hi=0x{enables_reg_hi:02X}, reg_lo=0x{reg_lo:02X}")
                print(f"    DWORD index=0x{dword_idx:03X}, byte addr=0x{byte_addr:03X}")
                if len(entry) >= 6:
                    val = entry[2:6]
                    print(f"    Value bytes: {hex_bytes(val)}")

    ptr_37418 = read_u32(data, 0x37418)
    print(f"DAT_00037418 = 0x{ptr_37418:08X} (command buffer byte 0)")
    ptr_3741c = read_u32(data, 0x3741c)
    print(f"DAT_0003741c = 0x{ptr_3741c:08X} (command buffer memcpy dest)")

    # ================================================================
    # pex8696_multi_host_mode_reg_set at 0x00037420 (388 bytes)
    # References:
    #   DAT_000375a4 - pointer to 8-byte data (local_1c init)
    #   DAT_000375a8 - pointer to 8-byte data (local_24 init)
    #   DAT_000375ac - pointer to 8-byte data (local_2c + auStack_34 init)
    #   DAT_000375b0 - callback/function pointer
    #   DAT_000375b4 - queue handle
    # ================================================================
    print("\n--- pex8696_multi_host_mode_reg_set (0x37420) ---")
    ptr_375a4 = read_u32(data, 0x375a4)
    print(f"DAT_000375a4 = 0x{ptr_375a4:08X} (pointer to 8-byte data for local_1c)")
    if ptr_375a4 > BASE_OFFSET and ptr_375a4 < len(data) + BASE_OFFSET:
        d = read_bytes(data, ptr_375a4, 8)
        print(f"  Data: {hex_bytes(d)}")

    ptr_375a8 = read_u32(data, 0x375a8)
    print(f"DAT_000375a8 = 0x{ptr_375a8:08X} (pointer to 8-byte data for local_24)")
    if ptr_375a8 > BASE_OFFSET and ptr_375a8 < len(data) + BASE_OFFSET:
        d = read_bytes(data, ptr_375a8, 8)
        print(f"  Data: {hex_bytes(d)}")

    ptr_375ac = read_u32(data, 0x375ac)
    print(f"DAT_000375ac = 0x{ptr_375ac:08X} (pointer to 8-byte data for local_2c/auStack_34)")
    if ptr_375ac > BASE_OFFSET and ptr_375ac < len(data) + BASE_OFFSET:
        d = read_bytes(data, ptr_375ac, 8)
        print(f"  Data: {hex_bytes(d)}")

    ptr_375b0 = read_u32(data, 0x375b0)
    print(f"DAT_000375b0 = 0x{ptr_375b0:08X} (callback/function pointer)")
    ptr_375b4 = read_u32(data, 0x375b4)
    print(f"DAT_000375b4 = 0x{ptr_375b4:08X} (queue handle)")

    # ================================================================
    # pex8696_multi_host_mode_cfg at 0x00037768 (448 bytes)
    # References:
    #   DAT_00037928 - pointer to 4-byte mode array (one per PEX8696 switch)
    #   DAT_0003792c - format string pointer
    #   DAT_00037930 - pointer to 8-byte buffer (zeroed before use)
    #   DAT_00037934 - function pointer (for 8:1 mode)
    #   DAT_00037938 - function pointer (for non-8:1 mode)
    #   DAT_0003793c - queue handle
    # ================================================================
    print("\n--- pex8696_multi_host_mode_cfg (0x37768) ---")
    ptr_37928 = read_u32(data, 0x37928)
    print(f"DAT_00037928 = 0x{ptr_37928:08X} (pointer to 4-byte mode array)")
    if ptr_37928 > BASE_OFFSET and ptr_37928 < len(data) + BASE_OFFSET:
        mode_arr = read_bytes(data, ptr_37928, 4)
        print(f"  Mode array: {hex_bytes(mode_arr)}")
        for i, m in enumerate(mode_arr):
            print(f"    Switch {i}: mode={m}")

    ptr_37934 = read_u32(data, 0x37934)
    print(f"DAT_00037934 = 0x{ptr_37934:08X} (function pointer for 8:1 / mode==0 path)")
    ptr_37938 = read_u32(data, 0x37938)
    print(f"DAT_00037938 = 0x{ptr_37938:08X} (function pointer for non-8:1 path)")

    # ================================================================
    # pex8647_multi_host_mode_cfg at 0x00037944 (312 bytes)
    # References:
    #   DAT_00037a7c - pointer to 1-byte mode value
    #   DAT_00037a84 - pointer to 8-byte buffer
    #   DAT_00037a88 - function pointer (for 8:1 mode)
    #   DAT_00037a8c - function pointer (for non-8:1 mode)
    #   DAT_00037a90 - queue handle
    # ================================================================
    print("\n--- pex8647_multi_host_mode_cfg (0x37944) ---")
    ptr_37a7c = read_u32(data, 0x37a7c)
    print(f"DAT_00037a7c = 0x{ptr_37a7c:08X} (pointer to mode byte)")
    if ptr_37a7c > BASE_OFFSET and ptr_37a7c < len(data) + BASE_OFFSET:
        mode_val = read_bytes(data, ptr_37a7c, 2)
        print(f"  Mode values: {hex_bytes(mode_val)}")

    ptr_37a88 = read_u32(data, 0x37a88)
    print(f"DAT_00037a88 = 0x{ptr_37a88:08X} (function pointer for 8:1 mode)")
    ptr_37a8c = read_u32(data, 0x37a8c)
    print(f"DAT_00037a8c = 0x{ptr_37a8c:08X} (function pointer for non-8:1 mode)")

    # ================================================================
    # multi_host_mode_set at 0x00038230 (312 bytes)
    # References:
    #   DAT_00038368 - format string
    # ================================================================
    print("\n--- multi_host_mode_set (0x38230) ---")
    ptr_38368 = read_u32(data, 0x38368)
    print(f"DAT_00038368 = 0x{ptr_38368:08X} (format string pointer)")
    if ptr_38368 > BASE_OFFSET and ptr_38368 < len(data) + BASE_OFFSET:
        fmt = read_bytes(data, ptr_38368, 80)
        # Find null terminator
        null_idx = fmt.find(b'\x00')
        if null_idx >= 0:
            fmt = fmt[:null_idx]
        print(f"  Format string: {fmt}")

    # ================================================================
    # pex8696_all_slot_off at 0x000375b8 (288 bytes)
    # References:
    #   DAT_000376d8 - pointer to 4-byte port table
    #   DAT_000376dc - pointer to 6-byte register data
    #   DAT_000376e0 - command buffer byte 0
    #   DAT_000376e4 - command buffer (memcpy dest)
    # ================================================================
    print("\n--- pex8696_all_slot_off (0x375b8) ---")
    ptr_376d8 = read_u32(data, 0x376d8)
    print(f"DAT_000376d8 = 0x{ptr_376d8:08X} (pointer to 4-byte port table)")
    if ptr_376d8 > BASE_OFFSET and ptr_376d8 < len(data) + BASE_OFFSET:
        port_tbl = read_bytes(data, ptr_376d8, 4)
        print(f"  Port table: {hex_bytes(port_tbl)}")
        for i, p in enumerate(port_tbl):
            station = p >> 1
            print(f"    Port[{i}]: 0x{p:02X} -> station={station}")

    ptr_376dc = read_u32(data, 0x376dc)
    print(f"DAT_000376dc = 0x{ptr_376dc:08X} (pointer to 6-byte register data)")
    if ptr_376dc > BASE_OFFSET and ptr_376dc < len(data) + BASE_OFFSET:
        reg_data = read_bytes(data, ptr_376dc, 6)
        print(f"  Register data: {hex_bytes(reg_data)}")
        if len(reg_data) >= 2:
            enables_reg_hi = reg_data[0]
            reg_lo = reg_data[1]
            dword_idx = ((enables_reg_hi & 0x03) << 8) | reg_lo
            byte_addr = dword_idx * 4
            print(f"    enables|reg_hi=0x{enables_reg_hi:02X}, reg_lo=0x{reg_lo:02X}")
            print(f"    DWORD index=0x{dword_idx:03X}, byte addr=0x{byte_addr:03X}")
            if len(reg_data) >= 6:
                val = reg_data[2:6]
                print(f"    Value bytes: {hex_bytes(val)}")

    ptr_376e0 = read_u32(data, 0x376e0)
    print(f"DAT_000376e0 = 0x{ptr_376e0:08X} (command buffer byte 0)")
    ptr_376e4 = read_u32(data, 0x376e4)
    print(f"DAT_000376e4 = 0x{ptr_376e4:08X} (command buffer memcpy dest)")

    # ================================================================
    # is_cfg_multi_host_8 at 0x000376e8 (128 bytes)
    # ================================================================
    print("\n--- is_cfg_multi_host_8 (0x376e8) ---")
    print("  Reading raw bytes of function:")
    func_bytes = read_bytes(data, 0x376e8, 128)
    # Try to find data references in the function
    # ARM instructions that load from PC-relative addresses
    for i in range(0, 128, 4):
        word = struct.unpack_from('<I', func_bytes, i)[0]
        # LDR instruction pattern: xxxx 0101 xxxx xxxx xxxx xxxx xxxx xxxx
        # Simplified: just look at the last few words which are typically literal pool
    # Just dump the last 16 bytes (literal pool area)
    print(f"  Last 32 bytes: {hex_bytes(func_bytes[96:])}")
    # Look for pointers in those
    for i in range(96, 128, 4):
        word = struct.unpack_from('<I', func_bytes, i)[0]
        addr = 0x376e8 + i
        print(f"    0x{addr:08X}: 0x{word:08X}")
        if word > BASE_OFFSET and word < len(data) + BASE_OFFSET:
            ref_data = read_bytes(data, word, 8)
            print(f"      -> data at 0x{word:08X}: {hex_bytes(ref_data)}")

    # ================================================================
    # Look at the pex8696_multi_host_mode_cfg function more carefully
    # to understand which function pointers are cfg_multi_host_2 vs _4
    # ================================================================
    print("\n--- Function Pointer Analysis ---")
    print(f"pex8696_cfg_multi_host_2 is at 0x00036bec")
    print(f"pex8696_cfg_multi_host_4 is at 0x00036cd4")
    print(f"pex8647_cfg_multi_host_8 is at 0x00036dbc")
    print(f"pex8647_cfg_multi_host_2_4 is at 0x00036ef0")
    print(f"pex8696_cfg is at 0x000372ac")

    # DAT_00037934 should be one of the cfg_ functions
    print(f"\nIn pex8696_multi_host_mode_cfg:")
    print(f"  8:1/mode==0 handler: 0x{ptr_37934:08X}")
    print(f"  non-8:1 handler:     0x{ptr_37938:08X}")

    print(f"\nIn pex8647_multi_host_mode_cfg:")
    print(f"  8:1 handler: 0x{ptr_37a88:08X}")
    print(f"  non-8:1 handler: 0x{ptr_37a8c:08X}")

    # ================================================================
    # Also dump raw data around the function areas
    # Try to understand what the mode values mean
    # ================================================================
    print("\n--- Additional Context ---")

    # Check what pex8696_multi_host_mode_cfg does with the mode values
    # DAT_00037928 points to mode array, let's read more context
    if ptr_37928 > BASE_OFFSET:
        # Read surrounding data
        print(f"\nMode array location: 0x{ptr_37928:08X}")
        context = read_bytes(data, ptr_37928, 16)
        print(f"  Data at 0x{ptr_37928:08X} (16 bytes): {hex_bytes(context)}")

    # The code checks DAT_00037928[local_11] == 0 || is_cfg_multi_host_8()
    # If true, uses DAT_00037934 (8:1 handler); else DAT_00037938 (non-8:1)
    # So mode==0 means 8:1 (or unconfigured/default)

    # For PEX8647, local_11 iterates 0, 2 (step 2)
    # If is_cfg_multi_host_8(local_11) == 1, use 8:1 handler
    # Else use 2:4 handler

    print("\n--- Summary of Multi-Host Mode Queue Messages ---")
    print("\npex8696_multi_host_mode_cfg sends per-switch queue messages:")
    print("  Switch 0: bus_mux=0x30F3 -> I2C addr 0x30 (PEX8696 #0), bus 3")
    print("  Switch 1: bus_mux=0x34F3 -> I2C addr 0x34 (PEX8696 #1), bus 3")
    print("  Switch 2: bus_mux=0x32F3 -> I2C addr 0x32 (PEX8696 #2), bus 3")
    print("  Switch 3: bus_mux=0x36F3 -> I2C addr 0x36 (PEX8696 #3), bus 3")
    print()
    print("pex8647_multi_host_mode_cfg sends per-switch queue messages:")
    print("  local_11=0: bus_mux=0xD4F3 -> I2C addr 0xD4 (PEX8647 #0), bus 3")
    print("  local_11=2: bus_mux=0xD0F3 -> I2C addr 0xD0 (PEX8647 #1), bus 3")

    # ================================================================
    # Also check what multi_host_mode_set does with param values
    # ================================================================
    print("\n--- multi_host_mode_set IPMI command mapping ---")
    print("  param_1 == 0x802D -> local_16 = 0x30 (PEX8696 I2C addr for switch 0)")
    print("  param_1 == 0x802E -> local_16 = 0x32 (PEX8696 I2C addr for switch 2)")
    print("  param_1 == 0x802F -> local_16 = 0x34 (PEX8696 I2C addr for switch 1)")
    print("  param_1 == other  -> local_16 = 0x36 (PEX8696 I2C addr for switch 3)")
    print("  Then reads discrete sensor value via RawDiscreteRead")


if __name__ == '__main__':
    main()
