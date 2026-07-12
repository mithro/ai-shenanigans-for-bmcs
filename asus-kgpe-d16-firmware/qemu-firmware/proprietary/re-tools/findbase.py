import struct
data = open("/home/tim/github/mithro/ai-shenanigans-for-bmcs/.worktrees/d16-qemu/tmp/c4/kernel.bin", "rb").read()
BASE = 0xC0008000
GLOBAL = 0xc03523a4
# The struct holding the AIM-global-pointer field. Its base = GLOBAL - offset,
# offset in [0, 0x400]. Find any 4-byte literal in the image whose value B is a
# plausible base (B <= GLOBAL <= B+0x400) AND B is 4-aligned. Report B + where
# the literal sits (a nearby code literal-pool -> the function using B).
n = len(data)
cands = {}
for off in range(0, n - 4, 4):
    v, = struct.unpack_from("<I", data, off)
    if 0xc0350000 <= v <= GLOBAL and (GLOBAL - v) <= 0x400 and v % 4 == 0:
        cands.setdefault(v, []).append(off)
print(f"candidate base pointers into the struct (value <= 0x{GLOBAL:x}, within 0x400):")
for v in sorted(cands):
    locs = cands[v]
    print(f"  base 0x{v:08x} (global is at +0x{GLOBAL-v:x})  literal at "
          + ", ".join(f"0x{l:x}" for l in locs[:6]))
