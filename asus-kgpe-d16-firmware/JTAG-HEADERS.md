# JTAG/Debug Headers on the ASUS KGPE-D16

## Overview

The ASUS KGPE-D16 has **two unpopulated JTAG debug headers** that are not
documented in the official ASUS user manual (E8847, Revised Edition V3,
November 2013). Both require soldering to use.

These headers were confirmed by
[Raptor Engineering](https://www.raptorengineering.com/coreboot/kgpe-d16-bmc-port-status.php),
who noted that the KGPE-D16 has "several unpopulated debug ports in the
final production PCBs" including a "BMC JTAG Port" and "AMD HDT
Attachment Ports".

| Header | Connected To | Purpose | Connector Type |
|--------|-------------|---------|---------------|
| AST_JTAG1 | Aspeed AST2050 BMC | BMC firmware debugging | 20-pin ARM JTAG (2x10, 2.54 mm pitch) |
| AMD HDT | AMD Opteron CPU(s) | CPU-level hardware debugging | 20-pin HDT+ (2x10, 1.27 mm pitch) |

---

## Header 1: AST_JTAG1 -- BMC JTAG

This is the **Aspeed AST2050 BMC's JTAG debug port**. It connects to the
ARM926EJ-S core inside the AST2050 BMC SoC and allows low-level
debugging of the BMC firmware (U-Boot, Linux kernel, userspace).

This header is documented in the
[Raptor Porting Guide](RAPTOR-PORTING-GUIDE.md) (Change 26) and on the
[Raptor Engineering BMC port status page](https://www.raptorengineering.com/coreboot/kgpe-d16-bmc-port-status.php).

### Usage

Raptor Engineering successfully used this header with:
- **Debug probe:** Olimex ARM-USB-TINY
- **Software:** OpenOCD
- **Configurations provided:**
  - `olimex-jtag-tiny.cfg`
  - `ast2050.cfg`
  - `kgpe-d16-bmc.cfg`

OpenOCD was functional for U-Boot bring-up. Raptor noted that they
"do not expect OpenOCD to be able to debug the Linux kernel" without
significant additional work.

### Physical Details

A standard 20-pin ARM JTAG header (2x10, 2.54 mm / 0.1" pitch) must
be soldered onto the AST_JTAG1 footprint. This follows the standard
ARM JTAG 20-pin connector pinout (active-low active signals, active-low
active signals).

---

## Header 2: AMD HDT -- CPU Debug (The "Second" JTAG Header)

This is the **AMD HDT (Hardware Debug Tool) attachment port**. It
connects to the AMD Opteron processor(s) and provides CPU-level
hardware debugging via the HDT protocol, which is built on top of
standard IEEE 1149.1 JTAG.

### What is AMD HDT?

HDT (Hardware Debug Tool) is AMD's proprietary CPU debug interface.
It is the AMD equivalent of Intel's XDP (eXtended Debug Port). HDT
extends standard JTAG with additional sideband signals that enable:

- **Run control:** Halt, resume, and single-step CPU cores
- **Register access:** Read/write CPU registers (GPRs, MSRs, CRs)
- **Memory access:** Read/write physical and virtual memory
- **Breakpoints:** Set hardware breakpoints and watchpoints
- **Multi-core debugging:** Independent control of each CPU core
- **Reset control:** Assert/deassert processor reset
- **Power state monitoring:** Monitor PWROK signal

HDT has been present in AMD processors since the K5 (1996). The
interface has evolved over the years:

| Connector | Pins | Pitch | Era | Processors |
|-----------|------|-------|-----|-----------|
| 25-pin HDT | 26 (1 key) | 2.54 mm | Pre-2010 | K5 through Phenom |
| 20-pin HDT+ | 20 | 1.27 mm | 2010+ | Opteron 4000/6000, Bulldozer+ |
| 16-pin Embedded Probe | 16 | 1.27 mm | 2012+ | AMD G-Series SoCs |

The KGPE-D16 uses **AMD Opteron 6100/6200/6300** processors (Family 10h
and Family 15h) in the G34 socket, which use the **20-pin HDT+**
connector format.

### HDT+ Connector Pinout (20-pin)

The HDT+ connector is a 2x10 header with 1.27 mm (0.05") pitch.

```
Pin 1 orientation marker (top-left)

 ┌─────────────────────────┐
 │  1 VDDIO    TCK     2  │
 │  3 GND      TMS     4  │
 │  5 GND      TDI     6  │
 │  7 GND      TDO     8  │
 │  9 TRST_L   PWROK  10  │
 │ 11 DBRDY3   RESET  12  │
 │ 13 DBRDY2   DBRDY0 14  │
 │ 15 DBRDY1   DBREQ  16  │
 │ 17 GND      TEST19 18  │
 │ 19 VDDIO    TEST18 20  │
 └─────────────────────────┘
```

| Pin | Signal | Direction | Description |
|-----|--------|-----------|-------------|
| 1 | VDDIO | Power | I/O reference voltage from target |
| 2 | TCK | Probe → CPU | JTAG Test Clock |
| 3 | GND | Ground | Ground |
| 4 | TMS | Probe → CPU | JTAG Test Mode Select |
| 5 | GND | Ground | Ground |
| 6 | TDI | Probe → CPU | JTAG Test Data In |
| 7 | GND | Ground | Ground |
| 8 | TDO | CPU → Probe | JTAG Test Data Out |
| 9 | TRST_L | Probe → CPU | JTAG Test Reset (active low) |
| 10 | PWROK_BUF | CPU → Probe | Buffered Power OK signal |
| 11 | DBRDY3 | CPU → Probe | Debug Ready for core group 3 |
| 12 | RESET_L | Probe → CPU | Processor Reset (active low) |
| 13 | DBRDY2 | CPU → Probe | Debug Ready for core group 2 |
| 14 | DBRDY0 | CPU → Probe | Debug Ready for core group 0 |
| 15 | DBRDY1 | CPU → Probe | Debug Ready for core group 1 |
| 16 | DBREQ_L | Probe → CPU | Debug Request (active low) |
| 17 | GND | Ground | Ground |
| 18 | TEST19 | -- | Reserved/test pin (may float) |
| 19 | VDDIO | Power | I/O reference voltage from target |
| 20 | TEST18 | -- | Reserved/test pin (may float) |

**Compatible receptacle:** Samtec ASP-137098-05

### HDT Signal Descriptions

**Standard JTAG signals (IEEE 1149.1):**
- **TCK** (Test Clock): Clock signal for the JTAG state machine
- **TMS** (Test Mode Select): Controls TAP state transitions
- **TDI** (Test Data In): Serial data input to the JTAG chain
- **TDO** (Test Data Out): Serial data output from the JTAG chain
- **TRST_L** (Test Reset): Asynchronous reset of the JTAG TAP controller

**AMD HDT sideband signals:**
- **DBREQ_L** (Debug Request): Driven low by the debug probe to request
  that the CPU enter debug mode. This halts execution on the targeted
  core(s).
- **DBRDY0-3** (Debug Ready): Asserted by the CPU when the targeted
  core group has entered debug mode (either in response to DBREQ_L or
  a breakpoint). De-asserted when the core exits debug mode. The
  multiple DBRDY lines correspond to different core groups in
  multi-core processors.
- **PWROK_BUF** (Power OK Buffer): A buffered copy of the platform's
  power-good signal. Indicates to the debug probe that the processor
  has stable power and is ready for debug operations.
- **RESET_L** (Reset): Allows the debug probe to assert a processor
  reset, forcing the CPU back to its reset vector.

### Why Does the KGPE-D16 Have an HDT Header?

The KGPE-D16 is a server/workstation motherboard that was actively
used for open-source firmware development (coreboot, OpenBMC) by
Raptor Engineering and others. HDT is essential for this kind of
low-level firmware work:

1. **BIOS/UEFI debugging:** When firmware crashes before serial output
   is initialised, HDT is the only way to inspect CPU state
2. **AGESA debugging:** AMD's AGESA firmware initialisation code runs
   before DRAM is available, making traditional debugging impossible
3. **Memory training:** DDR3 memory training failures can only be
   diagnosed at the register level
4. **Multi-socket debugging:** The KGPE-D16 is dual-socket; HDT can
   independently debug each CPU
5. **Silicon validation:** Server board manufacturers use HDT during
   board bring-up and validation

### Compatible Debug Probes

The following commercial debug probes support AMD HDT:

| Probe | Manufacturer | Notes |
|-------|-------------|-------|
| ECM-50 + PBD-AJ module | ASSET InterTech (American Arium) | Enterprise-grade |
| ECM-HDT | ASSET InterTech | Dedicated AMD HDT probe |
| ECM-XDP3e | ASSET InterTech | Multi-platform (also Intel XDP) |
| HDT Debug Kit ("Possum") | AMD | AMD-branded, limited availability |
| HDT/LPC Debug Kit ("Purple Possum") | AMD | Combined HDT + LPC debug |
| HDT Platform Debug Kit ("Wombat") | AMD | Full platform debug |
| SmartProbe | Sage Electronic Engineering | Multi-vendor support |

**Software tools:**
- **ASSET InterTech SourcePoint:** Commercial HDT debugger for AMD
  processors
- **AMD HDT (Hardware Debug Tool):** AMD's own debug software (NDA
  required)
- **AMD BIOSDBG:** BIOS debug tool for AMD platforms

Note: Unlike the BMC JTAG (which works with open-source OpenOCD),
AMD HDT requires proprietary debug probes and software. The HDT
protocol is not publicly documented by AMD, though it has been
[partially reverse-engineered](https://ieeexplore.ieee.org/document/10468135/).

### Dual-Socket Considerations

The KGPE-D16 is a **dual-socket** board (CPU1 and CPU2). The Raptor
Engineering page refers to "AMD HDT Attachment **Ports**" (plural),
suggesting there may be **one HDT header per CPU socket**, or a single
header with both CPUs daisy-chained on the JTAG scan chain.

Historical precedent from other AMD dual-socket boards supports both
configurations:

- **Tyan S2885** (dual Opteron): Had **two separate HDT headers** (one
  per CPU), plus jumpers (J94, J95) to configure the multiprocessor
  debug chain. A multiprocessor adapter was needed to connect both
  CPUs to a single debug probe.
  ([Source: coreboot mailing list](https://coreboot.coreboot.narkive.com/jIjhQTvx/problem-with-amd-hdt-setup-for-tyan-s2885-linuxbios-debugging))

- **Dell PowerEdge C6105** (Opteron 4100-4300): Documented as having
  a 20-pin HDT+ connector, likely a single connector per single-socket
  sled.

If the KGPE-D16 has two HDT headers, they would likely be located near
each CPU socket (CPU1 near the top-left, CPU2 near the top-right of
the board, based on the board layout in the ASUS manual section 2.2.3).

**Practical note:** When using HDT on a dual-socket board, only one CPU
needs to be populated for initial bring-up. Single-socket operation
simplifies the debug chain and avoids multi-processor adapter
requirements.

### Historical Use of HDT in Coreboot Development

HDT has been used for coreboot (formerly LinuxBIOS) development on
AMD platforms since the early 2000s. Early coreboot developers used
the Macraigor Systems OCDemon (Raven) debug device with AMD HDT to
debug LinuxBIOS on boards like the Tyan S2885.

Key challenges encountered historically:
- **Jumper configuration:** Some boards require specific jumper settings
  to enable HDT (not documented in user manuals)
- **Multi-processor adapters:** Dual-socket boards may need adapters to
  connect both CPUs to a single debug probe
- **EPP parallel port:** Older HDT probes required EPP-mode parallel
  ports on the host computer
- **Power sequencing:** HDT probes must be connected before the target
  powers on, or the TAP controller may not initialise correctly

Modern HDT probes (ASSET InterTech, Sage) use USB connections and
support both single and multi-socket configurations natively.

---

## Comparison: The Two JTAG Headers

| Feature | AST_JTAG1 (BMC JTAG) | AMD HDT (CPU JTAG) |
|---------|----------------------|-------------------|
| **Target** | Aspeed AST2050 BMC | AMD Opteron CPU(s) |
| **CPU architecture** | ARM926EJ-S | x86-64 (AMD Family 10h/15h) |
| **Protocol** | Standard ARM JTAG | AMD HDT (JTAG + sideband) |
| **Pin count** | 20 pins | 20 pins |
| **Pitch** | 2.54 mm (0.1") | 1.27 mm (0.05") |
| **Open-source tools** | Yes (OpenOCD) | No (proprietary only) |
| **Primary use** | BMC firmware debug | CPU/BIOS firmware debug |
| **Typical users** | BMC developers | BIOS/coreboot developers |
| **Difficulty to use** | Moderate (solder + OpenOCD) | High (solder + expensive probe) |

---

## References

### Raptor Engineering
- [KGPE-D16 BMC Port Status](https://www.raptorengineering.com/coreboot/kgpe-d16-bmc-port-status.php) --
  Confirms unpopulated debug ports including "AMD HDT Attachment Ports"
- [KGPE-D16 Coreboot Status](https://www.raptorengineering.com/coreboot/kgpe-d16-status.php) --
  Coreboot port details for the KGPE-D16

### AMD HDT Documentation
- [x86-JTAG-Open-Research: HDT+ Connector](https://github.com/x86-JTAG-Open-Research/x86-JTAG-Information/blob/master/Connector/HDTPlus.md) --
  20-pin HDT+ connector pinout
- [x86-JTAG-Open-Research: 25-pin HDT Connector](https://github.com/x86-JTAG-Open-Research/x86-JTAG-Information/blob/master/Connector/HDT.md) --
  Older 25-pin HDT connector pinout
- [AMD BC250 HDT+ Pinout](https://elektricm.github.io/amd-bc250-docs/hardware/pinouts/) --
  AMD BC250 board HDT+ connector documentation
- [Undocumented Debug Interface HDT of Modern AMD CPUs (IEEE)](https://ieeexplore.ieee.org/document/10468135/) --
  Reverse engineering of the HDT protocol on AMD EPYC
- [US Patent 7,665,002: Multi-core integrated circuit with shared debug port](https://patents.justia.com/patent/7665002) --
  AMD patent describing DBREQ/DBRDY debug signals

### AMD Processor Documentation
- [BKDG for AMD Family 15h Models 00h-0Fh](https://www.amd.com/content/dam/amd/en/documents/archived-tech-docs/programmer-references/42300_15h_Mod_10h-1Fh_BKDG.pdf) --
  BIOS and Kernel Developer's Guide for Opteron 6200 series
- [BKDG for AMD Family 15h Models 30h-3Fh](https://manualzz.com/doc/25989967/-bkdg--for-amd-family-15h-models-30h) --
  BKDG for Opteron 6300 series

### Community Resources
- [15h.org KGPE-D16 Wiki](https://15h.org/index.php/KGPE-D16) --
  Active coreboot development for the KGPE-D16
- [Vikings Wiki: KGPE-D16](https://wiki.vikings.net/hardware:kgpe-d16) --
  Hardware documentation including SR5690 firmware notes
- [Dasharo KGPE-D16 Setup](https://docs.dasharo.com/variants/asus_kgpe_d16/setup/) --
  Hardware setup guide with debug interface information

### Debug Probe Information
- [x86-JTAG-Open-Research: Target Systems](https://github.com/x86-JTAG-Open-Research/x86-JTAG-Information/blob/master/Target/Target.md) --
  Catalogue of systems with HDT connectors
- [ASSET InterTech: JTAG-based Debug of AMD Servers](https://www.asset-intertech.com/resources/blog/2021/08/jtag-based-debug-of-amd-servers/) --
  Overview of JTAG debugging on AMD server platforms

### Historical Coreboot HDT Usage
- [Coreboot ML: AMD HDT on Tyan S2885](https://coreboot.coreboot.narkive.com/jIjhQTvx/problem-with-amd-hdt-setup-for-tyan-s2885-linuxbios-debugging) --
  Practical HDT debugging discussion for dual-socket Opteron board
- [Slashdot: Hidden Debug Mode Found In AMD Processors](https://hardware.slashdot.org/story/10/11/12/047243/hidden-debug-mode-found-in-amd-processors) --
  Public disclosure of AMD HDT capabilities (2010)

---

## Additional Notes

### JTAG Scan Chain Topology

On AMD server platforms, the JTAG scan chain typically includes
multiple devices daisy-chained together. On the KGPE-D16, the chain
likely includes:

```
Debug Probe
    │
    ▼
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│  CPU 1  │───▶│  CPU 2  │───▶│ SR5690  │───▶│ SP5100  │
│ Opteron │    │ Opteron │    │ (NB)    │    │ (SB)    │
│ (G34)   │    │ (G34)   │    │         │    │         │
└─────────┘    └─────────┘    └─────────┘    └─────────┘
   TDI ──────────────────────────────────────────▶ TDO
```

The exact chain order has not been confirmed for the KGPE-D16.
In single-socket configurations (only CPU1 populated), CPU2's
position in the chain would be bypassed.

### SR5690 Northbridge Microcontroller

The AMD SR5690 (RD890S) northbridge on the KGPE-D16 contains an
embedded microcontroller that the
[Vikings wiki](https://wiki.vikings.net/hardware:kgpe-d16) notes
"requires a firmware upload from the main platform firmware or via
JTAG in order to start execution." This microcontroller handles
IOMMU functionality and possibly other northbridge management tasks.

The SR5690 is architecturally a HyperTransport-to-PCIe bridge and
switch, providing 46 PCIe lanes (42 for external devices, 4 for the
A-Link Express II interface to the SP5100 southbridge). Its embedded
microcontroller is critical for IOMMU initialisation, which the
[Vikings wiki](https://wiki.vikings.net/hardware:kgpe-d16) notes
must be "in the correct location to properly shield the main CPU
from all unauthorized traffic."

The SR5690 is likely accessible via the HDT JTAG chain, either as a
separate TAP in the daisy chain or through the CPU's internal JTAG
routing.

### SP5100 Southbridge

The AMD SP5100 southbridge contains an embedded **8051
microcontroller** core that handles SMBus controller functionality and
other low-level southbridge management. Like the SR5690, this
microcontroller "requires a firmware upload from the main platform
firmware or via JTAG in order to start execution"
([Vikings wiki](https://wiki.vikings.net/hardware:kgpe-d16)).

The SP5100 provides:
- 6x SATA II ports (3 Gb/s)
- USB 2.0 host controllers
- LPC bus interface (connecting to the Super I/O and TPM)
- SMBus controller (via the 8051 core)
- General purpose I/O

The SP5100's 8051 core may also be accessible through the JTAG chain.

### Security Considerations

Modern AMD processors (EPYC and later) have a
[debug unlock mechanism](https://ieeexplore.ieee.org/document/10468135/)
controlled by the Platform Security Processor (PSP/ASP). On the
Opteron 6000 series used in the KGPE-D16, this mechanism is simpler
-- the HDT interface is generally accessible without unlock procedures,
making these older processors more amenable to open-source firmware
debugging.

This is one reason why the KGPE-D16 has been popular for coreboot
and Libreboot development: the HDT debug interface is usable without
AMD NDA restrictions on the debug unlock process.

---

## Open Questions

1. **Exact header location(s):** The precise PCB location(s) of the
   AMD HDT footprint(s) on the KGPE-D16 need to be confirmed by
   physical inspection of the board. They are likely near the CPU
   socket(s).

2. **One or two HDT headers?** Raptor Engineering says "AMD HDT
   Attachment Ports" (plural) -- are there separate headers for each
   CPU socket, or is it a single header with both CPUs on the chain?

3. **Scan chain order:** The order of devices on the JTAG scan chain
   (CPU1 → CPU2 → SR5690 → SP5100, or a different arrangement) has
   not been confirmed.

4. **SR5690 JTAG access:** Is the SR5690's embedded microcontroller
   accessible via the HDT JTAG chain, or does it have a separate JTAG
   interface?

5. **HDT connector variant:** While the 20-pin HDT+ is the most likely
   connector (based on the era and processor family), the older 25-pin
   HDT connector is also possible. Physical inspection is needed.

6. **Jumper requirements:** Like the Tyan S2885, the KGPE-D16 may
   have undocumented jumpers that must be set to enable HDT debugging.

---

**Document Version:** 1.1
**Last Updated:** 2026-02-19
