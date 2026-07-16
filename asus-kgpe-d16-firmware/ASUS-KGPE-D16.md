# ASUS KGPE-D16 — board reference (15h.org mirror)

The **ASUS KGPE-D16** is this directory's board: the dual Socket-G34 AMD
Opteron server/workstation motherboard whose **Aspeed AST2050 BMC (on the
removable ASMB4/ASMB5 module, BMC_FW1 slot)** is the target of this
repository's open-firmware work (see
[`RAPTOR-PORTING-GUIDE.md`](RAPTOR-PORTING-GUIDE.md) and
[`RAPTOR_AST2050_SUMMARY.md`](RAPTOR_AST2050_SUMMARY.md)).

> **Source / provenance.** This document mirrors the complete content of the
> 15h.org wiki page **[ASUS KGPE-D16](https://15h.org/index.php/ASUS_KGPE-D16)**
> (permanent link: [`oldid=2924`](https://15h.org/index.php?title=ASUS_KGPE-D16&oldid=2924),
> retrieved 2026-07-16). 15h.org content is licensed **CC BY-SA 4.0**; this
> file is therefore CC BY-SA 4.0 (an exception to the repository's default
> Apache-2.0). Every PDF the page links is committed in
> [`datasheets/`](datasheets/) — see
> [`datasheets/15H-ORG-MIRROR.md`](datasheets/15H-ORG-MIRROR.md) for the
> link-by-link mapping. The sibling-board page is mirrored in
> [`ASUS-KCMA-D8.md`](ASUS-KCMA-D8.md).

---

## Introduction

The ASUS KGPE-D16, commonly referred to as the **D16**, is a dual-socket
server/workstation motherboard released by ASUS on 7 April 2010 (ref 1), for
use with Socket G34 Opteron processors. Originally sold as a standalone board
in a mostly-standard SSI EEB form factor, and intended for both desktop and
rack-mounted uses, the KGPE-D16 is popular among enthusiasts as a relatively
versatile and workstation-friendly G34 platform.

Ports of coreboot and OpenBMC to the D16 were initially developed by **Raptor
Engineering** between 2015 and 2017. Among major coreboot versions, it was
first supported in coreboot 4.2 in October 2015, and last supported in
coreboot 4.11 in November 2019. The port was never completed and was removed
in coreboot 4.12 due to lack of maintenance. Between 2021 and 2022, after
seeking funding for such an effort for several years, **3mdeb** developed an
out-of-tree fork of coreboot 4.15 for the board under their Dasharo brand.
The effort to complete and re-upstream the Raptor port was unsuccessful and
officially abandoned in August 2025 (ref 2).

An independent port of coreboot to the D16, using AMD's open source AGESA and
CIMx codebases, was released in October 2025 by 15h.org. It is currently the
most complete and only actively developed port of coreboot for the KGPE-D16.

## Overview / specifications (infobox)

| Field | Value |
|-------|-------|
| Introduced | 2010 |
| Manufacturer | ASUS |
| Socket | 2x G34 |
| Northbridge | AMD SR5690 |
| Southbridge | AMD SP5100 |
| Super I/O | Winbond W83667HG-A |
| BMC | ASPEED AST2050 |
| BMC Flash Location | Removable Module |
| Memory | 16 slots (8 channels) DDR3-1600 ECC UDIMM/RDIMM/LRDIMM, up to 512GB on coreboot |
| BIOS Flash | 2 MiB socketed DIP-8 (W25Q16V) |
| Form Factor | SSI EEB |
| Power Inputs | 2x 8-pin EPS |
| Graphics Adapter | AST2050 Integrated VGA |
| Network Interface | 2x Intel 82574L Gigabit |
| Storage Controller | SP5100's SATA2 (3.0 Gbps), no SAS unless PIKE2008 installed |
| USB Controller | SP5100's onboard USB 2.0 |
| Serial Interface | One SIO-provided RS232, one virtual BMC console port |
| Audio Interface | None (ASUS recommended a PCI sound card) |

Expansion slots:

- PCIe Gen2 x16 (disabled if Slot 2 in use)
- PCIe Gen2 x16 (disables Slot 1 if in use)
- PCIe Gen2 x8 (electrically x4)
- PCIe Gen2 x16 (x8 if Slot 5 in use)
- PCIe Gen2 x16 (electrically x8)
- 32-bit Legacy PCI
- ASUS PIKE2008 Interface

Board photo: [Kgpe-d16.jpeg](https://15h.org/index.php/File:Kgpe-d16.jpeg)

Board manual: [`datasheets/KGPE-D16_Manual.pdf`](datasheets/KGPE-D16_Manual.pdf)
(ASUS pub E8847, 158 pp — linked from the page's References section).

## Open Source Firmware

Open source firmware for the KGPE-D16 is provided by **coreboot-15h**,
utilizing AMD's open source AGESA and CIMx releases for platform
initialization. Git repository: <https://git.15h.org/mrothfuss/coreboot-15h>.

### coreboot-15h — supported board variants

- **KGPE-D16**
- **KGPE-D16/CHN**

### coreboot-15h — releases

Each release ships up to three 2 MB build flavours: *SeaBIOS + uCode +
VGA-OpROMs*, *SeaBIOS + uCode (text-mode)*, and *SeaBIOS (text-mode,
blob-free)*.

| Release | Notes | Downloads (2 MB tarballs) |
|---------|-------|---------------------------|
| 2026.05.04-v4.11-5d336ff7176 | Improved power efficiency; improved SATA performance; improved thermal management; enabled PCIe ASPM support; enabled the Power LED; enabled TPM support (TPM 1.2 and 2.0 supported, TPM 2.0 enabled by default, TPM measured boot supported) | [ucode+ast2050-oprom+vga-oproms](https://15h.org/images/3/34/Coreboot-15h_2026.05.04-v4.11-5d336ff7176_asus_kgpe-d16_seabios_ucode_ast2050-oprom_vga-oproms_2mb.tar.gz) · [ucode, no oproms](https://15h.org/images/7/72/Coreboot-15h_2026.05.04-v4.11-5d336ff7176_asus_kgpe-d16_seabios_ucode_no-oproms_2mb.tar.gz) · [blob-free](https://15h.org/images/9/9b/Coreboot-15h_2026.05.04-v4.11-5d336ff7176_asus_kgpe-d16_seabios_no-ucode_no-oproms_2mb.tar.gz) |
| 2025.12.17-v4.11-582d6f37158 | Fixed support for the BMC module | [ucode+ast2050-oprom+vga-oproms](https://15h.org/images/7/7b/Coreboot-15h_2025.12.17-v4.11-582d6f37158_asus_kgpe-d16_seabios_ucode_ast2050-oprom_vga-oproms_2mb.tar.gz) · [ucode, no oproms](https://15h.org/images/4/4e/Coreboot-15h_2025.12.17-v4.11-582d6f37158_asus_kgpe-d16_seabios_ucode_no-oproms_2mb.tar.gz) · [blob-free](https://15h.org/images/d/d9/Coreboot-15h_2025.12.17-v4.11-582d6f37158_asus_kgpe-d16_seabios_no-ucode_no-oproms_2mb.tar.gz) |
| 2025.12.08-v4.11-4bb1cd46931 | Added x16 support for PCIe Slot 4 (switches to x16 if PCIe 5 empty); enabled COM2; fixed COM1/COM2 ACPI entries (improves OS detection of COM1/COM2 ports) | [ucode+ast2050-oprom+vga-oproms](https://15h.org/images/6/65/Coreboot-15h_2025.12.08-v4.11-4bb1cd46931_asus_kgpe-d16_seabios_ucode_ast2050-oprom_vga-oproms_2mb.tar.gz) · [ucode, no oproms](https://15h.org/images/5/54/Coreboot-15h_2025.12.08-v4.11-4bb1cd46931_asus_kgpe-d16_seabios_ucode_no-oproms_2mb.tar.gz) · [blob-free](https://15h.org/images/0/0c/Coreboot-15h_2025.12.08-v4.11-4bb1cd46931_asus_kgpe-d16_seabios_no-ucode_no-oproms_2mb.tar.gz) |
| 2025.11.09-v4.11-6f1fd5cf220 | Optimized HyperTransport speed and deemphasis; optimized RAM power saving; optimized RAM ECC scrub rates; setup thermal throttling; enabled thermal shutdown | [ucode+ast2050-oprom+vga-oproms](https://15h.org/images/9/9c/Coreboot-15h_2025.11.09-v4.11-6f1fd5cf220_asus_kgpe-d16_seabios_ucode_ast2050-oprom_vga-oproms_2mb.tar.gz) · [ucode, no oproms](https://15h.org/images/8/86/Coreboot-15h_2025.11.09-v4.11-6f1fd5cf220_asus_kgpe-d16_seabios_ucode_no-oproms_2mb.tar.gz) · [blob-free](https://15h.org/images/4/4c/Coreboot-15h_2025.11.09-v4.11-6f1fd5cf220_asus_kgpe-d16_seabios_no-ucode_no-oproms_2mb.tar.gz) |
| 2025.10.31-v4.11-c71dd7896fe | Enabled the IOMMU; enabled the HPET; added coreinfo and memtest | [ucode+ast2050-oprom+vga-oproms](https://15h.org/images/0/0b/Coreboot-15h_2025.10.31-v4.11-c71dd7896fe_asus_kgpe-d16_seabios_ucode_ast2050-oprom_vga-oproms_2mb.tar.gz) · [ucode, no oproms](https://15h.org/images/f/f9/Coreboot-15h_2025.10.31-v4.11-c71dd7896fe_asus_kgpe-d16_seabios_ucode_no-oproms_2mb.tar.gz) · [blob-free](https://15h.org/images/2/22/Coreboot-15h_2025.10.31-v4.11-c71dd7896fe_asus_kgpe-d16_seabios_no-ucode_no-oproms_2mb.tar.gz) |
| 2025.10.11-v4.11-63a34806baf | Added support for microcode removal; created configs with blobs removed | [ucode+ast2050-oprom+vga-oproms](https://15h.org/images/1/16/Coreboot-15h_2025.10.11-v4.11-63a34806baf_asus_kgpe-d16_seabios_ucode_ast2050-oprom_vga-oproms_2mb.tar.gz) · [ucode, no oproms](https://15h.org/images/2/27/Coreboot-15h_2025.10.11-v4.11-63a34806baf_asus_kgpe-d16_seabios_ucode_no-oproms_2mb.tar.gz) · [blob-free](https://15h.org/images/8/89/Coreboot-15h_2025.10.11-v4.11-63a34806baf_asus_kgpe-d16_seabios_no-ucode_no-oproms_2mb.tar.gz) |
| 2025.10.10-v4.11-a99acc20d4a | Initial v4.11 AGESA release: robust support for all DIMM slots (up to 32GB RDIMMs, up to 64GB LRDIMMs), up to 4 PCIe cards supported, native fan control, latest microcode, IOMMU disabled | [ucode+ast2050-oprom+vga-oproms](https://15h.org/images/6/6c/Coreboot-15h_2025.10.10-v4.11-a99acc20d4a_asus_kgpe-d16_seabios_ucode_ast2050-oprom_vga-oproms_2mb.tar.gz) |

### Display Output

Jumper diagram: [KGPE-D16 VGA Jumper.png](https://15h.org/index.php/File:KGPE-D16_VGA_Jumper.png)

The mainboard **VGA_SW1** jumper determines whether the onboard VGA (AST2050)
or a PCIe GPU will be used as the bootup display. Set VGA_SW1 to "Enable" to
use the onboard VGA. Set VGA_SW1 to "Disable" to use a PCIe GPU. Once your OS
has booted, drivers for any GPU of your choice can be used to setup a
display. For blob-free operations, it is recommended to use the onboard VGA
in textmode for the bootup display but then switch to a FOSS driver (i.e.
amdgpu) for the user interface.

#### Onboard VGA Output

The onboard VGA, AST2050, can be setup with a closed-source VGABIOS (full VGA
support) or with an open-source coreboot driver (textmode VGA support). A
compatible display, generally an old VGA monitor, will be required to use the
open-source driver. The closed-source VGABIOS is only included in
coreboot-15h release ROMs with the "VGA-OpROMs" tag.

#### PCIe GPU Output

To use a PCIe GPU as the bootup display, PCIe Option ROMs must be executed by
SeaBIOS. This is enabled in 15h.org release ROMs with the "VGA-OpROMs" tag.
The relevant coreboot-15h menuconfig option for SeaBIOS is "Payload > Execute
PCIe Option ROMs". The "VGA Only" option is the recommended setting when
using a PCIe GPU as the bootup display.

### Fan Output

Jumper diagram: [KGPE-D16 Fan Jumper.png](https://15h.org/index.php/File:KGPE-D16_Fan_Jumper.png)

The coreboot-15h release ROMs for KGPE-D16 are configured to adjust fan
speeds based on temperatures measured at the CPUs and the Northbridge. The
KGPE-D16 has two fan zones: one for CPU fans (**CPUFAN_SEL1**) and one for
chassis fans (**CHAFAN_SEL1**). These can be assigned to either 4-pin (PWM
regulated) or 3-pin (voltage regulated) fan control outputs. The 4-pin (PWM
regulation) mode offers better control over fan speeds and is the recommended
setting for both fan zones. It is important to not use a 4-pin fan in a zone
configured for 3-pin control; the fan will receive both voltage regulation
and PWM regulation, causing irregular fan speeds. For quiet 3-pin chassis
fans, it is recommended to leave the CHAFAN_SEL1 set to 4-pin (PWM
regulation) mode. This will let the 3-pin chassis fans operate at 100% speed
regardless of thermal readings.

### Missing features

- SeaBIOS does not respond to keyboards behind a USB hub.
- Hibernation and Suspend/Resume are unsupported.
- Opteron 6100 series CPUs are unsupported.
- ASUS MIO audio cards are untested.

### Flashing

To switch from the stock firmware to coreboot, **external flashing** is
required. The DIP-8 flash chip is located at the bottom right corner of the
board (labeled BIOS in the motherboard diagram). A 3.3V CH341a programmer can
be used to flash coreboot onto the KGPE-D16. When switching to coreboot-15h
from the OEM BIOS or coreboot, clearing the CMOS is required.

**Clearing the CMOS:**

1. Turn off the computer, disconnect the power cord and any powered
   peripherals (monitors, USB devices, etc)
2. Move the CLRTC1 jumper (located under PCIe Slot 2) to positions 2-3
3. Wait 20 seconds
4. Restore the CLRTC1 jumper to positions 1-2
5. Connect the power cord and turn on the computer

## Deployed systems

15h.org community systems: [Qubesotron](https://15h.org/index.php/Qubesotron)
(which hosts 15h.org itself), EmCAST, Atlas, Orion, Unc, Ganoo, RAD01, RAD03.

Outside of the 15h.org community, it is known that, at least as of 2022, the
[Free Software Foundation](https://fsf.org) uses KGPE-D16s with 6200-series
Opterons
[for their servers](https://www.fsf.org/blogs/sysadmin/closing-in-on-fully-free-bioses-with-the-fsf-tech-team).

## Motherboard diagrams

Hosted on the wiki (CC BY-SA 4.0):

- [KGPE-D16 Diagram.png](https://15h.org/index.php/File:KGPE-D16_Diagram.png)
- [KGPE-D16 BlockDiagram.png](https://15h.org/index.php/File:KGPE-D16_BlockDiagram.png)
- [KGPE-D16-DIMM-Diagram.png](https://15h.org/index.php/File:KGPE-D16-DIMM-Diagram.png)
- [KGPE-D16 DDR3 Setting.png](https://15h.org/index.php/File:KGPE-D16_DDR3_Setting.png)
- [KGPE-D16 VGA Jumper.png](https://15h.org/index.php/File:KGPE-D16_VGA_Jumper.png)
- [KGPE-D16 Fan Jumper.png](https://15h.org/index.php/File:KGPE-D16_Fan_Jumper.png)
- [KGPE-D16 PCIE Jumpers.png](https://15h.org/index.php/File:KGPE-D16_PCIE_Jumpers.png)

**There is an undocumented 9-pin VGA header next to the rear-IO VGA port. The
pins are shared between this header and the rear-IO VGA port.** (Relevant to
this repo's AST2050 VGA/video-capture work — see
[`HARDWARE-ACCESS.md`](HARDWARE-ACCESS.md).)

## Motherboard components

### Socket G34

G34 was launched on 29 March 2010. It supports fam10h and fam15h Opteron
CPUs (ref 3). **All G34 Opteron CPUs are dual node processors with two NUMA
nodes.** CPU coolers: the socket pinout diagram is on Wikimedia Commons
([Socket G34 pinmap](https://15h.org/index.php/File:Socket_G34_pinmap.svg)).

#### AMD Opteron 6100 Series

Processors in the AMD Opteron 6100 Series were designed with the **K10**
microarchitecture and are compatible with the G34 socket.

Official source code and documentation (PDFs mirrored in
[`datasheets/`](datasheets/)):

- [AGESA Source Code](https://review.coreboot.org/c/coreboot/+/95) (coreboot Gerrit change 95)
- AGESA Interface Specification — `44065_Arch2008.pdf`
- BIOS and Kernel Developer's Guide (fam10h) — `AMD_Family_10h_BKDG_31116.pdf`
- Product Data Sheet — `AMD_Family_10h_Opteron_PDS_40036.pdf`
- Power and Thermal Data Sheet — `AMD_Family_10h_Power_Thermal_Data_Sheet_43374.pdf`
  (the page's direct link is stale on the wiki; see the mirror map)

Reverse engineering and analysis:

- Reverse Engineering x86 Processor Microcode (Koppe et al., USENIX Security
  2017) — `Sec17_Koppe_Reverse_Engineering_x86_Processor_Microcode.pdf`
- Security Analysis of x86 Processor Microcode (Chen & Ahn, 2014) —
  `2014_Chen_Ahn_Security_Analysis_of_x86_Processor_Microcode.pdf`

#### AMD Opteron 6200 and 6300 Series

Processors in the AMD Opteron 6200 and 6300 Series were designed with the
**Bulldozer** (6200 series) and **Piledriver** (6300 series)
microarchitectures and are compatible with the G34 socket.

Official source code and documentation:

- [AGESA Source Code](https://review.coreboot.org/c/coreboot/+/554) (coreboot Gerrit change 554)
- AGESA Interface Specification — `44065_Arch2008.pdf`
- BIOS and Kernel Developer's Guide — `42301_15h_Mod_00h-0Fh_BKDG.pdf`
- Product Data Sheet — `49687_15h_Mod_00h-0Fh_Opteron_PDS.pdf`
- Software Optimization Guide — `47414_15h_sw_opt_guide.pdf`

Reverse engineering and analysis:

- Security Analysis of x86 Processor Microcode (Chen & Ahn, 2014) —
  `2014_Chen_Ahn_Security_Analysis_of_x86_Processor_Microcode.pdf`

### DDR3 memory

The vast majority of UDIMM, RDIMM, and LRDIMM DDR3 modules are expected to
work without issue. So far only one module has been found to be
[incompatible with the AGESA](https://15h.org/index.php/AGESA_15h#Incompatible_DDR3_Modules).
The maximum RAM supported is **256 GB per CPU socket**. RDIMM modules are
recommended for motherboards that support them. The following is an
incomplete list of tested modules (review the deployed systems list for well
tested hardware configurations):

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

**DDR3 voltage jumper**: the KGPE-D16 provides an external method to override
the BIOS DDR3 voltage. BIOS control is configured to select a voltage that
maximizes performance for all DIMM modules attached to a socket. Forcing a
different voltage may cause stability problems. **Use the default jumper
setting (1.5V / BIOS control) when using coreboot-15h.**

### PCIe 2.0 slots

Jumper diagram: [KGPE-D16 PCIE Jumpers.png](https://15h.org/index.php/File:KGPE-D16_PCIE_Jumpers.png)

| Slot | Width | Wired Lanes | Notes |
|------|-------|-------------|-------|
| PCIe1 | x16 | x16 | A special PCIe slot designed for the ASUS MIO audio card. Disabled if PCIe2 is occupied. |
| PCIe2 | x16 | x16 | Disables PCIe1 if occupied. Set motherboard jumper PCIE2_SW1 to positions 2-3 to always enable PCIe2. |
| PCIe3 | x8 | x4 | |
| PCIe4 | x16 | x8 or x16 | Switches to x16 mode if PCIe5 is empty. If motherboard jumper PCIE5_SW1 is set to position 2-3, it will always be in x8 mode. |
| PCIe5 | x16 | x8 | Disables if no card is detected. Set motherboard jumper PCIE5_SW1 to positions 2-3 to always enable PCIe5. |

PCIe bifurcation of slots PCIe2 and PCIe4 in x8+x8 mode is supported.
Bifurcation is a compile-time option that is available under the Motherboard
menuconfig section.

### PIKE slots

The two PIKE slots, PIKE1 and PIKE2, are used together to attach an ASUS PIKE
module to the KGPE-D16. This is required to utilize the 8 onboard SAS ports.
These SAS ports support SAS2 and SATA3, making them faster than the onboard
SATA2 ports provided by the SP5100. Drives attached to these ports are
accessible to the operating system when the PIKE card is configured for IT
Mode, but SeaBIOS will not boot from them. The PIKE2008 card, flashed to IT
Mode, is recommended to utilize these features.

### DIP-8 socket (BIOS flash)

The DIP-8 socket houses the mainboard's BIOS ROM. The following DIP-8 chips
are known to work with coreboot on the KGPE-D16:

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
([coreboot Gerrit change 11937](https://review.coreboot.org/c/coreboot/+/11937),
ref 4). Full VGA output support requires ASPEED's closed source VGABIOS to be
included in the coreboot rom. A rudimentary port of OpenBMC was also
developed by Raptor Engineering
([kgpe-d16-bmc-port-status](https://www.raptorengineering.com/coreboot/kgpe-d16-bmc-port-status.php),
ref 5) — the same port analysed throughout this directory.

Official documentation (mirrored in [`datasheets/`](datasheets/)):

- AST2050 Datasheet — the page's copy is byte-identical to
  `AST2050_AST1100_A3_Datasheet_V1.05.pdf` (the A3 Datasheet V1.05 this repo
  already relies on)
- S25FL128P Datasheet — byte-identical to `S25FL128P_Datasheet.pdf`
  (the SPI-NOR flash on the BMC module)

**Remote administration features on the AST2050 are only activated when a
firmware module (ASMB4 or ASMB5) is attached to the KGPE-D16 mainboard
(BMC_FW1 slot).**

### AMD SR5690

The AMD SR5690, also known as RD890S, was released in March 2010 as a
powerful system logic for server and workstation platforms. It offers 46 PCI
Express lanes, with 42 lanes dedicated to external PCIe devices and 4 for the
A-Link Express II interface to AMD's Southbridges like the SP5100 (formerly
SB700S). The chipset boasts the latest technologies, including HyperTransport
3 and PCIe Gen 2, and its highly integrated, thermally efficient design comes
in a compact 29mm x 29mm package.
([TheRetroWeb chip 5696](https://theretroweb.com/chips/5696), ref 6)

Official source code and documentation:

- [CIMx Source Code](https://review.coreboot.org/c/coreboot/+/557) (coreboot Gerrit change 557)
- BIOS Developer's Guide — `AMD_SR5690_5670_5650_BIOS_Developers_Guide.pdf` (pub 43870)
- IOMMU Specification — `AMD_IOMMU_Spec_48882_v2.62.pdf`
- Register Reference Guide — byte-identical to
  `AMD_SR5690_Register_Reference_Guide_43871.pdf` (already committed)
- Register Programming Requirements — `AMD_SR5690_5670_5650_Register_Programming_Requirements.pdf` (pub 43872)
- Product Databook — `AMD_SR5690_Databook.pdf` (pub 43869, rev 2.20)
- Product Errata — `SR56x0_Product_Errata.pdf` (pub 46303)

Part numbers:

- AMD 215-0716022
- AMD 215-0716038
- AMD 215-0716056

### AMD SP5100

The AMD SP5100 is a versatile Southbridge designed to complement AMD's server
Northbridges, integrating essential I/O, communication, and other features
for advanced server platforms into a single device.
([TheRetroWeb chip 5699](https://theretroweb.com/chips/5699), ref 7)

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

- Data Book — `W83667hg-a-datasheet-v1-2.pdf` (fills the gap recorded in
  [`datasheets/README.md`](datasheets/README.md), which previously found the
  full datasheet only behind NDA/registration walls)

### Nuvoton W83795G

The Nuvoton W83795G/ADG can be used to monitor several critical hardware
parameters of a system; including power supply voltages, fan speeds, and
temperatures.

Official documentation:

- Product Data Sheet — `Nuvoton_W83795G_W83795ADG_Datasheet_V1.43.pdf`

**The ASUS thermal sensor cable (10G090101035) can be used to control fan
speeds based on case air temperature readings.**

## Motherboard revisions

Four KGPE-D16 revisions are known: **1.02G, 1.03G, 1.04, and 1.05**. The
differences between the four revisions have not been disclosed. The more
recent boards (1.04 and 1.05) are generally in better condition and are
recommended. Board revisions 1.03G, 1.04, and 1.05 are known to perform
equally well when in similar condition. No community members have tested a
1.02G revision board. The KGPE-D16 can be found rebranded for distribution in
China (**KGPE-D16/CHN**). The CHN variant can also run coreboot like the
other KGPE-D16 variants; there are no known differences.

## Board view / schematics

Board views are available for the KGPE-D16; the files can be opened with
[OpenBoardView](https://openboardview.org/):

- [ASUS_KGPE-D16_Rev_1.04_-_Schematics.zip](https://15h.org/images/f/f0/ASUS_KGPE-D16_Rev_1.04_-_Schematics.zip)
  (not a PDF, so not part of the in-repo PDF mirror — see
  `datasheets/15H-ORG-MIRROR.md`)

## Custom parts and mods

### Northbridge fan

3D-printable bracket designed to work with a Noctua NF-A4x10 fan. If your
motherboard is not in a high-airflow server case, the northbridge fan is
highly recommended. The fan bracket mounts onto the northbridge heatsink by
snapping onto the metal arms that secure the heatsink. The file may need to
be edited to accommodate the exact placement of your 40mm fan cable (the
provided design has a cable hole at the bottom right position).

- [KGPE-D16_Chipsetfan_40mm.stl](https://15h.org/images/8/8a/KGPE-D16_Chipsetfan_40mm.stl)
- [KGPE-D16_Chipsetfan_40mm.blend](https://15h.org/images/9/98/KGPE-D16_Chipsetfan_40mm.blend)

### Chipset thermal paste

Removing the NB/SB heatsinks to reapply the thermal paste can be daunting due
to glue used for the NB heatsink, limited wiggle room, and marginal benefit.
It is generally considered not worth it.

### RAM fan

3D-printable mount designed to work with a Noctua NF-A8 fan. When two of
these fan mounts are attached to a Noctua NF-A8 fan, they will be spaced
correctly to snap onto the KGPE-D16 RAM clips (white). These clips vary
between boards. The included file is designed to work with L-shaped RAM
clips. It will not fit as nicely onto the parallelogram-shaped RAM clips.

- [KGPE-D16_Ramfan_80mm.stl](https://15h.org/images/f/f8/KGPE-D16_Ramfan_80mm.stl)
- [KGPE-D16_Ramfan_80mm.blend](https://15h.org/images/9/9c/KGPE-D16_Ramfan_80mm.blend)

## References (as cited on the wiki page)

The References section also links the board manual —
[`datasheets/KGPE-D16_Manual.pdf`](datasheets/KGPE-D16_Manual.pdf).

1. ASUS releases KGPE-D16 (TechPowerUp, 7 April 2010):
   <https://www.techpowerup.com/119540/asus-releases-kgpe-d16-socket-g34-motherboard-for-12-core-amd-opteron-processors>
2. Dasharo KGPE-D16 effort abandoned (August 2025):
   <https://github.com/Dasharo/dasharo-issues/issues/478>
3. Socket G34 (Wikipedia): <https://en.wikipedia.org/wiki/Socket_G34>
4. AST2050 text-mode VGA in coreboot (Raptor Engineering):
   <https://review.coreboot.org/c/coreboot/+/11937>
5. Raptor Engineering OpenBMC port status:
   <https://www.raptorengineering.com/coreboot/kgpe-d16-bmc-port-status.php>
6. AMD SR5690 (TheRetroWeb): <https://theretroweb.com/chips/5696>
7. AMD SP5100 (TheRetroWeb): <https://theretroweb.com/chips/5699>
