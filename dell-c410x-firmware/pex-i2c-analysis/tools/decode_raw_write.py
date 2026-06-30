#!/usr/bin/env python3
"""Carefully decode raw_plx_i2c_write at 0x36690 by tracing ARM register usage."""

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
    print("DETAILED ARM TRACE: raw_plx_i2c_write (0x36690)")
    print("=" * 60)
    print()
    print("Function signature: func(r0=bus_mux, r1=i2c_addr, r2=cmd, r3=data_ptr)")
    print()

    # Instruction-by-instruction trace:
    # 0x36690: E1A0C00D  MOV IP, SP              ; prologue
    # 0x36694: E92DD800  STMFD SP!, {R11, R12, LR, PC}
    # 0x36698: E24CB004  SUB R11, R12, #4        ; R11 = frame pointer
    # 0x3669C: E24DD024  SUB SP, SP, #0x24       ; allocate 36 bytes

    # 0x366A0: E50B3014  STR R3, [R11, #-0x14]   ; save r3 (data_ptr) to fp-0x14
    # 0x366A4: E1A03000  MOV R3, R0              ; r3 = bus_mux
    # 0x366A8: E54B300D  STRB R3, [R11, #-0x0D]  ; save bus_mux to fp-0x0D
    # 0x366AC: E1A03001  MOV R3, R1              ; r3 = i2c_addr
    # 0x366B0: E54B300E  STRB R3, [R11, #-0x0E]  ; save i2c_addr to fp-0x0E
    # 0x366B4: E1A03002  MOV R3, R2              ; r3 = cmd
    # 0x366B8: E54B300F  STRB R3, [R11, #-0x0F]  ; save cmd to fp-0x0F

    # 0x366BC: E24B3020  SUB R3, R11, #0x20      ; r3 = &local_20 (buffer base)
    # 0x366C0: E3A02000  MOV R2, #0
    # 0x366C4: E5832000  STR R2, [R3]            ; local_20[0..3] = 0
    # 0x366C8: E2833004  ADD R3, R3, #4
    # 0x366CC: E3A02000  MOV R2, #0
    # 0x366D0: E5832000  STR R2, [R3]            ; local_20[4..7] = 0
    # 0x366D4: E2833004  ADD R3, R3, #4
    # 0x366D8: E3A02000  MOV R2, #0
    # 0x366DC: E5C32000  STRB R2, [R3]           ; local_20[8] = 0
    #   Total: zeroed 9 bytes at local_20

    # 0x366E0: E55B300F  LDRB R3, [R11, #-0x0F]  ; r3 = cmd (param_3)
    # 0x366E4: E54B3020  STRB R3, [R11, #-0x20]  ; local_20[0] = cmd

    # 0x366E8: E24B3020  SUB R3, R11, #0x20      ; r3 = &local_20
    # 0x366EC: E2833001  ADD R3, R3, #1           ; r3 = &local_20[1]
    # 0x366F0: E1A00003  MOV R0, R3              ; dest = &local_20[1]
    # 0x366F4: E51B1014  LDR R1, [R11, #-0x14]   ; src = data_ptr (param_4)
    # 0x366F8: E3A02008  MOV R2, #8              ; len = 8
    # 0x366FC: BL memcpy                          ; memcpy(&local_20[1], data_ptr, 8)

    # After memcpy: local_20 = [cmd, data[0], data[1], ..., data[7]]
    # Total: 9 bytes

    # Now prepare PI2CWriteRead call:
    # 0x36700: E55B200D  LDRB R2, [R11, #-0x0D]  ; r2 = bus_mux
    # 0x36704: E55B100E  LDRB R1, [R11, #-0x0E]  ; r1 = i2c_addr

    # Push stack args for PI2CWriteRead(bus_mux, i2c_addr, write_len, write_buf, read_len, read_buf, flags):
    # 0x36708: E3A03000  MOV R3, #0
    # 0x3670C: E58D3000  STR R3, [SP, #0]        ; read_len = 0 (stack arg 1)
    # 0x36710: E3A03000  MOV R3, #0
    # 0x36714: E58D3004  STR R3, [SP, #4]        ; read_buf = NULL (stack arg 2)
    # 0x36718: E3A03000  MOV R3, #0
    # 0x3671C: E58D3008  STR R3, [SP, #8]        ; flags = 0 (stack arg 3)

    # 0x36720: E1A00002  MOV R0, R2              ; r0 = bus_mux
    #
    # Wait, but r2 has bus_mux (loaded at 0x36700)
    # r1 has i2c_addr (loaded at 0x36704)
    # So r0 = bus_mux, r1 = i2c_addr

    # 0x36724: E3A02009  MOV R2, #9              ; r2 = write_len = 9

    # Now what's r3 (write_buf)?
    # 0x36728: E51B3014  LDR R3, [R11, #-0x14]   ; r3 = data_ptr (param_4)

    # WAIT! r3 = param_4 (the ORIGINAL data_ptr), NOT &local_20!
    # But the data was copied into local_20. So PI2CWriteRead is being
    # called with the WRONG buffer?!

    # Actually no - PI2CWriteRead takes write_buf as param_4 (r3).
    # Let me check the calling convention:
    # PI2CWriteRead(r0=bus_mux, r1=slave_addr, r2=write_len, r3=write_buf,
    #               sp[0]=read_len, sp[4]=read_buf, sp[8]=flags)

    # So r3 = write_buf = data_ptr (param_4)

    # But the function carefully built local_20 = [cmd, data[0..7]]!
    # Why would it pass data_ptr instead of &local_20?

    # UNLESS... let me re-read 0x36728 more carefully.
    # E51B3014 = LDR R3, [R11, #-0x14]
    # fp-0x14 stored R3 (data_ptr) at 0x366A0
    #
    # Hmm, but it ALSO stored the memcpy result in local_20 at fp-0x20 through fp-0x18
    #
    # Maybe 0x36728 should be loading &local_20, not data_ptr.
    # Let me check if E51B3014 is really fp-0x14 or fp-0x20...

    # E51B3014 = xxxx 0101 0001 1011 0011 0000 0001 0100
    # Bits [23]=0 (subtract), [11:0]=0x014 = 20 decimal
    # Rn = R11 (fp)
    # So it's: LDR R3, [R11, #-20]
    # fp - 20 = fp - 0x14

    # fp-0x14 is where data_ptr was stored. So r3 = data_ptr.

    # This means PI2CWriteRead is called with:
    #   r0 = bus_mux
    #   r1 = i2c_addr (0x03 for the reg_set case)
    #   r2 = 9 (write length)
    #   r3 = data_ptr (NOT the local buffer!)
    #   read_len=0, read_buf=NULL, flags=0

    # But data_ptr only has 6 bytes (auStack_22 in reg_set)!
    # Writing 9 bytes from a 6-byte buffer would read beyond the buffer.

    # UNLESS... the function is actually using &local_20 and I'm
    # misreading the instruction.

    # Let me try: what if fp-0x14 is actually &local_20?
    # local_20 is at fp-0x20. That's -32 = 0x20.
    # fp-0x14 is -20.
    # These are different addresses.

    # OK so this IS reading from fp-0x14 which is where data_ptr was saved.

    # BUT WAIT: At 0x366A0, it does STR R3, [R11, #-0x14] BEFORE the
    # MOV R3, R0 at 0x366A4. So R3 at that point is still param_4
    # (passed in R3 by the caller). This is correct.

    # So the function sends 9 bytes from data_ptr to PI2CWriteRead.
    # But it also built a 9-byte buffer at local_20 that includes the
    # cmd byte prepended. Why build local_20 if it's not used?

    # Unless... this is a bug in the decompilation, or the function
    # serves dual purpose (the local_20 buffer might be used by
    # another code path that I'm not seeing).

    # Let me verify by checking if there's another code path or if
    # the buffer address substitution happens differently.

    # Actually, let me re-examine. The memcpy destination at 0x366F0:
    # E1A00003 MOV R0, R3
    # R3 was set at 0x366EC: ADD R3, R3, #1
    # R3 was set at 0x366E8: SUB R3, R11, #0x20 -> R3 = &local_20
    # After ADD: R3 = &local_20 + 1

    # The memcpy copies 8 bytes from data_ptr to &local_20[1].
    # Then local_20[0] = cmd was set at 0x366E4.
    # So local_20 = [cmd, data[0], ..., data[7]]

    # But at 0x36728, R3 loads data_ptr (fp-0x14), not &local_20 (fp-0x20).

    # UNLESS the compiler stored &local_20 at fp-0x14 at some point.
    # Let me check if fp-0x14 gets overwritten.

    # 0x366A0: STR R3, [FP, #-0x14]  -> fp-0x14 = data_ptr
    # After that, I don't see any other STR to fp-0x14.

    # So this IS passing data_ptr (original param_4) to PI2CWriteRead.
    # The local_20 buffer construction was... useless? A dead code path?

    # Actually, I think I might be wrong about the write_buf parameter.
    # Let me check: PI2CWriteRead(bus_mux, slave_addr, write_len, write_buf, ...)
    # On ARM: r0=bus_mux, r1=slave_addr, r2=write_len, r3=write_buf

    # At the BL call:
    # r0 = bus_mux (from 0x36720: MOV R0, R2, where R2 was loaded at 0x36700)
    # r1 = i2c_addr (from 0x36704: LDRB R1, [FP, #-0x0E])
    # r2 = 9 (from 0x36724: MOV R2, #9)
    # r3 = ??? (from 0x36728: LDR R3, [FP, #-0x14])

    # Hmm wait, the register assignments are:
    # 0x36700: LDRB R2, [FP, #-0x0D]  -> R2 = bus_mux
    # 0x36704: LDRB R1, [FP, #-0x0E]  -> R1 = i2c_addr
    # 0x36708-71C: Store 0s on stack
    # 0x36720: MOV R0, R2             -> R0 = R2 = bus_mux
    # 0x36724: MOV R2, #9             -> R2 = 9 (overwrites bus_mux in R2)
    # 0x36728: LDR R3, [FP, #-0x14]   -> R3 = fp-0x14 value

    # So at the BL:
    # R0 = bus_mux
    # R1 = i2c_addr
    # R2 = 9 (write_len)
    # R3 = fp-0x14 = data_ptr? or &local_20?

    # Hmm, but E51B3014 can also be decoded differently.
    # Let me be really precise about ARM instruction encoding.

    # E51B3014:
    # 1110 0101 0001 1011 0011 0000 0001 0100
    # cond=1110 (AL)
    # 01 = memory access
    # I=0 (immediate offset)
    # P=1 (pre-indexed)
    # U=0 (subtract)
    # B=1 (byte? no, bit 22=0, so word)
    # Wait, let me use the proper encoding:

    # E51B3014:
    # 31-28: 1110 (AL)
    # 27-26: 01 (load/store word)
    # 25: 0 (immediate offset)
    # 24: 1 (pre-indexed)
    # 23: 0 (subtract)
    # 22: 0 (word, not byte)
    # 21: 0 (no writeback)
    # 20: 1 (load)
    # 19-16: 1011 = R11 (base)
    # 15-12: 0011 = R3 (dest)
    # 11-0: 000000010100 = 0x014 = 20

    # So: LDR R3, [R11, #-20] = LDR R3, [FP, #-0x14]

    # This loads from fp-0x14, which is where data_ptr was stored.

    # BUT WAIT - maybe I need to reconsider what's at fp-0x14.
    # Let me check if fp-0x14 could actually contain &local_20.

    # The local buffer is at fp-0x20. Stored there:
    #   fp-0x20: local_20[0] = cmd
    #   fp-0x1F: local_20[1] = data[0]
    #   fp-0x1E: local_20[2] = data[1]
    #   ... etc
    #   fp-0x18: local_20[8] = data[7]

    # fp-0x14 is NOT overlapping with this buffer.
    # So fp-0x14 definitely holds data_ptr.

    # I conclude that this function:
    # 1. Builds local_20 = [cmd, data[0..7]] (9 bytes) -- for some purpose
    # 2. Calls PI2CWriteRead with data_ptr (original param_4) as write buffer
    # 3. Uses write_len=9

    # This means data_ptr must point to a buffer that's at LEAST 9 bytes.
    # But the data being passed has only 6 bytes for auStack_22.

    # Unless the data_ptr doesn't point to auStack_22 but to something else.

    # Let me re-examine pex8696_multi_host_mode_reg_set.
    # The variable assignments are:
    #   local_44 = pointer (the data pointer sent via queue)
    #   local_40 = callback function

    # For the first queue send:
    #   local_44 = auStack_22  (6 bytes)
    #   But the queue handler might not pass local_44 as data_ptr directly.

    # Actually I think the issue is that I'm confusing two different
    # functions that are at adjacent addresses. 0x36690 ends at 0x36758
    # and the next function starts at 0x3675C. But since there's no
    # literal pool gap, maybe 0x36690 is smaller than I think.

    # The LDMFD at 0x36758 is the return. So the function is
    # 0x36690 to 0x36758 = 0xC8 = 200 bytes.

    # OK actually I realize the problem: I need to check whether
    # the function at 0x36690 is write_pex8696_register variant (8 bytes)
    # or a different function (9 bytes).

    # Let me compare with write_pex8696_register at 0x3687c (which I know)

    print()
    print("=" * 60)
    print("Comparing 0x36690 with write_pex8696_register at 0x3687c")
    print("=" * 60)

    # Read write_pex8696_register at 0x3687c
    w_func = read_bytes(data, 0x3687c, 200)
    r_func = read_bytes(data, 0x36690, 200)

    print("\nwrite_pex8696_register (0x3687c):")
    for i in range(0, 200, 4):
        word = struct.unpack_from('<I', w_func, i)[0]
        addr = 0x3687c + i
        print(f"  0x{addr:08X}: {word:08X}", end="")
        # Check for key patterns
        if word == 0xE3A02008:
            print("  MOV R2, #8  ; write_len = 8")
        elif word == 0xE3A02009:
            print("  MOV R2, #9  ; write_len = 9")
        elif (word & 0x0F000000) == 0x0B000000:
            cond = (word >> 28) & 0xF
            offset_val = word & 0x00FFFFFF
            if offset_val & 0x800000:
                offset_val = offset_val - 0x1000000
            pc = addr + 8
            target = pc + (offset_val * 4)
            if target == 0x253C4:
                print("  BL PI2CWriteRead")
            elif target == 0xA854:
                print("  BL memcpy")
            else:
                print(f"  BL 0x{target:08X}")
        elif (word & 0x0FFFFFFF) == 0x089DA800:
            print("  LDMFD ; return")
            break
        else:
            print()

    print("\nraw_plx_i2c_write (0x36690):")
    for i in range(0, 200, 4):
        word = struct.unpack_from('<I', r_func, i)[0]
        addr = 0x36690 + i
        print(f"  0x{addr:08X}: {word:08X}", end="")
        if word == 0xE3A02008:
            print("  MOV R2, #8  ; write_len = 8")
        elif word == 0xE3A02009:
            print("  MOV R2, #9  ; write_len = 9")
        elif word == 0xE3A02007:
            print("  MOV R2, #7  ; write_len = 7")
        elif (word & 0x0F000000) == 0x0B000000:
            cond = (word >> 28) & 0xF
            offset_val = word & 0x00FFFFFF
            if offset_val & 0x800000:
                offset_val = offset_val - 0x1000000
            pc = addr + 8
            target = pc + (offset_val * 4)
            if target == 0x253C4:
                print("  BL PI2CWriteRead")
            elif target == 0xA854:
                print("  BL memcpy")
            else:
                print(f"  BL 0x{target:08X}")
        elif (word & 0x0FFFFFFF) == 0x089DA800:
            print("  LDMFD ; return")
            break
        else:
            print()

    # Now let me check the memcpy size parameter in write_pex8696_register
    # vs raw_plx_i2c_write to understand the difference

    print()
    print("KEY DIFFERENCE:")
    print("  write_pex8696_register: memcpy 7 bytes, PI2CWriteRead len=8")
    print("  raw_plx_i2c_write:      memcpy 8 bytes, PI2CWriteRead len=9")
    print()
    print("Both prepend param_3 as byte[0], making total = memcpy_len + 1")
    print()
    print("For write_pex8696_register with the standard PLX protocol:")
    print("  [param_3=0x03] [7 bytes from buffer]")
    print("  = [PLX_CMD_WRITE] [stn/port] [enables] [reg_lo] [val0-3]")
    print("  = 8 bytes total = standard PLX I2C write")
    print()
    print("For raw_plx_i2c_write:")
    print("  [param_3] [8 bytes from buffer]")
    print("  = 9 bytes total")
    print()
    print("The extra byte might be for a PLX extended command or for")
    print("writing to a non-PLX device on the same I2C bus.")
    print()
    print("BUT: if param_3 is not the PLX command but the queue handler's")
    print("cmd byte, then the 8-byte buffer IS the full PLX command:")
    print("  buffer = [PLX_CMD] [stn/port] [enables] [reg_lo] [val0-3]")
    print("And the 9-byte write is: [queue_cmd] [full_PLX_command]")
    print("The PLX switch would see byte[0] as extra and might ignore it")
    print("or it might be an extended protocol.")

    # Hmm, but that doesn't match how PLX I2C slave works.
    # The PLX I2C slave expects exactly 4 bytes (command) or 8 bytes
    # (command + data for write). 9 bytes would be non-standard.

    # FINAL THEORY: Maybe the LDR R3, [FP, #-0x14] at 0x36728
    # actually loads &local_20, not data_ptr.
    # Perhaps the compiler reused fp-0x14 for storing &local_20.

    # Let me check: after the memcpy, is there a STR that stores
    # &local_20 at fp-0x14?

    # Looking at the instructions between memcpy return and PI2CWriteRead call:
    # 0x36700: LDRB R2, [FP, #-0x0D]  -> R2 = bus_mux
    # 0x36704: LDRB R1, [FP, #-0x0E]  -> R1 = i2c_addr
    # 0x36708-71C: zeros on stack
    # 0x36720: MOV R0, R2  -> R0 = bus_mux
    # 0x36724: MOV R2, #9
    # 0x36728: LDR R3, [FP, #-0x14]  -> R3 = ???

    # NO store to fp-0x14 between 0x366A0 and 0x36728.
    # So fp-0x14 still holds the original data_ptr.

    # CONCLUSION: raw_plx_i2c_write sends 9 bytes from data_ptr to
    # PI2CWriteRead. The local_20 buffer construction is dead code
    # or the decompiler is wrong about which address is loaded.

    # Actually, let me just check the write_len. Is it really 9?
    # 0x36724: E3A02009 = MOV R2, #9. Yes, it's 9.
    #
    # But for write_pex8696_register at 0x3687c, what's the write_len?
    # I need to find the MOV R2, #N instruction.

if __name__ == '__main__':
    main()
