# AST2050 / AST1100 (A3) — PCI / A2P / P2A Bridge Register Reference

Datasheet-derived register model of the ASPEED **AST2050 / AST1100 (A3)**
PCI interface: the **A2P** (AHB→P-Bus / AHB→PCI) bridge, the **PCI Slave
Controller** (host-facing PCI target + its BARs), and the **P2A** (P-Bus→AHB /
PCI→AHB) *back-door* bridge. This is the block the **culvert `p2a`** backend
uses: a host PCI master reaches the BMC's internal AHB address space through a
PCI-slave memory BAR window whose target AHB address is set by a re-map
register.

Source PDF:
`datasheets/aspeed/AST2050_AST1100_A3_Datasheet_V1.05.pdf`
(**ASPEED AST2050/AST1100 A3 Datasheet, V1.05**, dated May 25, 2010; internal
title *"AST1100 Software Programming Guide"*). Copies also under
`asus-kgpe-d16-firmware/datasheets/` and `dell-c410x-firmware/datasheets/`.

> **Page numbering:** the datasheet's footer page numbers equal the physical PDF
> page index for this file (verified: PDF page 256 has footer "256", PDF page
> 400 has footer "400"). `Read` the PDF at the cited pages directly. Every value
> below carries a page cite. Where the datasheet is silent, this is stated and
> the memory-map / culvert-observed fallback is named — **no bit fields are
> invented.**

Cross-references (used to validate, not to trust blindly):
- Peer doc: `qemu-model/AST2050-MEMORY-MAP.md` (§9 address decode).
- Peer doc: `qemu-model/peripherals/scu/DATASHEET-SCU.md` (SCU register detail).
- Raptor register map `asus-kgpe-d16-firmware/hwreg.h` (does **not** define any
  A2P/P2A/PCI base — silent here; the datasheet §9 is the sole base-address
  source).

---

## 0. Where it lives in the datasheet (chapter / page map)

| Block | Section | Page(s) | Direction / role |
|---|---|---|---|
| §9 ARM Address Space Mapping (base-address table) | §9 | **p.97** | A2P base, PCI arbiter, PCI host windows |
| **AHB to P-Bus Bridge (A2P)** | **§21** | **p.256** | **AHB → PCI** (ARM masters the P-Bus) |
| MDMA Engine (adjacent, for context) | §22 | p.257–261 | (not PCI; AHB memory-DMA) |
| **PCI Slave Controller (PCIS)** | **§33** | **p.363–368** | **Host PCI target** + BARs (incl. P2A window) |
| VGA Display Controller | §34 | p.369–392 | Reached over the PCI BAR0/legacy VGA path |
| 2D Graphics Engine | §35 | p.393–399 | Reached over PCI |
| **P-Bus to AHB Bridge (P2A)** | **§36** | **p.400** | **PCI → AHB back door** (culvert `p2a`) |
| Graphics Hardware Cursor | §37 | p.401–403 | VGA-side |
| SCU PCI-config + gating bits | §18.2 | p.213–218 | SCU2C[8], SCU30/34/38, SCU70 |

Note there is **no dedicated register chapter for the PCI Arbiter** — it appears
only in the §9 map (`0x1E78_C000`, 4 KB, p.97).

---

## 1. §9 memory-map entries for the PCI subsystem (p.97, verbatim)

From the §9 "ARM Address Space Mapping" table (p.97), the PCI-related rows
(quoted exactly, `Write Mode` / `Read Mode` in bytes):

| Address Range | Size | Wr | Rd | IP Module |
|---|---|---|---|---|
| `1E72:0000–1E73:FFFF` | 128K | 1/2/4 | 1/2/4 | **AHB to PCI (P-Bus) Bridge Controller (A2P)** |
| `1E78:C000–1E78:CFFF` | 4K | 4 | 1/2/4 | **PCI Arbiter** |
| `6000:0000–7FFF:FFFF` | 512M | 1/2/4 | 1/2/4 | **PCI Host Memory #1** |
| `8000:0000–FFFF:FFFF` | 2G | 1/2/4 | 1/2/4 | **PCI Host Memory #2** |

So the **A2P bridge base = `0x1E72_0000`** and the **PCI arbiter base =
`0x1E78_C000`**, exactly as the memory-map doc records. `0x6000_0000` and
`0x8000_0000` are the ARM's *outbound* windows onto the external PCI bus (the
BMC as PCI host). §9 note (p.97): *"Program access the IP using un-supported
access mode will get an un-predictable result."*

---

## 2. A2P bridge — AHB → PCI (P-Bus), base `0x1E72_0000` (§21, p.256)

The entire §21 chapter is one page of prose plus a window table — **there are no
per-bit register definitions and no reset values printed.** Quoted in full
(p.256):

**Overview (§21.1):**
> *"AHB-to-P Bus Bridge (A2P) is an interface controller bridging two internal
> buses: **AHB** — the internal system bus supporting ARM SOC subsystem;
> **P-Bus** — the internal expansion bus supporting bus commands from PCI slave
> controller. A2P is a one way bus bridge providing a path for ARM to access all
> the IP modules located on the P-Bus."*

**Operation (§21.2):**
> *"The bridge will be auto enabled when set to PCI master mode (SCU70.bit[4]).
> AHB to P-bus bridge control registers address = 0x1E72_0000 + OFFSET*
> - *OFFSET = 00000-0007F  Address for relocated I/O on P-bus*
> - *OFFSET = 00080-0FFFF  reserved*
> - *OFFSET = 10000-1FFFF  Address for MMIO space on P-bus"*

Interpretation for the model:
- The A2P window is **128 KB** (`0x1E72_0000`–`0x1E73_FFFF`, §9). ARM reaches the
  P-Bus IP (VGA / 2D engine / SPI host / PCI-config of the slave) through it.
- Two sub-apertures: **relocated I/O** at offset `0x00000–0x0007F`, and **MMIO
  space** at offset `0x10000–0x1FFFF`; `0x00080–0x0FFFF` is reserved.
- **No mailbox / outbound-window / doorbell registers are defined for A2P in this
  datasheet.** The A2P direction is purely an address-decode bridge, not a
  register file. A faithful model presents the 128 KB window with the two
  sub-apertures and no side-effect registers; there is nothing to reset.
- ⚠️ **SCU70.bit[4] inconsistency (flagged, not resolved by the datasheet).**
  §21.2 attributes the auto-enable to *"PCI master mode (SCU70.bit[4])"*, but the
  SCU70 register definition (§18.2, p.218) lists **bit[4] as "Reserved, must keep
  at value '0'"** — there is no "PCI master mode" bit documented in the SCU70
  table. This is an internal datasheet contradiction. Note also that the AST2050
  never masters the *external* host PCI bus (PCIS04[2] "Bus master enable"
  *"always return 0"*, p.365) — "PCI master mode" here refers to the internal A2P
  (ARM-masters-P-Bus) direction, not to bus-mastering the host bus. Treat the
  A2P enable as effectively always-on for ARM-side P-Bus access; do not model a
  functional SCU70[4].

---

## 3. PCI Slave Controller — host-facing PCI target + BARs (§33, p.363–368)

This is the AST2050 as a **conventional 32-bit / 33 MHz PCI 2.3 target** on the
host's PCI bus. Its config space is where the host discovers the BARs that lead
to the VGA framebuffer, the VGA I/O, and — critically — the **P2A window**.

**Overview (§33.1, p.363):**
> *"PCI Slave Controller (PCIS) is a bus controller designed to bridge PCI bus
> and P-bus, which can directly communicate with VGA Controller, 2D Graphics
> Engine, SPI Host Controller, and **P2A Bridge**. PCIS total implements 13 PCI
> Configuration registers …"*

**Features (§33.2, p.363):**
> *"Support 32-bit 33 MHz PCI bus interface with PCI 2.3 specification compliant;
> Support big-endian & little-endian which can be enabled by register settings;
> Support PME# & CLKRUN# control pins; Support AD[31:0] bus reverse option for
> PCB layout optimization."*

### 3.1 PCI Slave config-space registers (base = PCI config space, §33, p.363–368)

| Off | Name | Init | Key fields (page) |
|---|---|---|---|
| 0x00 | **PCIS00 Device & Vendor ID** | `0x2000_1A03` | [31:16] Device ID = **0x2000** (same as AST2000, for driver compat); [15:0] Vendor ID = **0x1A03** (ASPEED). Mirrors **SCU30**. (p.363) |
| 0x04 | **PCIS04 Command & Status** | `0x0210_0000` | [1] RW **Memory space access enable** (0=disable,1=enable — *"determine whether AST2050/AST1100 will response to memory space accesses"*); [0] RW I/O space access enable; [10] RW Interrupt disable; [2] Bus master enable = *"always return 0"* (never a PCI master); [20] Capabilities-list=1; [26:25] DEVSEL=01 medium. (p.364–365) |
| 0x08 | **PCIS08 Class & Revision ID** | `0x0X00_0010` | [31:8] Class code: **`0x030000` when VGA enabled** (VGA controller); **`0x040000` when VGA disabled by external trapping resistor** (video device, *"will not decode any VGA command cycles"*); [7:0] Revision ID (rev1=00, rev2=10). Mirrors **SCU38**. (p.365) |
| 0x0C | PCIS0C Miscellaneous | `0x0000_0000` | [23:16] Header type=0; [15:8] Latency timer=0; [7:0] Cache line size. (p.365) |
| 0x10 | **PCIS10 Base Address 0 (BAR0)** | `0x0000_0000` | RW *"claim a re-locatable **memory** space (**8MB/16MB/32MB/64MB**) for **linear frame buffer** allocation … size depends on the two corresponding trapping resistors."* → VGA framebuffer BAR. (p.366) |
| 0x14 | **PCIS14 Base Address 1 (BAR1)** | `0x0000_0000` | RW *"claim a **128KB re-locatable memory** space … The **first 64KB is for VGA I/O** addressing space, the **second 64KB is for P2A Bridge** addressing space."* → **THIS BAR IS `MMIOBASE`** (see §4). (p.366) |
| 0x18 | **PCIS18 Base Address 2 (BAR2)** | `0x0000_0001` | RW *"claim a 128KB re-locatable **I/O** space … used for VGA legacy and extended I/O cycles."* (Init bit0=1 → PCI I/O-space BAR.) (p.366) |
| 0x2C | PCIS2C Subsystem ID | `0x2000_1A03` | [31:16] Subsystem ID=0x2000; [15:0] Sub-vendor ID=0x1A03. Per-byte **write-once** until next power-on. Mirrors **SCU34**. (p.366) |
| 0x30 | PCIS30 Expansion ROM Base | `0x0000_0000` | RW claims 64 KB for VGA BIOS; disableable by trapping resistor when VGA BIOS is merged into system BIOS. (p.366) |
| 0x34 | PCIS34 Capability | `0x0000_0040` | [7:0] Capabilities pointer = **0x40** (→ PCI Power Management cap). (p.366) |
| 0x3C | PCIS3C Interrupt | `0x0000_0100` | [15:8] Interrupt pin = **0x01 (INTA#)**; [7:0] Interrupt line (RW, no HW effect); [31:24] max-latency; [23:16] min-grant. (p.367) |
| 0x40 | PCIS40 PCI PM Capability | `0xffc3_0001` | PME support D0–D3cold, D1/D2 supported, PM rev 1.2, cap-ID=0x01. (p.367) |
| 0x44 | PCIS44 PCI PM Control/Status | `0x0000_0000` | [1:0] RW Power state D0/D1/D2/D3 (also gates HSYNC/VSYNC/DAC); [8] PME enable; [15] PME status. (p.367–368) |

Key takeaways for the P2A path:
- **BAR1 (PCIS14) is the P2A vehicle.** Its 128 KB memory window splits into VGA
  I/O (first 64 KB) and the **P2A bridge aperture (second 64 KB)**. This BAR base
  *is* the `MMIOBASE` referenced by §36.
- To reach any BAR over PCI memory cycles the host must set **PCIS04[1] = 1**
  (memory space access enable) — standard PCI enumeration, done by host BIOS.
- BAR0 = VGA linear framebuffer (memory), BAR2 = VGA legacy/extended I/O (I/O
  space). Neither is the AHB back door; only BAR1's second 64 KB is.

---

## 4. P2A bridge — PCI → AHB back door, base `MMIOBASE` (§36, p.400) ★

This is the exact mechanism culvert's `p2a` backend drives. Quoted in full.

**Overview (§36.1, p.400):**
> *"P-to-AHB Bus Bridge (P2A) is an interface controller bridging two internal
> buses: **P-Bus** — internal expansion bus supporting bus commands from PCI
> slave controller; **AHB** — internal system bus supporting ARM SOC subsystem.
> P2A is a one-way bus bridge providing a **back door for host CPU to access all
> the internal IP modules in ARM SOC sub-system.** Since P2A is a one-way bridge,
> ARM CPU cannot issue any PCI commands through the help of this bridge. In a
> normal condition, this back door should be well locked. The two potential
> usages of this bus bridge are: 1. Updating flash memory through host CPU;
> 2. H/W or S/W debugging through host CPU. P2A only implements **two sets of
> 32-bit registers** to provide a protection mechanism and specify the base
> address of the 64KB address re-mapping window."*

**Registers — Base Address = `MMIOBASE` (§36.2, p.400):**

| Offset (from MMIOBASE) | Name | Init | R/W | Definition (verbatim, p.400) |
|---|---|---|---|---|
| **`0xF000`** | **P2A00 Protection Key** | **0** | [0] **RW** | **Protection key: `0` = Disable P2A bridge, `1` = Enable P2A bridge.** *"When P2A is disabled, it will ignore all the P-Bus commands. Therefore, there will be no command conversion from P-Bus to AHB. Always keep this protect key in disabled state when there is no need."* [31:1] Reserved(0). |
| **`0xF004`** | **P2A04 Re-mapping Base Address** | **X** | [31:16] **R** | **Re-mapping base address.** *"This register defines the address re-mapping scheme from P-Bus to AHB. Bit[31:16] of AHB address is from the Bit[31:16] of this register, Bit[15:0] is directly from P-Bus command address."* [15:0] Reserved(0). |

**The re-map equation (verbatim, p.400):**
> **`AHB Address = (Re-mapping base address[31:16]) + (P-bus address[15:0])`**
>
> *"P2A will convert all the commands from P-bus with 64KB address range from
> **(MMIOBASE + 0x10000) to (MMIOBASE + 0x1FFFF)**. Where MMIOBASE is the
> re-locatable memory-mapped I/O base address defined in PCI configuration
> space. P2A supports byte, word or double word type of access commands."*

### 4.1 How this maps to `MMIOBASE` and BAR1

`MMIOBASE` (§36) = **BAR1 = PCIS14** (§33.1): the *"re-locatable memory-mapped
I/O base address defined in PCI configuration space."* Layout of the 128 KB
BAR1 window as seen by the host:

```
MMIOBASE + 0x00000 .. 0x0EFFF   VGA I/O space (first 64KB, §33 PCIS14)
MMIOBASE + 0x0F000              P2A00  Protection Key   (this bridge's control)
MMIOBASE + 0x0F004              P2A04  Re-mapping Base   (this bridge's control)
MMIOBASE + 0x10000 .. 0x1FFFF   P2A data aperture (second 64KB) → re-mapped to AHB
```

The P2A **control** registers sit at the top of the first 64 KB (`0xF000`/
`0xF004`); the P2A **data window** is the second 64 KB. A host access to
`MMIOBASE + 0x10000 + n` (n = 0…0xFFFF) is converted to AHB address
`(P2A04[31:16] << 16) | (n & 0xFFFF)` — i.e. the high 16 bits come from the
re-map register, the low 16 bits pass through. The window is therefore a **64 KB
sliding aperture**; to move it you rewrite P2A04[31:16].

> ⚠️ **P2A04 R/W caveat (flagged).** The datasheet prints P2A04[31:16] with R/W =
> **"R"** (read-only). Functionally the host *must* be able to set the re-map
> base (that is the whole point of the back door, and is exactly what culvert
> writes), so the "R" is best read as *ARM/AHB-side read-only* (ARM cannot steer
> the host's window) or a datasheet erratum; from the **P-Bus/host side the field
> is programmable**. A faithful model should make P2A04[31:16] writable from the
> host-facing (BAR1) path. This is the one place the datasheet's attribute
> column is self-inconsistent with the stated behaviour — noted, not invented.

---

## 5. The culvert `p2a` programming sequence (host side)

Putting §33 + §36 together, a host PCI master reaches an arbitrary BMC AHB
address `A` (e.g. `0x1E6E207C` = SCU7C) like this:

1. **Enumerate / place BAR1.** Host BIOS assigns PCIS14 (BAR1) a 128 KB memory
   window → `MMIOBASE`. Ensure **PCIS04[1] = 1** (memory space enable). (§33,
   p.364/366)
2. **Unlock the back door.** Write `MMIOBASE + 0xF000 = 0x0000_0001`
   (P2A00[0]=1 → *Enable P2A bridge*). (§36, p.400)
3. **Set the window's target.** Write `MMIOBASE + 0xF004`, field [31:16] = the
   high half-word of `A` (e.g. `0x1E6E` for SCU space) → P2A04 re-map base.
   (§36, p.400)
4. **Read/write through the aperture.** Access
   `MMIOBASE + 0x10000 + (A & 0xFFFF)` (e.g. `+0x1207C`) with byte/word/dword
   cycles. The bridge yields `AHB = (0x1E6E << 16) | 0x207C = 0x1E6E207C`. (§36,
   p.400)
5. **Re-lock when done.** Write P2A00[0]=0 to disable the bridge (datasheet:
   *"Always keep this protect key in disabled state when there is no need."*).

This is precisely the "write an AHB address into a window register, then
read/write through the BAR" pattern the task describes, and it is why culvert's
`p2a` backend can `devmem`-style peek/poke the whole SoC from the host.

---

## 6. SCU bits that gate the P2A path (§18.2)

The real per-transaction gate is **P2A00 (MMIOBASE+0xF000)**. But the PCI-slave →
AHB fabric that P2A rides on is additionally gated by SCU bits — all must be in
the "open" state for the back door to function. Values verbatim from
`DATASHEET-SCU.md` / §18.2:

| SCU reg | Bit | Meaning (page) | "Open P2A" state |
|---|---|---|---|
| **SCU2C** Misc. Control | **[8]** | **"Disable PCI slave to AHB bus bridge": 0 = Enable bridge, 1 = Disable bridge** (p.214) | **must be `0`** (bridge enabled). This is the SCU-level "PCI/VGA-slave → AHB enable" the culvert session opens. |
| SCU04 System Reset Ctrl | [8] | "Reset PCI Slave and VGA Controller" (p.206) | must be `0` (module out of reset). Init=0 → already released. |
| SCU0C Clock Stop | [4] | "Stop BCLK (PCI Slave)" (p.210) | must be `0` (clock running). Init=0 → already running. |
| SCU70 HW Trapping | [15] | "PCI Class Code selection: 0=video device, 1=VGA device" (p.218) | selects whether PCIS08 class = 0x040000 (video) vs 0x030000 (VGA); does not gate P2A itself. |
| SCU70 HW Trapping | [17] | "PCI VGA Config Space Prefetch bit setting" (p.218) | config-space prefetch hint. |
| SCU70 HW Trapping | [5] | "Enable VGA BIOS ROM" (p.218) | gates the expansion-ROM BAR (PCIS30), not P2A. |
| SCU70 HW Trapping | [3:2] | "VGA memory size: 8/16/32/64 MB" (p.218) | sizes BAR0 framebuffer. |

**⇒ On the AST2050 the single SCU register that "opens the PCIe/VGA-to-AHB back
door" is `SCU2C[8] = 0` (do not disable the PCI-slave→AHB bridge).** There is
**no** dedicated "P2A enable" bit inside the SCU on this part — the enable lives
in the P2A block itself (P2A00). (Contrast AST2400+, where the equivalent lives
in SCU180 "PCIe/VGA to AHB" enable bits.) Note the §21 reference to
"SCU70.bit[4]" is not a documented SCU70 field (see §2 flag).

---

## 7. PCI configuration identity (vendor / device / class / VGA function)

The BMC presents itself to the host as an ASPEED graphics/VGA device. The SCU
carries the identity that PCIS reflects into config space:

| SCU reg | Init | Fields (p.214–215) | Mirrors PCIS |
|---|---|---|---|
| **SCU30** PCI Config #1 | `0x2000_1A03` | [31:16] PCI **Device ID** = 0x2000; [15:0] PCI **Vendor ID** = **0x1A03 (ASPEED)** | PCIS00 |
| **SCU34** PCI Config #2 | `0x2000_1A03` | [31:16] **Sub-System ID** = 0x2000; [15:0] **Sub-Vendor ID** = 0x1A03 | PCIS2C |
| **SCU38** PCI Config #3 | `0x0300_0000` | [31:8] **Class Code** = **0x030000 (VGA)**; [7:0] **Revision ID** = 0x00 | PCIS08 |

- **Vendor 0x1A03 = ASPEED Technology Inc.** (assigned by PCI-SIG); Device
  **0x2000** deliberately equals the AST2000 device ID *"to make sure AST2050/
  AST1100 can directly run all the graphics display drivers developed for
  AST2000"* (PCIS00, p.363).
- **Class code 0x030000 = VGA-compatible display controller.** When VGA is
  disabled by an external trapping resistor (SCU70[15]=0 / strap), the class
  becomes **0x040000 = "video device"** and the part stops decoding VGA I/O
  cycles (PCIS08, p.365). Either way the P2A back door (a plain memory BAR) is
  unaffected — it does not depend on VGA decode.
- The **VGA display function** (§34, p.369–392) and 2D engine (§35) are the P-Bus
  IP that the framebuffer BAR0 / legacy-I/O BAR2 expose; they are *not* the back
  door. The memory-map doc's "PCI slave + VGA display function reached over PCI"
  is these blocks.

---

## 8. AST2050 (conventional PCI) vs AST2400+ (PCIe / X-DMA), and mainline QEMU

### 8.1 What the AST2050 actually is

- **Conventional 32-bit, 33 MHz PCI 2.3 *target*** (PCIS04/§33.2 features,
  p.363). No PCI Express. No bus-mastering (PCIS04[2] *"always return 0"*).
- The host→AHB path is the **PCI-slave BAR1 → P2A 64 KB sliding-window** scheme
  above: a *register-remapped* memory window, **no DMA descriptor engine**.
- The A2P bridge (`0x1E72_0000`) is the reverse (ARM→P-Bus) address bridge.
- There is a genuine **X-DMA/PCIe-to-AHB engine? NO** — the AST2050 has **no
  XDMA controller and no PCIe**. (No such chapter in §9/§ToC; the §9 map has only
  the A2P bridge, PCI arbiter, PCI-slave config, and PCI host windows.)

### 8.2 What AST2400+/G4+ do differently (external knowledge — not in this datasheet)

- AST2400/2500/2600 replace conventional PCI with a **PCIe** interface and add a
  dedicated **X-DMA controller** (a command-queue DMA engine, AHB-side base
  `0x1E6E_7000` on G4/G5) for host↔BMC bulk transfer. Their "P2A" is the
  **PCIe-to-AHB** bridge, enabled via **SCU180 "PCIe→AHB / VGA→AHB" enable
  bits** (plus the VGACRA/hicr config), with a different register layout than the
  AST2050's P2A00/P2A04. **[G4+: not in this datasheet]**
- Practical consequence: culvert's AST2400/2500 `p2a` code paths and the AST2050
  path differ (different enable bit, different window control). The AST2050 uses
  **P2A00 key + P2A04 remap inside BAR1**, gated by **SCU2C[8]**.

### 8.3 Does mainline QEMU model any of this? — No (verified in-tree)

Checked the vendored QEMU tree
(`asus-kgpe-d16-firmware/qemu-firmware/qemu/qemu`):

- The aspeed machine family starts at **AST2400 (G4)** — there is **no AST2050/G3
  SoC model at all** (`hw/arm/aspeed_ast2400.c`, `..._ast2600.c`, `..._ast27x0.c`,
  `..._ast10x0.c`).
- **No host-facing PCI/PCIe root complex, no VGA PCI endpoint, and no P2A/BAR
  window** is modelled for any aspeed BMC. `grep` for `p2a` / `MMIOBASE` /
  `0x1e72` across `hw/arm`, `hw/misc`, `hw/pci-host`, `include/hw` returns only:
  a comment in `include/hw/misc/aspeed_scu.h` (referencing *this project's*
  SCU7C=0x202 culvert-P2A work), and the XDMA stub.
- `hw/misc/aspeed_xdma.c` (245 lines) is a **command-queue register stub only**:
  it tracks `CMDQ_ADDR/ENDP/WRP/RDP` read/write pointers at the **AHB-side**
  address `0x1E6E_7000` and performs **no actual PCIe→AHB memory bridging**. It
  exists so the BMC-side driver probes; it does not expose a host back door.

**⇒ A faithful AST2050 P2A/PCI model is entirely new work — nothing in mainline
QEMU can be reused for the host→AHB back door, and the AST2050's conventional-PCI
BAR/P2A scheme is not even the same shape as the (unmodelled) AST2400 PCIe/XDMA
path.**

---

## 9. What a faithful QEMU AST2050 model must present

1. **A2P window** at `0x1E72_0000` (128 KB): a passive address bridge with a
   relocated-I/O sub-aperture (`+0x00000..0x0007F`) and an MMIO sub-aperture
   (`+0x10000..0x1FFFF`); `+0x00080..0x0FFFF` reserved. No side-effect registers,
   nothing to reset (§21, p.256).
2. **PCI Arbiter** at `0x1E78_C000` (4 KB): present in §9 only; datasheet gives no
   register bits — model as a 4 KB RAZ/WI (or scratch) block and note silence.
3. **A conventional PCI target device** exposing config space per §33: IDs
   `0x1A03:0x2000`, class `0x030000` (VGA) or `0x040000` (video per SCU70[15]),
   subsystem `0x1A03:0x2000`, cap pointer 0x40, INTA#. Reset values as tabulated
   in §3.1 (all page-cited).
4. **BAR0** = 8/16/32/64 MB memory (framebuffer, size per SCU70[3:2]); **BAR1** =
   128 KB memory (`MMIOBASE`; first 64 KB VGA I/O + P2A control regs at 0xF000/
   0xF004, second 64 KB = P2A aperture); **BAR2** = 128 KB I/O (VGA legacy/ext).
5. **P2A bridge** behind BAR1: `P2A00` (MMIOBASE+0xF000, key, reset 0) and
   `P2A04` (MMIOBASE+0xF004, remap base) implementing
   `AHB = (P2A04[31:16] << 16) | (host_offset & 0xFFFF)` over the
   `MMIOBASE+0x10000..0x1FFFF` aperture, **only when P2A00[0]=1** and
   **SCU2C[8]=0** and the PCI slave is out of reset (SCU04[8]=0) / clocked
   (SCU0C[4]=0). Make P2A04[31:16] host-writable (see §4.1 flag).
6. **SCU identity/gating**: SCU30/34/38 feed the PCI config IDs; SCU2C[8] gates
   the slave→AHB bridge. Model these so a host driving the culvert `p2a` sequence
   (unlock P2A00 → set P2A04 → read/write the aperture) can read e.g. SCU7C =
   `0x00000202` back through the window.

---

## 10. Source-quote appendix (exact wording, with page)

- **A2P base & window** (§21.2, p.256): *"AHB to P-bus bridge control registers
  address = 0x1E72_0000 + OFFSET … OFFSET = 00000-0007F Address for relocated I/O
  on P-bus … OFFSET = 10000-1FFFF Address for MMIO space on P-bus."* Auto-enable:
  *"when set to PCI master mode (SCU70.bit[4])"* — **contradicted** by SCU70[4]
  = *"Reserved, must keep at value '0'"* (§18.2, p.218).
- **P2A purpose** (§36.1, p.400): *"P2A is a one-way bus bridge providing a back
  door for host CPU to access all the internal IP modules in ARM SOC sub-system …
  this back door should be well locked."*
- **P2A protection key** (§36.2 P2A00, p.400): *"0: Disable P2A bridge, 1: Enable
  P2A bridge … Always keep this protect key in disabled state when there is no
  need."*
- **P2A re-map** (§36.2 P2A04, p.400): *"AHB Address = (Re-mapping base
  address[31:16]) + (P-bus address[15:0]) … convert all the commands from P-bus
  with 64KB address range from (MMIOBASE + 0x10000) to (MMIOBASE + 0x1FFFF).
  Where MMIOBASE is the re-locatable memory-mapped I/O base address defined in
  PCI configuration space. P2A supports byte, word or double word type of access
  commands."*
- **BAR1 = MMIOBASE, holds P2A aperture** (§33.1 PCIS14, p.366): *"claim a 128KB
  re-locatable memory space … The first 64KB is for VGA I/O addressing space, the
  second 64KB is for P2A Bridge addressing space."*
- **Memory-space enable** (§33 PCIS04[1], p.365): *"0: Disable memory space
  accesses, 1: Enable memory space accesses. This register will determine whether
  AST2050/AST1100 will response to memory space accesses."*
- **Not a PCI master** (§33 PCIS04[2], p.365): *"AST2050/AST1100 doesn't support
  PCI bus master cycles; this register will always return 0."*
- **Class code** (§33 PCIS08[31:8], p.365): *"When VGA Controller is enabled …
  return 0x030000 … When VGA is disabled by an external trapping resistor …
  return 0x040000 … As a video device, AST2050/AST1100 will not decode any VGA
  command cycles."*
- **Vendor/Device IDs** (§33 PCIS00, p.363): *"default setting … 0x2000 … device
  ID code … the same as AST2000 …"*, *"0x1A03 … vendor ID code … assigned for
  ASPEED Technology Inc. by PCISIG."*
- **SCU2C[8] slave→AHB bridge** (§18.2, p.214): *"Disable PCI slave to AHB bus
  bridge — 0: Enable bridge, 1: Disable bridge."*
- **PCI features** (§33.2, p.363): *"Support 32-bit 33 MHz PCI bus interface with
  PCI 2.3 specification compliant."*

---

*Derived entirely from AST2050/AST1100 A3 Datasheet V1.05 (2010-05-25), §9
(p.97), §21 (p.256), §33 (p.363–368), §36 (p.400), and §18.2 (p.213–218). Where
the datasheet is silent (A2P register bits, PCI arbiter registers) this is stated
and the §9 memory-map / culvert-observed behaviour is named as the fallback. Any
statement about AST2400/2500/2600 (PCIe/X-DMA) is external knowledge, flagged
"[G4+: not in this datasheet]", and is not a datasheet claim. Mainline-QEMU
status verified against the in-tree `hw/arm/aspeed_*` / `hw/misc/aspeed_xdma.c`
sources.*
