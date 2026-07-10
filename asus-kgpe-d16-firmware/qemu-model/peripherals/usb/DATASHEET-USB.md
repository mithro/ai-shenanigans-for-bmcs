# AST2050 / AST1100 USB2.0 Virtual Hub Controller — Datasheet Extract

Source: **ASPEED AST2050/AST1100 A3 Datasheet, V1.05** (May 25, 2010).
File: `datasheets/aspeed/AST2050_AST1100_A3_Datasheet_V1.05.pdf`
(Copies also under `asus-kgpe-d16-firmware/datasheets/` and
`dell-c410x-firmware/datasheets/`. Printed page = physical PDF page.)

Purpose: reference for a **faithful QEMU model** of the AST2050 USB2.0 block —
the **virtual-media / virtual-keyboard / virtual-mouse** path OpenBMC exposes to
the host. Every value carries a page cite; the datasheet is noted where silent;
no bit fields are invented.

**Base address of USB Hub = `0x1E6A0000`** (§15.3, p.155; §9 map p.97, "USB2.0
Controller 1E6A:0000–1E6B:FFFF, 128K"). Register = base + offset.
Interrupt: **USB 2.0 = INT#5**, "Sensitive high level trigger" (§10, p.99); the
init guide confirms *"Enable USB2.0 interrupt at VIC10[5]=1"* (p.176).

> ## ⚠️ There is NO EHCI **host** controller on the AST2050
>
> The task brief mentions an "EHCI host at 0x1E6A1000". **That is an
> AST2400/2500/2600 feature, not AST2050.** The AST2050 §9 memory map (p.97) has a
> *single* "USB2.0 Controller" entry at 0x1E6A0000–0x1E6BFFFF, and §15 documents
> only a **USB2.0 device / virtual-hub controller** — a *peripheral/gadget-side*
> controller that presents USB devices **to the host**. There is no EHCI/UHCI USB
> *host* controller (for downstream USB storage) in this SoC. Later Aspeed parts
> (G4+) add on-chip EHCI host(s) at 0x1E6A1000 etc.; the AST2050 does not have one.
> **All virtual media on AST2050 therefore goes through this virtual-hub device
> controller** (see §5). Do not model an EHCI host at 0x1E6A1000 for AST2050.

---

## 0. Where it lives in the datasheet

| What | Section | Page |
|---|---|---|
| Feature summary (§1.3.12 USB2.0 Virtual Hub) | ToC | p.21 |
| Overview + base + features | §15.1/15.2 | **p.154** |
| **Address definition (register map)** | §15.3.1 | **p.155** |
| Root/Global (HUB) registers | §15.3.2 | p.156–164 |
| Device #1–#7 registers | §15.3.3 | p.165–167 |
| Programmable Endpoint #0–#20 registers | §15.3.4 | p.167–171 |
| Endpoint DMA descriptor format | §15.3.5 | p.172–173 |
| Register reset table | §15.3.6 | p.173 |
| Software programming guide (reset/init/Set_Address) | §15.4 | p.174–176 |
| Hardware limitations | §15.5 | p.176–178 |

**Overview (p.154):** *"USB2.0 Controller implements **1 set of USB Hub register
and 7 sets of USB Device registers**."* **Features (p.154):** USB 2.0 (480 Mb/s
HS, 12 Mb/s FS) backward-compatible USB1.1; **virtual-hub architecture — 1 hub
device port + 7 downstream device ports**; **21 programmable endpoints**,
assignable to any device, configurable Bulk/Interrupt/Isochronous IN/OUT; hub =
1 default Control EP + 1 dedicated hub-status Interrupt-IN EP + up to 15
programmable EPs; each downstream device = 1 default Control EP + up to 15
programmable EPs; auto-retry + PING flow control; separate SETUP data buffers;
**integrated DMA (bypasses AHB), independent DMA channel per endpoint, 32-stage
descriptor mode**; USB remote wake-up.

---

## 1. Register map (§15.3.1 Address Definition, p.155)

| Offset range | Size | Block |
|---|---|---|
| 0x000–0x03F | 64B | **Root/Global (HUB) registers** |
| 0x080–0x087 | 8B | Root Device SETUP data buffer |
| 0x088–0x0BF | 8B×7 | Device 1–7 SETUP data buffers |
| 0x100–0x10F | 16B | **Device #1 registers (DEV)** |
| 0x110–0x16F | 16B×6 | Device #2–#7 registers |
| 0x200–0x2FF | 16B×16 | **Programmable Endpoint #0–#15 (EPP)** |
| 0x300–0x34F | 16B×5 | Programmable Endpoint #16–#20 |

`R`=read `W`=write `RW` `W1C`. All init 0 unless noted.

---

## 2. Root/Global (HUB) registers — §15.3.2 (p.156–164)

### HUB00 — Root Function Control & Status (0x00, p.156–157)
The primary control register.
| bit | acc | meaning |
|--|--|--|
| 31 | R | USB PHY clock enable status (mirrors SCU0C[14]) |
| 17 | RW | Isochronous-IN null-data response |
| 16 | RW | Complete "SPLIT IN" after SOF (**must=1 for Set_Address**) |
| 11 | RW | Disable USB PHY reset |
| 10:8 | RW | USB Test Mode select |
| 5 | RW | Remote-wakeup pulse width (0=8ms,1=12ms) |
| 4 | RW | Enable manual remote wakeup (in Suspend) |
| 3 | RW | Enable automatic remote wakeup |
| 2 | RW | Enable clock stopping in Suspend |
| 1 | RW | Upstream-port connection speed (0=HS+FS, 1=FS only) |
| 0 | RW | **Enable upstream port connection** |

Init procedure (p.156): `SCU0C[14]=1` (USB2.0 clock), **wait 10 ms**;
`SCU04[14]=0` (release global reset); `HUB00[11]=1` (release PHY reset); then use.

### HUB04 — Root Configuration Setting (0x04, p.158)
[31:16] R DMA page-buffer status (the 2 KB TX SRAM = 16×128B pages; pages 0–2 form
a ring for the active EP); **[6:0] RW Root function device address** (set after the
status phase of the `Set_Address` control transfer).

### HUB08 — Interrupt Control / enables (0x08, p.158–159)
[17] EP-pool NAK int; [16] EP-pool ACK/STALL int; **[15:9] Device #7–#1 controller
int**; [8] Suspend-Resume; [7] Suspend-Entry; [6] **USB Bus-Reset int**; [5] Hub
EP1 IN ACK; [4] Hub EP0 IN NAK; [3] Hub EP0 IN ACK/STALL; [2] Hub EP0 OUT NAK; [1]
Hub EP0 OUT ACK/STALL; [0] Hub EP0 SETUP ACK.

### HUB0C — Interrupt Status (0x0C, p.159–160, W1C)
[18] R **USB command bus dead-locked** (FATAL: clock stopped / PHY failed / stuck
in Suspend; unmaskable); [17]/[16] EP-pool NAK / ACK-STALL; [15:9] Device #7–#1;
[8] Suspend-Resume; [7] Suspend-Entry; [6] Bus-Reset; [5] EP1 IN ACK/STALL;
[4] EP0 IN NAK; [3] EP0 IN ACK/STALL; [2] EP0 OUT NAK; [1] EP0 OUT ACK/STALL;
[0] **EP0 SETUP data arrives**.

### Endpoint-pool interrupt enable/status (p.160–161)
`HUB10` (0x10) EP-pool ACK int enable [20:0]; `HUB14` (0x14) EP-pool NAK int enable
[20:0]; `HUB18` (0x18) EP-pool ACK int status [20:0] (W1C); `HUB1C` (0x1C) EP-pool
NAK int status [20:0] (W1C). One bit per programmable EP #0–#20.

### HUB20 — Device Controller Soft Reset Enable (0x20, p.162, init 0x3FF)
[9] EP-pool sw reset; [8] DMA controller sw reset; **[7:1] Device #7–#1 controller
sw reset**; [0] Root HUB controller sw reset. (1 = hold reset, resets state
machines/pointers, not register values; see §15.4.1.)

### Other HUB registers
`HUB24` (0x24, p.162) USB Status (debug): suspend/reset/line-state/speed/frame-
number/UTMI state/last EP#/last device address. `HUB28` (0x28, p.163) EP-pool data-
toggle set ([8] toggle value, [4:0] EP index). `HUB2C` (0x2C, p.163) isochronous
fail counters (debug).

### Hub's own endpoints (p.163–164)
- `HUB30` (0x30) **Endpoint 0 (Control) Control/Status**: [22:16] R EP0 OUT
  received byte count; [14:8] RW EP0 IN byte count; [2] EP0 OUT buffer ready;
  [1] EP0 IN buffer ready (mutually exclusive with [2]); [0] EP0 STALL.
- `HUB34` (0x34) Base address of EP0 IN/OUT data buffer [27:3] (64-byte, 64-bit
  aligned).
- `HUB38` (0x38) **Endpoint 1 (hub-status Interrupt-IN) Control/Status**: [2] reset
  EP1 toggle to DATA0; [1] EP1 STALL; [0] **Enable Endpoint 1**.
- `HUB3C` (0x3C) **Endpoint 1 Status-Change Bitmap**: [7:1] Port #7–#1 status change
  (Device #7–#1), [0] Hub port status change. *This is the USB hub status-change
  byte the host polls to discover a virtual device was "plugged".*

---

## 3. Device #1–#7 registers — §15.3.3 (16B each from 0x100, p.165–167)

Each downstream virtual device controller:
- `DEV00` (0x00, p.165) **Downstream Device Function Enable Control**: [14:8]
  downstream device address (Set_Address); [6] EP0 IN-NAK int en; [5] EP0
  IN-ACK/STALL int en; [4] EP0 OUT-NAK int en; [3] EP0 OUT-ACK/STALL int en; [2]
  EP0 SETUP-ACK int en; [1] device port speed (0 FS/LS, 1 HS); **[0] Enable device
  port** (cleared on upstream bus reset).
- `DEV04` (0x04, p.165–166, W1C) Interrupt Status: EP0 IN/OUT NAK, IN/OUT
  ACK/STALL, SETUP received.
- `DEV08` (0x08, p.166–167) Endpoint 0 Control/Status (same layout as `HUB30` plus
  debug DMA-state bits).
- `DEV0C` (0x0C, p.167) Base address of EP0 IN/OUT data buffer [27:3].

---

## 4. Programmable Endpoint #0–#20 — §15.3.4 (16B each from 0x200, p.167–171)

The shared pool of 21 endpoints, each assignable to any device/direction/type.
- `EPP00` (0x00, p.167–168) **Endpoint Configuration Register**:
  [15:14] isochronous data stages; [13] auto-data-toggle disable; [12] EP stall
  control; **[11:8] Endpoint Number**; **[6:4] Endpoint type** (00x disable /
  010 Bulk-In / 011 Bulk-Out / 100 Interrupt-In / 101 Interrupt-Out / 110
  Isochronous-In / 111 Isochronous-Out); **[3:1] Allocated Device Port Number**
  (000 root … 111 downstream device 7); [0] Enable Endpoint.
- `EPP04` (0x04, p.168–169) **DMA Descriptor List Control/Status**: descriptor-
  processing state (debug); [2] Descriptor List Operation Reset; [1] Single-Stage
  Descriptor mode; [0] Descriptor List Operation Enable (32-stage ring).
- `EPP08` (0x08, p.169) DMA Descriptor / Buffer Base Address [27:3] (8-byte aligned;
  descriptor-list base if enabled, else DMA data-buffer base).
- `EPP0C` (0x0C, p.170–171) **DMA Descriptor Read(DMA)/Write(CPU) Pointer & Status**:
  [31] list-empty flag; [29:28] current data toggle; [26:16] packet size; [12:8]
  DMA read pointer; [4:0] CPU write pointer.

### Endpoint DMA descriptor (§15.3.5, 64-bit, p.172–173)
`DES_0` [31:0]: [27:3] DMA data-buffer base (8-byte aligned).
`DES_1` [63:32]: [63] Enable interrupt generation; [62:60] device port (RX); [59:56]
EP number (RX); [54:48] device address (RX); [47:46] Data Packet PID (DATA0/1/2/
MDATA); [45] end-of-packet (RX, iso); [44] start-of-packet (RX, iso); [43] OUT
packet valid flag; [42:32] packet length.

Register reset table (§15.3.6, p.173) lists which fields reset on SCU0C[14],
USB bus reset, HUB20 bits, or EPP00 enable — needed for reset semantics.

---

## 5. Which does virtual media / vKVM-HID use?

**This device controller — there is no alternative on AST2050.** The BMC firmware
programs the virtual-hub to enumerate, *to the host*, one or more USB devices:
- **Virtual keyboard / mouse** → HID interrupt endpoints allocated from the EP pool
  (`EPP00` type = Interrupt-In, assigned to a device port), the vKVM path.
- **Virtual mass-storage** (remote CD/floppy/USB image) → Bulk-In/Out endpoints;
  data moved by the per-EP DMA descriptor engine between DRAM and the host.
- Up to **7 downstream virtual devices** can be presented simultaneously through
  the built-in hub (Device #1–#7), each with its own EP0 and pool endpoints.

The flow (p.174–176): enable clock/reset (SCU0C[14]/SCU04[14]) → configure hub
(`HUB00`…`HUB38`, enable upstream port) → attach a downstream device (`HUB20`
release reset, `DEV00` enable port) → assign endpoints (`EPP00` type/number/port,
`HUB10`/`HUB14` int enables, create DMA) → set the host-status-change bit in
`HUB3C` so the host re-enumerates the "new device". OpenBMC's virtual-media stack
(`obmc-ikvm` HID + `virtual-media`/nbd-backed USB-gadget) drives exactly this
device controller. **No EHCI host is involved on AST2050.**

---

## 6. AST2050 vs AST2400 / 2500 / 2600 — differences a faithful model must capture

1. **No EHCI/UHCI USB host controller on AST2050** — only the virtual-hub *device*
   controller (§9 map p.97; §15). AST2400+ add EHCI host(s) (0x1E6A1000 / 0x1E6B0000)
   plus a companion; a faithful AST2050 machine must **not** instantiate an EHCI
   host at 0x1E6A1000.
2. **Vendor register layout differs from `aspeed-vhub`.** Mainline
   `drivers/usb/gadget/udc/aspeed-vhub/` targets the AST2400/2500 vhub (5 downstream
   ports, 15 generic EPs on early parts, different offsets). AST2050 = **7 downstream
   ports + 21-EP pool + 32-stage per-EP DMA descriptors** with the HUB/DEV/EPP map
   above — a distinct register file.
3. **Clock/reset gating**: SCU0C[14] (clock) + SCU04[14] (global reset), with a
   **10 ms clock-stable delay** (A1+ requirement, p.156); PHY reset via HUB00[11].
4. Documented **hardware limitations** to reproduce for faithfulness (§15.5,
   p.176–178): Set_Address SPLIT-IN needs HUB00[16]=1; **no PRE packet**; DMA
   buffers ≥1024B (overflow risk); unique EP number per device; full-speed
   isochronous-IN >188B needs SW split; **High-Speed high-bandwidth (3 pkts/µframe)
   not supported**.

## 7. Does mainline QEMU model it?

**No** (for AST2050). QEMU attaches a generic EHCI **host** to the AST2400/2500/2600
SoCs (`hw/usb/hcd-ehci*`), but the AST2050 has no EHCI to attach, and the Aspeed
**vhub device controller** is not modelled at all. The 0x1E6A0000 region is
unmapped, so reads return 0 / writes drop — matching the prior modelling notes
(`qemu-firmware/AST2050-PERIPHERAL-MODELING.md` §1: ~79 accesses to `aspeed.io`
0x1E6A0000, "gap: reads 0, writes dropped"). A faithful virtual-media / vKVM path
needs a **new** vhub device model implementing at least HUB00/04/08/0C (control +
interrupt), HUB20 reset, the Device #1–#7 enable/EP0 path, the EPP pool config +
DMA descriptor engine, and the hub status-change bitmap (HUB3C) so the host
enumerates the virtual keyboard/mouse/mass-storage.
