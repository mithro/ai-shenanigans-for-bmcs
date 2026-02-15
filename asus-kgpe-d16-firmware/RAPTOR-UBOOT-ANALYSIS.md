# Raptor Engineering AST2050 U-Boot Analysis

## Repository Overview

| Field | Value |
|-------|-------|
| **Repository** | [raptor-engineering/ast2050-uboot](https://github.com/raptor-engineering/ast2050-uboot) |
| **Base U-Boot Version** | **2013.07** |
| **Base Upstream Hash** | `62c175fbb8a0f9a926c88294ea9f7e88eb898f6c` (from git.denx.de) |
| **Created** | 2017-08-23 |
| **Archived** | 2018-06-05 (read-only) |
| **Total Commits** | 3 |
| **CPU Architecture** | ARM926EJ-S |
| **Board Name** | `asus` (in `boards.cfg`) |

### Commits

| # | SHA | Date | Description |
|---|-----|------|-------------|
| 1 | `0223e59` | 2017-08-23 | Initial import of modified U-Boot tree |
| 2 | `323b3ac` | 2017-08-26 | Initialize GPIO bank A during U-Boot phase to prevent spurious host operation |
| 3 | `537b8cc` | 2017-08-28 | Add missing `compiler-gcc6.h` file (build fix) |

Unlike the Linux kernel (which was 2.6.28 from 2008), the U-Boot base is much more
recent (2013.07), and the codebase already included Aspeed support for AST2300 and
AST2400. The AST2050 board support was added alongside these, sharing much of the
SoC-level code.

---

## What Mainline U-Boot Supports Today

Mainline U-Boot (2025) supports:

| SoC | CPU Core | Status |
|-----|----------|--------|
| **AST2500** | ARM1176JZF-S | Full support (`evb-ast2500_defconfig`) |
| **AST2600** | Cortex-A7 (dual) | Full support (`evb-ast2600_defconfig`) |
| **AST2700** | RISC-V | Initial support (`ibex-ast2700_defconfig`) |
| **AST2050** | ARM926EJ-S | **No support** |
| **AST2400** | ARM926EJ-S | **No support** |

**Zero references to AST2050, AST2100, AST1100, or AST2400 exist in mainline U-Boot.**

The mainline architecture lives under `arch/arm/mach-aspeed/` with subdirectories
for `ast2500/` and `ast2600/` only. The Kconfig offers a choice between
`ASPEED_AST2500` and `ASPEED_AST2600`.

---

## Aspeed-Specific File Inventory

All files below are part of the Aspeed vendor SDK included in Raptor's fork.
Many are shared between AST2050/AST2300/AST2400 with `#ifdef` guards.

### 1. SoC-Level Code (`arch/arm/cpu/arm926ejs/aspeed/`)

These files handle core SoC functionality shared across all ARM926EJ-S Aspeed
parts (AST2050, AST2100, AST1100, AST2300, AST2400):

| File | Lines | Purpose |
|------|-------|---------|
| `timer.c` | 135 | Timer driver using Timer1 at `0x1E782000`. Provides `timer_init()`, `get_timer()`, `__udelay()`. Uses `CONFIG_ASPEED_TIMER_CLK` and `CONFIG_SYS_HZ`. |
| `reset.c` | 24 | `reset_cpu()` via watchdog at `0x1E785000`. Writes reload=0x10, restart=0x4755, control=0x23 for full chip reset. |
| `Makefile` | ~50 | Builds all SoC objects including test/diagnostic utilities. |
| `COMMINF.H` | 641 | Common infrastructure definitions for test utilities. |
| `SWFUNC.H` | 137 | Switch function definitions for hardware testing. |
| `TYPEDEF.H` | 74 | Type definitions for vendor test code. |
| `IO.H` / `IO.c` | 36/355 | I/O helper functions for register access during testing. |
| `LIB.H` / `LIB.c` | 37/184 | Library functions for vendor test utilities. |
| `MAC.H` / `MAC.c` | 157/~0 | MAC test register definitions. |
| `mactest.c` | 1214 | Ethernet MAC hardware test utility. |
| `PHY.H` / `PHY.c` | 56/1541 | PHY test code for all supported PHY types. |
| `NCSI.H` / `NCSI.c` | 189/934 | NC-SI (Network Controller Sideband Interface) test code. |
| `PLLTESTU.H` / `PLLTESTU.c` | 50/409 | PLL frequency test utility. |
| `STDUBOOT.H` / `STDUBOOT.c` | 17/224 | Standard U-Boot test interface. |
| `TRAPTEST.c` | 151 | Hardware trap/strap test utility. |
| `STRESS.c` | 144 | Memory stress test utility. |
| `SPIM.c` | 63 | SPI master test utility. |
| `DRAM_SPI.c` | 78 | DRAM-to-SPI test utility. |
| `PCI_SPI.c` | 83 | PCI-SPI bridge test utility. |
| `DEF_SPI.H` / `LIB_SPI.H` | 35/23 | SPI test definitions. |
| `LAN9303.c` | 525 | Microchip LAN9303 switch test code. |

> **Key insight:** Most of the files in this directory are **hardware test/diagnostic
> utilities** from Aspeed's SDK, not core boot code. Only `timer.c` and `reset.c` are
> essential for boot. The test utilities are useful for hardware bring-up but are not
> needed for a production U-Boot build.

### 2. Board-Level Code (`board/aspeed/ast2050/`)

| File | Lines | Purpose |
|------|-------|---------|
| `ast2050.c` | ~150 | **Main board init**: `board_init()`, `dram_init()`, `misc_init_r()`, PCI init. Unlocks AHB/SCU, sets PCLK divider, configures GPIO (ASUS-specific), detects chip revision. |
| `platform.S` | ~500 | **Critical**: Low-level DDR2 SDRAM controller init written in ARM assembly. Runs before C environment. Sets MPLL to 200MHz, programs DDR2 timing, runs calibration, outputs UART debug messages. |
| `hwreg.h` | ~200 | Hardware register address definitions for SDRAM controller, SCU, timers, GPIO, interrupt controller, watchdog, UART, AHB. |
| `config.mk` | 16 | Sets `CONFIG_SYS_TEXT_BASE = 0x00000000` (boot from SPI flash mapped to 0x0). |
| `Makefile` | ~40 | Builds board objects. |
| `flash.c` | ~300 | NOR flash driver (CFI). |
| `flash_spi.c` | 836 | **SPI flash driver**: Aspeed SPI controller flash access (read/write/erase). Maps SPI flash at `0x14000000`. |
| `pci.c` | ~80 | PCI controller driver using CSR at `0x60000000`. Type 0/1 configuration, I/O and memory access. PCI memory at `0x68000000` (384MB). |
| `slt.c` | ~100 | System Level Test framework. |
| `crc32.c` | ~40 | CRC32 utility for hardware test. |
| `aes.c` / `rc4.c` | ~100 | Crypto test utilities. |
| `crt.c/h` | ~100 | CRT (video) output test. |
| `vfun.c/h`, `vhace.c/h`, `videotest.c/h` | ~300 | Video/VGA test utilities. |
| `regtest.c/h` | ~100 | Register test utilities. |
| `mactest.c/h`, `mictest.c/h`, `hactest.c/h` | ~200 | MAC, MIC, HAC test utilities. |
| `type.h`, `vdef.h`, `vesa.h`, `vgahw.h`, `vreg.h` | ~200 | Hardware definitions for video/VGA subsystem. |

### 3. Drivers (`drivers/`)

| File | Lines | Purpose |
|------|-------|---------|
| `drivers/net/aspeednic.c` | 1619 | **Ethernet MAC driver**: FTGMAC100-compatible. Supports MAC1 at `0x1E660000`, MAC2 at `0x1E680000`. MII/RMII PHY access, NCSI support, TX/RX descriptor ring DMA. Multi-SoC: `#ifdef` for AST2050/AST2300/AST2400. |
| `drivers/i2c/aspeed_i2c.c` | ~200 | **I2C controller driver**: Byte-mode master using I2C base at `0x1E78A000`. Channel 5 for AST2050 (ASUS EEPROM). Pin mux via SCU register `0x74` (AST2050) vs `0x90` (others). |

### 4. Include Files (`include/configs/`)

Board/SoC configuration headers define memory map, peripherals, boot parameters:

| File | Target |
|------|--------|
| `ast2050.h` | **AST2050** (ASUS KGPE-D16) - Primary config |
| `ast1100.h` | AST1100 (pin-compatible with AST2050) |
| `ast2100.h` | AST2100 |
| `ast3100.h` | AST3100 |
| `ast2300.h` | AST2300 |
| `ast2300_spi.h` | AST2300 SPI boot variant |
| `ast2300_nor.h` | AST2300 NOR boot variant |
| `ast2300_ast1070.h` | AST2300 + AST1070 companion |
| `ast2400.h` | AST2400 |
| `ast2400_spi.h` | AST2400 SPI boot variant |
| `ast2400_nor.h` | AST2400 NOR boot variant |
| `ast2400_ast1070.h` | AST2400 + AST1070 companion |
| `ast2400_ast10701.h` | AST2400 + AST1070 variant |
| `ast2400_slt.h` | AST2400 SLT (System Level Test) |

### 5. Architecture Include (`arch/arm/include/asm/arch-aspeed/`)

| File | Purpose |
|------|---------|
| `aspeed_i2c.h` | I2C register definitions, per-SoC channel mapping, command/status bits. AST2050 uses channel 5 vs channel 3/4 for other SoCs. |

### 6. Build Configuration (`boards.cfg`)

```
# Board              Arch        CPU         Board dir     Vendor     Config
asus                 arm         arm926ejs   ast2050       aspeed     aspeed
wedge100             arm         arm926ejs   ast2400       aspeed     aspeed
fbyosemite           arm         arm926ejs   ast2400       aspeed     aspeed
fbplatform1          arm         arm926ejs   ast2400       aspeed     aspeed
```

The ASUS board is built with: `make asus_config && make`

---

## Detailed Component Analysis

### A. DDR2 SDRAM Controller Initialization (`platform.S`)

This is the most critical piece of code — it runs from the reset vector before any
C code, initializing DDR2 SDRAM so U-Boot can be loaded.

**Key sequence:**
1. Unlock SCU registers (key `0x1688A8A8` to `0x1E6E2000`)
2. Check scratch register bit 6 (skip if DRAM already initialized)
3. Set MPLL to 200MHz (`0x00004c81` → `0x1E6E2020`)
4. Initialize UART2 for debug output (prints "DRAM Init-DDR")
5. Unlock SDRAM controller (key `0xFC600309` to `0x1E6E0000`)
6. Configure DLL registers
7. Set DDR2 configuration register (MCR04) — supports 512MB and 1GB DDR2
8. Program AC timing registers (normal and low-speed modes)
9. Set IO buffer mode, DLL control, test registers
10. Enable power, program MRS/EMRS mode registers
11. Set refresh timing
12. Set scratch register bit 6 to indicate DRAM init complete
13. Lock SCU and SDRAM registers

**Register map used:**

| Address | Register | Purpose |
|---------|----------|---------|
| `0x1E6E2000` | SCU_KEY_CONTROL | SCU unlock (key: `0x1688A8A8`) |
| `0x1E6E2008` | SCU_CLK_SELECT | Clock divider config |
| `0x1E6E2020` | SCU_M_PLL_PARAM | MPLL (DDR clock) - 200MHz |
| `0x1E6E2040` | SCU_SOC_SCRATCH1 | Boot flags (bit 6=DRAM done, bit 7=init in progress) |
| `0x1E6E2070` | SCU_HW_STRAPPING | VGA memory size selection (bits 3:2) |
| `0x1E6E207C` | SCU_REV_ID | Chip ID and revision detection |
| `0x1E6E0000` | SDRAM_PROTECTION_KEY | SDRAM unlock (key: `0xFC600309`) |
| `0x1E6E0004` | SDRAM_CONFIG | DDR config (1GB DDR2: `0x00000d89`) |
| `0x1E6E0008` | SDRAM_GRAP_MEM_PROTECTION | Graphics memory protection |
| `0x1E6E0010` | SDRAM_NSPEED_REG1 | Normal speed AC timing |
| `0x1E6E0018` | SDRAM_NSPEED_REG2 | Normal speed AC timing (cont) |
| `0x1E6E0020` | SDRAM_NSPEED_DELAY_CTRL | Delay control (normal) |
| `0x1E6E0028` | SDRAM_MODE_SET_CTRL | MRS/EMRS mode control |
| `0x1E6E002C` | SDRAM_MRS_EMRS2 | MRS mode register values |
| `0x1E6E0030` | SDRAM_MRS_EMRS3 | EMRS mode register values |
| `0x1E6E0034` | SDRAM_PWR_CTRL | Power control |
| `0x1E6E0060` | SDRAM_IO_BUFF_MODE | IO buffer mode |
| `0x1E6E0064` | SDRAM_DLL_CTRL1 | DLL control |
| `0x1E6E0120` | AST2100_COMPAT_MPLL | Backward-compatible MPLL register |

### B. Board Initialization (`ast2050.c`)

**`board_init()`:**
1. Unlock AHB controller (`0xAEED1A03` → `0x1E600000`)
2. Remap DRAM to `0x00000000` (bit 0 of `0x1E60008C`)
3. Enable flash write access
4. Unlock SCU, set PCLK = HPLL/8, enable 2D clock
5. **ASUS-specific GPIO init** (`#ifdef ASUS_CONFIGURE_GPIO`):
   - Set GPIO PA4 as output (bit 4 of GPIO base `0x1E780000`)
   - Configure GPIO PH0 and PH1 (offset `0x20` and `0x24` from GPIO base)
   - Only drive PA4 high if it isn't already
6. Set machine type to `MACH_TYPE_ASPEED`
7. Set boot params at `0x40000100`

**`misc_init_r()`:**
- Reads chip revision from `0x1E6E207C`
- Chip ID byte 24: 0=AST2050/AST2150, 1=AST2300
- Initializes PCI if configured
- Sets default `verify=n`, `eeprom=y` environment variables

### C. GPIO Hardening (Commit `323b3ac`)

Raptor's second commit adds a safety check to the GPIO initialization:

```c
// Before (could inadvertently toggle host signals):
*((volatile ulong*) (AST_GPIO_BASE+0x04)) |= 0x00000010;

// After (only set if not already set):
if (!((*((volatile ulong*) (AST_GPIO_BASE+0x04))) & 0x00000010)) {
    *((volatile ulong*) (AST_GPIO_BASE+0x00)) |= 0x00000010;
    *((volatile ulong*) (AST_GPIO_BASE+0x04)) |= 0x00000010;
}
```

This prevents spurious host signals during BMC reboot — critical for a server BMC
where accidentally asserting a GPIO could trigger an unintended host power event.

### D. Ethernet Driver (`aspeednic.c`)

The Aspeed NIC driver is a substantial piece (~1600 lines) implementing:

- **FTGMAC100** MAC controller at `0x1E660000` (MAC1) and `0x1E680000` (MAC2)
- TX/RX descriptor ring DMA engine
- MII/RMII PHY management via MDIO
- NC-SI support for shared network controllers
- PHY detection and configuration
- Pin mux setup via SCU registers (different for AST2050 vs AST2300+)

**AST2050-specific differences from AST2300+:**
```c
#if defined(CONFIG_AST2300_FPGA_2) || defined(CONFIG_AST2300) || ...
  #define MAC1_MDIO   (1 << 31)  // SCU88 pin mux
  #define MAC1_MDC    (1 << 30)
  #define MAC2_MDC_MDIO  (1 << 2)  // SCU90
#else  // AST2050
  #define MAC2_MDC_MDIO  (1 << 20)  // Different SCU register layout
  #define MAC2_MII       (1 << 21)
  #define MAC1_PHY_LINK  (1 << 25)
  #define MAC2_PHY_LINK  (1 << 26)
#endif
```

### E. I2C Driver (`aspeed_i2c.c`)

Key differences for AST2050:
- **Channel 5** (vs channel 3 for AST2100, channel 4 for AST2200/2300/2400)
- Pin mux register at SCU offset `0x74` (vs `0x90` for AST2300+)
- Pin mux value `0x5000` (vs `0x30000` for AST2300+)

The ASUS firmware was observed constantly polling `/dev/i2c1` and trying `/dev/i2c4`
at startup — channel 5 was chosen for U-Boot's EEPROM access to avoid conflicts.

### F. SPI Flash Driver (`flash_spi.c`)

836 lines implementing read/write/erase for SPI NOR flash:
- SPI controller mapped at `0x16000000` (AST2050 static memory controller)
- Flash mapped at `0x14000000` (PHYS_FLASH_1)
- Supports sector erase, page program, read ID
- Environment stored in flash at offset `0x7F0000` (64KB)

### G. Memory Map Summary

| Address | Size | Description |
|---------|------|-------------|
| `0x00000000` | - | Reset vector (SPI flash mapped here initially, remapped to DRAM) |
| `0x10000000` | - | Secondary SPI flash base (if CONFIG_2SPIFLASH) |
| `0x14000000` | 8MB | SPI Flash Bank #1 (`PHYS_FLASH_1`) |
| `0x14800000` | 8MB | SPI Flash Bank #2 (`PHYS_FLASH_2`) |
| `0x16000000` | - | Static Memory Controller (flash controller registers) |
| `0x1E600000` | - | AHB Controller |
| `0x1E660000` | - | MAC1 (Ethernet) |
| `0x1E680000` | - | MAC2 (Ethernet) |
| `0x1E6C0000` | - | Interrupt Controller |
| `0x1E6E0000` | - | SDRAM Controller |
| `0x1E6E2000` | - | SCU (System Control Unit) |
| `0x1E780000` | - | GPIO Controller |
| `0x1E782000` | - | Timer Controller |
| `0x1E783000` | - | UART1 |
| `0x1E784000` | - | UART2 (console) |
| `0x1E785000` | - | Watchdog Timer |
| `0x1E78A000` | - | I2C Controller |
| `0x40000000` | 64MB | DRAM (`PHYS_SDRAM_1`, 64MB default) |
| `0x43000000` | - | Default load address |
| `0x60000000` | - | PCI CSR Base |
| `0x68000000` | 384MB | PCI Memory Space |

### H. Boot Configuration (`ast2050.h`)

Key settings from the board config header:

```c
CONFIG_ARM926EJS          1
CONFIG_ASPEED             1
CONFIG_AST2050            1
CONFIG_DDRII1G_200        1          // 1GB DDR2 at 200MHz

// Boot
CONFIG_BOOTARGS     "debug console=ttyS1,115200n8 ramdisk_size=16384 root=/dev/ram rw init=/linuxrc mem=80M"
CONFIG_BOOTCOMMAND  "bootm 14080000 14300000"
CONFIG_BOOTDELAY    3

// Console on UART2
CONFIG_CONS_INDEX   2
CONFIG_BAUDRATE     115200
CONFIG_SYS_NS16550_CLK   24000000
CONFIG_SYS_NS16550_COM1  0x1e783000  // UART1
CONFIG_SYS_NS16550_COM2  0x1e784000  // UART2

// Memory
PHYS_SDRAM_1       0x40000000
PHYS_SDRAM_1_SIZE  0x4000000        // 64 MB (but bootargs say mem=80M)

// Flash
PHYS_FLASH_1       0x14000000
CONFIG_ENV_OFFSET  0x7F0000
CONFIG_ENV_SIZE    0x010000          // 64KB

// I2C
CONFIG_SYS_I2C_SPEED    100000
CONFIG_DRIVER_ASPEED_I2C

// Network
CONFIG_ASPEEDNIC
CONFIG_MAC1_PHY_SETTING  0           // Dedicated PHY (not NC-SI)
CONFIG_IPADDR       192.168.0.188
CONFIG_SERVERIP     192.168.0.126
```

---

## Porting Gap Analysis: Raptor U-Boot → Modern U-Boot

### What exists in mainline that can be reused

Mainline U-Boot for AST2500/AST2600 uses the modern Driver Model (DM) framework.
The AST2050 vendor code uses the old pre-DM style with direct register access.

| Component | Mainline (AST2500+) | Reusable for AST2050? |
|-----------|--------------------|-----------------------|
| `arch/arm/mach-aspeed/` | Kconfig, Makefile | Structure reusable, needs new SoC dir |
| `arch/arm/mach-aspeed/ast_wdt.c` | Watchdog | Possibly — AST2050 WDT is similar |
| Timer driver (DM) | `drivers/timer/` | May have Aspeed timer, needs adaptation |
| UART (NS16550) | `drivers/serial/ns16550.c` | **Directly reusable** — standard 16550 |
| Ethernet | `drivers/net/ftgmac100.c` | Mainline has FTGMAC100 driver, likely reusable |
| SPI flash | `drivers/mtd/spi/` | Mainline SPI framework, needs Aspeed SPI controller support |
| I2C | `drivers/i2c/` | Mainline has Aspeed I2C for AST2500+, may need adaptation |
| Device Tree | `arch/arm/dts/` | Need new DTS for AST2050 |

### What needs to be created from scratch

| Component | Effort | Description |
|-----------|--------|-------------|
| **DRAM init (platform.S)** | High | AST2050 DDR2 controller init is completely different from AST2500's DDR4. Must be ported from Raptor's assembly code. This is not something that can be derived from datasheet — it requires the exact calibration sequence. |
| **Kconfig/Makefile** | Low | Add `ASPEED_AST2050` choice with `select CPU_ARM926EJS`. |
| **SoC init code** | Medium | SCU unlock, clock config, pin mux — different register layout from AST2500+. |
| **Device tree** | Medium | New `.dts` file describing AST2050 peripherals. |
| **SPI flash controller** | Medium | AST2050 uses static memory controller at `0x16000000`, different from AST2500's SPI controller. |
| **Board file** | Low | ASUS KGPE-D16 specific board init (GPIO, etc). |

### What can be adapted from the Raptor vendor code

| Raptor File | Modern Equivalent | Adaptation Needed |
|------------|-------------------|-------------------|
| `platform.S` (DRAM init) | SPL or inline assembly | Keep as-is — DRAM init is magic timing sequences that must be exact |
| `timer.c` | DM timer driver | Wrap in DM framework |
| `reset.c` | DM reset/sysreset driver | Wrap in DM, or reuse `ast_wdt.c` |
| `aspeednic.c` | `drivers/net/ftgmac100.c` | Use mainline FTGMAC100 with AST2050 pin mux |
| `aspeed_i2c.c` | `drivers/i2c/ast_i2c.c` | Adapt mainline driver, add AST2050 channel/pin config |
| `flash_spi.c` | `drivers/mtd/spi/` + SPI controller | Need AST2050 SPI controller driver |
| `ast2050.c` | Board file in DM style | Rewrite for modern U-Boot board init |

---

## Phased Porting Plan

### Phase 1: Boot to Console (Minimum Viable)

**Goal:** U-Boot prompt on UART2 with working DRAM.

1. Create `arch/arm/mach-aspeed/ast2050/` with Kconfig, Makefile
2. Add `ASPEED_AST2050` to Kconfig with `select CPU_ARM926EJS`
3. Port `platform.S` DRAM init (the assembly is self-contained, mostly portable)
4. Port `timer.c` (simple, ~135 lines)
5. Port `reset.c` (trivial, ~24 lines)
6. Configure NS16550 UART (already supported — just set base addresses)
7. Create minimal `ast2050-evb_defconfig`
8. Create device tree with UART, timer, memory nodes

**Key challenge:** The `platform.S` DRAM init code uses hard-coded register addresses
through `hwreg.h` defines. It needs no driver framework — it runs before C, so it's
self-contained assembly. This should be relatively straightforward to port.

### Phase 2: SPI Flash + Environment

**Goal:** U-Boot can read/write its environment and load images from SPI flash.

1. Port/adapt SPI flash controller driver for AST2050's static memory controller
2. Configure flash partitioning (kernel at `0x14080000`, rootfs at `0x14300000`)
3. Verify environment persistence across reboots

### Phase 3: Network Boot

**Goal:** TFTP boot for faster development iteration.

1. Use mainline `ftgmac100.c` driver with AST2050 pin mux configuration
2. Add AST2050-specific SCU pin mux setup for MAC1 MDIO/MDC
3. Configure PHY settings for the ASUS board's dedicated PHY

### Phase 4: I2C + EEPROM

**Goal:** Read board identification and configuration.

1. Adapt mainline Aspeed I2C driver for AST2050 register differences
2. Configure channel 5 for EEPROM access
3. Add EEPROM commands

### Phase 5: Device Tree and Upstream

**Goal:** Clean device tree, upstreamable code.

1. Create proper `aspeed-ast2050.dtsi` (SoC) and `aspeed-bmc-asus-kgpe-d16.dts` (board)
2. Convert all drivers to use DM (Driver Model)
3. Submit patches to U-Boot mailing list

---

## Key Differences: AST2050 vs AST2500

| Feature | AST2050 | AST2500 |
|---------|---------|---------|
| CPU Core | ARM926EJ-S | ARM1176JZF-S |
| DRAM Type | DDR2 | DDR4 |
| DRAM Controller | `0x1E6E0000` (different register set) | `0x1E6E0000` (different register set) |
| SCU Layout | Legacy register layout | Extended register layout |
| SPI Controller | Static Memory Controller `0x16000000` | FMC `0x1E620000` |
| I2C Pin Mux | SCU offset `0x74` | SCU offset `0x90` |
| I2C EEPROM Channel | 5 | 4 |
| Ethernet Pin Mux | Legacy SCU bits | SCU88/SCU90 |
| Boot Method | SPI flash → `0x00000000` | SPI flash → `0x00000000` |
| PCI | Yes (CSR at `0x60000000`) | Not typically used |

---

## Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| DRAM init porting | **High** | Raptor's `platform.S` is self-contained assembly with extensive comments. Port as-is. |
| SPI controller differences | **Medium** | AST2050 uses `0x16000000` vs AST2500's `0x1E620000`. Need new controller driver or adapt flash_spi.c |
| Pin mux differences | **Low** | Well-documented in Raptor code via `#ifdef CONFIG_AST2050` blocks |
| U-Boot framework changes | **Medium** | 2013.07 → 2025.xx is a large gap. Must convert from old board style to DM. |
| Missing AST2050 datasheet | **High** | Register definitions come from Raptor's reverse engineering + Aspeed SDK code. No public datasheet. |
