# F6 — USB on the AST2050 BMC ("connect USB devices")

**Goal (user):** demonstrate the BMC being able to *connect USB devices*, shown in
QEMU and characterized on real hardware, simplest-first.

**Headline finding (faithfulness-first):** the AST2050 has **exactly one USB block —
a USB2.0 *device / virtual-hub* controller at `0x1E6A0000` (VIC INT#5)**. It has **NO
USB *host* controller** (no EHCI, no UHCI, no OHCI). So on this BMC "connect USB
devices" does **not** mean "plug a USB stick into the BMC and enumerate it" (there is
no host port to do that). It means the BMC **presents virtual USB devices _to the
managed server host_** — a virtual keyboard, mouse, and mass-storage / remote media —
over that device/vhub during KVM. **F6 is therefore the same silicon as F8 (KVM);
this task lays the groundwork.**

---

## 1. What USB hardware the AST2050 really has (evidence)

### 1.1 Datasheet (the faithfulness oracle)

Source: **ASPEED AST2050/AST1100 A3 Datasheet V1.05** (in-repo:
`dell-c410x-firmware/datasheets/AST2050_AST1100_A3_Datasheet_V1.05.pdf`).

- **§9 memory map (p.97):** a *single* USB entry —
  `1E6A:0000–1E6B:FFFF` labelled **"USB2.0 Controller"** (128 KB). There is **no
  second USB region** (no host-controller aperture at 0x1E6A1000 / 0x1E6B0000).
- **§10 interrupt table (p.99):** **"USB 2.0 interrupt" = INT#5**, "Sensitive high
  level trigger". There is **no "USB 1.1 interrupt"** in the table.
- **§15 "USB2.0 Virtual Hub Controller" (p.154–178):** documents **only a
  device / virtual-hub controller** — "1 set of USB Hub register + 7 sets of USB
  Device registers", a **21-endpoint pool**, **per-endpoint DMA descriptors**, and a
  hub status-change bitmap the *host* polls to discover a "plugged" virtual device.
  This is a **peripheral/gadget-side** controller (it presents devices *to* a host),
  **not** a host controller (which would drive downstream USB storage).
- §2.7 (p.—) confirms the virtual-hub can "easily emulate USB keyboard and USB mouse
  functions" — i.e. it is the vKVM HID path.

Full register-level extract with page cites:
[`qemu-model/peripherals/usb/DATASHEET-USB.md`](../../qemu-model/peripherals/usb/DATASHEET-USB.md).

> The AST2400/2500/2600 (G4+) *do* add on-chip **EHCI host** controllers at
> 0x1E6A1000 etc. plus companions; **the AST2050 (G3) does not.** A faithful G3 model
> must not expose an EHCI host — see §3.

### 1.2 The "USB 1.1 Controller: Yes" feature-table entry

The datasheet's product feature table lists both a "USB 2.0 Controller" and a "USB
1.1 Controller" as present. This is the USB2.0 vhub's **USB 1.1 backward
compatibility** (the vhub runs HS 480 Mb/s *and* FS 12 Mb/s), **not** a separate
USB 1.1 host controller — there is no separate region or IRQ for one in §9/§10.

### 1.3 Raptor's 2.6.28 AST2050 Linux port (real-HW software evidence)

Raptor Engineering's working AST2050 kernel (analysed in
`asus-kgpe-d16-firmware/RAPTOR-PORTING-GUIDE.md`) contains USB *device-controller*
register headers (`regs-udc11.h`, "USB Device Controller") and — notably — a custom
UHCI *host* driver (`drivers/usb/astuhci/`, `dev-uhci.c`) with an assumed IRQ 4.

**Assessment:** the UHCI host driver is **dead / carried BSP code, not a real AST2050
host controller.** It contradicts the AST2050 datasheet, which has no host-controller
region and no USB-1.1 IRQ. Aspeed's BSP is shared across many SoCs; the AST2050 build
carries the UHCI files but the silicon has no UHCI host aperture. `RAPTOR-PORTING-
GUIDE.md` itself flags this as uncertain ("Does the standard UHCI driver work … or is
the custom `astuhci` driver needed?") and the datasheet resolves it: **there is no
host controller to drive.** The AST2050 USB story is entirely the device/vhub.

**Conclusion:** the *only* faithful AST2050 USB is the USB2.0 device/virtual-hub at
`0x1E6A0000`, IRQ5.

---

## 2. What that means for "connect USB devices" (and for F6 scope)

| Role | On a typical BMC | On the AST2050 |
|---|---|---|
| **USB host** (BMC reads an attached USB stick / keyboard) | EHCI/UHCI/OHCI host | **absent** — no host controller in silicon |
| **USB device / gadget** (BMC presents vKVM keyboard/mouse + virtual media to the *server host*) | UDC / vhub | **the USB2.0 device/vhub @0x1E6A0000** — the one and only USB block |

So the useful, faithful "USB works" demonstration for the AST2050 is: **the OpenBMC
kernel probes the AST2050 USB2.0 device/vhub controller and brings up the USB gadget
stack** — the foundation the F8 KVM work (obmc-ikvm HID + virtual-media) runs on.
A generic "kernel probes a host controller → enumerate an attached usb-storage" demo
is **not applicable to this SoC** and modelling an EHCI host to fake it would be
*un*faithful (and would undo the deliberately-removed phantom EHCI — see §3).

---

## 3. Prior faithful QEMU state (starting point)

The faithful `kgpe-d16-bmc` QEMU machine already:

- **Models the USB2.0 device/vhub** as `aspeed.udc-ast2050` at `0x1E6A0000`, IRQ-wired
  (`hw/misc/aspeed_udc_ast2050.c`) — a register block (HUB / device / EP-pool window,
  0x000–0x2FF) created only for `silicon_rev == AST2050_A1_SILICON_REV`.
- **Omits the phantom EHCI**: `hw/arm/aspeed_ast2400.c` gates EHCI creation off for the
  G3, so `0x1E6A1000` reads 0 (no AST2400 EHCI host on the AST2050).

Verified with the bare-metal fwtest (`peripherals/usb/fwtest.c`):
`hub00.rw PASS` (HUB00 is RW at 0x1E6A0000) and `ehci1000 = 0` (no phantom EHCI).

Full model plan + register map:
[`qemu-model/peripherals/usb/DOC.md`](../../qemu-model/peripherals/usb/DOC.md).

---

## 4. What F6 adds

1. **Kernel:** re-enable USB (the kernel had `CONFIG_USB_SUPPORT=n`) and turn on the
   **gadget** stack (`kernel/kgpe-d16-usb.config`): `aspeed-vhub` (the mainline Aspeed
   vhub UDC driver, bound at 0x1E6A0000/IRQ5), `dummy_hcd` (software UDC+host loopback
   for an in-guest enumeration demo), and configfs **mass-storage + HID** functions
   (the exact vKVM / virtual-media functions F8 needs).
2. **DTS:** enable `&vhub` at 0x1e6a0000/IRQ5 with the **faithful AST2050 counts**
   (7 downstream ports, 21-endpoint pool).
3. **Demonstration in QEMU:** boot the USB-enabled kernel on `-M kgpe-d16-bmc` and show
   (a) the OpenBMC kernel **probing the AST2050 USB2.0 device/vhub controller** and
   registering a UDC, and (b) the USB gadget stack **enumerating a device in-guest**
   over `dummy_hcd` (groundwork; the real vhub presents to the *server host*, which
   QEMU does not emulate). Evidence under `evidence/f6-usb/`.
4. **Tests/CI:** extend the bare-metal `fwtest`/`integration/test_usb.py` and add a CI
   job.

### Approximations (honest)

- `aspeed-vhub` is an **AST2400-family** driver; the AST2050 vhub register file differs
  (7 ports / 21-EP pool + 32-stage per-EP DMA descriptors vs the AST2400's 5/15 layout,
  see DATASHEET-USB §6). It is the correct *class* of controller and binds at the right
  base/IRQ, but a **dedicated G3 UDC driver + a functional QEMU vhub datapath** (so the
  BMC can actually present a device *to the host*) are **F8-KVM follow-ups**. The QEMU
  `aspeed.udc-ast2050` is a register block; full device semantics (enumeration, EP DMA,
  media transport) are the F8 refinement.
- `dummy_hcd` is a **software loopback**, not AST2050 silicon; it exists only to
  demonstrate the gadget stack end-to-end in-guest.

---

## 5. Real-hardware status

The USB2.0 controller register aperture (0x1E6A0000) is reachable on the real board via
the existing P2A / JTAG AHB paths (same access used to read SCU7C), so a non-disruptive
characterization (confirm the region decodes, read HUB00) is possible without a full
boot slot. **Bringing up the gadget on real silicon (presenting a virtual keyboard or
media image to the KGPE-D16 host) is F8-KVM and needs the dedicated G3 UDC driver.**
This document marks clearly what is QEMU-only vs HW-proven; see `PROGRESS.md`.
