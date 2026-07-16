# ASUS KCMA-D8 — board reference (15h.org mirror)

The **ASUS KCMA-D8** is the Socket-C32 sibling of the KGPE-D16: same AMD
SR5670/SP5100 chipset generation, same Winbond W83667HG-A Super I/O, same
Nuvoton W83795G hardware monitor, and — most relevant to this repository —
the **same Aspeed AST2050 BMC delivered on a removable ASMB4/ASMB5 module**.
Raptor Engineering's AST2050 port (the source of truth for this directory,
see [`RAPTOR-PORTING-GUIDE.md`](RAPTOR-PORTING-GUIDE.md)) explicitly targeted
both the KGPE-D16 and the KCMA-D8
([`RAPTOR_ENGINEERING_AST2050_ANALYSIS.md:29`](RAPTOR_ENGINEERING_AST2050_ANALYSIS.md)).

> **Source / provenance.** This document mirrors the complete content of the
> 15h.org wiki page **[ASUS KCMA-D8](https://15h.org/index.php/ASUS_KCMA-D8)**
> (permanent link: [`oldid=2941`](https://15h.org/index.php?title=ASUS_KCMA-D8&oldid=2941),
> last edited 8 July 2026, retrieved 2026-07-16). 15h.org content is licensed
> **CC BY-SA 4.0**; this file is therefore CC BY-SA 4.0 (an exception to the
> repository's default Apache-2.0). All PDFs the page links to are committed
> in [`datasheets/`](datasheets/) — see
> [`datasheets/15H-ORG-MIRROR.md`](datasheets/15H-ORG-MIRROR.md) for the
> link-by-link mapping.

---

## Overview / specifications (infobox)

| Field | Value |
|-------|-------|
| Introduced | 2010 |
| Manufacturer | ASUS |
| Socket | 2x C32 |
| Northbridge | 1x AMD SR5670 |
| Southbridge | AMD SP5100 |
| Super I/O | Winbond W83667HG-A |
| BMC | ASPEED AST2050 (OpenBMC-compatible) |
| BMC Flash Location | Removable Module |
| Memory | 8 slots (4 channels) DDR3-1600 ECC UDIMM/RDIMM/LRDIMM |
| BIOS Flash | 2 MiB socketed DIP-8 (W25Q16V) |
| Form Factor | SSI CEB, might fit in an ATX case that has 1 cm extra |
| Power Inputs | 1x 8-pin EPS |
| Graphics Adapter | AST2050 Integrated VGA |
| Network Interface | 2x Intel 82574L Gigabit |
| Storage Controller | SP5100's SATA2 (3.0 Gbps), no SAS unless PIKE2008 installed |
| USB Controller | SP5100's onboard USB 2.0 |
| Serial Interface | One SIO-provided RS232, one virtual BMC console port |
| Audio Interface | None (ASUS recommended a PCI sound card) |

Expansion slots:

- PCIe Gen2 x16
- PCIe Gen2 x16 (electrically x8)
- PCIe Gen2 x8 (electrically x4)
- 3x 32-bit Legacy PCI (5V)
- ASUS PIKE2008 Interface

Board photo: [Asus-kcma-d8-top-64c7d3a66747d247126312.jpg](https://15h.org/index.php/File:Asus-kcma-d8-top-64c7d3a66747d247126312.jpg)

## Open Source Firmware

Support for the KCMA-D8 motherboard by **coreboot-15h**, 15h.org's downstream
coreboot variant for fam15h systems, was recently completed (as of the page's
July 2026 revision).

Open source firmware for the KCMA-D8 is provided by coreboot-15h utilizing
AMD's open source AGESA and CIMx releases for platform initialization. Git
repository: <https://git.15h.org/mrothfuss/coreboot-15h>.

### coreboot-15h — supported board variants

Supported motherboard variants:

- KCMA-D8 (Serial Numbers **B9S2xxxxxxxx and up**)

Unsupported motherboard variants:

- KCMA-D8 (Serial Numbers **B8S2xxxxxxxx and below**)
  - These old boards only work with 4100 series Opterons

### coreboot-15h — releases

Each release ships three 2 MB build flavours: *SeaBIOS + uCode + VGA-OpROMs*,
*SeaBIOS + uCode (text-mode)*, and *SeaBIOS (text-mode, blob-free)*.

| Release | Notes | Downloads (2 MB tarballs) |
|---------|-------|---------------------------|
| 2026.05.04-v4.11-5d336ff7176 | Improved power efficiency; improved SATA performance; improved thermal management; enabled PCIe ASPM support; enabled the Power LED | [ucode+ast2050-oprom+vga-oproms](https://15h.org/images/c/c0/Coreboot-15h_2026.05.04-v4.11-5d336ff7176_asus_kcma-d8_seabios_ucode_ast2050-oprom_vga-oproms_2mb.tar.gz) · [ucode, no oproms](https://15h.org/images/7/71/Coreboot-15h_2026.05.04-v4.11-5d336ff7176_asus_kcma-d8_seabios_ucode_no-oproms_2mb.tar.gz) · [blob-free](https://15h.org/images/e/ed/Coreboot-15h_2026.05.04-v4.11-5d336ff7176_asus_kcma-d8_seabios_no-ucode_no-oproms_2mb.tar.gz) |
| 2025.12.17-v4.11-582d6f37158 | Fixed support for the BMC module | [ucode+ast2050-oprom+vga-oproms](https://15h.org/images/6/68/Coreboot-15h_2025.12.17-v4.11-582d6f37158_asus_kcma-d8_seabios_ucode_ast2050-oprom_vga-oproms_2mb.tar.gz) · [ucode, no oproms](https://15h.org/images/a/a5/Coreboot-15h_2025.12.17-v4.11-582d6f37158_asus_kcma-d8_seabios_ucode_no-oproms_2mb.tar.gz) · [blob-free](https://15h.org/images/7/70/Coreboot-15h_2025.12.17-v4.11-582d6f37158_asus_kcma-d8_seabios_no-ucode_no-oproms_2mb.tar.gz) |
| 2025.12.08-v4.11-4bb1cd46931 | Enabled COM2; fixed COM1/COM2 ACPI entries (improves OS detection of COM1/COM2 ports) | [ucode+ast2050-oprom+vga-oproms](https://15h.org/images/e/e9/Coreboot-15h_2025.12.08-v4.11-4bb1cd46931_asus_kcma-d8_seabios_ucode_ast2050-oprom_vga-oproms_2mb.tar.gz) · [ucode, no oproms](https://15h.org/images/d/db/Coreboot-15h_2025.12.08-v4.11-4bb1cd46931_asus_kcma-d8_seabios_ucode_no-oproms_2mb.tar.gz) · [blob-free](https://15h.org/images/a/a8/Coreboot-15h_2025.12.08-v4.11-4bb1cd46931_asus_kcma-d8_seabios_no-ucode_no-oproms_2mb.tar.gz) |
| 2025.11.11-v4.11-61cbef5bdd2 | Initial v4.11 AGESA release | [ucode+ast2050-oprom+vga-oproms](https://15h.org/images/4/4f/Coreboot-15h_2025.11.11-v4.11-61cbef5bdd2_asus_kcma-d8_seabios_ucode_ast2050-oprom_vga-oproms_2mb.tar.gz) · [ucode, no oproms](https://15h.org/images/f/f5/Coreboot-15h_2025.11.11-v4.11-61cbef5bdd2_asus_kcma-d8_seabios_ucode_no-oproms_2mb.tar.gz) · [blob-free](https://15h.org/images/4/48/Coreboot-15h_2025.11.11-v4.11-61cbef5bdd2_asus_kcma-d8_seabios_no-ucode_no-oproms_2mb.tar.gz) |

Note the "ast2050-oprom" flavour: full VGA output requires Aspeed's
closed-source VGABIOS option ROM in the coreboot image (see the
[ASPEED AST2050](#aspeed-ast2050) section below).

### Missing features

- SeaBIOS does not respond to keyboards behind a USB hub.
- Hibernation and Suspend/Resume are unsupported.
- Opteron 4100 series CPUs are unsupported.
- ASUS MIO audio cards are untested.

### Flashing

To switch from the stock firmware to coreboot, **external flashing** is
required. The DIP-8 flash chip is located at the bottom right corner of the
board (labeled BIOS in the motherboard diagram). A 3.3V CH341a programmer can
be used to flash coreboot onto the KCMA-D8. When switching to coreboot-15h
from the OEM BIOS or coreboot, clearing the CMOS is required.

**Clearing the CMOS:**

1. Turn off the computer and disconnect the power cord
2. Move the CLRTC1 jumper (located under PCI Slot 4) to positions 2-3
3. Wait 20 seconds
4. Restore the CLRTC1 jumper to positions 1-2
5. Connect the power cord and turn on the computer

## Deployed systems

- [Ponos](https://15h.org/index.php/Ponos) (a 15h.org community system)

15h.org itself is hosted from *Qubesotron*, Dodoid's **KGPE-D16** server —
i.e. the wiki runs on this repo's target board family.

## Motherboard diagrams

Hosted on the wiki (CC BY-SA 4.0):

- [KCMA-D8 Motherboard Diagram.png](https://15h.org/index.php/File:KCMA-D8_Motherboard_Diagram.png)
- [KCMA-D8 Motherboard BlockDiagram.png](https://15h.org/index.php/File:KCMA-D8_Motherboard_BlockDiagram.png)
- [KCMA-D8 Motherboard DDR3 Slots.png](https://15h.org/index.php/File:KCMA-D8_Motherboard_DDR3_Slots.png)
- [KCMA-D8 Motherboard DDR3 Voltage.png](https://15h.org/index.php/File:KCMA-D8_Motherboard_DDR3_Voltage.png)

## Motherboard components

### Socket C32

Socket C32 is compatible with AMD Opteron 4000 series processors. All
compatible CPUs contain a single NUMA node. CPU coolers designed for Socket F
are compatible with Socket C32.

#### AMD Opteron 4100 Series

Processors in the AMD Opteron 4100 Series were designed with the **K10**
microarchitecture and are compatible with the C32 socket.

Official source code and documentation (PDFs mirrored in
[`datasheets/`](datasheets/)):

- [AGESA Source Code](https://review.coreboot.org/c/coreboot/+/95) (coreboot Gerrit change 95)
- AGESA Interface Specification — `44065_Arch2008.pdf`
- BIOS and Kernel Developer's Guide (fam10h) — `AMD_Family_10h_BKDG_31116.pdf`
- Product Data Sheet — `AMD_Family_10h_Opteron_PDS_40036.pdf`
- Power and Thermal Data Sheet — `AMD_Family_10h_Power_Thermal_Data_Sheet_43374.pdf`
  (the page's direct link is stale on the wiki; see the mirror map)

#### AMD Opteron 4200 and 4300 Series

Processors in the AMD Opteron 4200 and 4300 Series were designed with the
**Bulldozer** (4200 series) and **Piledriver** (4300 series) microarchitectures
and are compatible with the C32 socket.

Official source code and documentation:

- [AGESA Source Code](https://review.coreboot.org/c/coreboot/+/554) (coreboot Gerrit change 554)
- AGESA Interface Specification — `44065_Arch2008.pdf`
- BIOS and Kernel Developer's Guide — `42301_15h_Mod_00h-0Fh_BKDG.pdf`
- Product Data Sheet — `49687_15h_Mod_00h-0Fh_Opteron_PDS.pdf`
- Software Optimization Guide — `47414_15h_sw_opt_guide.pdf`

### DDR3 memory

The vast majority of UDIMM, RDIMM, and LRDIMM DDR3 modules are expected to
work without issue. So far only one module has been found to be
[incompatible with the AGESA](https://15h.org/index.php/AGESA_15h#Incompatible_DDR3_Modules).
The maximum RAM supported is **256 GB per CPU socket**. RDIMM modules are
recommended for motherboards that support them. The following is an incomplete
list of tested modules (review the deployed systems list for well tested
hardware configurations):

| Product | ECC | Type | Capacity | Speed | Tester |
|---------|-----|------|----------|-------|--------|
| Actica ACT4GHU72D8H1333S | Yes | UDIMM | 4 GB | 1333 MHz | mrothfuss |
| Actica ACT8GHR72Q4H1600S | Yes | RDIMM | 8 GB | 1600 MHz | mrothfuss |
| ASint SLA302G08-GGNHC | No | UDIMM | 4 GB | 1600 MHz | mrothfuss |
| ELPIDA EBJ81RF4BDWD-DJ-F | Yes | RDIMM | 8 GB | 1333 MHz | mrothfuss |
| Corsair TR3X6G1333C9 | No | UDIMM | 2 GB | 1333 MHz | mrothfuss |
| Crucial CT16G3ERSLD4160B | Yes | RDIMM | 16 GB | 1600 MHz | mrothfuss |
| Crucial CT32G3ELSDQ4186D | Yes | LRDIMM | 32 GB | 1866 MHz | mrothfuss |
| Hynix HMT42GR7AFR4A-PB | Yes | RDIMM | 16 GB | 1600 MHz | pkubaj |
| Hynix HMT84GL7MMR4A-H9 | Yes | LRDIMM | 32 GB | 1333 MHz | mrothfuss |
| Kingston KVR13N9S8/4 | No | UDIMM | 4 GB | 1333 MHz | mrothfuss |
| Kingston KVR16E11/8I | Yes | UDIMM | 8 GB | 1600 MHz | mrothfuss |
| Kingston KVR1333D3D4R9S/4G | Yes | RDIMM | 4 GB | 1333 MHz | mrothfuss |
| Kingston KVR16R11D4K4/32I | Yes | RDIMM | 8 GB | 1600 MHz | mrothfuss |
| Micron MT36KSF2G72PZ-1G4E1 | Yes | RDIMM | 16 GB | 1333 MHz | mrothfuss |
| Micron MT36KSF2G72PZ-1G6E1FE | Yes | RDIMM | 16 GB | 1600 MHz | mrothfuss |
| Micron MT36KSF2G72PZ-1G6N1KF | Yes | RDIMM | 16 GB | 1600 MHz | mrothfuss |
| Nanya NT4GC64B8HG0NF-DI | No | UDIMM | 4 GB | 1600 MHz | mrothfuss |
| Samsung M393B1K70DH0-YH9 | Yes | RDIMM | 8 GB | 1333 MHz | mrothfuss |
| Samsung M393B1G70QH0-YK0 | Yes | RDIMM | 8 GB | 1600 MHz | mrothfuss |
| Samsung M393B2K70DM0-YF8 | Yes | RDIMM | 16 GB | 1066 MHz | mrothfuss |
| Samsung M393B2G70BH0-CK0 | Yes | RDIMM | 16 GB | 1600 MHz | mrothfuss |
| Samsung M393B4G70BM0-YH9 | Yes | RDIMM | 32 GB | 1333 MHz | mrothfuss |
| Samsung M393B4G70DM0-YH9 | Yes | RDIMM | 32 GB | 1333 MHz | mrothfuss |
| Samsung M386B4G70DM0-CMA | Yes | LRDIMM | 32 GB | 1866 MHz | mrothfuss |
| Samsung M386B4G70DM0-YK04 | Yes | LRDIMM | 32 GB | 1600 MHz | sbrudenell |
| Samsung M386B8G70DE0-YH93 | Yes | LRDIMM | 64 GB | 1333 MHz | mrothfuss |
| Super Talent W1333UB4GS | No | UDIMM | 4 GB | 1333 MHz | frantic |
| Super Talent W1333EB4GS | Yes | UDIMM | 4 GB | 1333 MHz | mrothfuss |
| Super Talent W16RB8G4S | Yes | RDIMM | 8 GB | 1600 MHz | mrothfuss |
| Super Talent W13RC16G4H | Yes | RDIMM | 16 GB | 1333 MHz | mrothfuss |

**DDR3 voltage jumper**: the KCMA-D8 provides an external method to override
the BIOS DDR3 voltage. BIOS control is configured to select a voltage that
maximizes performance for all DIMM modules attached to a socket. Forcing a
different voltage may cause stability problems. **Use the default jumper
setting (1.5V / BIOS control) when using coreboot-15h.**

### PCIe 2.0 slots

| Slot | Width | Wired Lanes | Notes |
|------|-------|-------------|-------|
| PCIe1 | x16 | x16 | |
| PCIe3 | x16 | x8 | |
| PCIe5 | x8 | x4 | Disabled if PIKE is occupied. |

### PIKE slots

The two PIKE slots, PIKE1 and PIKE2, are used together to attach an ASUS PIKE
card to the KCMA-D8. This is required to utilize the 8 onboard SAS ports.

The PIKE2008 card is recommended for most cases. This card offers 6Gbps
SAS2/SATA3 support, which is faster than the 3Gbps SATA2 provided by the
SP5100. The card can be flashed to IT Mode, which allows the host operating
system to access the drives individually. Other PIKE cards provide 3Gbps
SAS1/SATA2 support.

The family of ASUS PIKE cards are just PCIe SAS host bus adapters with a
proprietary PIKE connector. PIKE cards have no onboard SAS/SATA connectors.
The motherboard's SAS ports are wired to the PIKE slots, and function as a
proprietary wiring harness for the PIKE card. PIKE cards use common HBA chips
(LSI or Marvell) supported in the Linux kernel.

PIKE cards are low-profile, and fit in a 1U chassis. The PIKE connector has a
latch which anchors the card to the motherboard, so the card does not need to
be fixed to the chassis. The PIKE slot is placed at the bottom of the
motherboard, leaving space for e.g. an additional full-height card in a
90-degree riser.

SeaBIOS has limited support for SAS adapters including the PIKE2008. It
cannot boot from them, unless the card's option ROM is executed. Option ROMs
are disabled in the pre-built releases of coreboot-15h. LinuxBoot or other
payloads may be able to boot from these cards.

**Note**: On the KCMA-D8, the PIKE slot is shared with PCIe5 (only one may be
used). So a standard HBA may be used in PCIe5 instead of a PIKE card, which
may be better depending on your use case:

- Use another PCIe HBA if you want a mini-SAS connector
- Use an AHCI PCIe HBA if you want to boot from SATA3 drives (with SeaBIOS,
  without oproms) — this is untested but should work
- Use a PIKE card if you are constrained on chassis space (if you need both
  an HBA and another full-height card in a 90-degree riser)

### DIP-8 socket (BIOS flash)

The DIP-8 socket houses the mainboard's BIOS ROM. The following DIP-8 chips
are known to work with coreboot on the KCMA-D8:

| Model | Size (MB) | Size (Mb) |
|-------|-----------|-----------|
| W25Q16BVAIG | 2 | 16 |
| W25Q64BVAIG | 8 | 64 |
| W25Q128FVIQ | 16 | 128 |

### ASPEED AST2050

The AST2050 chipset is an Integrated Remote Management Processor introduced
by ASPEED Technology Inc. It is a high performance and highly integrated SOC
device designed to support various management functions required for server
platforms which require baseboard management, virtual storage functions,
and/or KVM-over-IP functions.

Open source support for the AST2050's VGA output (**text-mode only**) was
implemented in coreboot by Raptor Engineering
([coreboot Gerrit change 11937](https://review.coreboot.org/c/coreboot/+/11937)).
Full VGA output support requires ASPEED's closed source VGABIOS to be included
in the coreboot rom. A rudimentary port of OpenBMC was also developed by
Raptor Engineering
([kgpe-d16-bmc-port-status](https://www.raptorengineering.com/coreboot/kgpe-d16-bmc-port-status.php))
— the same port analysed throughout this directory.

Official documentation (mirrored in [`datasheets/`](datasheets/)):

- AST2050 Datasheet — the page's copy is byte-identical to
  `AST2050_AST1100_A3_Datasheet_V1.05.pdf` (the A3 Datasheet V1.05 this repo
  already relies on)
- S25FL128P Datasheet — byte-identical to `S25FL128P_Datasheet.pdf`
  (the SPI-NOR flash on the BMC module)

Remote administration features on the AST2050 are only activated when a
firmware module (**ASMB4 or ASMB5**) is attached to the mainboard's BMC_FW1
slot. *(The wiki text says "the KGPE-D16 mainboard" here — an apparent
copy-over from the KGPE-D16 page; the same ASMB4/ASMB5-in-BMC_FW1 arrangement
applies to the KCMA-D8, whose infobox lists the BMC flash as "Removable
Module".)*

### AMD SR5670

The AMD SR5670, formerly known as RD870S, is a versatile system logic designed
for the latest server/workstation platform, supporting AMD's next-generation
CPUs. The chipset features 34 PCI Express (PCIe) lanes, with 30 lanes
dedicated to external PCIe devices and 4 for the A-Link Express II interface
to AMD's Southbridges like the SP5100 (formerly SB700S). Utilizing
HyperTransport 3 and PCIe Gen 2 technologies, the SR5670 offers high
performance and reliability in a compact 29mm x 29mm package.
([TheRetroWeb chip 5697](https://theretroweb.com/chips/5697))

Official source code and documentation:

- [CIMx Source Code](https://review.coreboot.org/c/coreboot/+/557) (coreboot Gerrit change 557)
- BIOS Developer's Guide — `AMD_SR5690_5670_5650_BIOS_Developers_Guide.pdf` (pub 43870)
- IOMMU Specification — `AMD_IOMMU_Spec_48882_v2.62.pdf`
- Register Reference Guide — byte-identical to
  `AMD_SR5690_Register_Reference_Guide_43871.pdf` (already committed)
- Register Programming Requirements — `AMD_SR5690_5670_5650_Register_Programming_Requirements.pdf` (pub 43872)
- Product Databook — `AMD_SR5670_Databook.pdf` (pub 44549)
- Product Errata — `SR56x0_Product_Errata.pdf` (pub 46303)

### AMD SP5100

The AMD SP5100 is a versatile Southbridge designed to complement AMD's server
Northbridges, integrating essential I/O, communication, and other features
for advanced server platforms into a single device.
([TheRetroWeb chip 5699](https://theretroweb.com/chips/5699))

Official source code and documentation:

- [CIMx Source Code](https://review.coreboot.org/c/coreboot/+/560) (coreboot Gerrit change 560)
- BIOS Developer's Guide — `AMD_SP5100_BIOS_Developers_Guide.pdf` (pub 44415)
- Register Reference Guide — byte-identical to
  `AMD_SP5100_Register_Reference_Guide_44413.pdf` (already committed)
- Register Programming Requirements — `AMD_SP5100_Register_Programming_Requirements.pdf` (pub 44414)
- Product Databook — `AMD_SP5100_Databook.pdf` (pub 44409)
- Product Errata — `SP5100_Product_Errata.pdf` (pub 46836)

Part numbers:

- AMD 218-0660013
- AMD 218-0660024
- AMD 218-0660026

### Winbond W83667HG-A

The Winbond W83667HG-A is a member of Nuvoton's LPC Super I/O product line
for desktop PCs.

Official documentation:

- Data Book — `W83667hg-a-datasheet-v1-2.pdf` (this fills the gap recorded in
  [`datasheets/README.md`](datasheets/README.md), which previously found the
  full datasheet only behind NDA/registration walls)

### Nuvoton W83795G

The Nuvoton W83795G/ADG can be used to monitor several critical hardware
parameters of a system; including power supply voltages, fan speeds, and
temperatures.

Official documentation:

- Product Data Sheet — `Nuvoton_W83795G_W83795ADG_Datasheet_V1.43.pdf`

## Kill-a-Watt power draw

User Sbrudenell performed some power draw tests of the KCMA-D8 in various
configurations. The following setup was used:

- Firmware: coreboot-15h 2026.05.04-v4.11-5d336ff7176
- Power was measured using a kill-a-watt in "watts" mode
- PSU: Supermicro PWS-351-1H (350W 1U 80 Plus Gold)
- DIMMs: M386B4G70DM0-YK04 (32GB 1600MHz ECC LRDIMM)
- CPU: 4365 EE
- No case/CPU fans (an external box fan was used for cooling)
- No PCIe or USB peripherals, except PIKE2008 as noted
- An ASMB4 module using OEM firmware was used
- DIMMs distributed evenly across memory channels
- Host booted to alpine linux liveusb (kernel 6.18.35)
- Default cpufreq driver and governor `acpi-cpufreq` and `schedutil` were used
- k10temp measured CPU temperature(s) at 25-30C at idle. After 10 minutes
  stress, they measured 40-45C
- CPU was stressed using `stress-ng --matrix 0`, and measured at different
  amounts of time since being idle
- The fam15_power reading in all cases was 15.47W per CPU at idle, and
  ~40.09W per CPU under stress
- **With host power off (but ASMB4 online), the kill-a-watt read 4W in all
  cases** — i.e. the AST2050 BMC module idles the board at ~4 W
- The PIKE2008 module was used, but no drives or backplanes were connected

| CPUs | DIMMs | PIKE2008 | Idle (W) | CPU Stress 10s (W) | CPU Stress 10m (W) |
|------|-------|----------|----------|--------------------|--------------------|
| 1 | 2 | N | 39 | 71 | ? |
| 2 | 2 | N | 61 | 125 | ? |
| 2 | 4 | N | 66 | 130 | ? |
| 2 | 8 | N | 72 | 138 | 142 |
| 2 | 8 | Y | 79 | 145 | 148 |

## Board view / schematics

Board views are available for the KCMA-D8; the files can be opened with
[OpenBoardView](https://openboardview.org/):

- [Asus KCMA-D8 1.02 Schematics.zip](https://15h.org/index.php/File:Asus_KCMA-D8_1.02_Schematics.zip)
  (wiki file page; not a PDF, so not part of the in-repo PDF mirror — see
  `datasheets/15H-ORG-MIRROR.md`)

## References (as cited on the wiki page)

1. AST2050 text-mode VGA in coreboot (Raptor Engineering):
   <https://review.coreboot.org/c/coreboot/+/11937>
2. Raptor Engineering OpenBMC port status:
   <https://www.raptorengineering.com/coreboot/kgpe-d16-bmc-port-status.php>
3. AMD SR5670 (TheRetroWeb): <https://theretroweb.com/chips/5697>
4. AMD SP5100 (TheRetroWeb): <https://theretroweb.com/chips/5699>
