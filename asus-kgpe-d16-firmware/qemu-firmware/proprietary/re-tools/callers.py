import struct, sys
data = open("/home/tim/github/mithro/ai-shenanigans-for-bmcs/.worktrees/d16-qemu/tmp/c4/kernel.bin", "rb").read()
BASE = 0xC0008000
target = int(sys.argv[1], 16) if len(sys.argv) > 1 else 0xa5678
callers = []
for off in range(0, len(data) - 4, 4):
    w, = struct.unpack_from("<I", data, off)
    if (w >> 24) == 0xeb:                      # bl (AL)
        imm = w & 0xffffff
        if imm & 0x800000:
            imm -= 0x1000000
        tgt = off + 8 + imm * 4                # file-offset target
        if tgt == target:
            callers.append(off)
print(f"{len(callers)} callers of 0x{BASE+target:08x} (fn at file 0x{target:x}):")
for c in callers:
    print(f"  bl at file 0x{c:x} (vaddr 0x{BASE+c:08x})")
