#!/usr/bin/env python3
"""Disassemble is_cfg_multi_host_8 function from fullfw binary."""

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
    print("is_cfg_multi_host_8 (0x376e8, 128 bytes)")
    print("=" * 60)

    func_bytes = read_bytes(data, 0x376e8, 128)

    # Dump as ARM words with basic decode
    for i in range(0, 128, 4):
        word = struct.unpack_from('<I', func_bytes, i)[0]
        addr = 0x376e8 + i
        print(f"  0x{addr:08X}: {word:08X}", end="")

        # Very basic ARM instruction decode for common patterns
        cond = (word >> 28) & 0xF
        cond_str = ['EQ','NE','CS','CC','MI','PL','VS','VC',
                     'HI','LS','GE','LT','GT','LE','AL','NV'][cond]

        # Check if it's a data word (in literal pool area)
        if addr >= 0x37760:
            if word > 0x8000 and word < 0x200000:
                ref_data = read_bytes(data, word, 8)
                print(f"  ; data ptr -> 0x{word:08X}: {hex_bytes(ref_data)}")
            else:
                print(f"  ; literal: {word}")
        else:
            print(f"  ; cond={cond_str}")

    print()

    # Now analyze the pex8696_multi_host_mode_reg_set more carefully
    # The function has complex byte manipulation that the decompiler
    # didn't handle well. Let me trace through the logic.
    print("=" * 60)
    print("pex8696_multi_host_mode_reg_set data flow analysis")
    print("=" * 60)

    # From decompiled code:
    # local_12 = param_2 (char, the mode value)
    # local_11 = param_1 (undefined, possibly switch index)
    #
    # Three 8-byte data sets are loaded:
    # memcpy(&local_1c, DAT_000375a4, 8);  -> d_1c = 03 07 BC EB 00 00 00 01
    # memcpy(&local_24, DAT_000375a8, 8);  -> d_24 = 03 07 BC E1 00 00 00 00
    # memcpy(&local_2c, DAT_000375ac, 8);  -> d_2c = 03 07 BC E0 00 11 01 10
    # memcpy(auStack_34, DAT_000375ac, 8); -> same as d_2c
    #
    # if (local_12 != '\x01'):
    #   local_40 = DAT_000375b0;  // = 0x00036690 (callback function)
    #   // Build queue message combining data from local_24, local_2c, local_1c
    #   // Each queue send combines bus/addr info from one set with the callback
    #
    # The function sends 3 queue messages if mode != 1

    d_1c = bytes.fromhex("03 07 BC EB 00 00 00 01".replace(" ",""))
    d_24 = bytes.fromhex("03 07 BC E1 00 00 00 00".replace(" ",""))
    d_2c = bytes.fromhex("03 07 BC E0 00 11 01 10".replace(" ",""))

    print("\nThese look like pre-formatted PLX I2C write commands.")
    print("Each 8-byte sequence is: [cmd] [stn/port] [enables] [reg_lo] [val0-3]")
    print()

    # But wait - the function doesn't call write_pex8696_register directly.
    # It sends queue messages. The queue handler will call the callback
    # (0x00036690) which then does the actual I2C write.
    #
    # However, the way the function assembles the queue message is complex.
    # Let me re-read the decompiled code more carefully.

    print("Re-reading pex8696_multi_host_mode_reg_set decompiled code...")
    print()
    print("The function assembles bus/addr from the data bytes:")
    print()
    print("Queue message 1 (from local_24 data):")
    print(f"  local_38._0_2_ = CONCAT11(local_24, 0xf3)")
    print(f"  local_24 byte[0] = 0x{d_24[0]:02X} (0x03)")
    print(f"  So local_38 low 2 bytes = 0x03F3")
    print(f"  Then: local_38._0_3_ = CONCAT12(local_23, local_38._0_2_)")
    print(f"  local_23 = d_24[1] = 0x{d_24[1]:02X} (0x07)")
    print(f"  So local_38 low 3 bytes = 0x0703F3")
    print(f"  Then: local_38 = (uint)(uint3)local_38 => 0x000703F3?")
    print()

    # Actually, I think the CONCAT operations are building a queue message
    # structure that includes bus_mux and i2c_addr, not using the data as
    # PLX commands directly.
    #
    # Let me reconsider. The variable names suggest:
    # local_38 = bus/addr info for the queue message
    # local_44 = data pointer
    # local_40 = callback function
    #
    # Looking at pex8696_multi_host_mode_cfg as reference:
    # local_18._0_2_ = 0x30F3  (bus_mux=0xF3, addr=0x30)
    # local_18 = (uint)CONCAT12(3, (undefined2)local_18)
    # This builds: byte[0]=0xF3, byte[1]=0x30, byte[2]=0x03
    # Which is: bus_mux=0xF3, addr=0x30, cmd=0x03
    #
    # In reg_set, the construction is similar but uses bytes from the data:
    # local_38._0_2_ = CONCAT11(local_24[0], 0xf3)
    # = byte[0]=0xF3, byte[1]=local_24[0]
    #
    # But local_24[0] is the FIRST byte of the memcpy'd data.
    # Looking at the memcpy: memcpy(&local_24, DAT_000375a8, 8)
    # On ARM (little-endian), local_24 as a struct starts at the lowest addr:
    #   local_24 byte = d_24[0] = 0x03
    #   local_23 byte = d_24[1] = 0x07
    # Wait, but the variables are:
    #   undefined local_24;  (1 byte)
    #   undefined local_23;  (1 byte)
    #   undefined auStack_22 [6];  (6 bytes)
    # Total = 8 bytes, matching the memcpy size.
    #
    # So: local_24 = 0x03, local_23 = 0x07, auStack_22 = BC E1 00 00 00 00
    #
    # Now the queue message construction:
    # local_38._0_2_ = CONCAT11(local_24, 0xf3) = {0xF3, 0x03}
    #   As uint16: 0x03F3 (little-endian: byte[0]=0xF3, byte[1]=0x03)
    #
    # Hmm, but 0x03 as an I2C address doesn't make sense.
    # Unless... the first byte of the data isn't the PLX command but something else.

    print("=" * 60)
    print("CORRECTED INTERPRETATION")
    print("=" * 60)
    print()
    print("The 8-byte data sets are NOT pre-formatted PLX commands.")
    print("Instead, they contain:")
    print("  byte[0] = I2C bus_mux low byte (address portion)")
    print("  byte[1] = additional parameter")
    print("  bytes[2-7] = PLX command data (copied to command buffer)")
    print()

    # Actually wait, let me re-examine. The function variables:
    # local_1c, local_1b, auStack_1a[8] -> memcpy(&local_1c, ..., 8)
    # local_24, local_23, auStack_22[6] -> memcpy(&local_24, ..., 8)
    # local_2c, local_2b, auStack_2a[6] -> memcpy(&local_2c, ..., 8)
    #
    # Ghidra names them by stack offset.
    # local_1c is at fp-0x1c, local_1b at fp-0x1b, etc.
    # So the 8-byte memcpy fills: local_1c (1 byte), local_1b (1 byte), auStack_1a (6 bytes)
    #
    # d_1c: local_1c=0x03, local_1b=0x07, auStack_1a=[BC EB 00 00 00 01]
    # d_24: local_24=0x03, local_23=0x07, auStack_22=[BC E1 00 00 00 00]
    # d_2c: local_2c=0x03, local_2b=0x07, auStack_2a=[BC E0 00 11 01 10]

    # The queue message assembly for the first send:
    # local_38._0_2_ = CONCAT11(local_24, 0xf3)
    #   byte[0]=0xF3, byte[1]=local_24=0x03
    # local_38._0_3_ = CONCAT12(local_23, local_38._0_2_)
    #   byte[0]=0xF3, byte[1]=0x03, byte[2]=local_23=0x07
    # local_44 = auStack_22 (pointer to the 6-byte data)
    # local_38 = (uint)(uint3)local_38
    #   local_38 = 0x000703F3

    # So the queue message has:
    #   local_44 = pointer to data buffer (6 bytes: PLX command data)
    #   local_40 = callback function (0x00036690)
    #   local_38 = bus/addr/cmd = 0x000703F3
    #     byte[0] = 0xF3 = bus_mux
    #     byte[1] = 0x03 = ???
    #     byte[2] = 0x07 = ???

    # Compare with pex8696_multi_host_mode_cfg queue message:
    #   local_18 = 0x000330F3 for switch addressed 0x30
    #   byte[0] = 0xF3 = bus_mux
    #   byte[1] = 0x30 = i2c_addr (8-bit)
    #   byte[2] = 0x03 = cmd (PLX write)

    # AH! So for reg_set:
    #   byte[0] = 0xF3 = bus_mux
    #   byte[1] = 0x03 = i2c_addr???
    #
    # That can't be right. 0x03 isn't a valid PEX I2C address.
    #
    # Unless the ordering of CONCAT is different. Let me think again...
    # CONCAT11(a, b) = concatenate two 1-byte values into a 2-byte value
    # In Ghidra, CONCAT11(hi, lo) puts hi in the upper byte.
    # So CONCAT11(local_24, 0xF3) = local_24 << 8 | 0xF3 = 0x03F3
    # As a 16-bit value stored little-endian: byte[0]=0xF3, byte[1]=0x03
    #
    # But wait - the decompiled code says:
    # local_38._0_2_ = CONCAT11(local_24, 0xf3);
    # The "._0_2_" means bytes 0-1 (a 2-byte slice starting at offset 0)
    # So local_38 bytes [0:2] = 0x03F3 as uint16
    # On little-endian ARM: memory[0]=0xF3, memory[1]=0x03
    #
    # Then: local_38._0_3_ = CONCAT12(local_23, local_38._0_2_)
    # CONCAT12(byte, uint16) = byte << 16 | uint16
    # = 0x07 << 16 | 0x03F3 = 0x0703F3
    # local_38 bytes [0:3] = 0x0703F3 as uint24
    # memory[0]=0xF3, memory[1]=0x03, memory[2]=0x07
    #
    # Then: local_38 = (uint)(uint3)local_38
    # Zero-extends to 32 bits: 0x000703F3
    #
    # So the 4-byte value sent in the queue is 0x000703F3:
    #   byte[0]=0xF3 (bus_mux)
    #   byte[1]=0x03 (this is NOT i2c_addr; it's the data byte)
    #   byte[2]=0x07
    #   byte[3]=0x00
    #
    # Hmm. But comparing with pex8696_multi_host_mode_cfg:
    #   local_18._0_2_ = 0x30f3 -> byte[0]=0xF3, byte[1]=0x30
    #   local_18 = (uint)CONCAT12(3, (undefined2)local_18)
    #   CONCAT12(3, 0x30F3) = 0x0330F3
    #   local_18 = 0x000330F3
    #     byte[0]=0xF3, byte[1]=0x30, byte[2]=0x03

    # So in pex8696_multi_host_mode_cfg:
    #   byte[0]=0xF3 = bus_mux
    #   byte[1]=0x30 = i2c_addr
    #   byte[2]=0x03 = PLX write command

    # In pex8696_multi_host_mode_reg_set:
    #   byte[0]=0xF3 = bus_mux
    #   byte[1]=0x03 = i2c_addr??? NO!

    # I think the 8-byte data is NOT structured as I initially assumed.
    # Let me look at what the queue handler does with these bytes.
    # The callback at 0x00036690 receives (bus_mux, i2c_addr, cmd, buffer_ptr).

    # Actually, wait. The queue message structure may be:
    #   local_44 = data buffer pointer
    #   local_40 = callback function
    #   local_38 = packed bus/addr/cmd

    # But the queue sends the ADDRESS of local_44, i.e., &local_44.
    # So the queue receives a pointer to a struct:
    #   [ptr to data] [callback] [???] [bus/addr/cmd]
    # Or maybe:
    #   [data_ptr=local_44] [callback=local_40] [unused=local_3c] [packed=local_38]

    # The queue handler extracts these and calls:
    #   callback(bus_mux, i2c_addr, cmd, data_ptr)

    # So from 0x000703F3:
    #   bus_mux = 0xF3
    #   i2c_addr = 0x03
    #   cmd = 0x07

    # That still doesn't make sense. 0x03 isn't a valid PEX8696 address.

    # Unless the function doesn't send to a specific PEX8696 switch.
    # The reg_set function takes param_1 which might be the switch index,
    # and the actual I2C address is determined elsewhere.

    # Actually, re-reading the decompiled code more carefully:
    # void pex8696_multi_host_mode_reg_set(undefined param_1, char param_2)
    # param_1 is an undefined (probably the switch I2C address or index)
    # param_2 is the mode

    # But the function body doesn't seem to use param_1 for the queue message.
    # Let me trace which function calls reg_set.

    print()
    print("Looking at who calls pex8696_multi_host_mode_reg_set...")
    print("Need to search for references to 0x37420 in the binary")
    print()

    # Search for the function address in the binary
    target = struct.pack('<I', 0x37420)
    offset = 0
    refs = []
    while True:
        pos = data.find(target, offset)
        if pos == -1:
            break
        vaddr = pos + BASE_OFFSET
        refs.append(vaddr)
        offset = pos + 1

    print(f"References to 0x37420 found at:")
    for r in refs:
        context = data[r-BASE_OFFSET-8:r-BASE_OFFSET+12]
        print(f"  0x{r:08X}: context {hex_bytes(context)}")

    # Also look for BL (branch-link) instructions targeting 0x37420
    # ARM BL encoding: cond 1011 offset24
    # offset = (target - PC - 8) / 4
    # PC = instruction_addr + 8 in ARM mode
    print()
    print("Scanning for BL instructions targeting 0x37420...")
    for i in range(0, len(data) - 4, 4):
        word = struct.unpack_from('<I', data, i)[0]
        if (word & 0x0F000000) == 0x0B000000:  # BL instruction
            cond = (word >> 28) & 0xF
            if cond != 0xE:  # Only unconditional calls for now
                continue
            offset_val = word & 0x00FFFFFF
            if offset_val & 0x800000:  # Sign extend
                offset_val |= 0xFF000000
                offset_val = offset_val - 0x100000000
            pc = i + BASE_OFFSET + 8  # PC = current + 8 in ARM
            branch_target = pc + (offset_val * 4)
            if branch_target == 0x37420:
                caller_addr = i + BASE_OFFSET
                print(f"  BL at 0x{caller_addr:08X} -> 0x{branch_target:08X}")
                # Show surrounding context
                ctx_start = max(0, i - 16)
                ctx_end = min(len(data), i + 20)
                for j in range(ctx_start, ctx_end, 4):
                    w = struct.unpack_from('<I', data, j)[0]
                    marker = " <-- BL" if j == i else ""
                    print(f"    0x{j+BASE_OFFSET:08X}: {w:08X}{marker}")

if __name__ == '__main__':
    main()
