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

### 2.1 BMC/AHB side — `peripherals/p2a/fwtest.c`
- ✓ **PCI vendor id = 0x1A03** (ASPEED) via SCU30 — faithful identity.
- observed: **SCU2C[8]=0** (PCI-slave→AHB enabled); the A2P bridge region (0x1E720000)
  reads 0 (the G4 memmap keeps SRAM there — a separate, noted discrepancy).

### 2.2 Host side — the P2A back door is now MODELLED (KCS-M2 pattern) ✅

The faithful G3 P2A model **`hw/misc/aspeed_p2a_ast2050.c`** (`aspeed.p2a-ast2050`,
child `p2a-g3`, wired G3-only in `hw/arm/aspeed_ast2400.c`) implements the §36 back
door and exposes its HOST half as an **honest QOM back-channel** — the same technique
the G3 LPC/KCS model (`aspeed_lpc_ast2050.c`, KCS-M2) uses for the LPC bus wires the
BMC-only machine cannot have. The device masters the AHB (a linked `AddressSpace` over
the SoC `s->memory`), so an aperture cycle lands on the **real modelled peripherals**.

| QOM property (on `/machine/soc/p2a-g3`) | Host operation modelled |
|---|---|
| `host-p2a00-key`   write/read | OUT/IN to **P2A00** (MMIOBASE+0xF000): bit0 unlock (§36.2) |
| `host-p2a04-remap` write/read | OUT/IN to **P2A04** (MMIOBASE+0xF004): bits[31:16] remap base (§36.2) |
| `host-p2a-offset`  write/read | the host's low-16-bit offset into the second-64 KB aperture |
| `host-p2a-data`    write | a host WRITE cycle → AHB dword at `(P2A04[31:16]<<16)\|offset` |
| `host-p2a-data`    read  | a host READ  cycle → AHB dword at the same address |

**Gating is genuine, not faked.** A `host-p2a-data` cycle is honoured only when
**P2A00[0]=1** (host unlock) **and** **SCU2C[8]=0** — the SCU bit is read **live from the
real SCU model** over the AHB on every cycle. Either gate closed → the property **fails
loudly** (`error_setg`), exactly as an ignored (P2A00=0, §36.2 *"ignore all the P-Bus
commands"*) or SCU-disabled host cycle raises no AHB command on silicon.

**Why this is honest.** The QOM properties replace **only** the physical PCI bus wires
(the host memory cycles to BAR1) and the host-BIOS BAR1 placement / memory-space-enable
they subsume — the machine has no host CPU. Everything they trigger — the P2A00 unlock
semantics, the P2A04 remap **equation** (§36.2 p.400), the live SCU2C[8] gate (§18.2
p.214), and a genuine AHB access — is the modelled silicon behaviour. This is the exact
boundary the KCS-M2 model documents (`F5B-HOST-KCS-STATUS.md §5.2`).

**Note:** culvert's *in-band* devmem path (the BMC ARM accessing its own AHB) is not the
P2A backdoor — P2A is the **host→BMC** path. The silicon behaviour is independently
validated via culvert on real hardware (SCU7C=0x202 read over P2A; HW-VALIDATION-CHECKLIST).

### 2.3 Demonstration (`integration/test_p2a.py::TestP2AHostBackdoor`, qtest + QMP)

Drives the BMC side over qtest MMIO and the host side over the QOM back-channel:
- **`test_unlock_and_read_scu7c_through_window`** — unlock P2A00, aim P2A04+offset at
  SCU7C, read **`0x00000202`** back through the aperture: the exact value culvert reads
  over P2A on the real AST2050.
- **`test_window_read_matches_bmc_side`** — the host-side P2A read == the BMC-side AHB
  read of the same register (faithful translation, not a fake).
- **`test_write_roundtrip_into_ahb_dram`** — a host WRITE cycle lands in real AHB/DRAM
  (read back via both the BMC MMIO and the window).
- **`test_remap_equation_low16_passthrough`** — two words in one 64 KB window reached by
  moving only the offset (verifies `AHB=(P2A04[31:16]<<16)|offset`).
- **`test_locked_backdoor_refuses`** / **`test_scu2c_gate_closes_the_backdoor`** — both
  gates (P2A00[0], SCU2C[8]) genuinely refuse when closed.

## 3. Design choice: honest back-channel vs full host-PCI machine

The alternative — adding a **host-side PCI root complex + an ASPEED PCI/VGA endpoint** so a
QEMU PCI master (or a paired host guest) drives BAR1 physically — is a large, machine-level
change to a currently BMC-only machine, and mainline QEMU models **none** of the G3's
conventional-PCI/P2A path (`aspeed_xdma.c` is an AHB-side XDMA stub for the *AST2400 PCIe*
scheme, a different shape). The KCS-M2-style back-channel models the **faithful part** (the
§36 translation + the §18.2/§36 gates, landing on real AHB) while replacing only the bus
wires + BIOS enumeration the BMC-only machine cannot honestly have — the same, accepted
boundary already used for the LPC/KCS host ports. If a paired host-PCI machine is built
later, `host-p2a-*` maps directly onto the endpoint's BAR1 decode with no model change.

## 4. Deliverable status

| # | Deliverable | State |
|---|---|---|
| 1 | firmware test (`fwtest.c`) | ☑ PCI identity + SCU2C enable + A2P observation |
| 2 | doc (this + `DATASHEET-P2A.md`) | ☑ |
| 3 | QEMU model (`hw/misc/aspeed_p2a_ast2050.c`) | ☑ **faithful §36 back door + honest QOM host back-channel** |
| 4 | integration test (`../../integration/test_p2a.py`) | ☑ **`TestP2AHostBackdoor` — SCU7C=0x202 through the window + write round-trip (was xfail, now passing)** |
