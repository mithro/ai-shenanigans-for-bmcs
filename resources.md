# Legacy Aspeed OpenBMC Porting — Project Resource Summary

**Generated:** 2026-02-10

**Purpose:** Reference document for AI agents (Claude Code and others) working on this project.

---

## 1. Project Goals

The goal is to **reverse engineer existing proprietary BMC firmware** on the **Dell C410x** and **Supermicro X11** hardware platforms to enable replacement with either **OpenBMC** or **u-bmc** (an open source BMC stack written in Go).

### 1.1 The Hard Problem: Pinout Extraction

The critical challenge is **determining the BMC IC pin connections** — which GPIO pins on the Aspeed SoC are wired to which board-level functions (power control, LED indicators, fan tachometers, I2C sensor buses, SPI flash chip selects, UART mux controls, etc.). This mapping is proprietary and undocumented by the board vendors.

**How to extract pinout information:**

- **From existing firmware images:** The proprietary BMC firmware contains device tree blobs (DTBs), GPIO configuration tables, and IPMI sensor definition records (SDRs) that encode the pin-to-function mapping. Extracting and decompiling these from SPI flash dumps reveals the wiring.
- **From live firmware dumps:** Running systems can be probed via the BMC's debug interfaces (UART, JTAG) or through IPMI/web UI to read GPIO states, sensor configurations, and device tree contents from the running kernel.
- **From firmware update packages:** Vendor firmware update files (e.g., Supermicro BMC update `.bin` files, Dell lifecycle controller packages) contain flashable images that can be unpacked with tools like `binwalk` to extract the filesystem, kernel, and device tree.

### 1.2 Enabling Linux/Zephyr on Older Aspeed Parts

The older Aspeed SoCs (particularly the **AST2050** used in the Dell C410x) are **not supported in upstream Linux**. Work is needed to either:

- Port/upstream Linux kernel support for the AST2050 (building on existing AST2400/2500 support from Joel Stanley and the OpenBMC project), or
- Use **Zephyr RTOS** as a lighter-weight alternative for the older, more resource-constrained parts.

This is a prerequisite — without a working OS on the BMC SoC, the open firmware stack has nothing to run on.

---

## 2. Target BMC Replacement Stacks

### 2.1 OpenBMC

OpenBMC is the primary replacement target. It provides a complete Linux-based BMC stack: upstream u-boot + Linux kernel for Aspeed hardware, plus a modern userspace. The proprietary IPMI protocol is replaced by a REST API over HTTPS, and IPMI Serial Over LAN (SOL) is replaced with SSH.

OpenBMC already has production support for AST2400 and AST2500. The project prioritizes upstream kernel support over maintaining forks.

Key upstream references:
- OpenBMC x86 power control: https://github.com/openbmc/x86-power-control
- OpenBMC project: https://github.com/openbmc/openbmc

### 2.2 u-bmc

u-bmc is a lighter-weight alternative written in Go. It runs on a minimal Linux kernel with a Go userspace via u-root, rather than the full OpenBMC Yocto/systemd stack. This may be more practical for older/smaller Aspeed parts like the AST2050.

Key upstream references:
- u-bmc: https://github.com/u-root/u-bmc
- u-root (Go Linux initramfs): https://github.com/u-root/u-root

### 2.3 Decision Criteria

The choice between OpenBMC and u-bmc may differ per target:
- **AST2050 (Dell C410x):** u-bmc or Zephyr may be more practical given limited RAM/flash and lack of upstream Linux support.
- **AST2400/2500 (Supermicro X11):** OpenBMC is the natural choice — upstream kernel support already exists, and the hardware is capable enough for the full stack.

---

## 3. Target Hardware

### 3.1 Aspeed BMC SoC Generations

| Generation | CPU | Target Boards | Upstream Linux | Notes |
|---|---|---|---|---|
| **AST2050** | ARM (older core) | Dell C410x, ASUS KGPE-D16, ASUS P8B-M | **No** — needs porting | Most constrained; first OpenBMC port target |
| **AST2400** | ARM | Supermicro X10, most X11 boards | **Yes** | Primary Supermicro target |
| **AST2500** | 2× ARM Cortex A7 + Cortex M3 | Some X11 boards (e.g., X11SCH-F) | **Yes** | DDR4 1600Mbps, Quad GbE, 16-ch ADC |
| **AST2600** | 2× ARM Cortex A7, 1.2 GHz | Supermicro X12 series | **Yes** | Future target |

### 3.2 BMC Porting Pathway (Aspeed 2050)

From the master planning doc:
1. **Step 1 — ASUS KGPE-D16:** Replicate abandoned port from Raptor Engineering (https://www.raptorengineering.com/coreboot/kgpe-d16-bmc-port-status.php) and update.
2. **Step 2 — Dell C410X**
3. **Step 3 — ASUS P8B-M**

---

## 4. Dell C410x — Hardware Details

The Dell C410x is a **GPU expansion chassis** with an **Aspeed AST2050 BMC** on the middle board (GC-BM3P).

Source: [Dell C410X Documentation](https://docs.google.com/document/d/1BFdn8vOxtryp-q8HkAw_GiRQoxe0PEtjwET4yxvckgg/edit)

### 4.1 Assemblies / Part Numbers

| Assembly | Part Number | Use | Description |
|---|---|---|---|
| GC-IPASS2 | H0NJH | iPass Upper Card | Dell Cloudedge C410x Upper PCI-e Port Card |
| GC-IPASS3 | 5XX39 | iPass Bottom Card | I/O Card Bottom IPASS3 5678 |
| GC-BM3P | M6XXT | **Motherboard / Midplane** | Midplane Controller Card (contains BMC) |
| — | Y53VG | Power Supply | PowerEdge C2100/C410X/C6100/C6145 PSU |
| — | HRMPW | GPU Sled | GPU Sled Enclosure |
| — | 0J1HPX | Generic Sled | Universal Carrier/Sled RTS Enclosure |
| — | JCPM0 | Fan Cage | Cooling Fan Cage Assembly |
| — | 2FMHG | Cooling Fan | Cooling Fan |

### 4.2 BMC

**Aspeed AST2050** — located on the GC-BM3P midplane controller board.

### 4.3 PCIe Switches

4 × **PEX 8696** — 96-Lane, 24-Port PCI Express Gen 2 (5.0 GT/s) Switch, 35×35mm FCBGA from Broadcom/PLX.

Each PEX 8696 has 6 stations of 4 ports each (24 ports total). The PEX 8696 is an **I2C Slave** — its configuration registers can be read/written by an external I2C Master, independently of the PCIe upstream link.

**PEX 8696 I2C Addresses:**

| Part # | PLX Address | GBT Address |
|---|---|---|
| 1 | 0x18 | 0x30 |
| 2 | 0x1A | 0x34 |
| 3 | 0x19 | 0x32 |
| 4 | 0x1B | 0x36 |

**I2C/EEPROM Notes:**
- PLXMon GUI doesn't support I2C, but the command-line tool (PlxCm) and PDE GUI do.
- All tools can access EEPROM in-band over PCIe.
- EEPROM byte address width (1, 2, or 3) is auto-detected if 0x5A is in byte 0. 2-byte addressing is most popular.
- Refer to the PLX SDK FAQ document (freely downloadable PLX PCI SDK) for EEPROM details.

### 4.4 ICs on the Middle Board

| IC | Type | Notes |
|---|---|---|
| **NXP PCA9555** | 16-bit I2C GPIO expander | Address: `010X_XXXb`. Datasheet: https://www.nxp.com/docs/en/data-sheet/PCA9555.pdf. Linux DT binding: https://www.kernel.org/doc/Documentation/devicetree/bindings/gpio/gpio-pca953x.txt |
| **NXP PCA9548A** | 8-channel I2C switch/mux | Used to multiplex I2C buses |
| **ISL6112** | Hot-swap controller | Power sequencing for PCIe slots |
| **4459A** | (Unknown — likely voltage regulator) | — |
| **ATMLH050** | (Unknown — likely EEPROM) | — |
| **ICS0413823** | (Unknown — likely clock generator) | — |

The PCA9555 is critical for understanding GPIO expansion — the BMC likely uses it (via I2C) to control slot power, read presence detect, and drive LEDs. The kernel device tree binding (`gpio-pca953x`) already exists in Linux.

### 4.5 PCIe Routing Modes

The C410x supports three PCIe routing configurations through iPass ports:

| iPass Port | 1:2 mode | 1:4 mode | 1:8 mode |
|---|---|---|---|
| 1 | Slots 1, 15 | Slots 1, 2, 15, 16 | Slots 1-4, 13-16 |
| 2 | Slots 3, 13 | Slots 3, 4, 13, 14 | Disabled |
| 3 | Slots 5, 11 | Slots 5, 6, 11, 12 | Slots 5-12 |
| 4 | Slots 7, 9 | Slots 7, 8, 9, 10 | Disabled |
| 5 | Slots 2, 16 | Disabled | Disabled |
| 6 | Slots 4, 14 | Disabled | Disabled |
| 7 | Slots 6, 12 | Disabled | Disabled |
| 8 | Slots 8, 10 | Disabled | Disabled |

### 4.6 Host-Side PCIe Topology (from lspci on connected host)

The C410x connects to a host system. The PCIe bus hierarchy as seen from the host:

```
Bus 00: Primary host bus
  01.0 Bridge → 01-03
    01:00.0 Bridge → 02-03
      02:08.0 Bridge → 03-03
  02.0 Bridge → 05-05
  1c.0 Bridge → 07-07
  1c.1 Bridge → 08-08
  1c.2 Bridge → 09-09
  1e.0 Bridge → 0a-0a

Bus 80: Secondary host bus
  00.0 Bridge → 81-81
  02.0 Bridge → 82-82
  03.0 Bridge → 83-88
    83:00.0 NVIDIA NF200 PCIe 2.0 switch (upstream port)
      84:00.0-84:03.0 NF200 downstream ports → buses 85-88 (GPU slots)
```

The `83:00.0` NF200 bridge is the switch that fans out to the 4 GPU slots in the sled. Each downstream port (84:00.0-84:03.0) connects to one GPU slot.

### 4.7 DMI/SMBIOS Slot Information

From `dmidecode`:
- **Slot 1:** x4 PCIe Gen2 x8, Available
- **Slot 2:** x16 PCIe Gen2, In Use (bus 05:00.0)
- **Slot 5:** 32-bit PCI, Available
- **Slot 7:** x16 PCIe Gen2, In Use (bus 83:00.0 — NF200 switch)

---

## 5. Supermicro X11 — Hardware Details

### 5.1 Board Variants and Porting Pathway

Source: [Tim's Coreboot/OpenBMC Plan](https://docs.google.com/document/d/1-y8QPPGeA4QWTYFHwW2moe4WQnzgKxIVZEb10eMVHMo/edit)

The project expects to focus on **OpenBMC and LinuxBoot/NERF initially** rather than Coreboot.

Coreboot is currently already supported on:
- **X10SLM+-F**
- **X11SSH-TF**
- **X11SSH-LN4F**

**Incremental Porting Strategy (one variable at a time):**

| Step | Motherboard | What's New | What's Existing |
|---|---|---|---|
| 1 | **X11SSH-F** | Non-boot peripherals only | Socket, Southbridge, BMC, Form Factor |
| 2 | **X11SCH-F** | Southbridge (C246), BMC (AST2500) | Socket, Peripherals, Form Factor |
| 3a | **X11SSH-GF-1585** | Socket (embedded processor) | BMC, Southbridge, Form Factor |
| 3b | **X11SPM-TF** | Socket (LGA3647), Southbridge (C622) | BMC, Form Factor |
| 4 | **X11SP** series | Form factor (ATX) | Socket, Southbridge, BMC |
| 5 | **X11DP** series | Dual socket | Socket, Form Factor, BMC, Southbridge |
| 6a | **X12SPM** | Next-gen platform | Form Factor, Southbridge |
| 6b | **X11QP** | Quad socket | Socket, Form Factor, BMC |

**Alternative Pathway (X10 series):**
1. X10SLM+-F / X10SLM+-LN4F — LGA1150 / C224 / AST2400 / Micro-ATX (already supported)
2. X10SSL-F — LGA1150 / C222 / AST2400 (only southbridge change: C224→C222)
3. X10S???-F — LGA2011 variant
4. X10D??-F — Dual LGA2011 / C612 / AST2400
5. X10Q??-F — Quad LGA2011 / C602J / AST2400

**Another Pathway (ASUS/LGA1155):**
- ASUS P8C WS — LGA1155 + C216 + ATX
- Related to ASUS P8B-M — LGA1155 + C204 + micro-ATX
- Comparable to Supermicro X9SAE(-V) — LGA1155 + C216 (but lacks BMC)

### 5.2 Target Board Inventory

From the [Remote Control Board](https://docs.google.com/document/d/1LhrtVZL2c0Hm8FCm_akZ0Hvk2fXt6JLkTgUt4vKUrPY/edit) design doc — actual hardware in Tim's inventory:

| Model | Southbridge | Socket | Processor | Memory |
|---|---|---|---|---|
| X10SLM+-LN4F (×2) | C224 | LGA1150 | E3-1240 V3 | DDR3 UDIMM |
| **X11SSH-F** (×2) | C236 | LGA1151(v1) | E3-1260L V5 | DDR4 UDIMM |
| X11SSH-LN4F | C236 | LGA1151(v1) | E3-1260L V5 | DDR4 UDIMM |
| X11SSZ-F | C236 | LGA1151(v1) | E3-1260L V5 | DDR4 UDIMM |
| X11SSM-F | C236 | LGA1151(v1) | E3-1260L V5 | DDR4 UDIMM |
| X11SSL-F | C232 | — | — | DDR4 UDIMM |
| X11SCZ-F | C246 | LGA1151(v2) | E-2124 | DDR4 UDIMM |
| **X11SPM-F** | C621 | LGA3647 | Bronze 3106 | DDR4 RDIMM |
| X11SPM-TF | C622 | LGA3647 | — | — |
| X11SPI-TF | C622 | LGA3647 | — | — |
| X11SRM-F | C422 | LGA-2066 | — | — |
| X12SPM-TF | C621A | LGA4189 | — | — |
| X10DGO-T | C612 | LGA2011-v3 | — | — |
| X10QBI | C602J | LGA2011-v1 | — | — |
| X11DSC+ | C621 | LGA3647 | — | — |

### 5.3 BMC ↔ Southbridge Thermal Interface

From the PCIe trees doc — the Intel C620 series southbridge provides BMC thermal reporting:

- The PCH reports its temperature to the BMC over **SMLink1** or **eSPI OOB Channel**.
- BMC issues SMBus read or eSPI OOB request; receives single byte (1-254 = temperature in °C, 0xFF or 0x00 = sensor not enabled / boot phase).
- After sensor enable: 0x01-0x7F = valid temperature (0-127°C). 0x80-0xFE = error (should have shut down before reaching 128°C via catastrophic trip point).
- The PCH does **not** monitor temperature itself; the BMC is responsible for thermal management.

### 5.4 BMC as PCI Device on Supermicro Boards

From the PCIe tree dumps, the BMC appears as a PCI device via an AST1150 PCI-to-PCI bridge:

**On big-storage server (C610/X99 chipset):**
```
00:1c.7 PCI bridge: Intel C610/X99 PCI Express Root Port #8
  └─ 1b:00.0 PCI bridge: ASPEED AST1150 PCI-to-PCI Bridge (rev 03)
       └─ 1c:00.0 VGA: ASPEED Graphics Family (rev 30)
```

**On GPU server (C620 chipset):**
```
00:1d.1 root_port, device present, speed 5GT/s, width x1
  └─ 02:00.0 pci_bridge
       └─ 03:00.0 PCI, ASPEED Technology, Inc. ASPEED Graphics Family (2000)
```

The BMC's VGA controller is visible as a PCI device on the host side. The AST1150 bridge is on **PCH Root Port #8** (bus 00:1c.7) for the big-storage config.

### 5.5 I2C Bus Scan from Running Supermicro System

From the PCIe trees doc — actual `i2cdetect` output from the big-storage server:

**I2C bus 0:**
```
     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
00:                         08 -- -- -- -- -- -- --
10: 10 -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
20: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
30: -- -- -- -- -- -- -- -- 38 39 -- -- -- -- -- --
40: -- -- -- -- 44 -- -- -- -- -- -- -- -- -- -- --
50: 50 -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
60: -- -- -- -- -- -- -- -- -- -- -- -- 6c -- -- 6f
70: -- 71 -- -- -- 75 -- 77
```

Devices at: **0x08, 0x10, 0x38, 0x39, 0x44, 0x50, 0x6c, 0x6f, 0x71, 0x75, 0x77**

**I2C bus 1:**
```
     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
00:                         -- -- -- -- -- -- -- --
10: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
20: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
30: -- -- -- -- -- -- -- 37 -- -- -- -- -- -- -- --
40: -- -- -- -- -- -- -- -- -- 49 -- -- -- -- -- --
50: 50 -- -- -- -- -- -- -- -- 59 -- -- -- -- -- --
60: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
70: -- -- -- -- -- -- -- --
```

Devices at: **0x37, 0x49, 0x50, 0x59**

These addresses need to be mapped to specific ICs (temperature sensors, EEPROMs, I2C muxes, etc.) as part of the pinout extraction work. Common address assignments on server boards:
- 0x08-0x0F: IPMI/BMC controllers
- 0x10: Clock generator or voltage regulator
- 0x38-0x39: PCF8574 I2C GPIO expanders
- 0x44: Temperature sensor (e.g., TMP175/LM75 variant)
- 0x49: Temperature sensor
- 0x50, 0x59: SPD EEPROMs (DIMM slots)
- 0x6c-0x6f: Voltage regulators or LED controllers
- 0x71, 0x75, 0x77: I2C mux/switch (e.g., PCA9548)

### 5.6 Supermicro PCIe Topology (GPU Server)

The GPU server uses PLX PCIe switches extensively. Key topology:

**CPU1 Slots:**
- **SLOT2** (x8): PMC PM8533 PFX 48xG3 switch → 8× NVMe endpoints (Intel DC SSD, Union Memory, Phison, etc.)
- **SLOT6** (x16): PLX 9765 switch → 2× Tesla V100 SXM2 16GB GPUs + PLX 8733 sub-switch
- **SLOT5** (x16): PLX 9765 switch → 2× Tesla V100 + ASMedia ASM2824 → 4× NVMe drives
- **PCH Root Port #1** (x4): Broadcom SAS3008 HBA
- **PCH Root Port #8** (x1): ASPEED AST1150 → ASPEED Graphics (BMC)

**CPU2 Slots:**
- **Root Port 0** (x4): Intel X540 10GbE (×2)
- **SLOT1** (x8): NVIDIA T1000 8GB
- **SLOT4** (x16): PLX 9765 → ASM2824 (4× NVMe) + 2× Tesla V100 GPUs
- **SLOT3** (x16): PLX 9765 → 2× Tesla V100 + PLX 8733 sub-switch

Total: 8× Tesla V100 SXM2 16GB, 1× T1000, 16+ NVMe, SAS HBA, 10GbE.

### 5.7 Supermicro Southbridge/PCH Details

**C610/X99 series (big-storage, X10 boards):**
- 3× MS SMBus controllers (00:11.1-11.3)
- 1× SMBus Controller (00:1f.3)
- xHCI USB (00:14.0), 2× EHCI USB
- MEI Controllers (00:16.0, 00:16.1)
- LPC Controller / ISA bridge (00:1f.0)
- 8× PCIe Root Ports (Device 28, Functions 0-7)

**C620 series (X11SP boards):**
- BMC thermal reporting over SMLink1 or eSPI OOB
- Up to 8× PCIe Root Ports, each x1 lane at 5 Gb/s (Gen2)

---

## 6. Firmware Reverse Engineering Approach

### 6.1 Extracting Firmware Images

**From SPI flash (physical access):**
- Use external SPI programmers (Dediprog EM100Pro, Bus Pirate, Raspberry Pi with flashrom) to read BMC SPI flash directly.
- The Supermicro X11 boards have **separate SPI flash chips** for the southbridge (BIOS/Coreboot) and the BMC (OpenBMC).

**From vendor update packages:**
- Supermicro publishes BMC firmware update binaries on their support site.
- Dell publishes lifecycle controller / BMC firmware update packages.
- Unpack with `binwalk` to extract kernel, rootfs, and device tree.

**From running systems:**
- BMC debug UART (usually accessible via board header pins)
- JTAG access to the Aspeed SoC
- Network access via IPMI/web UI to read sensor records, GPIO states
- `/proc/device-tree/` and `/sys/class/gpio/` from a BMC shell

### 6.2 Extracting Pinout from Firmware

Once a firmware image is obtained, the pinout can be recovered from:

1. **Device Tree Blob (DTB):** Decompile with `dtc -I dtb -O dts`. Contains GPIO pin assignments, I2C bus configs, SPI chip selects, peripheral connections.
2. **IPMI Sensor Data Records (SDRs):** Maps sensor types to hardware addresses — reveals which I2C addresses host which sensors.
3. **GPIO configuration in kernel/bootloader:** Vendor kernel DTS and u-boot board config files define the complete pin mapping.
4. **Userspace config files:** Proprietary BMC userspace often has XML/JSON/custom config files mapping GPIO pins to functions (power button, reset, LEDs, etc.).

### 6.3 SPI Flash Layout

Diagram of SPI flash connections between southbridge and BMC on Supermicro X11:
- [SPI Layout / Southbridge & BMC - Supermicro SSG-6049P-E1CR60L](https://docs.google.com/drawings/d/1F6xLTsJsBC6fASu0AkINkimx4Ae_9cUXEpqng8eEoPI/edit)

### 6.4 SPI Tools and Emulators

| Tool | Purpose | URL |
|---|---|---|
| **flashrom** | SPI flash read/write/verify | https://flashrom.org — Also see [Flashrom @ Chromium.org](https://docs.google.com/document/d/1H8zZ3aEMZmfO4ZEsWbHooUdGOgxy5LTPJ19YbaDsxdQ/edit) |
| **qspimux** | SPI mux for flash interception | https://github.com/felixheld/qspimux |
| **spisolator2** | SPI flash isolation/interception | https://github.com/lynxis/spisolator2 |
| **spisolator** | SPI flash isolation | https://github.com/urjaman/spisolator |
| **SPISpy** | SPI flash emulation | https://github.com/osresearch/spispy |
| **em100 (Dediprog)** | Professional SPI flash emulator | https://github.com/YADRO-KNS/em100 / https://www.dediprog.com/product/EM100Pro-G3 |
| **binwalk** | Firmware image analysis/extraction | https://github.com/ReFirmLabs/binwalk |
| **LPC/SPI Analysis Tool** | Analysis | https://www.osti.gov/servlets/purl/1124403 |

---

## 7. CI/Testing Infrastructure

### 7.1 Remote Control Board

Source: [Supermicro Motherboard "Remote Control board"](https://docs.google.com/document/d/1LhrtVZL2c0Hm8FCm_akZ0Hvk2fXt6JLkTgUt4vKUrPY/edit)

A planned custom board enables remote CI testing. Goals: flash Coreboot/OpenBMC images over SPI and validate Linux boots.

**Connections:**
- **SPI bus** — for BIOS/BMC flash programming
- **Front panel header** — power/reset control
- **RPi Zero W** (optional) — USB OTG for keyboard/mouse/storage emulation

**Test matrix:** Intel southbridge parts C222, C224, C232, C236, C246, C422, C602J, C612, C621, C621A, C622 and CPU sockets LGA1150, LGA1151 (v1/v2), LGA2011 (v1/v3), LGA2066, LGA3647, LGA4189.

Related: **3mdeb RTE** (Remote Test Environment): https://github.com/3mdeb/rte-schematics

### 7.2 Coreboot / Dasharo

- https://doc.coreboot.org/mainboard/supermicro/x11-lga1151-series/x11ssh-tf/x11ssh-tf.html
- https://docs.dasharo.com/variants/supermicro_x11_lga1151_series/overview/
- https://doc.coreboot.org/mainboard/supermicro/x10slm-f.html
- Dasharo docs PR: https://github.com/Dasharo/docs/pull/488

---

## 8. PCIe BAR / Memory Mapping Notes

The PCIe trees doc contains extensive notes on BAR assignment issues relevant to BMC development:

- With many PCIe devices (GPUs, NVMe, switches), 32-bit BAR space can be exhausted. BIOS **TOLUD** setting controls the RAM/PCIe boundary.
- **"Above 4G MMIO"** BIOS setting moves 64-bit BARs into high address space, freeing 32-bit space.
- **SR-IOV BARs** (BAR 7-12) require explicit BIOS support; missing enumeration causes "BAR 10: no space" errors.
- PLX switches add bridge windows (BAR 13-16) that must be accounted for.
- BAR types: I/O BAR (legacy, rarely used) and Memory BAR (32-bit or 64-bit). 64-bit BARs join two adjacent 32-bit registers.
- BAR sizing: BIOS writes all-1s, reads back to determine size from reserved bits.
- ResizableBAR capability can override standard BAR sizes.

This matters because the BMC manages PCIe topology (hot-swap, power, error reporting) and its own VGA device needs BAR space.

---

## 9. Google Drive Resource Index

### 9.1 Primary Project Documents

| Document | Key Content | Last Modified | Link |
|---|---|---|---|
| **Tim's Coreboot/OpenBMC Plan** | Master roadmap: BMC pathway (AST2050→2600), Coreboot pathway (X11SSH-F→X12), board-by-board strategy, focus on OpenBMC/LinuxBoot first, alternative pathways via X10 and ASUS boards | 2025-12-30 | [Open](https://docs.google.com/document/d/1-y8QPPGeA4QWTYFHwW2moe4WQnzgKxIVZEb10eMVHMo/edit) |
| **Dell C410X Documentation** | Assemblies/part numbers, BMC (AST2050), 4× PEX 8696 PCIe switches with I2C addresses, PCA9555/PCA9548A GPIO/I2C expanders, ISL6112 hot-swap, PCIe routing modes, host-side lspci/dmidecode dumps, board photos | 2025-12-30 | [Open](https://docs.google.com/document/d/1BFdn8vOxtryp-q8HkAw_GiRQoxe0PEtjwET4yxvckgg/edit) |
| **PCIe trees (SuperMicro)** | Full lspci trees for big-storage & GPU configs, i2cdetect bus scans, BMC-to-PCH thermal reporting protocol, comprehensive BAR/memory mapping explanation, southbridge details | 2025-12-30 | [Open](https://docs.google.com/document/d/112fK18lKBScLqsE-kLr5qnpEj8BHVG4tH-6dXQWcKLw/edit) |
| **SuperMicro SSG-6049P NVMe docs** | NVMe backplane CPLD, sideband signaling, OCulink/SFF-8643 cabling, PLX 8749 switch, CPU1/CPU2 NVMe config | 2025-12-30 | [Open](https://docs.google.com/document/d/1FfLRi6TKbpXUBDBoiIRnafUtI3bJOuOsE3N6xzI47SU/edit) |

### 9.2 Hardware & IC Reference

| Document | Key Content | Link |
|---|---|---|
| **FPGA BMC Resources** | Aspeed AST2500 specs, BOM analysis, RunBMC/DC-SCM module info | [Open](https://docs.google.com/document/d/1dpN-FS3LdKBQ-pRrEqmO5kzTjD_2x3pdOm0eVUe6gkU/edit) |
| **Remote Control Board** | CI board design, SPI flash layout diagrams, full target board inventory with specs, SPI tools reference | [Open](https://docs.google.com/document/d/1LhrtVZL2c0Hm8FCm_akZ0Hvk2fXt6JLkTgUt4vKUrPY/edit) |
| **Supermicro Motherboards** (Spreadsheet) | Master list of all board variants | [Open](https://docs.google.com/spreadsheets/d/1tb7xHrtSQLASPVy_Zj8J2syP3X3D07MdVAFtIkLtgR4/edit) |
| **RPi Zero W Pin Planning** (Spreadsheet) | Pin mapping for RPi → Supermicro remote control | [Open](https://docs.google.com/spreadsheets/d/17T4msLQmFCg9YwkQXFdmNz_fxkPkPlbuZaP0nYtzBZ4/edit) |
| **Boards with BMCs and Coreboot Potential** (Drawing) | Visual board classification | [Open](https://docs.google.com/drawings/d/1ttCKc1yLfi8wCIHqGdjYfPsM8INfIOLYqYZc-VsXpDw/edit) |
| **SPI Flash Layout Diagram** (Drawing) | SPI connections between southbridge and BMC | [Open](https://docs.google.com/drawings/d/1F6xLTsJsBC6fASu0AkINkimx4Ae_9cUXEpqng8eEoPI/edit) |
| **Dell C410X Middle Board Diagram** (Drawing) | Board layout for GC-BM3P midplane | [Open](https://docs.google.com/drawings/d/1ZOptkZ-HyONxiqBqNDNotxNdA6itCmMq4OyyWSkJ8zM/edit) |
| **Flashrom @ Chromium.org** | Comprehensive flashrom reference | [Open](https://docs.google.com/document/d/1H8zZ3aEMZmfO4ZEsWbHooUdGOgxy5LTPJ19YbaDsxdQ/edit) |

### 9.3 Background

| Document | Key Content | Link |
|---|---|---|
| **OpenBMC LCA 2017 abstract** | Motivation: proprietary BMC stacks use ancient kernels + closed userspace. OpenBMC replaces with upstream u-boot + Linux, REST/HTTPS over IPMI, SSH over SOL. Most common BMC HW is AST2400. | [Open](https://docs.google.com/document/d/19TDEmRT0l3lG9Y15mhoEabymEhWA5yc4id-dn7yg1Kg/edit) |

---

## 10. Key People & Organizations

| Person/Org | Role |
|---|---|
| **Tim "mithro" Ansell** | Project lead; hardware inventory owner, Coreboot/OpenBMC planning |
| **Joel Stanley** | OpenBMC kernel maintainer; AST2400 upstream Linux support |
| **3mdeb / Dasharo** | Commercial Coreboot/Dasharo support for Supermicro X11 |
| **Raptor Engineering** | ASUS KGPE-D16 Coreboot/BMC port (abandoned, to be replicated) |

---

## 11. Immediate Action Items for Claude Code

### 11.1 Firmware Image Analysis

1. **Obtain firmware images:** Download Supermicro BMC firmware update packages from Supermicro support site for X11SSH-TF (known Coreboot-supported board with AST2400). Download Dell C410x BMC firmware if available.
2. **Unpack with binwalk:** Extract kernel, rootfs, device tree from firmware images.
3. **Decompile device trees:** Use `dtc -I dtb -O dts` on extracted DTB files to recover GPIO pin assignments.
4. **Map GPIO pins to functions:** Cross-reference extracted GPIO assignments with Aspeed AST2400/AST2500 datasheets.
5. **Extract IPMI SDR data:** Parse Sensor Data Records to map sensor addresses to I2C buses.

### 11.2 Live System Analysis

1. **Connect to BMC UART:** Access proprietary BMC serial console.
2. **Dump device tree:** `dtc -I fs -O dts /proc/device-tree/`
3. **Enumerate GPIOs:** Read `/sys/class/gpio/` and `/sys/kernel/debug/gpio`.
4. **Dump I2C topology:** `i2cdetect` on all buses. Cross-reference with known addresses (see Sections 4.3, 5.5).
5. **Capture SPI flash:** `flashrom` (internal programmer) or read via `/dev/mtd*`.

### 11.3 OpenBMC/u-bmc Board Support Package

1. **Create device tree source:** Based on extracted pinout, write `.dts` following OpenBMC conventions.
2. **Define machine configuration:** Yocto machine config (OpenBMC) or Go board definition (u-bmc).
3. **Build and flash:** Compile firmware, flash to BMC SPI, validate boot over BMC UART.

### 11.4 Upstream Linux/Zephyr for AST2050

1. **Assess AST2050 delta from AST2400:** Determine which drivers/DT bindings can be reused.
2. **Evaluate Zephyr feasibility:** Check for existing Aspeed SoC support or adaptable ARM target.
3. **Prototype minimal boot:** Get minimal kernel booting on AST2050 with UART output.

---

## 12. Known Gaps

1. **No u-bmc resources in Google Drive.** Upstream repo: https://github.com/u-root/u-bmc
2. **AST2050 datasheet:** Aspeed datasheets are typically NDA-restricted. May need to work from AST2400/2500 kernel code and the ASUS KGPE-D16 abandoned port.
3. **Zephyr on Aspeed:** No existing Zephyr BSP found for any Aspeed SoC.
4. **I2C device identification:** The i2cdetect results (Section 5.5) need to be mapped to specific ICs. Tentative assignments provided but need verification against board schematics or firmware DTBs.
5. **Dell C410x firmware availability:** Need to verify if Dell publishes standalone BMC firmware updates for the C410x chassis.
6. **Embedded images in Google Docs:** The source docs contain board photos, IC marking close-ups, and layout diagrams as embedded images that cannot be extracted via the text API. These must be viewed in-browser for visual information.

---

*This document was generated by extracting and synthesizing content from Google Drive documents. For embedded images, diagrams, and visual data, refer to the linked source documents directly in a browser.*
