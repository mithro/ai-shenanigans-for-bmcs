#!/usr/bin/env python3
"""Trace the multi-host orchestration function and understand the complete flow."""

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

# Known function addresses
KNOWN_FUNCS = {
    0x0000A854: "memcpy",
    0x000253C4: "PI2CWriteRead",
    0x000256C4: "PI2CMuxWriteRead",
    0x0002EAD4: "write_pex8696_register_0",
    0x0002EBF0: "read_pex8696_register_0",
    0x000325D0: "write_pex8696_register_1",
    0x000326EC: "read_pex8696_register_1",
    0x00031184: "pex8696_hp_on",
    0x000312EC: "pex8696_hp_off",
    0x00031454: "pex8696_hp_ctrl",
    0x000332AC: "pex8696_slot_power_ctrl",
    0x000317E4: "get_PEX8696_addr_port_1",
    0x00036690: "raw_plx_i2c_write",
    0x00036998: "read_pex8647_register",
    0x00036AD0: "write_pex8647_register",
    0x00036BEC: "pex8696_cfg_multi_host_2",
    0x00036CD4: "pex8696_cfg_multi_host_4",
    0x00036DBC: "pex8647_cfg_multi_host_8",
    0x00036EF0: "pex8647_cfg_multi_host_2_4",
    0x000371B8: "pex8696_dump",
    0x000372AC: "pex8696_cfg",
    0x00037420: "pex8696_multi_host_mode_reg_set",
    0x000375B8: "pex8696_all_slot_off",
    0x000376E8: "is_cfg_multi_host_8",
    0x00037768: "pex8696_multi_host_mode_cfg",
    0x00037944: "pex8647_multi_host_mode_cfg",
    0x00038230: "multi_host_mode_set",
    0x0003836C: "pex8696_all_slot_power_off",
    0x00037F7C: "get_PEX8696_addr_port_2",
    0x0002E66C: "get_PEX8696_addr_port_0",
    0x0002F7C4: "pex8696_slot_power_on_reg",
    0x0002FA90: "pex8696_slot_power_on",
    0x0002FC74: "pex8696_un_protect_reg",
    0x0002FDF8: "pex8696_un_protect",
}

def disasm_function(data, addr, max_bytes=512, label=""):
    """Disassemble a function, showing BL targets."""
    print(f"\n{'='*60}")
    print(f"Disassembly: {label or f'func_{addr:08X}'} (0x{addr:08X})")
    print(f"{'='*60}")

    func_bytes = read_bytes(data, addr, max_bytes)
    calls = []

    for i in range(0, min(max_bytes, len(func_bytes)), 4):
        word = struct.unpack_from('<I', func_bytes, i)[0]
        iaddr = addr + i
        line = f"  0x{iaddr:08X}: {word:08X}"

        # Check for function epilogue (return)
        is_return = False

        # BL instruction
        if (word & 0x0F000000) == 0x0B000000:
            cond = (word >> 28) & 0xF
            offset_val = word & 0x00FFFFFF
            if offset_val & 0x800000:
                offset_val = offset_val - 0x1000000
            pc = iaddr + 8
            target = pc + (offset_val * 4)
            name = KNOWN_FUNCS.get(target, f"func_{target:08X}")
            cond_str = ['EQ','NE','CS','CC','MI','PL','VS','VC',
                        'HI','LS','GE','LT','GT','LE','AL','NV'][cond]
            line += f"  BL{cond_str} {name} (0x{target:08X})"
            calls.append((iaddr, target, name))

        # LDR PC (return or function pointer call)
        elif (word & 0x0FFFFFFF) == 0x089DA800 or (word & 0x0FFFFFFF) == 0x089DA808:
            line += "  LDMFD sp!, {..., pc}  ; return"
            is_return = True

        # STR/LDR with string pointer (literal pool)
        elif word > BASE_OFFSET and word < len(data) + BASE_OFFSET and i > max_bytes - 64:
            name = KNOWN_FUNCS.get(word, "")
            if name:
                line += f"  ; -> {name}"
            elif word > 0xF0000:
                ref = read_bytes(data, word, min(40, len(data) - (word - BASE_OFFSET)))
                null_idx = bytes(ref).find(b'\x00')
                if null_idx > 0 and null_idx < 40:
                    try:
                        s = bytes(ref[:null_idx]).decode('ascii')
                        if all(c.isprintable() or c in '\n\r\t' for c in s):
                            line += f'  ; -> "{s[:60]}"'
                    except (UnicodeDecodeError, ValueError):
                        pass

        print(line)

        if is_return and i > 20:
            # Check if next words are literal pool
            remaining = max_bytes - i - 4
            if remaining > 0:
                print("  --- literal pool ---")
                for j in range(i+4, min(max_bytes, len(func_bytes)), 4):
                    w2 = struct.unpack_from('<I', func_bytes, j)[0]
                    a2 = addr + j
                    l2 = f"  0x{a2:08X}: {w2:08X}"
                    name = KNOWN_FUNCS.get(w2, "")
                    if name:
                        l2 += f"  ; -> {name}"
                    elif w2 > 0xF0000 and w2 < len(data) + BASE_OFFSET:
                        ref = read_bytes(data, w2, 40)
                        null_idx = bytes(ref).find(b'\x00')
                        if null_idx > 0:
                            try:
                                s = bytes(ref[:null_idx]).decode('ascii')
                                if all(c.isprintable() or c in '\n\r\t' for c in s):
                                    l2 += f'  ; -> "{s[:60]}"'
                            except:
                                pass
                        else:
                            l2 += f"  ; -> data: {hex_bytes(ref[:16])}"
                    print(l2)
                break

    return calls


def main():
    data = read_binary()

    # Disassemble the orchestration function at 0x38B30's caller area
    # First, find the function that contains the call at 0x38B30
    # Look backwards for function prologue
    print("Looking for function containing 0x38B30...")

    # Scan backwards for STMFD (function prologue)
    for offset in range(0x38B30, 0x38900, -4):
        word = read_u32(data, offset)
        # Common ARM prologue: MOV IP, SP  (E1A0C00D)
        if word == 0xE1A0C00D:
            print(f"  Found prologue at 0x{offset:08X}")
            # Find function end (LDMFD)
            end = offset
            for j in range(offset, offset + 1024, 4):
                w = read_u32(data, j)
                if (w & 0x0FFFF000) == 0x089DA000:  # LDMFD sp!, {..., pc}
                    end = j + 4
                    break

            size = end - offset + 64  # Include some literal pool
            calls = disasm_function(data, offset, min(size, 1024),
                                   f"orchestrator (contains call at 0x38B30)")
            break

    # Now disassemble the raw_plx_i2c_write (0x36690) to understand what it does
    print("\n\nNow analyzing raw_plx_i2c_write (0x36690):")
    print("This is the callback used by pex8696_multi_host_mode_reg_set")

    calls = disasm_function(data, 0x36690, 256, "raw_plx_i2c_write")

    # It calls PI2CWriteRead at 0x3672C
    # Let me trace the parameters:
    # From the disassembly:
    # 0x366A0: E50B3014  STR r3, [fp, #-0x14]  ; save param_4
    # 0x366A4: E1A03000  MOV r3, r0            ; r3 = param_1 (bus_mux)
    # 0x366A8: E54B300D  STRB r3, [fp, #-0x0D] ; local_0d = bus_mux
    # 0x366AC: E1A03001  MOV r3, r1            ; r3 = param_2 (i2c_addr)
    # 0x366B0: E54B300E  STRB r3, [fp, #-0x0E] ; local_0e = i2c_addr
    # 0x366B4: E1A03002  MOV r3, r2            ; r3 = param_3 (cmd)
    # 0x366B8: E54B300F  STRB r3, [fp, #-0x0F] ; local_0f = cmd
    # 0x366BC: E24B3020  SUB r3, fp, #0x20     ; r3 = &local_20 (stack buffer)
    # 0x366C0-CC: Zero out local_20 (12 bytes)
    # 0x366E0: E55B300F  LDRB r3, [fp, #-0x0F] ; r3 = cmd
    # 0x366E4: E54B3020  STRB r3, [fp, #-0x20] ; local_20[0] = cmd
    # 0x366E8: E24B3020  SUB r3, fp, #0x20     ; r3 = &local_20
    # 0x366EC: E2833001  ADD r3, r3, #1        ; r3 = &local_20 + 1
    # 0x366F0: E1A00003  MOV r0, r3            ; dest = &local_20[1]
    # 0x366F4: E51B1014  LDR r1, [fp, #-0x14]  ; src = param_4
    # 0x366F8: E3A02008  MOV r2, #8            ; len = 8
    # 0x366FC: BL memcpy                       ; memcpy(&local_20[1], param_4, 8)

    # Then:
    # 0x36700: E55B200D  LDRB r2, [fp, #-0x0D] ; r2 = bus_mux
    # 0x36704: E55B100E  LDRB r1, [fp, #-0x0E] ; r1 = i2c_addr
    # 0x36720: E1A00002  MOV r0, r2            ; r0 = bus_mux
    # 0x36724: E3A02009  MOV r2, #9            ; write_len = 9!
    # 0x36728: E51B3014  LDR r3, [fp, #-0x14]  ; r3 = write buffer
    #   Wait, this should be &local_20 not param_4
    #   Actually let me re-check...

    print("\n\n" + "=" * 60)
    print("ANALYSIS: raw_plx_i2c_write (0x36690)")
    print("=" * 60)
    print()
    print("This function:")
    print("1. Takes (bus_mux, i2c_addr, cmd, data_ptr) as parameters")
    print("2. Builds a 9-byte buffer: [cmd] [data_ptr[0..7]]")
    print("3. Calls PI2CWriteRead(bus_mux, i2c_addr, 9, buffer, 0, 0, 0)")
    print("   -> Write-only I2C transaction of 9 bytes")
    print()
    print("IMPORTANT: This writes 9 bytes, not 8 like write_pex8696_register!")
    print("The extra byte means the data pointer has 8 bytes, not 7.")
    print()
    print("So for pex8696_multi_host_mode_reg_set:")
    print("The 8-byte data tables are the FULL PLX command payload:")
    print("  [cmd] [stn/port] [enables|reg_hi] [reg_lo] [val0] [val1] [val2] [val3]")
    print()
    print("But wait - the callback gets (bus_mux, i2c_addr, cmd, buffer_ptr)")
    print("from the queue message. The cmd is byte[2] of the packed field.")
    print("So the total on-wire is: [queue_cmd] [buffer[0..7]]")
    print()
    print("Hmm, but that gives 9 bytes which is more than the standard 8-byte")
    print("PLX write command. Unless the extra byte is something else...")
    print()

    # Actually, I need to reconsider. The function at 0x36690 builds:
    # local_20[0] = param_3 (cmd from queue)
    # local_20[1..8] = memcpy from param_4, 8 bytes
    # Then calls PI2CWriteRead with write_len=9

    # But write_pex8696_register does:
    # local_20[0] = param_3 (PLX command byte, 0x03)
    # local_20[1..7] = memcpy from param_4, 7 bytes
    # Then calls PI2CWriteRead with write_len=8

    # So raw_plx_i2c_write sends 9 bytes vs 8 bytes.
    # The extra byte is because the data_ptr has 8 bytes instead of 7.
    # This means the data_ptr for raw_plx_i2c_write contains the FULL
    # 8-byte PLX command (stn/port + enables + reg_lo + 4 value bytes
    # + 1 extra byte).

    # OR... the param_3 in the queue message ISN'T the PLX command byte.
    # It might be something else entirely.

    # Let me look at what the queue sends as cmd (byte[2] of packed field).

    print("Let me check the queue message format more carefully...")
    print()
    print("In pex8696_multi_host_mode_reg_set, the queue messages are constructed:")
    print("  local_38._0_2_ = CONCAT11(byte_from_data, 0xF3)")
    print("  local_38._0_3_ = CONCAT12(another_byte, local_38._0_2_)")
    print("  local_38 = (uint)(uint3)local_38")
    print()
    print("From data d_24 = [03 07 BC E1 00 00 00 00]:")
    print("  local_24 = 0x03, local_23 = 0x07")
    print("  local_38._0_2_ = CONCAT11(0x03, 0xF3) = 0x03F3")
    print("  local_38._0_3_ = CONCAT12(0x07, 0x03F3) = 0x0703F3")
    print("  local_38 = 0x000703F3")
    print()
    print("The queue handler unpacks this as:")
    print("  byte[0] = 0xF3 (bus_mux)")
    print("  byte[1] = 0x03 (i2c_addr? Or cmd?)")
    print("  byte[2] = 0x07 (cmd? Or something else?)")
    print()
    print("But 0x03 as i2c_addr makes no sense for PEX switches.")
    print()
    print("ALTERNATIVE INTERPRETATION:")
    print("What if the data structure is different?")
    print("  local_24 = first byte = PLX command (0x03 = write)")
    print("  local_23 = second byte = station/port (0x07)")
    print("  auStack_22 = remaining 6 bytes = [BC E1 00 00 00 00]")
    print()
    print("And the queue message format for reg_set is:")
    print("  local_44 = pointer to auStack_22 (6 bytes)")
    print("  local_38 = bus_mux | (plx_cmd << 8) | (stn_port << 16)")
    print()
    print("Then the callback (raw_plx_i2c_write) would receive:")
    print("  bus_mux = 0xF3")
    print("  i2c_addr = 0x03  <- PLX write command, NOT i2c_addr!")
    print("  cmd = 0x07        <- station/port, NOT cmd!")
    print("  data_ptr -> auStack_22 = [BC E1 00 00 00 00]")
    print()
    print("And builds: [0x07] [BC E1 00 00 00 00 ?? ??]")
    print("That's: [stn/port=0x07] [enables=0xBC] [reg_lo=0xE1] [val=00 00 00 00]")
    print("+ 2 extra bytes from the 8-byte memcpy beyond the 6-byte data")
    print()

    # Hmm, this is getting complex. Let me step back and look at how
    # pex8696_multi_host_mode_cfg sends its queue messages, since those
    # are more clearly documented.

    print("=" * 60)
    print("COMPARING QUEUE MESSAGE FORMATS")
    print("=" * 60)
    print()
    print("pex8696_multi_host_mode_cfg (well-understood):")
    print("  local_20 = callback_function_pointer")
    print("  local_24 = context_pointer")
    print("  local_18 = packed (bus_mux=0xF3, i2c_addr=0x30, cmd=0x03)")
    print("  _lx_QueueSend(queue, &local_24, 0)")
    print()
    print("  Queue receives: [context] [callback] [???] [packed]")
    print("  Queue handler calls: callback(bus_mux, i2c_addr, cmd, context)")
    print()
    print("pex8696_multi_host_mode_reg_set:")
    print("  local_40 = callback (0x36690 = raw_plx_i2c_write)")
    print("  local_44 = data_pointer (auStack_22, auStack_2a, auStack_1a)")
    print("  local_38 = packed bytes from data")
    print("  _lx_QueueSend(queue, &local_44, 0)")
    print()
    print("  Queue receives: [data_ptr] [callback] [???] [packed]")
    print("  Queue handler calls: callback(byte0, byte1, byte2, data_ptr)")
    print()
    print("So the callback signature is: callback(bus_mux, i2c_addr, cmd, data_ptr)")
    print("For reg_set: callback(0xF3, 0x03, 0x07, data_ptr)")
    print()
    print("Since 0x36690 (raw_plx_i2c_write) builds [cmd][data[0..7]]:")
    print("  On wire: [0x07] [data_ptr[0..7]]")
    print("  = [0x07] [BC E1 00 00 00 00 ?? ??]")
    print()
    print("BUT this means 0x07 is the 'cmd' parameter passed to PI2CWriteRead")
    print("as part of the write buffer, not the PLX command byte.")
    print()
    print("WAIT - the i2c_addr is 0x03!")
    print("That means it's sending to I2C address 0x03 (7-bit: 0x01)")
    print("which is a reserved I2C address.")
    print()
    print("Unless... the packed format is different for reg_set.")
    print("Let me check if the queue structure has the same field layout.")

    # Actually, let me re-examine the construction more carefully.
    # In pex8696_multi_host_mode_cfg:
    #   local_18._0_2_ = 0x30f3;  // literal 16-bit value
    #   local_18 = (uint)CONCAT12(3,(undefined2)local_18);
    #   // CONCAT12(byte=3, uint16=0x30F3) = (3 << 16) | 0x30F3 = 0x0330F3

    # In pex8696_multi_host_mode_reg_set:
    #   local_38._0_2_ = CONCAT11(local_24, 0xf3);
    #   // CONCAT11(hi=local_24, lo=0xF3) = (local_24 << 8) | 0xF3

    # If local_24 = 0x03:
    #   local_38._0_2_ = (0x03 << 8) | 0xF3 = 0x03F3

    # In multi_host_mode_cfg: local_18._0_2_ = 0x30F3 (i2c_addr=0x30, bus=0xF3)
    # In reg_set: local_38._0_2_ = 0x03F3 (i2c_addr=0x03, bus=0xF3)

    # Then:
    # In multi_host_mode_cfg:
    #   local_18 = CONCAT12(3, 0x30F3) = 0x0330F3
    # In reg_set:
    #   local_38._0_3_ = CONCAT12(local_23=0x07, 0x03F3) = 0x0703F3
    #   local_38 = 0x000703F3

    # Hmm. So the packed format IS:
    #   byte[0] = bus_mux (0xF3)
    #   byte[1] = i2c_addr (0x30 in cfg, 0x03 in reg_set)
    #   byte[2] = command (3 in cfg, 7 in reg_set)

    # Command 3 = PLX write
    # Command 7 = ???

    # But in the callback, write_pex8696_register uses param_3 as the PLX
    # command byte (0x03 for write, 0x04 for read).
    # raw_plx_i2c_write also uses param_3 as the first byte of the write buffer.

    # So for reg_set:
    #   raw_plx_i2c_write(0xF3, 0x03, 0x07, data_ptr)
    #   Builds: [0x07] + data_ptr[0..7] = 9 bytes
    #   PI2CWriteRead(0xF3, 0x03, 9, buffer, 0, 0, 0)

    # This sends 9 bytes to I2C address 0x03 (7-bit: 0x01) on bus 3.
    # I2C address 0x01 is the "CBUS" address in the I2C specification,
    # which is reserved.

    # UNLESS the data doesn't map the way I think it does.
    # Let me check if the local_24/local_23 assignment might be swapped
    # due to endianness.

    # On little-endian ARM:
    # memcpy(&local_24, source, 8) copies 8 bytes starting at &local_24
    # local_24 is a single byte at stack offset.
    # If local_24 is at fp-0x24, then:
    #   fp-0x24 = byte 0 of source
    #   fp-0x23 = byte 1 of source (= local_23)
    #   fp-0x22..fp-0x1D = bytes 2-7 of source (= auStack_22)

    # Source d_24 = 03 07 BC E1 00 00 00 00
    # So local_24 = 0x03, local_23 = 0x07 -- CONFIRMED

    # Maybe the queue handler dispatches differently for different commands?
    # Command 3 -> standard PLX write (calls write_pex8696_register)
    # Command 7 -> raw I2C write (calls raw_plx_i2c_write at 0x36690)

    # This would make sense! The queue handler looks at byte[2] (command)
    # and dispatches to different callbacks:
    #   cmd=3 -> write_pex8696_register-like callback
    #   cmd=4 -> read_pex8696_register-like callback
    #   cmd=7 -> raw I2C write callback

    # For command 7 (raw write):
    #   i2c_addr = byte[1] = 0x03 from data
    #   But NO! The callback is specified in local_40, not determined by cmd.

    # Actually, looking again at the queue message structure:
    #   local_44 = data pointer (void *)
    #   local_40 = callback function
    #   local_3c = 0 (unused?)
    #   local_38 = packed bus/addr/cmd

    # The _lx_QueueSend sends the address of local_44, which is a 16-byte
    # struct: [data_ptr(4)] [callback(4)] [zero(4)] [packed(4)]

    # The queue HANDLER reads this struct and calls:
    #   callback(packed_byte0, packed_byte1, packed_byte2, data_ptr)

    # So for reg_set with d_24:
    #   callback = 0x36690 (raw_plx_i2c_write)
    #   data_ptr -> auStack_22 = [BC E1 00 00 00 00]
    #   packed = 0x000703F3
    #   Call: raw_plx_i2c_write(0xF3, 0x03, 0x07, &auStack_22)

    # Inside raw_plx_i2c_write:
    #   buffer[0] = param_3 = 0x07
    #   memcpy(buffer+1, param_4, 8) -> copies [BC E1 00 00 00 00 XX XX]
    #   PI2CWriteRead(0xF3, 0x03, 9, buffer, 0, 0, 0)

    # So it sends 9 bytes to I2C slave 0x03 (7-bit 0x01).
    # This CANNOT be right for PLX switches.

    # NEW THEORY: Maybe the queue handler doesn't pass byte[1] as i2c_addr.
    # Maybe it uses local_20 (callback function) to determine the callback,
    # and the packed field is passed differently.

    # OR: Maybe the ordering of the struct on the stack is different.
    # Let me check: &local_44 is at fp-0x44
    # local_44 at fp-0x44 (4 bytes)
    # local_40 at fp-0x40 (4 bytes)
    # local_3c at fp-0x3C (4 bytes)
    # local_38 at fp-0x38 (4 bytes)

    # _lx_QueueSend(queue, &local_44, 0) sends the address of fp-0x44
    # The queue receives the struct starting at fp-0x44.
    # But wait -- the queue parameter is &local_24 in pex8696_multi_host_mode_cfg:
    #   _lx_QueueSend(DAT_0003793c, &local_24, 0)
    #   local_24 at fp-0x24
    #   local_20 at fp-0x20
    #   local_1c at fp-0x1C
    #   local_18 at fp-0x18
    #
    # So the 16-byte struct is:
    #   [local_24=context_ptr] [local_20=callback] [local_1c=0] [local_18=packed]
    #
    # For reg_set:
    #   [local_44=data_ptr] [local_40=callback] [local_3c=0] [local_38=packed]
    #
    # Same layout!

    # OK, I think the answer is that the 0x03 in byte[1] IS intentional.
    # The raw_plx_i2c_write callback at 0x36690 doesn't use i2c_addr from
    # the queue message - it uses a DIFFERENT addressing scheme.

    # Actually wait, let me re-examine the reg_set function.
    # The variable assignment is:
    #   local_38._0_2_ = CONCAT11(local_24, 0xf3)
    #
    # BUT - which set of local vars is used for which queue send?
    # The function sends 3 messages, each using a different data set.

    print("\n\n" + "=" * 60)
    print("RE-EXAMINING pex8696_multi_host_mode_reg_set QUEUE MESSAGES")
    print("=" * 60)
    print()
    print("The function has 3 queue sends. Each uses local_24/local_2c/local_1c")
    print("but the Ghidra decompilation is hard to follow because of the")
    print("CONCAT byte manipulation.")
    print()
    print("Key: The first 2 bytes of each data set are used to build")
    print("the bus/addr packed value, and the remaining 6 bytes are the")
    print("data pointer content.")
    print()
    print("All 3 data sets start with the same 2 bytes: 03 07")
    print("  d_1c: 03 07 | BC EB 00 00 00 01")
    print("  d_24: 03 07 | BC E1 00 00 00 00")
    print("  d_2c: 03 07 | BC E0 00 11 01 10")
    print()
    print("If 03 07 are NOT bus/addr info but rather PLX protocol bytes:")
    print("  0x03 = PLX_CMD_I2C_WRITE")
    print("  0x07 = station/port byte (station 3, port bit1=1)")
    print()
    print("Then these are complete PLX write commands!")
    print("  Command 1: WRITE station 3 port 3, reg 0xEB*4=0x3AC, val 0x01000000")
    print("  Command 2: WRITE station 3 port 3, reg 0xE1*4=0x384, val 0x00000000")
    print("  Command 3: WRITE station 3 port 3, reg 0xE0*4=0x380, val 0x10011100")
    print()
    print("Enables byte 0xBC:")
    print("  bit[7] = 1 -> port_lo = 1")
    print("  bits[5:2] = 0b1111 -> all bytes enabled")
    print("  bits[1:0] = 0b00 -> reg_hi = 0")
    print()
    print("So port = (port_bit1 << 1) | port_lo = (1 << 1) | 1 = 3")
    print("Global port = station * 4 + port = 3*4 + 3 = 15")
    print()
    print("Wait, that's port 15 which makes no sense for PEX8696 (24 ports, 0-23)")
    print("Actually port 15 within station 3 = global port 15")
    print("The PEX8696 has 24 ports total (6 stations x 4 ports)")
    print("Station 3, port 3 = global port 15")
    print()
    print("Actually let me re-decode:")
    print("  stn/port byte 0x07:")
    print("    station = 0x07 >> 1 = 3")
    print("    port_bit1 = 0x07 & 1 = 1")
    print("  enables byte 0xBC:")
    print("    port_bit0 = (0xBC >> 7) & 1 = 1")
    print("  port = (port_bit1 << 1) | port_bit0 = 3")
    print("  global_port = 3 * 4 + 3 = 15")
    print()
    print("Port 15 on PEX8696 could be an NT (Non-Transparent) bridge port")
    print("or a configuration port used for multi-host setup.")


if __name__ == '__main__':
    main()
