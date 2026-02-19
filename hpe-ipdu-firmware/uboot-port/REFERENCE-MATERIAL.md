# U-Boot Port Reference Material for HPE iPDU (NS9360)

## Target Hardware: HPE Intelligent Modular PDU (AF531A)

| Property | Value |
|----------|-------|
| SoC | Digi NS9360B-0-C177 |
| CPU | ARM926EJ-S, 177 MHz, boots big-endian (gpio[44]=0), runs little-endian |
| SDRAM | 32 MB ISSI IS42S32800D-7BLI @ 0x00000000 |
| NOR Flash | 16 MB (2x 8MB Macronix MX29LV640EBXEI, bottom boot) |
| Flash CS0 | 0x40000000 (8 MB) |
| Flash CS1 | 0x50000000 (8 MB) |
| Crystal | 29.4912 MHz (Y1) |
| CPU Clock | 176.9 MHz (PLL: 29.4912 MHz x 12 / 2) |
| AHB Bus | 88.5 MHz |
| BBus | 44.2 MHz |
| Debug UART | Port A @ 0x90200040, 115200/8/N/1 (J25 header) |
| Ethernet | NS9360 MAC + ICS1893AFLF PHY (25 MHz, Y2) |
| I2C | gpio[34-35], 100/400 kHz |
| Current firmware | NET+OS (ThreadX RTOS) - no Linux or U-Boot |

## Reference Material Inventory

### 1. Digi U-Boot 1.1.4 Source (Primary Reference)

**Location:** `reference/digi-cc9p9360-uboot/u-boot-1.1.4-digi/U-Boot/`
**Source:** `CC9U_UBOOT114_SRC_A.zip` from ftp1.digi.com/support/patches/

This is the most valuable reference. It is a complete U-Boot 1.1.4 source tree
with Digi's NS9360/NS9750 modifications. It includes:

**Board support:**
- `board/cc9c/` - ConnectCore 9C board (NS9360-based, closest to HPE iPDU)
  - `cc9c.c` - Board init, SDRAM size detection, flash CS1 setup, ethernet init
  - `platform.S` - Low-level init: memory controller setup, SDRAM timing, AHB monitor
  - `switch_to_le.S` - Endianness switching (NS9360 boots big-endian)
  - `flash.c` - CFI NOR flash driver
  - `nand.c` - NAND flash support (not needed for HPE iPDU)
- `board/digi_cc/` - Common Digi ConnectCore code
  - `cmd_bsp.c` - Digi-specific commands (dboot, update, etc.)
- `board/ns9750dev/` - NS9750 dev board (earlier reference, less relevant)

**Drivers (NS9xxx-specific):**
- `drivers/ns9750_eth.c` - Ethernet MAC driver (NS9360/NS9750 share same MAC)
- `drivers/ns9750_serial.c` - UART driver (4 ports, configurable)
- `drivers/ns9750_i2c.c` - I2C master driver
- `drivers/ns9750_usb_ohci.c` - USB OHCI host driver

**Headers (register definitions):**
- `include/ns9750_sys.h` - System control registers (PLL, clock, GPIO config)
- `include/ns9750_mem.h` - Memory controller registers (SDRAM, static memory)
- `include/ns9750_bbus.h` - BBus peripheral registers
- `include/ns9750_ser.h` - Serial port registers
- `include/ns9750_eth.h` - Ethernet MAC registers
- `include/ns9750_i2c.h` - I2C controller registers
- `include/ns9360_rtc.h` - NS9360-specific RTC registers
- `include/ns9360_usb.h` - NS9360-specific USB registers
- `include/ns9750_nand.h` - NAND flash registers

**Board configs:**
- `include/configs/cc9c.h` - ConnectCore 9C config (NS9360, NOR flash, 29.4912 MHz crystal)
- `include/configs/digi_common.h` - Digi common command definitions
- `include/configs/ns9750dev.h` - NS9750 dev board config

**Key configuration values from cc9c.h (most relevant to HPE iPDU):**
```
CONFIG_ARM926EJS = 1
CONFIG_NS9360 = 1
CRYSTAL = 294912          (29.4912 MHz - same as HPE iPDU)
CONFIG_CONS_INDEX = 1     (Port A - same as HPE iPDU debug UART)
CONFIG_BAUDRATE = 38400   (HPE iPDU uses 115200)
NS9750_ETH_PHY_ADDRESS = 0x0001
PHYS_SDRAM_1 = 0x00000000
PHYS_FLASH_1 = 0x50000000 (CS1 - HPE iPDU has flash on both CS0 and CS1)
CFG_FLASH_BASE = 0x50000000
```

### 2. Digi U-Boot 1.1.3 Source (Secondary Reference)

**Location:** `reference/digi-cc9p9360-uboot/u-boot-1.1.3-digi/U-Boot/`
**Source:** `uboot113fs3.tbz2` from ftp1.digi.com/support/patches/

Earlier version. Has `board/cc9c/` and `board/ns9750dev/` but lacks `board/digi_cc/`
(common Digi code). Useful for diffing against 1.1.4 to see what changed.

Build targets (from `build.sh`):
- `cc9p9360val` - CC9P9360 validation board
- `cc9p9360js` - CC9P9360 JumpStart board
- `cc9p9750dev` - CC9P9750 dev board
- `cc9p9750val` - CC9P9750 validation board

### 3. Pre-compiled U-Boot Binaries

**Location:** `reference/digi-cc9p9360-uboot/binaries/`

| File | Version | Size |
|------|---------|------|
| `u-boot-cc9p9360js-v1.1.4e.bin` | U-Boot 1.1.4 RevE | 238 KB |
| `u-boot-cc9p9360js-v1.1.6-revf6.bin` | U-Boot 1.1.6 RevF6 | 257 KB |

These can be disassembled to verify register values, memory maps, and boot
sequences. They were compiled for the CC9P9360 JumpStart board.

### 4. Mainline U-Boot v2012.10 (NS9750dev)

**Location:** `reference/ns9750dev-uboot/u-boot-v2012.10/` (git submodule)
**Source:** https://github.com/u-boot/u-boot.git @ tag v2012.10

The last mainline U-Boot version with NS9750 board support (removed ~2013).
Full git history available. Key files:
- `board/ns9750dev/` - Board support (simpler than Digi version)
- `board/ns9750dev/lowlevel_init.S` - Memory controller init
- `drivers/serial/ns9750_serial.c` - Serial driver
- `include/configs/ns9750dev.h` - Board config
- `include/ns9750_*.h` - Register definitions (same as Digi version)

This provides context for what upstream U-Boot expected and how the NS9750
support was structured in the mainline codebase.

### 5. Linux Kernel mach-ns9xxx (v2.6.39)

**Location:** `reference/linux-mach-ns9xxx/linux-v2.6.39/` (git submodule, shallow)
**Source:** https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git @ v2.6.39

The Linux kernel had `arch/arm/mach-ns9xxx/` with NS9360-specific support.
Key files (checked out under `arch/arm/mach-ns9xxx/`):
- `processor-ns9360.c` - NS9360 processor init
- `gpio-ns9360.c` - GPIO controller driver with pin mux
- `time-ns9360.c` - Timer/clock driver
- `board-jscc9p9360.c` - CC9P9360 JumpStart board definition
- `mach-cc9p9360js.c` - Machine type registration
- `clock.c` - Clock tree management
- `include/mach/regs-sys-ns9360.h` - System register definitions
- `include/mach/regs-bbu.h` - BBus utility registers
- `include/mach/regs-mem.h` - Memory controller registers

These provide a second, independent set of NS9360 register definitions and
hardware init sequences to cross-reference against the U-Boot code.

### 6. Hardware Documentation (PDFs)

**Location:** `reference/docs/`

| File | Description |
|------|-------------|
| `lxnetes-users-guide-cc9p9360-9750.pdf` | LxNETES Linux BSP guide with U-Boot build instructions |
| `connectcore-9p-9360-hardware-reference.pdf` | CC9P9360 module hardware reference |
| `digi-uboot-reference-manual.pdf` | Digi U-Boot command reference |
| `ns9360-dev-board-schematic.pdf` | NS9360 development board schematic |
| `ns9360-pinout.pdf` | NS9360 BGA pinout diagram |
| `ns9360-gpio-pin-mux.pdf` | GPIO pin multiplexing reference |
| `ns9360-gpio-table.pdf` | Complete GPIO function table |
| `ns9360-x32-dram-application-note.pdf` | 32-bit SDRAM configuration guide |
| `ns9360-spi-boot-hardware-defect-app-note.pdf` | SPI boot mode errata |
| `ns9360-design-rules.pdf` | PCB design rules for NS9360 |
| `ns9360-assembly-drawing.pdf` | NS9360 package assembly drawing |
| `ns9360-ns9750-lcd-app-note.pdf` | LCD controller app note |
| `ns9360-product-brief.pdf` | NS9360 product overview |
| `ns9360-ram-test.pdf` | SDRAM test procedures |
| `ns9750-ns9360-power-sequencing.pdf` | Power supply sequencing requirements |
| `connectcore-9p-9360-important-info.pdf` | Important errata and notices |

The NS9360 datasheet and hardware reference manual are already in the parent
directory at `hpe-ipdu-firmware/datasheets/`:
- `NS9360_datasheet_91001326_D.pdf` (705 KB)
- `NS9360_HW_Reference_90000675_J.pdf` (2.7 MB) - **the definitive register reference**

### 7. Additional Archives

| File | Description |
|------|-------------|
| `uboot-setup-1.1.4-netos.exe` | NET+OS U-Boot installer (Windows/Cygwin, may have additional source) |
| `uboot113fs3-binaries.zip` | Pre-compiled U-Boot 1.1.3 binaries for multiple platforms |

## Key Differences: CC9C vs HPE iPDU

The CC9C (ConnectCore 9C) is the closest board to the HPE iPDU, but there are
important differences to account for in the U-Boot port:

| Feature | CC9C (Digi) | HPE iPDU |
|---------|-------------|----------|
| SoC | NS9360 | NS9360B (same family) |
| Crystal | 29.4912 MHz | 29.4912 MHz (same) |
| SDRAM | Varies (16-64 MB) | 32 MB (IS42S32800D, 32-bit) |
| NOR Flash | 1x on CS1 (0x50000000) | 2x: CS0 (0x40000000) + CS1 (0x50000000) |
| Flash type | CFI compatible | Macronix MX29LV640EBXEI (CFI compatible) |
| Debug UART | Port A, 38400 baud | Port A, 115200 baud |
| Ethernet PHY | Unknown model | ICS1893AFLF (MII, 25 MHz crystal) |
| Boot source | Flash at CS1 | Flash at CS0 (0x40000000) |
| Endianness | Big-endian (default), switched to LE | Big-endian boot (gpio[44]=0), switched to LE by stub |
| I2C EEPROM | M24LC64 at 0x50 | Unknown (test point on I2C bus) |
| NAND Flash | Optional | Not present |
| USB | OHCI host | OHCI host (unused in stock firmware) |
| RTC | On-chip NS9360 | On-chip NS9360 + coin cell (BT1) |

## Critical Adaptation Points for the HPE iPDU Port

1. **Flash base address**: CC9C uses CS1 (0x50000000) as primary flash. HPE iPDU
   uses CS0 (0x40000000) as primary with CS1 as secondary. The `lowlevel_init`
   and flash driver need updating.

2. **SDRAM configuration**: CC9C's `platform.S` configures SDRAM generically.
   HPE iPDU uses specific IS42S32800D-7BLI (32-bit, 256Mbit). Timing parameters
   need verification against the datasheet.

3. **Baud rate**: Change from 38400 to 115200 for the debug console.

4. **Ethernet PHY**: The ICS1893AFLF uses MII interface. Need to verify PHY
   address and any PHY-specific initialization requirements.

5. **Dual flash chip support**: Need to configure both CS0 and CS1 for the two
   8 MB Macronix flash chips.

6. **Boot from CS0**: The existing code assumes boot from CS1. The mirror bit
   and memory controller configuration need adjustment for CS0 boot.

## Source URLs

All Digi downloads came from:
- Source: https://ftp1.digi.com/support/patches/
- Docs: https://ftp1.digi.com/support/documentation/
- U-Boot reference: https://docs.digi.com/resources/documentation/digidocs/pdfs/90000852.pdf

Mainline U-Boot: https://github.com/u-boot/u-boot (tag v2012.10)
Linux kernel: https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git (tag v2.6.39)
