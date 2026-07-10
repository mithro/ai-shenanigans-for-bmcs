# P2A / PCI-to-AHB bridge — AST2050 faithfulness doc

The **culvert `p2a` backdoor**: a host PCI master reaches the BMC AHB address space
through the AST2050's **conventional PCI** target. Full detail:
**[`DATASHEET-P2A.md`](DATASHEET-P2A.md)**. A2P bridge (AHB→PCI) @ **0x1E720000**;
PCI arbiter @ 0x1E78C000.

## 1. The P2A→AHB window (host-side, §36)

- Host accesses **PCI-slave BAR1 (`MMIOBASE`)**, a 128 KB memory BAR; its **second
  64 KB is the P2A aperture** (`MMIOBASE+0x10000..0x1FFFF`).
- Control (top of the first 64 KB): **P2A00 @ `MMIOBASE+0xF000`** (bit0 enable, reset 0),
  **P2A04 @ `MMIOBASE+0xF004`** (remap base).
- Mapping: **`AHB = (P2A04[31:16] << 16) | (host_offset & 0xFFFF)`**.
- Enable: **SCU2C[8] = 0** (enable PCI-slave→AHB bridge). No dedicated SCU "P2A enable"
  bit on the G3 (unlike AST2400's SCU180).
- PCI identity: SCU30/34/38 → vendor **0x1A03 (ASPEED)**, device 0x2000, VGA/video class.

## 2. QEMU faithfulness

`peripherals/p2a/fwtest.c` (BMC/AHB side — the host side needs a PCI master):
- ✓ **PCI vendor id = 0x1A03** (ASPEED) via SCU30 — faithful identity.
- observed: **SCU2C[8]=0** (PCI-slave→AHB enabled); the A2P bridge region (0x1E720000)
  reads 0 (unmodelled).
- ✗ **the P2A backdoor cannot be exercised in QEMU**: the machine has **no host PCI/VGA
  endpoint** and **no P2A BAR window** (mainline QEMU models none of it; `aspeed_xdma.c`
  is an AHB-side stub, and the AST2400 uses PCIe/XDMA, not the G3's conventional-PCI BAR).

**Note:** culvert's *in-band* devmem path (the BMC ARM accessing its own AHB, as used in
the culvert HW session) is not the P2A backdoor — P2A is the **host→BMC** path. The
backdoor's silicon behaviour is validated via culvert on real hardware
(HW-VALIDATION-CHECKLIST).

## 3. Faithful-model plan (large, machine-level change)

Add a **host-side PCI bus + an ASPEED PCI/VGA endpoint** to the machine, exposing the
128 KB BAR with the P2A window (P2A00 enable, P2A04 remap → AHB), gated by SCU2C[8]. This
lets a QEMU PCI master (or a host guest) drive the culvert `p2a` path. Big new work
(the machine is currently BMC-only); oracle-gated.

## 4. Deliverable status

| # | Deliverable | State |
|---|---|---|
| 1 | firmware test (`fwtest.c`) | ☑ PCI identity + SCU2C enable + A2P observation |
| 2 | doc (this + `DATASHEET-P2A.md`) | ☑ |
| 3 | QEMU model | ☐ host PCI/VGA endpoint + P2A window (§3, machine-level) |
| 4 | integration test (`../../integration/test_p2a.py`) | ☑ (backdoor xfail — host-side/unmodelled) |
