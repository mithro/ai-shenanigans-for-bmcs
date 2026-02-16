#!/usr/bin/env python3
"""Verify exactly what buffer is passed to PI2CWriteRead in raw_plx_i2c_write."""

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

def decode_arm_data_proc(word, addr):
    """Decode ARM data processing instruction."""
    cond = (word >> 28) & 0xF
    opcode = (word >> 21) & 0xF
    S = (word >> 20) & 1
    Rn = (word >> 16) & 0xF
    Rd = (word >> 12) & 0xF
    I = (word >> 25) & 1

    op_names = ['AND','EOR','SUB','RSB','ADD','ADC','SBC','RSC',
                'TST','TEQ','CMP','CMN','ORR','MOV','BIC','MVN']

    if I:
        rotate = ((word >> 8) & 0xF) * 2
        imm = word & 0xFF
        operand2 = (imm >> rotate) | (imm << (32 - rotate)) if rotate else imm
        operand2 &= 0xFFFFFFFF
        op2_str = f"#0x{operand2:X}"
    else:
        Rm = word & 0xF
        shift_type = (word >> 5) & 3
        shift_names = ['LSL','LSR','ASR','ROR']
        shift_imm = (word >> 7) & 0x1F
        if shift_imm:
            op2_str = f"R{Rm}, {shift_names[shift_type]} #{shift_imm}"
        else:
            op2_str = f"R{Rm}"

    reg_names = {11: 'FP', 13: 'SP', 14: 'LR', 15: 'PC', 12: 'IP'}

    rn_name = reg_names.get(Rn, f"R{Rn}")
    rd_name = reg_names.get(Rd, f"R{Rd}")

    if opcode in (13, 15):  # MOV, MVN
        return f"{op_names[opcode]}{'S' if S else ''} {rd_name}, {op2_str}"
    elif opcode in (8, 9, 10, 11):  # TST, TEQ, CMP, CMN
        return f"{op_names[opcode]} {rn_name}, {op2_str}"
    else:
        return f"{op_names[opcode]}{'S' if S else ''} {rd_name}, {rn_name}, {op2_str}"

def decode_arm_ldr_str(word, addr):
    """Decode ARM LDR/STR instruction."""
    I = (word >> 25) & 1
    P = (word >> 24) & 1
    U = (word >> 23) & 1
    B = (word >> 22) & 1
    W = (word >> 21) & 1
    L = (word >> 20) & 1

    Rn = (word >> 16) & 0xF
    Rd = (word >> 12) & 0xF

    reg_names = {11: 'FP', 13: 'SP', 14: 'LR', 15: 'PC', 12: 'IP'}
    rn_name = reg_names.get(Rn, f"R{Rn}")
    rd_name = reg_names.get(Rd, f"R{Rd}")

    op = "LDR" if L else "STR"
    if B:
        op += "B"

    if not I:
        offset = word & 0xFFF
        sign = "+" if U else "-"
        if P:
            if offset == 0:
                return f"{op} {rd_name}, [{rn_name}]"
            else:
                return f"{op} {rd_name}, [{rn_name}, #{sign}0x{offset:X}]"
        else:
            return f"{op} {rd_name}, [{rn_name}], #{sign}0x{offset:X}"
    else:
        Rm = word & 0xF
        rm_name = reg_names.get(Rm, f"R{Rm}")
        sign = "+" if U else "-"
        return f"{op} {rd_name}, [{rn_name}, {sign}{rm_name}]"

def decode_arm(word, addr):
    """Basic ARM instruction decoder."""
    cond = (word >> 28) & 0xF
    cond_str = ['EQ','NE','CS','CC','MI','PL','VS','VC',
                'HI','LS','GE','LT','GT','LE','','NV'][cond]

    bits27_26 = (word >> 26) & 3
    bit25 = (word >> 25) & 1

    if bits27_26 == 0:
        if (word & 0x0F000000) == 0x0A000000:  # B
            offset_val = word & 0x00FFFFFF
            if offset_val & 0x800000:
                offset_val = offset_val - 0x1000000
            target = addr + 8 + (offset_val * 4)
            return f"B{cond_str} 0x{target:08X}"
        elif (word & 0x0F000000) == 0x0B000000:  # BL
            offset_val = word & 0x00FFFFFF
            if offset_val & 0x800000:
                offset_val = offset_val - 0x1000000
            target = addr + 8 + (offset_val * 4)
            return f"BL{cond_str} 0x{target:08X}"
        else:
            return decode_arm_data_proc(word, addr)
    elif bits27_26 == 1:
        return decode_arm_ldr_str(word, addr)
    elif bits27_26 == 2:
        if (word & 0x0E000000) == 0x0A000000:
            offset_val = word & 0x00FFFFFF
            if offset_val & 0x800000:
                offset_val = offset_val - 0x1000000
            target = addr + 8 + (offset_val * 4)
            is_link = (word >> 24) & 1
            return f"B{'L' if is_link else ''}{cond_str} 0x{target:08X}"
        else:
            # LDM/STM
            Rn = (word >> 16) & 0xF
            reg_list = word & 0xFFFF
            regs = [f"R{i}" for i in range(16) if reg_list & (1 << i)]
            reg_names_map = {11: 'FP', 12: 'IP', 13: 'SP', 14: 'LR', 15: 'PC'}
            regs = [reg_names_map.get(i, f"R{i}") for i in range(16) if reg_list & (1 << i)]
            L = (word >> 20) & 1
            op = "LDM" if L else "STM"
            U = (word >> 23) & 1
            P = (word >> 24) & 1
            W = (word >> 21) & 1
            rn_name = reg_names_map.get(Rn, f"R{Rn}")
            suffix = "FD" if (not U and P) else "ED" if (not U and not P) else "FA" if (U and not P) else "EA"
            wb = "!" if W else ""
            return f"{op}{suffix} {rn_name}{wb}, {{{', '.join(regs)}}}"
    return f"??? (0x{word:08X})"

def main():
    data = read_binary()

    print("=" * 70)
    print("FULL DISASSEMBLY: raw_plx_i2c_write (0x36690) with register tracking")
    print("=" * 70)

    func_bytes = read_bytes(data, 0x36690, 200)

    for i in range(0, 200, 4):
        word = struct.unpack_from('<I', func_bytes, i)[0]
        addr = 0x36690 + i

        if (word & 0x0FFFFFFF) == 0x089DA800 or (word & 0x0FFFFFFF) == 0x089DA808:
            decoded = decode_arm(word, addr)
            print(f"  0x{addr:08X}: {word:08X}  {decoded}")
            print("  --- end of function ---")
            break

        decoded = decode_arm(word, addr)
        print(f"  0x{addr:08X}: {word:08X}  {decoded}")

    print()
    print("=" * 70)
    print("REGISTER STATE AT PI2CWriteRead CALL (0x3672C)")
    print("=" * 70)
    print()
    print("Working backwards from the BL PI2CWriteRead at 0x3672C:")
    print()
    print("  0x36728: LDR R3, [FP, #-0x14]  -> R3 = *(fp-0x14) = data_ptr (param_4)")
    print("  0x36724: MOV R2, #9             -> R2 = 9 (write_len)")
    print("  0x36720: MOV R0, R2             -> R0 = R2 (but R2 was set at 0x36700!)")
    print()
    print("  Wait - R0 = R2, but R2 was set at 0x36700 (bus_mux).")
    print("  Then R2 is overwritten at 0x36724 with #9.")
    print("  So the order matters:")
    print("    0x36700: R2 = bus_mux")
    print("    0x36720: R0 = R2 (=bus_mux)")
    print("    0x36724: R2 = 9")
    print()
    print("  R1 was set at 0x36704: R1 = i2c_addr")
    print("  R1 is NOT modified between 0x36704 and 0x3672C")
    print()
    print("  So at BL PI2CWriteRead:")
    print("    R0 = bus_mux")
    print("    R1 = i2c_addr")
    print("    R2 = 9")
    print("    R3 = data_ptr (fp-0x14)")
    print()
    print("  PI2CWriteRead(bus_mux, i2c_addr, 9, data_ptr, 0, NULL, 0)")
    print()
    print("  CONCLUSION: The function sends 9 bytes from data_ptr to i2c_addr.")
    print("  The local_20 buffer (with cmd prepended) is built but NEVER USED!")
    print("  This is likely a compiler optimization artifact where dead code")
    print("  was not eliminated, or the decompiler is confused.")
    print()

    # Actually wait - let me reconsider. Maybe the buffer IS used and
    # I'm confused about which instruction sets R3.

    # Let me verify: between memcpy return (0x36700) and BL (0x3672C),
    # does R3 get set to anything other than stack values?

    print("Instruction trace from 0x36700 to 0x3672C:")
    for i in range(0x36700 - 0x36690, 0x36730 - 0x36690, 4):
        word = struct.unpack_from('<I', func_bytes, i)[0]
        addr = 0x36690 + i
        decoded = decode_arm(word, addr)
        print(f"  0x{addr:08X}: {word:08X}  {decoded}")

    # 0x36700: LDRB R2, [FP, #-0xD]   -> R2 = bus_mux
    # 0x36704: LDRB R1, [FP, #-0xE]   -> R1 = i2c_addr
    # 0x36708: MOV R3, #0
    # 0x3670C: STR R3, [SP]           -> stack[0] = 0 (read_len)
    # 0x36710: MOV R3, #0
    # 0x36714: STR R3, [SP, #4]       -> stack[4] = 0 (read_buf)
    # 0x36718: MOV R3, #0
    # 0x3671C: STR R3, [SP, #8]       -> stack[8] = 0 (flags)
    # 0x36720: MOV R0, R2             -> R0 = bus_mux
    # 0x36724: MOV R2, #9             -> R2 = 9
    # 0x36728: LDR R3, [FP, #-0x14]   -> R3 = fp[-0x14] = data_ptr

    # R3 at 0x36728 loads from fp-0x14.
    # data_ptr was stored at fp-0x14 at 0x366A0.
    # No subsequent store to fp-0x14.
    # So R3 = data_ptr at the BL.

    # The local_20 buffer (at fp-0x20) is built but never passed to PI2CWriteRead.
    # This IS dead code.

    # HOWEVER: maybe the function is correct and PI2CWriteRead sends
    # 9 bytes from data_ptr. The data_ptr would need to point to a
    # buffer with at least 9 bytes.

    # In pex8696_multi_host_mode_reg_set, the data comes from ROM
    # (8 bytes per entry), but the pointer is to the stack copy.
    # The stack variables are contiguous, so auStack_22 (6 bytes) is
    # followed by local_24/local_23 (2 bytes), potentially giving 8 bytes.
    # But PI2CWriteRead reads 9 bytes.

    # HMPH. Let me re-examine whether the dead code means the ACTUAL
    # write_len might be 8, not 9. Maybe I misread 0x36724.

    word_at_724 = struct.unpack_from('<I', func_bytes, 0x36724 - 0x36690)[0]
    imm = word_at_724 & 0xFF
    rotate = ((word_at_724 >> 8) & 0xF) * 2
    if rotate:
        val = ((imm >> rotate) | (imm << (32 - rotate))) & 0xFFFFFFFF
    else:
        val = imm
    print(f"\n  0x36724: 0x{word_at_724:08X}")
    print(f"  Immediate value: {val} (0x{val:X})")
    print(f"  This IS 9 (0x9).")

    print()
    print("FINAL CONCLUSION:")
    print("raw_plx_i2c_write (0x36690):")
    print("  - Receives (bus_mux, i2c_addr, cmd, data_ptr)")
    print("  - Builds local buffer: [cmd] [data[0..7]] = 9 bytes")
    print("  - Passes DATA_PTR (NOT local buffer) and len=9 to PI2CWriteRead")
    print("  - Dead code: the local buffer is constructed but never used")
    print()
    print("For pex8696_multi_host_mode_reg_set queue messages:")
    print("  bus_mux = 0xF3")
    print("  i2c_addr = 0x03 (from data byte[0])")
    print("  cmd = 0x07 (from data byte[1])")
    print("  data_ptr = &data[2..7] = 6 bytes + 3 more from adjacent memory")
    print()
    print("This sends 9 bytes to I2C address 0x03 (7-bit: 0x01).")
    print()
    print("WAIT - this CAN'T be right. I2C address 0x01 is reserved.")
    print()
    print("ALTERNATIVE: Maybe the queue handler modifies the packed value")
    print("before calling the callback. It might add the actual I2C address")
    print("from the switch being configured.")
    print()
    print("In pex8696_multi_host_mode_cfg, each queue message has a different")
    print("I2C address (0x30, 0x32, 0x34, 0x36). The reg_set function is")
    print("called AFTER cfg_multi_host_2/4, so maybe the I2C address is")
    print("already set in the queue handler context from the previous message.")


if __name__ == '__main__':
    main()
