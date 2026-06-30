#!/usr/bin/env python3
"""Trace callers of pex8696_multi_host_mode_reg_set and understand queue dispatch."""

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

def main():
    data = read_binary()

    print("=" * 60)
    print("TRACING QUEUE DISPATCH MECHANISM")
    print("=" * 60)

    # The table at 0x109C50 references 0x37420.
    # Let me dump more of this table to understand its structure.
    print("\nTable at 0x109C40 (64 bytes):")
    for i in range(16):
        addr = 0x109C40 + i * 4
        val = read_u32(data, addr)
        print(f"  0x{addr:08X}: 0x{val:08X}")

    # Larger context
    print("\nTable at 0x109C00 (256 bytes):")
    for i in range(64):
        addr = 0x109C00 + i * 4
        val = read_u32(data, addr)
        # Mark known function addresses
        known = {
            0x36BEC: "pex8696_cfg_multi_host_2",
            0x36CD4: "pex8696_cfg_multi_host_4",
            0x36DBC: "pex8647_cfg_multi_host_8",
            0x36EF0: "pex8647_cfg_multi_host_2_4",
            0x372AC: "pex8696_cfg",
            0x37420: "pex8696_multi_host_mode_reg_set",
            0x375B8: "pex8696_all_slot_off",
            0x376E8: "is_cfg_multi_host_8",
            0x37768: "pex8696_multi_host_mode_cfg",
            0x37944: "pex8647_multi_host_mode_cfg",
            0x38230: "multi_host_mode_set",
            0x36690: "callback_0x36690",
        }
        label = known.get(val, "")
        if label:
            label = f" <- {label}"
        print(f"  0x{addr:08X}: 0x{val:08X}{label}")

    # Now, let me understand the actual calling mechanism.
    # The pex8696_multi_host_mode_reg_set is called from pex8696_multi_host_mode_cfg
    # (or somewhere in the queue handler chain).

    # Let me look more carefully at pex8696_multi_host_mode_cfg.
    # It dispatches queue messages, and the callback is either
    # pex8696_cfg_multi_host_4 (0x36CD4) or pex8696_cfg_multi_host_2 (0x36BEC).
    # So those are the "primary" mode config functions.

    # But pex8696_multi_host_mode_reg_set is a SEPARATE function that sends
    # additional queue messages via a DIFFERENT callback (0x36690).

    # Let me check what 0x36690 is.
    print("\n" + "=" * 60)
    print("Function at 0x36690 (callback from reg_set)")
    print("=" * 60)

    # Dump the function bytes
    func_bytes = read_bytes(data, 0x36690, 256)
    for i in range(0, 256, 4):
        word = struct.unpack_from('<I', func_bytes, i)[0]
        addr = 0x36690 + i
        # Check for BL instructions
        if (word & 0x0F000000) == 0x0B000000 and ((word >> 28) & 0xF) == 0xE:
            offset_val = word & 0x00FFFFFF
            if offset_val & 0x800000:
                offset_val = offset_val - 0x1000000
            pc = addr + 8
            target = pc + (offset_val * 4)
            known_name = {
                0x2EAD4: "write_pex8696_register",
                0x2EBF0: "read_pex8696_register",
                0x36AD0: "write_pex8647_register",
                0x36998: "read_pex8647_register",
                0x253C4: "PI2CWriteRead",
                0x256C4: "PI2CMuxWriteRead",
            }.get(target, f"func_{target:08X}")
            print(f"  0x{addr:08X}: {word:08X}  BL -> 0x{target:08X} ({known_name})")
        elif addr >= 0x36690 + 200:  # Literal pool area
            print(f"  0x{addr:08X}: {word:08X}  (literal pool)")
            if word > BASE_OFFSET and word < len(data) + BASE_OFFSET:
                ref = read_bytes(data, word, 8)
                print(f"             -> 0x{word:08X}: {hex_bytes(ref)}")
        else:
            print(f"  0x{addr:08X}: {word:08X}")

    # Now let me look at who calls pex8696_multi_host_mode_reg_set
    # It's likely called from pex8696_multi_host_mode_cfg or a related setup function
    print("\n" + "=" * 60)
    print("Scanning for ALL callers (BL) of reg_set and related functions")
    print("=" * 60)

    targets = {
        0x37420: "pex8696_multi_host_mode_reg_set",
        0x37768: "pex8696_multi_host_mode_cfg",
        0x37944: "pex8647_multi_host_mode_cfg",
        0x38230: "multi_host_mode_set",
    }

    for target_addr, target_name in targets.items():
        found = False
        for i in range(0, len(data) - 4, 4):
            word = struct.unpack_from('<I', data, i)[0]
            if (word & 0x0F000000) == 0x0B000000:
                cond = (word >> 28) & 0xF
                offset_val = word & 0x00FFFFFF
                if offset_val & 0x800000:
                    offset_val = offset_val - 0x1000000
                pc = i + BASE_OFFSET + 8
                branch_target = pc + (offset_val * 4)
                if branch_target == target_addr:
                    caller_addr = i + BASE_OFFSET
                    if not found:
                        print(f"\n  Callers of {target_name} (0x{target_addr:08X}):")
                        found = True
                    cond_str = ['EQ','NE','CS','CC','MI','PL','VS','VC',
                                'HI','LS','GE','LT','GT','LE','AL','NV'][cond]
                    print(f"    BL{cond_str} at 0x{caller_addr:08X}")
        if not found:
            print(f"\n  No direct callers found for {target_name} (0x{target_addr:08X})")

    # Also check who calls the callback 0x36690
    print("\n  Scanning for callers of 0x36690:")
    for i in range(0, len(data) - 4, 4):
        word = struct.unpack_from('<I', data, i)[0]
        if (word & 0x0F000000) == 0x0B000000:
            cond = (word >> 28) & 0xF
            offset_val = word & 0x00FFFFFF
            if offset_val & 0x800000:
                offset_val = offset_val - 0x1000000
            pc = i + BASE_OFFSET + 8
            branch_target = pc + (offset_val * 4)
            if branch_target == 0x36690:
                caller_addr = i + BASE_OFFSET
                cond_str = ['EQ','NE','CS','CC','MI','PL','VS','VC',
                            'HI','LS','GE','LT','GT','LE','AL','NV'][cond]
                print(f"    BL{cond_str} at 0x{caller_addr:08X}")


if __name__ == '__main__':
    main()
