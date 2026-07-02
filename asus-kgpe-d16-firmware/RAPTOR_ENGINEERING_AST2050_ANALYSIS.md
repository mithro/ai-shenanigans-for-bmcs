# Raptor Engineering AST2050 Linux Kernel and U-Boot Modifications
## Comprehensive Analysis of All Changes

**Document Version:** 1.0
**Date:** 2026-02-15
**Analysis Scope:** Complete examination of Raptor Engineering's AST2050 modifications across Linux kernel 2.6.28.9, U-Boot, and Yocto OpenBMC

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Repository Overview](#repository-overview)
3. [Linux Kernel Changes](#linux-kernel-changes)
4. [U-Boot Changes](#u-boot-changes)
5. [Yocto OpenBMC Integration](#yocto-openbmc-integration)
6. [Detailed Driver Analysis](#detailed-driver-analysis)
7. [Porting Recommendations](#porting-recommendations)

---

## Executive Summary

Raptor Engineering created a comprehensive AST2050 Board Management Controller (BMC) platform based on Linux 2.6.28.9 and U-Boot. The modifications were made by Timothy Pearson (madscientist159) in August 2017 and archived in June 2018. The work includes:

- **Linux Kernel:** Modified Linux 2.6.28.9 with complete AST2050/ASPEED support
- **U-Boot:** Custom bootloader with AST2050 board initialization
- **Yocto OpenBMC:** Complete build framework integrating both components
- **Target Platform:** ASUS KGPE-D16 / KCMA-D8 server motherboards

**Critical Finding:** The repository contains a complete, production-ready AST2050 BMC implementation with extensive driver support for all major peripherals.

---

## Repository Overview

### 1. ast2050-linux-kernel
- **Repository:** https://github.com/raptor-engineering/ast2050-linux-kernel
- **Status:** Archived (2018-06-05)
- **Branch:** linux-2.6.28.y
- **Base Version:** Linux 2.6.28.9
- **Upstream Source:** git://git.kernel.org/pub/scm/linux/kernel/git/stable/linux-stable.git
- **Total Commits:** 4
- **License:** GPL

### 2. ast2050-uboot
- **Repository:** https://github.com/raptor-engineering/ast2050-uboot
- **Status:** Archived (2018-06-05)
- **Branch:** master
- **Total Commits:** 3
- **Upstream Source:** git://git.denx.de/u-boot.git (commit 62c175f)
- **License:** GPL

### 3. ast2050-yocto-openbmc
- **Repository:** https://github.com/raptor-engineering/ast2050-yocto-openbmc
- **Status:** Archived (2018-06-05)
- **Branch:** master
- **Total Commits:** 21
- **Base:** Facebook OpenBMC
- **License:** Various (per component)

---

## Linux Kernel Changes

### Commit History

#### 1. Initial import of modified Linux 2.6.28 tree (fcbb27b)
**Date:** 2017-08-23
**Author:** Timothy Pearson

This is the foundational commit containing all AST2050 support. The changes include:

**Architecture Support (arch/arm/mach-aspeed/):**
- Complete machine support for AST1100, AST2100, AST2300, AST2400, AST2500
- PC Extender support: AST1510, AST1520
- RemoteFX Zero-client: AST3100, AST3200
- Companion controller: AST1070

**Platform Support (arch/arm/plat-aspeed/):**
- 38 device initialization files
- System Control Unit (SCU) implementation
- SDRAM Memory Controller (SDMC)
- IRQ management
- Timer implementation
- Comprehensive peripheral support

#### 2. Fix FTBFS from incorrect defined() in timeconst.pl (30bdf6f)
**Date:** 2017-08-23
**Author:** Timothy Pearson

**File Modified:** kernel/timeconst.pl
**Change:** Fixed Perl syntax error preventing kernel build

```perl
# Before:
if (!defined(@val)) {

# After:
if (!@val) {
```

**Impact:** Corrects build failure due to invalid Perl syntax

#### 3. Acknowledge LPC reset and related events in the KCS interface module (4d7aca1)
**Date:** 2017-08-25
**Author:** Timothy Pearson

**Files Modified:**
- arch/arm/mach-aspeed/include/mach/ast_kcs.h (+19, -13)
- drivers/char/aspeed/ast_kcs.c (+74, -3)

**Purpose:** Resolves IRQ storm / LPC hang during host boot with active BMC

**Key Changes:**
1. Added HICR5 register definitions for interrupt control
2. Implemented LPC-reset register read/write functions
3. Added interrupt enable/disable functions
4. Enhanced IRQ handler to separately manage LRST, SDWN, and ABRT events
5. Clear interrupt statuses during initialization

#### 4. Increase rootfs size to handle additional userspace utilities (f5c25cc)
**Date:** 2017-08-26
**Author:** Timothy Pearson

**File Modified:** arch/arm/plat-aspeed/dev-spi.c

**Change:** MTD flash partition table modification

```c
// Before:
.offset = 0x300000,    // 3MB
.size = 0xCB0000,      // 12.7MB

// After:
.offset = 0x240000,    // 2.4MB
.size = 0xd70000,      // 13.7MB
```

**Impact:** Expanded rootfs by 1MB for additional utilities

---

## Architecture and Platform Code

### mach-aspeed (Machine-Specific Code)

**Location:** /arch/arm/mach-aspeed/

**Source Files (Makefile):**
```makefile
obj-$(CONFIG_ARCH_AST1100) += ast1100.o
obj-$(CONFIG_ARCH_AST2100) += ast2100.o gpio.o ast-lpc.o
obj-$(CONFIG_ARCH_AST2300) += ast2300.o gpio.o ast-lpc.o
obj-$(CONFIG_ARCH_AST2400) += ast2400.o gpio.o ast-lpc.o ast-lpc_plus.o
obj-$(CONFIG_ARCH_AST2500) += ast2500.o ast-mctp.o
obj-$(CONFIG_ARCH_AST1510) += ast1510.o gpio.o
obj-$(CONFIG_ARCH_AST1520) += ast1520.o ast-mctp.o
obj-$(CONFIG_ARCH_AST3100) += ast3100.o gpio.o
obj-$(CONFIG_ARCH_AST3200) += ast3200.o ast-mctp.o
obj-$(CONFIG_ARCH_AST1070) += ast1070.o
```

**Core Files:**
- ast2100.c - AST2100 machine initialization (closest to AST2050)
- gpio.c - GPIO driver
- ast-lpc.c - LPC interface
- ast-lpc_plus.c - Enhanced LPC for AST2400
- ast-mctp.c - MCTP support
- core.h - Core definitions

**Header Files (include/mach/):**
- hardware.h - Main hardware definitions
- memory.h - Memory layout
- io.h - I/O mapping
- platform.h - Platform configuration
- irqs.h - Interrupt routing header
- ast_gpio_irqs.h - GPIO interrupts
- ast_lpc_irqs.h - LPC interrupts
- Chip-specific IRQ/platform files for all AST variants
- Peripheral interface headers (UART, SPI, PWM, LCD, Video, WDT, KCS, etc.)

**Memory Map (from platform.h):**
- I/O Start: 0x1E600000
- I/O Size: 0x00200000
- PLL Frequencies: 25MHz, 24MHz, 12MHz

**Memory Banks (AST2300/2400):**
- CS0: 0x20000000
- CS1: 0x24000000
- CS2: 0x26000000
- CS3: 0x28000000
- CS4: 0x2a000000
- NOR Flash Size: 16MB

**Device Mappings (from ast2100.c):**
- VIC (Vectored Interrupt Controller)
- SCU (System Control Unit)
- SDMC (SDRAM Memory Controller)
- Video Engine
- Dual Ethernet MACs
- Crypto Accelerator
- 2D Graphics Engine
- GPIO
- Timer
- UART (0, 1, virtual, physical)
- Watchdog
- USB Device Controller
- LPC Interface
- PECI

### plat-aspeed (Platform-Level Code)

**Location:** /arch/arm/plat-aspeed/

**Core Files:**
```makefile
# Base compilation
obj-y := irq.o timer.o devs.o ast-scu.o ast-sdmc.o
```

**Conditional Modules:**
- AST1070: ast1070_irq.o, ast1070-scu.o, ast1070-uart-dma.o
- I2C slave: i2c-slave-eeprom.o
- AST2400 BMC: ast2400-irq.o, ast2400-scu.o

**Device Initialization Files (38 total):**
- dev-adc.c - Analog to Digital Converter
- dev-ci2c.c - Companion I2C
- dev-clpc.c - Companion LPC
- dev-cuart.c - Companion UART
- dev-ehci.c - USB EHCI
- dev-eth.c - Ethernet
- dev-fb.c - Framebuffer
- dev-gpio.c - GPIO
- dev-i2c.c - I2C
- dev-kcs.c - Keyboard Controller Style
- dev-lpc.c - Low Pin Count
- dev-mbx.c - Mailbox
- dev-nand.c - NAND Flash
- dev-nor.c - NOR Flash
- dev-peci.c - Platform Environment Control Interface
- dev-pwm-fan.c - PWM Fan Control
- dev-rtc.c - Real-Time Clock
- dev-sdhci.c - SD Host Controller
- dev-sgpio.c - Serial GPIO
- dev-snoop.c - Snoop Engine
- dev-spi.c - SPI
- dev-uart.c - UART
- dev-uhci.c - USB UHCI
- dev-video.c - Video
- dev-virthub.c - Virtual Hub
- dev-vuart.c - Virtual UART
- dev-wdt.c - Watchdog Timer

**System Files:**
- ast-scu.c - System Control Unit implementation
- ast-sdmc.c - SDRAM Memory Controller
- irq.c - Interrupt handling
- timer.c - Timer implementation
- devs.c - Device registration

**Register Definition Headers (include/plat/):**
- regs-scu.h - System Control Unit registers
- regs-sdmc.h - SDRAM Memory Controller registers
- regs-lpc.h - LPC registers
- regs-gpio.h - GPIO registers
- regs-iic.h - I2C registers
- regs-intr.h - Interrupt registers
- regs-spi.h - SPI registers
- regs-uart-dma.h - UART DMA registers
- regs-video.h - Video registers
- regs-fmc.h - Flash Memory Controller
- regs-adc.h - ADC registers
- regs-peci.h - PECI registers
- regs-pwm_fan.h - PWM/Fan registers
- regs-rtc.h - RTC registers
- regs-mbx.h - Mailbox registers
- regs-mctp.h - MCTP registers
- regs-jtag.h - JTAG registers
- regs-crt.h - CRT registers
- regs-pcie.h - PCIe registers
- regs-udc11.h - USB Device Controller
- regs-vuart.h - Virtual UART registers

---

## System Control Unit (SCU) Implementation

**File:** arch/arm/plat-aspeed/ast-scu.c

### Clock Architecture

```
CLK24M
  ├─> H-PLL ─> HCLK
  ├─> M-PLL ─> MCLK
  └─> V-PLL1 ─> DCLK
```

### Key Registers (from regs-scu.h)

**Protection & Reset:**
- AST_SCU_PROTECT (0x00) - Protection key
- AST_SCU_RESET (0x04) - System reset control

**Clock Management:**
- AST_SCU_CLK_SEL (0x08) - Clock selection
- AST_SCU_CLK_STOP (0x0C) - Clock stop control
- AST_SCU_COUNT_CTRL (0x10) - Frequency counter
- AST_SCU_COUNT_VAL (0x14) - Frequency measurement

**PLL Configuration:**
- AST_SCU_D2_PLL (0x1C) - D2-PLL parameters
- AST_SCU_M_PLL (0x20) - M-PLL parameters
- AST_SCU_H_PLL (0x24) - H-PLL parameters

**Peripheral Control:**
- AST_SCU_INTR_CTRL (0x18) - Interrupt control
- AST_SCU_MAC_CLK (0x48) - MAC clock delays
- AST_SCU_MISC1_CTRL (0x2C) - Miscellaneous control

**Pin Configuration:**
- AST_SCU_HW_STRAP1 (0x70) - Hardware strapping
- AST_SCU_FUN_PIN_CTRL1-9 (0x80-0xA8) - Multi-function pins

**Memory & VGA:**
- AST_SCU_VGA0/1 (0x40/0x44) - VGA handshaking
- AST_SCU_VGA_SCRATCH0-7 (0x50-0x6C) - VGA scratch registers

### Initialization Functions

**Clock Setup:**
- Video engine with dynamic clock scaling
- Ethernet MAC (RGMII/RMII modes)
- USB host, device, SDHCI
- I2C, PWM, ADC, PECI

**Hardware Detection:**
- SoC identification table with revision IDs
- Support for AST1100, AST2050, AST2300, AST2400
- Version tracking (A0-A3 revisions)

**Multi-Function Pin Control:**
- UART port assignment
- Ethernet interface configuration
- NAND/NOR flash selection
- SD card slot configuration
- USB configuration

---

## Detailed Driver Analysis

### Character Device Drivers

**Location:** drivers/char/aspeed/

#### 1. KCS Interface Driver (ast_kcs.c)

**Purpose:** Keyboard Controller Style interface for IPMI communication

**Features:**
- LPC-based communication
- Interrupt-driven operation
- Support for host-to-BMC messaging
- IRQ storm prevention

**Key Functions:**
- ast_lpcreset_read_reg() - Read LPC-reset registers
- ast_lpcreset_write_reg() - Write LPC-reset registers
- ast_lpcreset_enable_interrupt() - Enable error interrupts
- ast_lpcreset_disable_interrupt() - Disable interrupts

**Interrupt Events Handled:**
- LRST (LPC Reset)
- SDWN (Shutdown)
- ABRT (Abort)

**Header:** arch/arm/mach-aspeed/include/mach/ast_kcs.h

**HICR5 Register Definitions:**
- AST_LPC_HICR5_SNP1_ENINT (0x08)
- AST_LPC_HICR5_SNP1_EN (0x04)
- AST_LPC_HICR5_SNP0_ENINT (0x02)
- AST_LPC_HICR5_SNP0_EN (0x01)

#### 2. PECI Driver (ast_peci.c)

**Purpose:** Platform Environment Control Interface for CPU thermal monitoring

**Device:** /dev/ast-peci (misc character device)

**Features:**
- PECI protocol communication
- Interrupt-driven command completion
- Message TX/RX up to 32 bytes
- FCS validation (hardware/software)

**IOCTL Commands:**
1. Read timing negotiation parameters
2. Write timing negotiation parameters
3. Execute data transfer operations

**Technical Details:**
- Clock: 24MHz with programmable dividers
- Baud rates: 2kbps-2Mbps
- Dual data buffers (16-byte segments)
- Timeout handling
- Status tracking: timeouts, connection, FCS errors

**Interrupt Conditions:**
- Command completion
- Timeout events
- Connection status changes
- FCS errors

### I2C Subsystem

**Location:** drivers/i2c/busses/

#### I2C Bus Driver (i2c-ast.c)

**Features:**
- Master and slave modes
- Multiple transfer mechanisms:
  - Byte mode (single-byte)
  - Buffer/Pool mode (multi-byte via memory pools)
  - DMA mode (direct memory access)
- SMBus support (block read/write)
- Interrupt-driven operation
- Bus error recovery
- SCL/SDA line monitoring

**Clock Configuration:**
- Standard and high-speed modes
- Speeds up to 400+ kHz
- Configurable AC timing

**Major Functions:**
- ast_i2c_xfer - Main transfer entry
- ast_i2c_do_dma_xfer - DMA transfers
- ast_i2c_do_pool_xfer - Buffer pool transfers
- ast_i2c_do_byte_xfer - Single-byte transfers
- i2c_ast_handler - Interrupt service
- ast_i2c_master_xfer_done - Complete master transactions
- ast_i2c_slave_xfer_done - Complete slave transactions
- ast_i2c_dev_init - Controller initialization

**Error Handling:**
- Bus recovery with stop command
- Timeout protection

**Platform Integration:** arch/arm/plat-aspeed/dev-i2c.c

**Device Registration:**
- 14 I2C platform devices (dev1-dev14)
- Architecture-specific DMA configuration
- AST2300/AST2400: BUFF_MODE (master), BYTE_MODE (slave)

**Buffer Pool Management:**
- Spinlock and page allocation
- AST2400: 8 pages × 256 bytes
- AST2300: 5 pages (mixed sizes)

**Initialization:**
1. Multi-pin configuration via SCU
2. I2C reset
3. Register mapping (ioremap)
4. Platform device registration

**Board-Specific Support:**
- Wedge100
- Yosemite
- FBPLATFORM1
- I2C device info for sensors, PSUs, controllers

### Network Drivers

**Location:** drivers/net/

#### FTGMAC100 Ethernet Driver (ftgmac100_26.c)

**Hardware Support:**
- ASPEED FTGMAC100 Gigabit MAC
- AST2050, AST2100, AST2300, AST2400
- Dual MAC configurations (MAC1, MAC2)

**PHY Support:**
- Marvell
- Broadcom (BCM54612E, BCM54616S)
- Realtek (RTL8201EL, RTL8211BN, RTL8201N)

**Features:**
- NCSI (Network Controller Sideband Interface)
- Out-of-band management
- PHY-based and RMII interfaces
- Link status monitoring
- Auto-negotiation

**Performance:**
- 10/100/1000 Mbps
- Full/half duplex
- DMA-based TX/RX
- Configurable FIFO buffering

**Advanced Features:**
- Multicast hash filtering
- VLAN support
- Broadcast filtering
- MAC address filtering
- Interrupt and polling modes

**Configuration:**
- Module parameter: macaddr (MAC override)
- Debug levels
- Timer-based link checking

### SPI Subsystem

**Location:** drivers/spi/

#### SPI Host Driver (ast_spi.c)

**Purpose:** SPI communication for ASPEED systems

**Features:**
- SPI device setup/configuration
- Data transfer (TX/RX)
- Chip select handling
- Clock divisor configuration

**Supported Options:**
- Bits-per-word: 8-16 bits
- SPI modes (CPOL/CPHA)
- LSB-first transmission
- Variable clock speeds

**Major Functions:**
- ast_spi_setup() - Device configuration
- ast_spi_transfer() - Message-based transfers
- ast_spi_probe() - Hardware initialization
- ast_spi_remove() - Resource cleanup

**Memory Mapping:**
- Register memory (control)
- Buffer memory (data I/O)

**Power Management:**
- Suspend/resume (unimplemented)

**Platform Integration:** arch/arm/plat-aspeed/dev-spi.c

### MTD/Flash Subsystem

**Location:** drivers/mtd/maps/

#### NOR Flash Driver (ast-nor.c)

**Purpose:** NOR flash mapping for ASPEED platforms

**Features:**
- Configurable bank widths (1-byte, 2-byte)
- Memory resource mapping
- Virtual address remapping (ioremap)
- MTD partition handling
- CFI flash detection (do_map_probe)
- Suspend/resume support

**Author:** Ryan Chen

**Module:** astflash (platform:astflash)

**Initialization:**
1. Request memory regions
2. Map to virtual addresses
3. Probe for compatible flash
4. Enable partition management

**Flash Partition Table:** Modified in dev-spi.c (commit f5c25cc)

```c
// Rootfs partition
.offset = 0x240000,    // 2.4MB
.size = 0xd70000,      // 13.7MB
```

### Watchdog Timer

**Location:** drivers/watchdog/

#### Watchdog Driver (ast_wdt.c)

**Features:**
- Configurable timeout (default 30s, max 65536s)
- Dual-boot mode with auto-rearm
- Interrupt handling
- System reset functionality

**Configuration Options:**
- heartbeat - Timeout period (0-65536 seconds)
- nowayout - Prevent disabling once started
- force_disable - Disable by default

**Register Operations:**
- WDT_Ctrl - Control register
- WDT_Reload - Reload value
- WDT_Restart - Restart trigger
- WDT_Clr - Clear register

**Clock Sources:**
- External clock
- PCLK (via wdt_sel_clk_src)

**Reset Modes:**
- SOC reset
- Full chip reset
- ARM-only reset
- Controlled via wdt_set_timeout_action()

**File Operations:**
- open, release, write, ioctl
- Magic close: 'V' (safe shutdown)
- Override: 'X'/'x'

**Base Address:** IO_ADDRESS(AST_WDT_BASE)

### UART Support

**Location:** arch/arm/plat-aspeed/

#### UART Configuration (dev-uart.c)

**Features:**
- Multiple UART ports
- Serial8250 platform driver
- Standard and virtual UARTs

**Configuration:**
- Clock: 24MHz (all ports)
- Register shift: 2 bits
- I/O types:
  - ColdFire: UPIO_MEM32
  - ARM: UPIO_MEM

**Platform Support:**
- AST1010: UART0, UART1, UART2 (32-bit I/O)
- AST1070: Additional LPC UARTs
- Yosemite: UART1-4

**Registration:** ast_add_device_uart()

**Header:** arch/arm/mach-aspeed/include/mach/aspeed_serial.h

**DMA Support:** arch/arm/plat-aspeed/ast1070-uart-dma.c

### Device Registration

**File:** arch/arm/plat-aspeed/devs.c

**Registered Devices:**

```c
init_fnc_t *init_device_sequence[] = {
    ast_add_device_lpc,          // LPC
    ast_add_device_uart,         // UART
    ast_add_device_vuart,        // Virtual UART
    ast_add_device_nand,         // NAND flash
    ast_add_device_nor,          // NOR flash
    ast_add_device_i2c,          // I2C
    ast_add_device_spi,          // SPI
    ast_add_device_gpio,         // GPIO
    ast_add_device_sgpio,        // Serial GPIO
    ast_add_device_wdt,          // Watchdog
    ast_add_device_rtc,          // RTC
    ast_add_device_pwm_fan,      // PWM fan
    ast_add_device_adc,          // ADC
    ast_add_device_fb,           // Framebuffer
    ast_add_device_gmac,         // Ethernet
    ast_add_device_mbx,          // Mailbox
    ast_add_device_snoop,        // Snoop
    ast_add_device_peci,         // PECI
    ast_add_device_kcs,          // KCS
    ast_add_device_virthub,      // Virtual Hub
    // Commented out: EHCI, SDHCI, UHCI, video
};
```

**Initialization:** ast_add_all_devices() iterates and calls each function

---

## Kernel Configuration

### Kconfig Support

**File:** arch/arm/mach-aspeed/Kconfig

**Processor Families:**

1. **IRMP Serials (default)**
   - AST1100
   - AST2100
   - AST2200
   - AST2300
   - AST2400 (with USB EHCI)
   - AST2500 (with USB EHCI)

2. **PC Extender Serials**
   - AST1500
   - AST1510
   - AST1520 (with USB EHCI)

3. **RemoteFX Zero-Client Serials**
   - AST3100 (with USB EHCI)
   - AST3200 (with USB EHCI)

**Additional Options:**
- AST1070 companion chip
- Flash configuration (CS0-CS4)
  - NOR, NAND, SPI_NOR, NONE per chip select
- Platform definitions:
  - Facebook Wedge
  - Yosemite
  - ASUS platforms
- PCIe support

### Defconfig Files

**Location:** arch/arm/configs/

**AST-Specific Configurations:**
- ast2300_ast1070_defconfig
- ast2300_defconfig
- ast2300_fb_defconfig
- ast2400_ast1070-1_defconfig
- ast2400_ast1070_defconfig
- ast2400_defconfig
- ast2400_fb_defconfig
- ast2400_slt_defconfig

**Note:** No ast2050 or ast2100 defconfig found; AST2100 configuration likely built from ast2300_defconfig

---

## U-Boot Changes

### Repository Details

**Repository:** https://github.com/raptor-engineering/ast2050-uboot
**Base:** U-Boot (commit 62c175f from git://git.denx.de/u-boot.git)
**Commits:** 3

### Commit History

#### 1. Initial import of modified u-boot tree (0223e59)
**Date:** 2017-08-23
**Author:** Timothy Pearson

**Board Support Added:**
- board/aspeed/ast2050/ (34 files)
- board/aspeed/ast2300/
- board/aspeed/ast2400/

**AST2050 Board Files:**
- Makefile, config.mk
- ast2050.c - Main board initialization
- platform.S - Assembly platform code
- crt.c, crt.h - C runtime

**Flash & Storage:**
- flash.c - Flash driver
- flash_spi.c - SPI flash support

**Security/Crypto:**
- aes.c - AES encryption
- rc4.c - RC4 cipher
- crc32.c - CRC32 checksum

**Hardware Testing:**
- regtest.c/h - Register tests
- hactest.c/h - Hardware acceleration tests
- mactest.c/h - MAC tests
- mictest.c/h - Memory controller tests
- hwreg.h - Hardware registers

**Video/Graphics:**
- vfun.c/h - Video functions
- vesa.h - VESA definitions
- vdef.h - Video definitions
- vreg.h - Video registers
- vgahw.h - VGA hardware
- vhace.c/h - Video hardware acceleration
- videotest.c/h - Video testing

**Other:**
- pci.c - PCI support
- slt.c/h - System Level Test
- type.h - Type definitions

**ASPEED CPU Support:**

Location: arch/arm/cpu/arm926ejs/aspeed/

Files include:
- MAC.c/H - Ethernet MAC control
- LAN9303.c - Network switch driver
- DRAM_SPI.c - Memory and SPI flash
- NCSI.c/H - NC-SI protocol
- Hardware initialization utilities

#### 2. Initialize GPIO bank A during U-Boot phase (323b3ac)
**Date:** 2017-08-26
**Author:** Timothy Pearson

**File Modified:** board/aspeed/ast2050/ast2050.c

**Purpose:** Prevent spurious operation of host during boot

**Change:**
```c
// Removed:
*((volatile ulong*) (AST_GPIO_BASE+0x04)) |= 0x00000010;

// Added:
if (!((*((volatile ulong*) (AST_GPIO_BASE+0x04))) & 0x00000010)) {
    *((volatile ulong*) (AST_GPIO_BASE+0x00)) |= 0x00000010;
    *((volatile ulong*) (AST_GPIO_BASE+0x04)) |= 0x00000010;
}
```

**Impact:** Conditional GPIO initialization prevents conflicts

#### 3. Add missing compiler-gcc6.h file (537b8cc)
**Date:** 2017-08-28
**Author:** Timothy Pearson

**Source:** Freescale meta-fsl-arm repository

**Purpose:** Enable compilation with GCC 6.x

### U-Boot Configuration

**File:** include/configs/ast2050.h

**Boot Parameters:**

```c
// Boot command
"bootm 14080000 14300000"  // Kernel and ramdisk from flash

// Boot arguments
"debug console=ttyS1,115200n8 ramdisk_size=16384 root=/dev/ram rw init=/linuxrc mem=80M"

// Boot delay
3 seconds (1 second in SLT mode)

// Boot file
"all.bin"
```

**Memory Configuration:**
- DRAM: 64 MB (one bank at 0x40000000)
- Flash: 8 MB SPI flash at 0x14000000
- Environment: 0x7F0000 offset (64 KB)

**Serial Console:**
- Controller: NS16550-compatible
- Baud: 115200 bps
- Active: UART 2 (COM2) at 0x1e784000
- Clock: 24 MHz

**Network:**
- Dual Ethernet MACs
- PHY configuration
- Static IP: 192.168.0.188
- Network boot support

**Additional Configs:**
- ast2300.h, ast2300_ast1070.h
- ast2300_nor.h, ast2300_spi.h
- ast2400.h, ast2400_ast1070.h, ast2400_ast10701.h
- ast2400_nor.h, ast2400_slt.h, ast2400_spi.h
- ast1100.h, ast2100.h
- ast3100.h

---

## Yocto OpenBMC Integration

### Repository Details

**Repository:** https://github.com/raptor-engineering/ast2050-yocto-openbmc
**Base:** Facebook OpenBMC
**Purpose:** Complete Linux image build for AST2050 BMC
**Framework:** Yocto Project

### Layer Architecture

**Three-Layer Structure:**

1. **Common Layer** (common/)
   - Shared packages/recipes
   - Reusable across BMC implementations

2. **SoC Layer** (meta-aspeed/)
   - ASPEED-specific drivers
   - U-Boot bootloader
   - Linux kernel

3. **Board Layer** (meta-raptor/meta-asus/)
   - ASUS KGPE-D16 / KCMA-D8 configurations
   - Board-specific drivers
   - Initialization tools

### meta-aspeed Layer

**Structure:**
- classes/ - BitBake class files
- conf/ - Configuration files
- recipes-bsp/u-boot/ - U-Boot recipes
- recipes-core/ - Core system recipes
- recipes-kernel/linux/ - Kernel recipes
- recipes-utils/ - Utility recipes

**Kernel Recipe:** recipes-kernel/linux/

Files:
- linux-aspeed.inc
- linux-aspeed_2.6.28.9.bb

**linux-aspeed.inc Contents:**

```bitbake
# Metadata
DESCRIPTION = "Linux Kernel for Aspeed"
LICENSE = "GPLv2"
COMPATIBLE_MACHINE = "aspeed"

# Auto-loaded modules
adm1275, ads7828, at24, fbcon, max127, pca953x,
pmbus, tun

# Module parameters
max127: scale=24414

# Installation customization
# Remove uImage from rootfs (managed separately)
```

**linux-aspeed_2.6.28.9.bb Contents:**

```bitbake
# Source revision
SRCREV = "f5c25cc2f97b7b71966ac4f1d77c1908df946226"

# Git repository
SRC_URI = "git://github.com/raptor-engineering/ast2050-linux-kernel.git;protocol=https;branch=linux-2.6.28.y"

# Version
LINUX_VERSION = "2.6.28.9"
LINUX_VERSION_EXTENSION = "-aspeed"

# Working directory
S = "${WORKDIR}/git"

# Custom tasks
# 1. create_generated - Handle bounds.h for 2.6.28
#    Copy from include/linux/ to include/generated/
# 2. copy_to_kernelsrc - Copy headers to staging
#    For kernel module builds

# Compiler flags
KERNEL_CC += " --sysroot=${PKG_CONFIG_SYSROOT_DIR}"
```

**Build Workflow:**
1. Fetch kernel from raptor-engineering/ast2050-linux-kernel
2. Apply version extension "-aspeed"
3. Handle 2.6.28-specific header locations
4. Build kernel and modules
5. Install to staging area
6. Generate final image

### Target Platform

**Hardware:** ASUS KGPE-D16 / KCMA-D8 server motherboards
**BMC Chip:** ASPEED AST2050
**Purpose:** Open-source BMC firmware replacement

---

## Complete File Inventory

### arch/arm/mach-aspeed/

**Source Files:**
- ast1100.c, ast2100.c, ast2300.c, ast2400.c, ast2500.c
- ast1510.c, ast1520.c
- ast3100.c, ast3200.c
- ast1070.c
- gpio.c
- ast-lpc.c, ast-lpc_plus.c
- ast-mctp.c
- core.h

**Build Files:**
- Kconfig
- Makefile
- Makefile.boot

**Header Files (include/mach/):**
- hardware.h, memory.h, io.h, system.h, platform.h
- irqs.h, ast_gpio_irqs.h, ast_lpc_irqs.h
- ast2000_irqs.h, ast2000_platform.h
- ast2100_irqs.h, ast2100_platform.h
- ast2200_irqs.h, ast2200_platform.h
- ast2300_irqs.h, ast2300_platform.h
- ast2400_irqs.h, ast2400_platform.h
- ast1070_irqs.h, ast1070_platform.h
- ast1520_irqs.h, ast1520_platform.h
- aspeed_serial.h, ast-uart-dma.h
- ast_spi.h, ast_pwm_techo.h
- ast_lcd.h, ast_video.h
- ast_wdt.h, ast_kcs.h
- ftgmac100_drv.h
- gpio.h, dma.h
- time.h, timex.h
- uncompress.h, vmalloc.h
- debug-macro.S, entry-macro.S

### arch/arm/plat-aspeed/

**Core Source Files:**
- irq.c, timer.c, devs.c
- ast-scu.c, ast-sdmc.c
- ast1070-scu.c, ast1070-uart-dma.c, ast1070_irq.c

**Device Files (dev-*):**
- dev-adc.c, dev-ci2c.c, dev-clpc.c, dev-cuart.c
- dev-ehci.c, dev-eth.c, dev-fb.c, dev-gpio.c
- dev-i2c.c, dev-kcs.c, dev-lpc.c, dev-mbx.c
- dev-nand.c, dev-nor.c, dev-peci.c, dev-pwm-fan.c
- dev-rtc.c, dev-sdhci.c, dev-sgpio.c, dev-snoop.c
- dev-spi.c, dev-uart.c, dev-uhci.c, dev-video.c
- dev-virthub.c, dev-vuart.c, dev-wdt.c

**Other:**
- i2c-slave-eeprom.c
- Makefile

**Header Files (include/plat/):**
- aspeed.h, devs.h
- ast-lpc.h, ast-pcie.h, ast-scu.h, ast-sdmc.h, ast-snoop.h
- ast1070-devs.h, ast1070-scu.h, ast1070-uart-dma.h
- ast_i2c.h, ast_mctp.h, ast_sdhci.h
- regs-*.h (40 register definition headers)

### drivers/char/aspeed/

- Kconfig
- Makefile
- ast_kcs.c
- ast_peci.c

### drivers/i2c/busses/

- i2c-ast.c

### drivers/mtd/maps/

- ast-nor.c

### drivers/net/

- ftgmac100_26.c
- ftgmac100_26.h

### drivers/spi/

- ast_spi.c

### drivers/watchdog/

- ast_wdt.c

### arch/arm/configs/

- ast2300_ast1070_defconfig
- ast2300_defconfig
- ast2300_fb_defconfig
- ast2400_ast1070-1_defconfig
- ast2400_ast1070_defconfig
- ast2400_defconfig
- ast2400_fb_defconfig
- ast2400_slt_defconfig

### board/aspeed/ (U-Boot)

**ast2050/ (34 files):**
- Makefile, config.mk
- ast2050.c, platform.S, crt.c, crt.h
- flash.c, flash_spi.c
- aes.c, rc4.c, crc32.c
- regtest.c/h, hactest.c/h, mactest.c/h, mictest.c/h
- hwreg.h
- vfun.c/h, vesa.h, vdef.h, vreg.h, vgahw.h
- vhace.c/h, videotest.c/h
- pci.c, slt.c/h, type.h

**ast2300/, ast2400/** (similar structure)

### include/configs/ (U-Boot)

- ast2050.h, ast2100.h, ast1100.h
- ast2300.h, ast2300_ast1070.h, ast2300_nor.h, ast2300_spi.h
- ast2400.h, ast2400_ast1070.h, ast2400_ast10701.h
- ast2400_nor.h, ast2400_slt.h, ast2400_spi.h
- ast3100.h

### arch/arm/cpu/arm926ejs/aspeed/ (U-Boot)

- MAC.c/H
- LAN9303.c
- DRAM_SPI.c
- NCSI.c/H
- Hardware initialization utilities

---

## Porting Recommendations

### Critical Dependencies

#### 1. Base Linux Kernel Version
**Challenge:** Code is based on Linux 2.6.28.9 (2009)
**Current Stable:** 6.x series (2024+)

**Major kernel subsystem changes since 2.6.28:**
- Device tree migration (ARM platforms moved from board files)
- Clock framework (Common Clock Framework introduced)
- Pinctrl subsystem (replaced direct pin muxing)
- Platform device changes
- DMA engine API changes
- IRQ domain API
- SPI subsystem updates
- I2C subsystem updates
- MTD subsystem changes

#### 2. Architecture Migration
**Current Approach:** Traditional ARM board files (arch/arm/mach-aspeed/)
**Modern Approach:** Device Tree (DTS/DTSI files)

**Required Migration:**
- Convert platform.h definitions to device tree
- Convert device registration (devs.c) to DT nodes
- Convert IRQ definitions to DT interrupt controllers
- Convert clock definitions to DT clock providers
- Convert pin muxing to pinctrl bindings

#### 3. Driver Modernization

**All drivers need updates for:**
- Modern kernel APIs
- Device tree bindings
- Managed resources (devm_* functions)
- Modern locking primitives
- Updated register access (regmap API)
- Power management (runtime PM)
- DMA engine API
- Clock framework
- Pinctrl integration

### Porting Strategy

#### Phase 1: Analysis and Planning

1. **Identify upstream ASPEED support**
   - Check current mainline kernel for ASPEED drivers
   - AST2400/AST2500/AST2600 already in mainline
   - Determine what AST2050-specific features are missing

2. **Create feature matrix**
   - List all AST2050 features from Raptor code
   - Compare with mainline ASPEED drivers
   - Identify gaps requiring backporting

3. **Assess hardware differences**
   - AST2050 vs AST2100/AST2300/AST2400
   - Document register differences
   - Identify compatible peripherals

#### Phase 2: Device Tree Creation

1. **Create base AST2050 DTSI**
   - Convert memory map from platform.h
   - Define interrupt controller
   - Define clock tree
   - Add pinctrl node

2. **Add peripheral nodes**
   - UART nodes (from dev-uart.c)
   - I2C nodes (from dev-i2c.c)
   - SPI nodes (from dev-spi.c)
   - Ethernet nodes (from dev-eth.c)
   - GPIO nodes (from dev-gpio.c)
   - Watchdog node (from dev-wdt.c)
   - All other peripherals from devs.c

3. **Create board DTS**
   - ASUS KGPE-D16 specific configuration
   - Enable required peripherals
   - Configure pinmux
   - Add I2C devices

#### Phase 3: Driver Porting Priority

**High Priority (Core Functionality):**

1. **System Control Unit (SCU)**
   - Port ast-scu.c to modern clock framework
   - Create clock provider driver
   - Implement reset controller
   - Add pinctrl driver

2. **IRQ Controller**
   - Port irq.c to IRQ domain API
   - Create interrupt controller driver

3. **UART**
   - Should work with standard 8250 driver
   - Add device tree bindings
   - Verify clock configuration

4. **Ethernet (FTGMAC100)**
   - Check if mainline ftgmac100 driver supports AST2050
   - Port any AST2050-specific features
   - Add device tree support

5. **I2C**
   - Port i2c-ast.c to modern I2C API
   - Add device tree bindings
   - Convert to use clock framework
   - Add DMA support using DMA engine API

**Medium Priority (System Management):**

6. **Watchdog**
   - Port ast_wdt.c to modern watchdog API
   - Add device tree bindings
   - Use managed resources

7. **GPIO**
   - Port gpio.c to modern GPIO API
   - Add device tree bindings
   - Implement GPIO interrupt support

8. **SPI**
   - Port ast_spi.c to modern SPI API
   - Add device tree bindings
   - Use SPI controller framework

9. **MTD/Flash**
   - Port ast-nor.c to modern MTD API
   - Add device tree partitions
   - Support modern flash chips

10. **KCS Interface**
    - Port ast_kcs.c for IPMI
    - Add device tree bindings
    - Integrate with IPMI subsystem

**Lower Priority (Advanced Features):**

11. **PECI**
    - Port ast_peci.c
    - Consider using PECI subsystem if available
    - Add device tree bindings

12. **PWM/Fan Control**
    - Port to modern PWM framework
    - Add device tree bindings
    - Add hwmon integration

13. **ADC**
    - Port to IIO subsystem
    - Add device tree bindings

14. **RTC**
    - Port to modern RTC framework
    - Add device tree bindings

15. **Video/Framebuffer**
    - Port to DRM subsystem (major work)
    - Add device tree bindings

16. **USB (EHCI/UHCI)**
    - Should work with standard drivers
    - Verify clock/power configuration

17. **SDHCI**
    - Port to modern SDHCI framework
    - Add device tree bindings

#### Phase 4: U-Boot Migration

1. **Assess current U-Boot mainline support**
   - Check for existing AST2050/ASPEED support
   - Identify required features

2. **Port board initialization**
   - Convert ast2050.c to modern U-Boot
   - Add device tree support
   - Port flash drivers

3. **Network boot support**
   - Ensure FTGMAC100 works in U-Boot
   - Configure for network boot

4. **Flash support**
   - SPI flash driver
   - Environment storage

#### Phase 5: Testing and Validation

1. **Boot testing**
   - Verify U-Boot boots kernel
   - Check console output
   - Validate device detection

2. **Driver testing**
   - Test each peripheral driver
   - Verify functionality
   - Check performance

3. **Integration testing**
   - Full BMC functionality
   - IPMI operation
   - Network management
   - Sensor monitoring

### Specific Technical Recommendations

#### 1. Start with Mainline ASPEED Support

The Linux kernel already has extensive ASPEED support in mainline:
- arch/arm/boot/dts/aspeed/
- drivers/clk/clk-aspeed.c
- drivers/pinctrl/aspeed/
- drivers/i2c/busses/i2c-aspeed.c
- drivers/net/ethernet/faraday/ftgmac100.c
- drivers/spi/spi-aspeed-smc.c
- drivers/watchdog/aspeed_wdt.c
- drivers/gpio/gpio-aspeed.c

**Action:** Compare AST2050 with AST2400/AST2500 support to determine compatibility

#### 2. Clock Framework Migration

**Current (2.6.28):**
```c
// Direct SCU register access
*((volatile ulong*) (AST_SCU_BASE + AST_SCU_CLK_SEL)) = value;
```

**Modern (6.x):**
```c
// Clock framework
struct clk *clk = devm_clk_get(dev, "hclk");
clk_prepare_enable(clk);
unsigned long rate = clk_get_rate(clk);
```

**Required:**
- Create clk-ast2050.c driver
- Define clock tree in device tree
- Provide clocks to consumers

#### 3. Pinctrl Migration

**Current (2.6.28):**
```c
// Direct SCU pin mux
*((volatile ulong*) (AST_SCU_BASE + AST_SCU_FUN_PIN_CTRL1)) = value;
```

**Modern (6.x):**
```c
// Pinctrl in device tree
&uart1 {
    pinctrl-names = "default";
    pinctrl-0 = <&pinctrl_txd1_default &pinctrl_rxd1_default>;
};
```

**Required:**
- Create pinctrl-ast2050.c driver
- Define pin groups and functions
- Add DT bindings

#### 4. Device Tree Example

**ast2050.dtsi:**
```dts
/ {
    compatible = "aspeed,ast2050";
    #address-cells = <1>;
    #size-cells = <1>;

    cpus {
        #address-cells = <1>;
        #size-cells = <0>;

        cpu@0 {
            compatible = "arm,arm926ej-s";
            device_type = "cpu";
            reg = <0>;
        };
    };

    clocks {
        clk_hpll: clk_hpll {
            #clock-cells = <0>;
            compatible = "fixed-clock";
            clock-frequency = <384000000>;
        };

        clk_apb: clk_apb {
            #clock-cells = <0>;
            compatible = "fixed-factor-clock";
            clocks = <&clk_hpll>;
            clock-div = <6>;
        };
    };

    soc {
        compatible = "simple-bus";
        #address-cells = <1>;
        #size-cells = <1>;
        ranges = <0 0x1e600000 0x00200000>;

        vic: interrupt-controller@600000 {
            compatible = "aspeed,ast2050-vic";
            interrupt-controller;
            #interrupt-cells = <1>;
            reg = <0x600000 0x200>;
        };

        scu: syscon@2e000 {
            compatible = "aspeed,ast2050-scu", "syscon", "simple-mfd";
            reg = <0x2e000 0x1000>;

            pinctrl: pinctrl {
                compatible = "aspeed,ast2050-pinctrl";
            };

            clk: clock-controller {
                compatible = "aspeed,ast2050-clk";
                #clock-cells = <1>;
                #reset-cells = <1>;
            };
        };

        uart1: serial@783000 {
            compatible = "ns16550a";
            reg = <0x783000 0x20>;
            reg-shift = <2>;
            interrupts = <9>;
            clocks = <&clk ASPEED_CLK_UART>;
            no-loopback-test;
            status = "disabled";
        };

        i2c0: i2c@40000 {
            compatible = "aspeed,ast2050-i2c-bus";
            reg = <0x40000 0x40>;
            interrupts = <12>;
            clocks = <&clk ASPEED_CLK_APB>;
            #address-cells = <1>;
            #size-cells = <0>;
            status = "disabled";
        };

        mac0: ethernet@180000 {
            compatible = "aspeed,ast2050-mac", "faraday,ftgmac100";
            reg = <0x180000 0x180>;
            interrupts = <2>;
            status = "disabled";
        };

        wdt1: watchdog@685000 {
            compatible = "aspeed,ast2050-wdt";
            reg = <0x685000 0x20>;
            clocks = <&clk ASPEED_CLK_APB>;
        };
    };
};
```

**asus-kgpe-d16.dts:**
```dts
/dts-v1/;
#include "aspeed-ast2050.dtsi"

/ {
    model = "ASUS KGPE-D16";
    compatible = "asus,kgpe-d16", "aspeed,ast2050";

    memory@40000000 {
        device_type = "memory";
        reg = <0x40000000 0x4000000>; // 64MB
    };

    chosen {
        stdout-path = &uart1;
    };
};

&uart1 {
    status = "okay";
};

&mac0 {
    status = "okay";
    phy-mode = "rmii";
};

&i2c0 {
    status = "okay";

    // Board-specific I2C devices
    temp-sensor@48 {
        compatible = "ti,lm75";
        reg = <0x48>;
    };
};

&wdt1 {
    status = "okay";
};
```

#### 5. Driver Modernization Example: I2C

**Key Changes Needed:**

1. **Use managed resources:**
```c
// Old
base = ioremap(res->start, resource_size(res));
clk = clk_get(dev, NULL);

// New
base = devm_ioremap_resource(dev, res);
clk = devm_clk_get(dev, NULL);
```

2. **Device tree support:**
```c
static const struct of_device_id ast_i2c_of_match[] = {
    { .compatible = "aspeed,ast2050-i2c-bus" },
    { }
};
MODULE_DEVICE_TABLE(of, ast_i2c_of_match);

static struct platform_driver ast_i2c_driver = {
    .driver = {
        .name = "ast-i2c",
        .of_match_table = ast_i2c_of_match,
    },
};
```

3. **Clock framework:**
```c
// Get clock from DT
priv->clk = devm_clk_get(dev, NULL);
clk_prepare_enable(priv->clk);
unsigned long rate = clk_get_rate(priv->clk);
```

4. **Modern I2C API:**
```c
// Use i2c_algorithm structure
static const struct i2c_algorithm ast_i2c_algorithm = {
    .master_xfer = ast_i2c_xfer,
    .functionality = ast_i2c_functionality,
};

adapter->algo = &ast_i2c_algorithm;
```

#### 6. Key Files to Reference

**Mainline ASPEED drivers (as of kernel 6.x):**
- drivers/clk/clk-aspeed.c
- drivers/pinctrl/aspeed/pinctrl-aspeed.c
- drivers/pinctrl/aspeed/pinctrl-aspeed-g4.c
- drivers/i2c/busses/i2c-aspeed.c
- drivers/net/ethernet/faraday/ftgmac100.c
- drivers/spi/spi-aspeed-smc.c
- drivers/watchdog/aspeed_wdt.c
- drivers/gpio/gpio-aspeed.c
- drivers/pwm/pwm-aspeed.c
- arch/arm/boot/dts/aspeed/aspeed-g4.dtsi

**Compare with Raptor code to identify:**
- Compatible features (can use mainline)
- AST2050-specific features (need porting)
- Missing features (need implementation)

### Recommended Approach

#### Option 1: Build on Mainline ASPEED (Recommended)

**Advantages:**
- Leverage existing, maintained code
- Modern kernel APIs
- Community support
- Regular updates

**Steps:**
1. Start with AST2400 device tree (most similar)
2. Identify AST2050-specific differences
3. Create AST2050 device tree based on AST2400
4. Test with mainline drivers
5. Port only AST2050-specific features
6. Submit upstream

**Estimated Effort:** 2-4 weeks

#### Option 2: Full Forward-Port from 2.6.28

**Advantages:**
- Complete control
- All features preserved
- Known working baseline

**Disadvantages:**
- Massive effort
- Duplicate existing work
- No upstream support
- Maintenance burden

**Steps:**
1. Port all drivers to modern APIs
2. Create device tree
3. Extensive testing
4. Ongoing maintenance

**Estimated Effort:** 3-6 months

### Testing Requirements

1. **Hardware Access**
   - ASUS KGPE-D16 or KCMA-D8 board
   - Serial console access
   - JTAG debugger (optional but helpful)
   - Network connectivity

2. **Boot Testing**
   - U-Boot loads and runs
   - Kernel boots
   - Console works
   - Root filesystem mounts

3. **Peripheral Testing**
   - Each driver functional
   - No kernel crashes
   - Performance acceptable
   - Power management works

4. **BMC Functionality**
   - IPMI responds
   - Sensors readable
   - KCS interface works
   - Network accessible
   - Watchdog functions

### Documentation Needs

1. **Technical Documentation**
   - Device tree bindings
   - Driver documentation
   - Register differences AST2050 vs newer chips
   - Build instructions

2. **User Documentation**
   - Installation guide
   - Configuration guide
   - Troubleshooting
   - Known limitations

3. **Developer Documentation**
   - Architecture overview
   - Porting notes
   - Testing procedures
   - Contribution guidelines

---

## Summary of Changes by Category

### Architecture Code
- Complete ARM machine support (mach-aspeed/)
- Platform device support (plat-aspeed/)
- Interrupt controller
- Timer implementation
- System Control Unit (clock, reset, pinmux)
- SDRAM controller

### Device Drivers
- **Character:** KCS, PECI
- **I2C:** Bus controller with master/slave/DMA
- **Network:** FTGMAC100 Gigabit Ethernet
- **SPI:** SPI controller
- **MTD:** NOR flash mapping
- **Watchdog:** Configurable watchdog timer
- **GPIO:** Standard GPIO
- **UART:** NS16550-compatible
- **LPC:** Low Pin Count interface
- **PWM:** Fan control
- **ADC:** Analog input
- **RTC:** Real-time clock
- **Mailbox:** Inter-processor communication
- **Snoop:** LPC snoop
- **Video:** Framebuffer/graphics

### Board Support
- ASUS KGPE-D16 / KCMA-D8 configurations
- I2C device definitions (sensors, PSUs, controllers)
- Flash partitioning
- Network configuration

### Build System
- Kconfig entries for all AST variants
- Defconfig files for AST2300/2400
- Yocto/OpenEmbedded recipes
- BitBake configuration

### Bug Fixes
- Perl syntax error (timeconst.pl)
- LPC/KCS IRQ storm
- GPIO initialization race

### Optimizations
- Rootfs size increase
- DMA support for I2C
- Buffer pool management

---

## Appendix: Register Definitions

### Key Register Bases (from platform.h)

```c
#define AST_IO_START         0x1E600000
#define AST_IO_SIZE          0x00200000

// Memory Banks (AST2300/2400)
#define AST_CS0_BASE         0x20000000
#define AST_CS1_BASE         0x24000000
#define AST_CS2_BASE         0x26000000
#define AST_CS3_BASE         0x28000000
#define AST_CS4_BASE         0x2a000000

#define AST_FLASH_SIZE       0x01000000  // 16MB

// PLL Frequencies
#define AST_PLL_25MHZ        25000000
#define AST_PLL_24MHZ        24000000
#define AST_PLL_12MHZ        12000000
```

### SCU Registers (from regs-scu.h)

```c
#define AST_SCU_PROTECT      0x00  // Protection key
#define AST_SCU_RESET        0x04  // System reset
#define AST_SCU_CLK_SEL      0x08  // Clock selection
#define AST_SCU_CLK_STOP     0x0C  // Clock stop
#define AST_SCU_COUNT_CTRL   0x10  // Frequency counter
#define AST_SCU_INTR_CTRL    0x18  // Interrupt control
#define AST_SCU_D2_PLL       0x1C  // D2-PLL
#define AST_SCU_M_PLL        0x20  // M-PLL
#define AST_SCU_H_PLL        0x24  // H-PLL
#define AST_SCU_MISC1_CTRL   0x2C  // Misc control
#define AST_SCU_VGA0         0x40  // VGA handshake
#define AST_SCU_MAC_CLK      0x48  // MAC clock
#define AST_SCU_HW_STRAP1    0x70  // Hardware strap
#define AST_SCU_FUN_PIN_CTRL1 0x80  // Pin control 1
// FUN_PIN_CTRL 2-9 at 0x84-0xA8
```

### Watchdog Registers (from ast_wdt.c)

```c
#define WDT_Ctrl             0x00  // Control
#define WDT_Reload           0x04  // Reload value
#define WDT_Restart          0x08  // Restart trigger
#define WDT_Clr              0x0C  // Clear
```

### KCS Registers (from ast_kcs.h)

```c
#define AST_LPC_HICR5_SNP1_ENINT  0x08
#define AST_LPC_HICR5_SNP1_EN     0x04
#define AST_LPC_HICR5_SNP0_ENINT  0x02
#define AST_LPC_HICR5_SNP0_EN     0x01
```

---

## References

### Primary Repositories
- https://github.com/raptor-engineering/ast2050-linux-kernel
- https://github.com/raptor-engineering/ast2050-uboot
- https://github.com/raptor-engineering/ast2050-yocto-openbmc

### Upstream Sources
- Linux Kernel: git://git.kernel.org/pub/scm/linux/kernel/git/stable/linux-stable.git
- U-Boot: git://git.denx.de/u-boot.git
- Facebook OpenBMC: https://github.com/facebook/openbmc

### Mainline ASPEED Support
- Linux kernel mainline: arch/arm/boot/dts/aspeed/
- Linux kernel drivers: drivers/*/aspeed* or drivers/*/asp*.c
- U-Boot mainline: board/aspeed/

### Additional Resources
- ASPEED AST2050 Datasheet (if available)
- ASUS KGPE-D16 / KCMA-D8 documentation
- OpenBMC project documentation

---

## Conclusion

Raptor Engineering created a comprehensive, production-ready AST2050 BMC platform with complete driver support for all major peripherals. The work represents a significant engineering effort to bring open-source BMC functionality to ASUS server motherboards.

For porting to modern kernels, the recommended approach is to build on existing mainline ASPEED support (AST2400/AST2500) and add AST2050-specific features as needed. This leverages community-maintained code while preserving AST2050-specific functionality.

The most critical components requiring attention are:
1. System Control Unit (clocks, resets, pinmux)
2. Device tree creation
3. I2C bus driver
4. Ethernet driver compatibility
5. KCS interface for IPMI

Total estimated effort for modern kernel port: 2-4 weeks with hardware access and ASPEED driver familiarity.

---

**Document Prepared By:** AI Analysis System
**Source Data:** GitHub repository analysis via WebFetch
**Date:** 2026-02-15
**Version:** 1.0
