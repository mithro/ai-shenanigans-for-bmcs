# Porting Raptor Engineering's AST2050 Work to Mainline Linux

## Background

Raptor Engineering created a working OpenBMC port for the Aspeed AST2050
BMC on the ASUS KGPE-D16 and KCMA-D8 server motherboards. Their work is
based on Linux 2.6.28.9 and was archived in June 2018. This document
catalogues every change they made and maps each one to the corresponding
mainline Linux subsystem that needs modification to bring AST2050 support
to a modern kernel.

**Test hardware:** ASUS KGPE-D16 or KCMA-D8 (same boards Raptor used)

### Raptor Repositories (all archived, read-only)

| Repository | Branch | Commits | Based On |
|---|---|---|---|
| [ast2050-linux-kernel](https://github.com/raptor-engineering/ast2050-linux-kernel) | linux-2.6.28.y | 4 | Linux 2.6.28.9 stable |
| [ast2050-uboot](https://github.com/raptor-engineering/ast2050-uboot) | master | 3 | U-Boot (commit 62c175f) |
| [ast2050-yocto-openbmc](https://github.com/raptor-engineering/ast2050-yocto-openbmc) | master | 21 | Facebook OpenBMC |

### AST2050 vs Mainline Aspeed Support

The mainline kernel supports three Aspeed generations:

| Generation | Chip | CPU | Clock | Mainline DTSI |
|---|---|---|---|---|
| G4 | AST2400 | ARM926EJ-S | 400 MHz | `aspeed-g4.dtsi` |
| G5 | AST2500 | ARM1176JZ-S | 800 MHz | `aspeed-g5.dtsi` |
| G6 | AST2600 | Dual Cortex-A7 | 1.2 GHz | `aspeed-g6.dtsi` |

The AST2050 (also sold as AST1100) is **not supported** in mainline. It
shares the ARM926EJ-S core with the AST2400 (G4) and has broadly
compatible register layouts, but with important differences:

| Feature | AST2050 | AST2400 |
|---|---|---|
| CPU | ARM926EJ-S @ 200 MHz | ARM926EJ-S @ 400 MHz |
| I2C engines | 7 (engines 0-6) | 14 (engines 0-13) |
| Input clock | Always 24 MHz | 24/25/48 MHz options |
| H-PLL strap | SCU70 bits [11:9] | SCU70 bits [9:8] |
| CPU:AHB ratio | SCU70 bits [13:12] | SCU70 bits [11:10] |
| DRAM base | 0x40000000 | 0x40000000 |
| I/O base | 0x1E600000 | 0x1E600000 |
| Ethernet | 10/100 only (RMII) | 10/100/1000 (RGMII/RMII) |
| USB EHCI | No | Yes |
| Boot address | 0x40008000 | 0x40008000 |

The `drivers/soc/aspeed/aspeed-socinfo.c` driver in mainline already
recognises AST2050 and AST1100 silicon IDs, but no device tree or
driver support exists beyond that.

---

## Raptor Kernel Commits

The Raptor kernel has exactly 4 commits on top of upstream Linux 2.6.28.9.

### Commit 1: fcbb27b -- Initial import of modified Linux 2.6.28 tree

This is the bulk commit containing all AST2050 platform and driver code.
It adds ~150 files across architecture support, platform devices, and
hardware drivers. Everything below in the "Changes to Port" section
comes from this commit.

### Commit 2: 30bdf6f -- Fix FTBFS from incorrect defined() in timeconst.pl

**File:** `kernel/timeconst.pl` (+1/-1)

```perl
# Before:
if (!defined(@val)) {
# After:
if (!@val) {
```

**Porting action:** None. This was a Perl syntax fix for building the
ancient 2.6.28 kernel with modern Perl. Not relevant to current kernels.

### Commit 3: 4d7aca1 -- Acknowledge LPC reset and related events in the KCS interface module

**Files:**
- `arch/arm/mach-aspeed/include/mach/ast_kcs.h` (+19/-13)
- `drivers/char/aspeed/ast_kcs.c` (+74/-3)

**Problem:** When the host CPU boots with the BMC already active, an IRQ
storm occurs on the shared LPC interrupt. The KCS driver was returning
`IRQ_NONE` for LPC reset (LRST), shutdown (SDWN), and abort (ABRT)
events without clearing the interrupt flags, causing infinite retriggering.

**Fix:** Clear each event's interrupt flag in HICR2 individually instead
of ignoring them. Added HICR5 register definitions for snoop interrupt
control. During probe, clear all pending interrupt flags and disable
snoop interrupts to prevent spurious IRQs.

**Key changes:**
- Added `ast_lpcreset_read_reg()` / `ast_lpcreset_write_reg()` helpers
- Added `ast_lpcreset_enable_interrupt()` / `ast_lpcreset_disable_interrupt()`
- IRQ handler now clears LRST, SDWN, ABRT flags individually
- Probe clears HICR2 and HICR5/HICR6 interrupt state on init
- Added HICR5 register bit definitions (SNP0/SNP1 enable and interrupt)

**Porting action:** The mainline `drivers/char/ipmi/kcs_bmc_aspeed.c`
driver handles KCS differently. Need to verify whether this IRQ storm
bug exists in the mainline driver and port the fix if so. See
[Change 14: KCS/IPMI Interface](#change-14-kcsipmi-interface) below.

### Commit 4: f5c25cc -- Increase rootfs size to handle additional userspace utilities

**File:** `arch/arm/plat-aspeed/dev-spi.c` (+2/-2)

```c
// Before:
.offset = 0x300000,  /* From 3M */
.size   = 0xCB0000,  /* Size 12.7M */
// After:
.offset = 0x240000,  /* From 2.4M */
.size   = 0xd70000,  /* Size 13.7M */
```

**Porting action:** None. Flash partitions are defined in the device tree
on modern kernels, not hardcoded in platform code. The partition layout
is board-specific and will be defined in the board `.dts` file.

---

## Changes to Port

Each section below describes a component from Raptor's kernel, what it
does, where the equivalent lives in mainline, and what specific work is
needed to add AST2050 support.

### Change 1: Machine Definition

**Raptor files:**
- `arch/arm/mach-aspeed/ast1100.c` -- MACHINE_START for AST1100/AST2050
- `arch/arm/mach-aspeed/Kconfig` -- CONFIG_ARCH_AST1100 option
- `arch/arm/mach-aspeed/Makefile` -- build rules
- `arch/arm/mach-aspeed/Makefile.boot` -- boot addresses (missing for AST1100!)
- `arch/arm/mach-aspeed/core.h`

**What it does:** Defines the ARM machine type, maps I/O regions, sets up
the interrupt controller, timer, and calls `ast_add_all_devices()` to
register all platform devices.

```c
MACHINE_START(ASPEED, "AST1100")
    .phys_io     = ASPEED_IO_START,
    .io_pg_offst = (IO_ADDRESS(IO_START)>>18) & 0xfffc,
    .map_io      = aspeed_map_io,
    .timer       = &aspeed_timer,
    .init_irq    = aspeed_init_irq,
    .init_machine = aspeed_init,
MACHINE_END
```

**Notable:** The AST1100 Makefile entry does NOT build `gpio.o` or
`ast-lpc.o` (unlike AST2100+). The Makefile.boot also has no entry for
AST1100, meaning boot addresses default to the AST2100 values
(zreladdr=0x40008000).

**Mainline equivalent:** None. Modern ARM Aspeed boards boot via device
tree, not MACHINE_START. The machine setup is in:
- `arch/arm/mach-aspeed/aspeed.c` (generic DT-based machine)

**Porting action:** No code changes needed here. The mainline
`aspeed_dt_init()` in `arch/arm/mach-aspeed/aspeed.c` handles all
Aspeed chips generically via device tree. The AST2050 just needs a
device tree (see Change 2).

### Change 2: Device Tree (Does Not Exist -- Must Create)

**Raptor files:** None. Raptor's kernel predates device tree adoption for
Aspeed. All hardware is registered via platform device code in
`arch/arm/plat-aspeed/devs.c`.

**Mainline equivalent:**
- `arch/arm/boot/dts/aspeed/aspeed-g4.dtsi` (AST2400 base)

**Porting action:** Create `aspeed-g3.dtsi` (or `aspeed-ast2050.dtsi`)
for the AST2050 generation. This is the single most important piece of
work. The file must define:

| Node | Source of truth (Raptor) | Key differences from G4 |
|---|---|---|
| CPU | `mach-aspeed/include/mach/platform.h` | Same ARM926EJ-S, lower clock |
| Memory map | `mach-aspeed/include/mach/platform.h` | Same base addresses |
| SCU/syscon | `plat-aspeed/ast-scu.c`, `regs-scu.h` | Different H-PLL strap bits |
| Interrupt controller | `plat-aspeed/irq.c`, `ast2000_irqs.h` | Same VIC, fewer IRQs? |
| Timer | `plat-aspeed/timer.c` | Same |
| I2C | `plat-aspeed/dev-i2c.c`, `regs-iic.h` | Only 7 engines (0-6) |
| GPIO | `plat-aspeed/dev-gpio.c`, `regs-gpio.h` | Same register layout |
| UART | `plat-aspeed/dev-uart.c` | Same NS16550, 24 MHz clock |
| Ethernet | `plat-aspeed/dev-eth.c` | 10/100 RMII only |
| FMC/SPI | `plat-aspeed/dev-spi.c`, `regs-spi.h` | Same controller |
| Watchdog | `plat-aspeed/dev-wdt.c` | Same |
| LPC/KCS | `plat-aspeed/dev-kcs.c`, `regs-lpc.h` | Same |
| PECI | `plat-aspeed/dev-peci.c`, `regs-peci.h` | Same |
| PWM/Fan | `plat-aspeed/dev-pwm-fan.c`, `regs-pwm_fan.h` | Same |
| ADC | `plat-aspeed/dev-adc.c`, `regs-adc.h` | Same |

The existing Dell C410X device tree (`aspeed-bmc-dell-c410x.dts`) already
uses `aspeed-g4.dtsi` as a base with the note that AST2050 and AST2400
share compatible register layouts. This is a pragmatic starting point,
but a proper `aspeed-g3.dtsi` should be created to avoid silently
referencing I2C engines 7-13 that don't exist on the AST2050.

**Initial test:** Create a minimal board DTS for the KGPE-D16 that
includes `aspeed-g4.dtsi` (like the C410X does) and enables only UART
and Ethernet. If the kernel boots to a console, the basic register
compatibility is confirmed. Then iteratively create a proper G3 dtsi.

### Change 3: System Control Unit (SCU) -- Clocks and Resets

**Raptor files:**
- `arch/arm/plat-aspeed/ast-scu.c` -- SCU implementation
- `arch/arm/plat-aspeed/include/plat/regs-scu.h` -- register definitions

**What it does:** Configures the clock tree (H-PLL, M-PLL, V-PLL), pin
muxing, module resets, and hardware strap detection. The clock tree is:

```
24 MHz crystal
  ├─> H-PLL ──> HCLK (CPU/AHB bus clock)
  ├─> M-PLL ──> MCLK (memory clock)
  └─> V-PLL ──> DCLK (display clock)
```

**Critical AST2050 vs AST2400 differences in SCU70 (Hardware Strap):**
- H-PLL frequency strap: bits [11:9] on AST2050, bits [9:8] on AST2400
- CPU:AHB clock ratio: bits [13:12] on AST2050, bits [11:10] on AST2400
- Input clock: always 24 MHz on AST2050 (no 25/48 MHz crystal options)

**Mainline equivalent:**
- `drivers/clk/clk-aspeed.c` -- clock provider (supports `aspeed,ast2400-scu` and `aspeed,ast2500-scu`)
- `drivers/reset/reset-aspeed.c` -- reset controller

**Porting action:**
1. Add `aspeed,ast2050-scu` compatible string to `clk-aspeed.c`
2. Add AST2050-specific H-PLL strap decoding (bits [11:9] instead of [9:8])
3. Add AST2050 CPU:AHB ratio decoding (bits [13:12] instead of [11:10])
4. Force 24 MHz input clock (ignore crystal detection)
5. Add compatible to `reset-aspeed.c` (likely works as-is with just the string)

The Dell C410X device tree already overrides the SCU compatible to
`"aspeed,ast2050-scu", "aspeed,ast2400-scu"` for this reason.

### Change 4: Pinctrl / Pin Muxing

**Raptor files:**
- `arch/arm/plat-aspeed/ast-scu.c` (pin mux functions within SCU driver)
- `arch/arm/plat-aspeed/include/plat/regs-scu.h` (SCU80-SCU9C pin ctrl registers)

**What it does:** Configures multi-function pins via SCU registers
SCU80-SCU9C. Functions include I2C bus enables, UART routing, Ethernet
mode (RMII/RGMII), NAND/NOR selection, SD card pins, USB pins.

**Mainline equivalent:**
- `drivers/pinctrl/aspeed/pinctrl-aspeed.c` -- core pinctrl
- `drivers/pinctrl/aspeed/pinctrl-aspeed-g4.c` -- G4 pin definitions
- `drivers/pinctrl/aspeed/pinmux-aspeed.h` -- pin mux helpers

**Porting action:**
1. Create `pinctrl-aspeed-g3.c` with AST2050 pin definitions
2. The pin mux register offsets (SCU80-SCU9C) appear identical between
   AST2050 and AST2400, but the available functions may differ (fewer
   pins, no RGMII, no EHCI USB)
3. Register the pin groups and functions
4. Add `aspeed,ast2050-pinctrl` compatible string

**Shortcut for testing:** The AST2400 pinctrl driver may work as-is for
the pins that exist on both chips. Test with `aspeed,ast2400-pinctrl`
first and create G3-specific driver only if pin mux failures occur.

### Change 5: SDRAM Memory Controller (SDMC)

**Raptor files:**
- `arch/arm/plat-aspeed/ast-sdmc.c`
- `arch/arm/plat-aspeed/include/plat/regs-sdmc.h`

**What it does:** Configures SDRAM timing, ECC, and provides memory size
detection for the SoC info driver.

**Mainline equivalent:**
- `drivers/soc/aspeed/aspeed-socinfo.c` -- reads SDMC for memory info

**Porting action:** The socinfo driver already has AST2050/AST1100
silicon ID recognition. Verify that the SDMC base address and register
layout match. The SDMC is at `0x1E6E0000` on both AST2050 and AST2400.

### Change 6: Interrupt Controller

**Raptor files:**
- `arch/arm/plat-aspeed/irq.c`
- `arch/arm/mach-aspeed/include/mach/ast2000_irqs.h` (IRQ numbers for AST1100/AST2050)
- `arch/arm/plat-aspeed/include/plat/regs-intr.h`

**What it does:** Initialises the Aspeed VIC (Vectored Interrupt
Controller) at `0x1E6C0000`.

**AST2050 IRQ assignments** (from `ast2000_irqs.h`):
```
IRQ 0:  UART0          IRQ 16: Timer2
IRQ 1:  UART1          IRQ 17: Timer3
IRQ 2:  MAC0           IRQ 18: Crypto
IRQ 3:  MAC1           IRQ 19: (reserved)
IRQ 4:  USB1.1         IRQ 20: GPIO
IRQ 5:  USB2.0         IRQ 21: SCU
IRQ 6:  PCIe/MCTP      IRQ 22: ADC
IRQ 7:  NOR/SPI        IRQ 23: (reserved)
IRQ 8:  VUART          IRQ 24: (reserved)
IRQ 9:  LPC            IRQ 25: CRT
IRQ 10: I2C            IRQ 26: SD/MMC
IRQ 11: (reserved)     IRQ 27: (reserved)
IRQ 12: Video          IRQ 28: (reserved)
IRQ 13: 2D             IRQ 29: (reserved)
IRQ 14: WDT            IRQ 30: (reserved)
IRQ 15: Timer1         IRQ 31: (reserved)
```

**Mainline equivalent:**
- The aspeed-g4.dtsi uses a standard `"aspeed,ast2400-vic"` interrupt
  controller node. The VIC driver is generic for ARM VIC.

**Porting action:** Verify IRQ assignments match between AST2050 and
AST2400. If they match (likely), the G4 VIC node can be reused in the
G3 dtsi. If they differ, create a separate interrupt map.

### Change 7: Timer

**Raptor files:**
- `arch/arm/plat-aspeed/timer.c`

**What it does:** System timer using the Aspeed timer peripheral at
`0x1E782000`. Standard ARM timer with configurable prescaler.

**Mainline equivalent:** Handled by device tree timer nodes in the dtsi.
The Aspeed timer driver in mainline (`drivers/clocksource/timer-fttmr010.c`)
supports the Faraday FTTMR010 timer used by all Aspeed chips.

**Porting action:** Add the timer node to the G3 dtsi. Should work
as-is since all Aspeed generations use the same timer IP block.

### Change 8: I2C Controller

**Raptor files:**
- `drivers/i2c/busses/i2c-ast.c` -- bus driver
- `arch/arm/plat-aspeed/dev-i2c.c` -- platform device registration
- `arch/arm/plat-aspeed/include/plat/regs-iic.h` -- register definitions
- `arch/arm/plat-aspeed/include/plat/ast_i2c.h` -- platform data

**What it does:** Full I2C master/slave controller driver supporting:
- Byte mode (single-byte transfers)
- Buffer/pool mode (multi-byte via on-chip SRAM pools)
- DMA mode (direct memory access transfers)
- SMBus block read/write
- Up to 14 buses (but AST2050 only has 7: engines 0-6)

**I2C engine register base:** `0x1E78A000` with 0x40 stride per engine.

**Mainline equivalent:**
- `drivers/i2c/busses/i2c-aspeed.c`

**Porting action:**
1. Add `"aspeed,ast2050-i2c-bus"` compatible string to `i2c-aspeed.c`
2. Verify register layout compatibility (base and stride are identical)
3. In the G3 dtsi, define only I2C engines 0-6 (not 7-13)
4. Verify clock divisor calculation works with 24 MHz input

**Risk:** Low. The I2C controller IP is the same across generations; only
the number of engines differs.

### Change 9: GPIO Controller

**Raptor files:**
- `arch/arm/mach-aspeed/gpio.c` -- GPIO driver
- `arch/arm/plat-aspeed/dev-gpio.c` -- platform device
- `arch/arm/plat-aspeed/include/plat/regs-gpio.h` -- register definitions

**What it does:** GPIO controller at `0x1E780000`. Ports A-H (64 pins)
with interrupt support (edge/level configurable), direction control, and
data registers. Higher ports (I-P, Q-T) available on some variants.

**Mainline equivalent:**
- `drivers/gpio/gpio-aspeed.c`

**Porting action:**
1. Add `"aspeed,ast2050-gpio"` compatible string to `gpio-aspeed.c`
2. Verify the number of available GPIO ports/pins on AST2050
3. The register layout at `0x1E780000` is the same across generations

**Risk:** Low. GPIO controller is register-compatible.

### Change 10: Ethernet (FTGMAC100)

**Raptor files:**
- `drivers/net/ftgmac100_26.c` -- Ethernet MAC driver
- `drivers/net/ftgmac100_26.h` -- header
- `arch/arm/plat-aspeed/dev-eth.c` -- platform device

**What it does:** Faraday FTGMAC100 Gigabit MAC supporting:
- Dual MAC (MAC0, MAC1)
- PHY modes: RMII, MII, RGMII (AST2050 only supports RMII/MII)
- NC-SI sideband management
- Supported PHYs: Marvell, Broadcom (BCM54612E, BCM54616S), Realtek (RTL8201EL, RTL8211BN)

**Mainline equivalent:**
- `drivers/net/ethernet/faraday/ftgmac100.c`

**Porting action:**
1. Add `"aspeed,ast2050-mac"` compatible string to `ftgmac100.c`
2. The mainline driver already supports `"aspeed,ast2400-mac"` which
   uses the same MAC IP block
3. AST2050 is 10/100 only via RMII -- verify the driver doesn't
   assume gigabit capability when it sees an Aspeed compatible
4. The SCU MAC clock delay configuration (SCU48) may differ

**Risk:** Low-medium. The MAC IP is the same; the main concern is
the PHY interface configuration in the SCU.

### Change 11: SPI / Flash Memory Controller (FMC)

**Raptor files:**
- `drivers/spi/ast_spi.c` -- SPI host driver
- `drivers/mtd/maps/ast-nor.c` -- NOR flash mapping
- `arch/arm/plat-aspeed/dev-spi.c` -- platform device with partition table
- `arch/arm/plat-aspeed/include/plat/regs-spi.h` -- register definitions
- `arch/arm/plat-aspeed/include/plat/regs-fmc.h` -- FMC register definitions

**What it does:** SPI NOR flash access for the BMC firmware storage.
Supports chips: STM25P64, STM25P128, S25FL128P, MX25L128D, W25X64.

**Mainline equivalent:**
- `drivers/spi/spi-aspeed-smc.c` (combined FMC + SPI controller)
- `drivers/mtd/spi-nor/` (standard SPI NOR framework)

**Porting action:**
1. Add `"aspeed,ast2050-fmc"` and `"aspeed,ast2050-spi"` compatible
   strings to `spi-aspeed-smc.c`
2. Verify FMC base address and register layout match AST2400
3. Flash partitions go in the board DTS, not driver code

**Risk:** Low. The FMC/SPI controller is register-compatible.

### Change 12: Watchdog

**Raptor files:**
- `drivers/watchdog/ast_wdt.c`
- `arch/arm/plat-aspeed/dev-wdt.c`

**What it does:** Watchdog timer at `0x1E785000` (offset from timer base).
Features: configurable timeout (default 30s, max 65536s), dual-boot
mode, SOC/full-chip/ARM-only reset modes.

**Mainline equivalent:**
- `drivers/watchdog/aspeed_wdt.c`

**Porting action:**
1. Add `"aspeed,ast2050-wdt"` compatible string to `aspeed_wdt.c`
2. The watchdog registers are identical across generations

**Risk:** Very low.

### Change 13: PECI (Platform Environment Control Interface)

**Raptor files:**
- `drivers/char/aspeed/ast_peci.c`
- `arch/arm/plat-aspeed/dev-peci.c`
- `arch/arm/plat-aspeed/include/plat/regs-peci.h`

**What it does:** PECI controller at `0x1E78B000` for reading CPU die
temperatures from the host server. Interrupt-driven, supports timing
negotiation, data transfer up to 32 bytes, FCS validation.

**Mainline equivalent:**
- `drivers/peci/controller/peci-aspeed.c`

**Porting action:**
1. Add `"aspeed,ast2050-peci"` compatible string
2. Verify register compatibility
3. The PECI IP block should be the same across generations

**Note:** The KGPE-D16 uses AMD Opteron CPUs which use PECI for thermal
monitoring. Verify PECI works with AMD PECI protocol (vs Intel).

**Risk:** Low-medium. PECI protocol may have AMD-specific quirks.

### Change 14: KCS/IPMI Interface

**Raptor files:**
- `drivers/char/aspeed/ast_kcs.c`
- `arch/arm/mach-aspeed/include/mach/ast_kcs.h`
- `arch/arm/plat-aspeed/dev-kcs.c`
- `arch/arm/plat-aspeed/include/plat/regs-lpc.h`

**What it does:** KCS (Keyboard Controller Style) interface for IPMI
host-to-BMC communication over the LPC bus. The LPC host interface
controller (HIC) is at `0x1E789000`.

**Critical bug fix from commit 4d7aca1:** The IRQ handler must clear
LRST, SDWN, and ABRT interrupt flags individually in HICR2, otherwise
an IRQ storm occurs during host boot. The handler must also disable
snoop interrupts (HICR5) and clear snoop status (HICR6) during
initialisation.

**Mainline equivalent:**
- `drivers/char/ipmi/kcs_bmc_aspeed.c`

**Porting action:**
1. Add `"aspeed,ast2050-kcs-bmc"` compatible string
2. Verify the mainline driver handles LPC reset events correctly
   (the IRQ storm bug may already be fixed differently, or may still
   exist for AST2050)
3. The LPC register layout should be compatible
4. Check HICR5 snoop interrupt handling exists in mainline

**Risk:** Medium. The IRQ storm fix is critical for a working system.
The mainline KCS driver has been significantly rewritten since Raptor's
2.6.28 version and may handle this differently.

### Change 15: PWM / Fan Control

**Raptor files:**
- `arch/arm/plat-aspeed/dev-pwm-fan.c`
- `arch/arm/plat-aspeed/include/plat/regs-pwm_fan.h`

**What it does:** PWM controller at `0x1E786000` for fan speed control.
8 PWM channels and fan tachometer inputs. On the KGPE-D16, only 2
channels are wired: channel 1 for CPU fans (4-pin), channel 2 for
chassis fans (3-pin).

**Mainline equivalent:**
- `drivers/pwm/pwm-aspeed-g4.c` (G4 PWM)
- `drivers/hwmon/aspeed-pwm-tacho.c` (combined PWM + tach hwmon)

**Porting action:**
1. Add `"aspeed,ast2050-pwm-tacho"` compatible string
2. Verify register compatibility
3. Configure fan zone mapping in the board DTS

**Risk:** Low.

### Change 16: ADC (Analog to Digital Converter)

**Raptor files:**
- `arch/arm/plat-aspeed/dev-adc.c`
- `arch/arm/plat-aspeed/include/plat/regs-adc.h`

**What it does:** ADC at `0x1E6E9000` for voltage monitoring.

**Mainline equivalent:**
- `drivers/iio/adc/aspeed_adc.c` (IIO subsystem, not hwmon)

**Porting action:**
1. Add `"aspeed,ast2050-adc"` compatible string
2. Verify register compatibility and number of channels

**Risk:** Low.

### Change 17: Video / Framebuffer

**Raptor files:**
- `drivers/video/astfb.c` -- old-style framebuffer driver
- `arch/arm/plat-aspeed/dev-fb.c`
- `arch/arm/plat-aspeed/dev-video.c`
- `arch/arm/plat-aspeed/include/plat/regs-video.h`
- `arch/arm/plat-aspeed/include/plat/regs-crt.h`

**What it does:** 2D VGA graphics engine with 8 MB dedicated VRAM.
Provides KVM remote console capability.

**Mainline equivalent:**
- `drivers/gpu/drm/ast/` -- DRM driver (note: this driver explicitly
  says it does NOT support AST1100 due to lack of test hardware)
- `drivers/media/platform/aspeed/aspeed-video.c` -- video capture

**Porting action:** The mainline DRM AST driver does not support
AST1100/AST2050. This is low priority for BMC functionality (headless
operation). Skip unless KVM console is needed.

**Risk:** High effort, low priority for BMC use case.

### Change 18: USB Host (UHCI)

**Raptor files:**
- `drivers/usb/astuhci/` -- custom UHCI driver (5 files)
- `arch/arm/plat-aspeed/dev-uhci.c`

**What it does:** USB 1.1 host controller. The AST2050 has UHCI only
(no EHCI/USB 2.0). Used for USB virtual media and keyboard/mouse
emulation for KVM.

**Mainline equivalent:**
- Standard `drivers/usb/host/uhci-hcd.c` should work
- `arch/arm/plat-aspeed/dev-ehci.c` exists but is for AST2400+ only

**Porting action:**
1. Add USB UHCI node to the G3 dtsi
2. Verify the standard UHCI driver works with Aspeed's implementation
3. Do NOT add EHCI -- AST2050 doesn't have it

**Risk:** Medium. The custom UHCI driver may exist because the standard
one doesn't work with Aspeed's USB controller variant.

### Change 19: LPC Bus Interface

**Raptor files:**
- `arch/arm/mach-aspeed/ast-lpc.c`
- `arch/arm/plat-aspeed/dev-lpc.c`
- `arch/arm/plat-aspeed/include/plat/regs-lpc.h`
- `arch/arm/plat-aspeed/include/plat/ast-lpc.h`

**What it does:** LPC (Low Pin Count) bus interface at `0x1E789000`.
Provides host-to-BMC communication channels: KCS, BT (Block Transfer),
UART, snoop, and mailbox.

**Note:** The AST1100 Makefile does NOT build `ast-lpc.o` (only
AST2100+ builds it). This suggests the AST1100/AST2050 has a simpler
LPC interface or the KGPE-D16 doesn't use advanced LPC features.

**Mainline equivalent:**
- `drivers/soc/aspeed/aspeed-lpc-ctrl.c`
- `drivers/soc/aspeed/aspeed-lpc-snoop.c`

**Porting action:**
1. Add AST2050 compatible strings
2. Verify which LPC features are used on the KGPE-D16
3. The basic KCS interface (Change 14) is the critical LPC feature

**Risk:** Low for basic KCS; medium for advanced LPC features.

### Change 20: Mailbox

**Raptor files:**
- `arch/arm/plat-aspeed/dev-mbx.c`
- `arch/arm/plat-aspeed/include/plat/regs-mbx.h`

**What it does:** Inter-processor mailbox for host-BMC communication.

**Mainline equivalent:**
- Part of the LPC subsystem in mainline

**Porting action:** Add to G3 dtsi if needed. Low priority.

**Risk:** Low.

### Change 21: Snoop Engine

**Raptor files:**
- `arch/arm/plat-aspeed/dev-snoop.c`
- `arch/arm/plat-aspeed/include/plat/ast-snoop.h`

**What it does:** LPC POST code snooping -- captures BIOS POST codes
written to I/O port 0x80 by the host CPU during boot.

**Mainline equivalent:**
- `drivers/soc/aspeed/aspeed-lpc-snoop.c`

**Porting action:** Add compatible string. Low priority for KGPE-D16
testing (POST code snoop is a nice-to-have, not essential).

### Change 22: RTC (Real-Time Clock)

**Raptor files:**
- `arch/arm/plat-aspeed/dev-rtc.c`
- `arch/arm/plat-aspeed/include/plat/regs-rtc.h`

**Mainline equivalent:**
- Standard RTC drivers; the Aspeed RTC may be compatible with an
  existing driver.

**Porting action:** Add RTC node to G3 dtsi. Low priority.

### Change 23: Serial GPIO (SGPIO)

**Raptor files:**
- `arch/arm/plat-aspeed/dev-sgpio.c`

**What it does:** Serial GPIO for LED control and other uses.

**Mainline equivalent:**
- `drivers/gpio/sgpio-aspeed.c`

**Porting action:** Add compatible string if SGPIO is used on the
KGPE-D16. Check board schematics.

### Change 24: Virtual UART

**Raptor files:**
- `arch/arm/plat-aspeed/dev-vuart.c`
- `arch/arm/plat-aspeed/include/plat/regs-vuart.h`

**What it does:** Virtual UART that appears as a COM port to the host
CPU via LPC, providing Serial Over LAN (SOL) capability.

**Mainline equivalent:**
- `drivers/tty/serial/8250/8250_aspeed_vuart.c`

**Porting action:** Add compatible string. The VUART IP block should
be the same across generations.

### Change 25: SDHCI (SD/MMC Host Controller)

**Raptor files:**
- `arch/arm/plat-aspeed/dev-sdhci.c`
- `arch/arm/plat-aspeed/include/plat/ast_sdhci.h`

**Mainline equivalent:**
- `drivers/mmc/host/sdhci-of-aspeed.c`

**Porting action:** Add compatible string if SD card slot exists on
the KGPE-D16. Low priority.

### Change 26: JTAG

**Raptor files:**
- `arch/arm/plat-aspeed/include/plat/regs-jtag.h`

**What it does:** JTAG master controller. The KGPE-D16 has an
unpopulated JTAG footprint (AST_JTAG1) that requires soldering.

**Mainline equivalent:**
- `drivers/jtag/jtag-aspeed.c`

**Porting action:** Low priority. Only needed for debugging.

---

## Platform-Level Infrastructure Files

These files from Raptor's `arch/arm/plat-aspeed/` provide the
infrastructure that connects all the above drivers. In a modern
kernel, this infrastructure is replaced by device tree + standard
frameworks.

| Raptor File | Purpose | Modern Equivalent |
|---|---|---|
| `devs.c` | Register all platform devices | Device tree nodes |
| `ast-scu.c` | Clock, reset, pinmux control | `clk-aspeed.c` + `pinctrl-aspeed.c` + `reset-aspeed.c` |
| `ast-sdmc.c` | Memory controller setup | `aspeed-socinfo.c` |
| `irq.c` | Interrupt controller init | VIC driver + DT |
| `timer.c` | System timer setup | `timer-fttmr010.c` + DT |
| `i2c-slave-eeprom.c` | I2C slave EEPROM emulation | `drivers/i2c/i2c-slave-eeprom.c` |

---

## Header Files (Register Definitions)

The Raptor register definition headers in
`arch/arm/plat-aspeed/include/plat/regs-*.h` are the most valuable
reference material. They document every register offset and bit field
for each peripheral. The mainline drivers have their own register
definitions (typically inline in the driver `.c` file), but the Raptor
headers provide a complete cross-reference.

| Header | Peripheral | Base Address |
|---|---|---|
| `regs-scu.h` | System Control Unit | 0x1E6E2000 |
| `regs-sdmc.h` | SDRAM Controller | 0x1E6E0000 |
| `regs-iic.h` | I2C Controller | 0x1E78A000 |
| `regs-gpio.h` | GPIO Controller | 0x1E780000 |
| `regs-lpc.h` | LPC Interface | 0x1E789000 |
| `regs-intr.h` | Interrupt Controller | 0x1E6C0000 |
| `regs-spi.h` | SPI Controller | 0x1E620000 |
| `regs-fmc.h` | Flash Memory Controller | 0x1E620000 |
| `regs-peci.h` | PECI Controller | 0x1E78B000 |
| `regs-pwm_fan.h` | PWM/Fan Controller | 0x1E786000 |
| `regs-adc.h` | ADC | 0x1E6E9000 |
| `regs-rtc.h` | RTC | -- |
| `regs-video.h` | Video Engine | -- |
| `regs-crt.h` | CRT/VGA | -- |
| `regs-vuart.h` | Virtual UART | -- |
| `regs-mbx.h` | Mailbox | -- |
| `regs-mctp.h` | MCTP | -- |
| `regs-pcie.h` | PCIe | -- |
| `regs-jtag.h` | JTAG | -- |
| `regs-udc11.h` | USB Device Controller | -- |
| `regs-uart-dma.h` | UART DMA | -- |
| `regs-smc.h` | Static Memory Controller | -- |
| `regs-scu-g5.h` | SCU (G5 additions) | -- |

---

## U-Boot Changes

Raptor's U-Boot repo has 3 commits. The key content is in the initial
import.

### Board Support: `board/aspeed/ast2050/` (34 files)

| File | Purpose |
|---|---|
| `ast2050.c` | Main board init (DRAM, GPIO, clocks) |
| `platform.S` | Assembly startup |
| `flash.c` / `flash_spi.c` | Flash driver |
| `crt.c` | C runtime |
| `pci.c` | PCI support |
| `aes.c` / `rc4.c` / `crc32.c` | Crypto utilities |
| `*test.c` | Hardware test routines |
| `v*.c` / `v*.h` | Video/VGA support |

### U-Boot Config: `include/configs/ast2050.h`

Key settings:
- DRAM: 64 MB at 0x40000000
- Flash: 8 MB SPI at 0x14000000
- Console: UART2 at 0x1E784000, 115200 bps
- Boot: `bootm 14080000 14300000`
- Boot args: `console=ttyS1,115200n8 ramdisk_size=16384 root=/dev/ram rw init=/linuxrc mem=80M`
- Network: static IP 192.168.0.188
- Environment: offset 0x7F0000, size 64 KB

### GPIO Init Fix (commit 323b3ac)

Conditional GPIO bank A initialisation to prevent spurious host
operation during boot. Checks if GPIO A4 direction bit is already
set before configuring it.

### GCC 6 Fix (commit 537b8cc)

Added `compiler-gcc6.h` for GCC 6.x compatibility.

**Porting action for U-Boot:** Modern U-Boot already has Aspeed AST2400
support. The AST2050 support would follow a similar pattern -- add
`ast2050_defconfig`, board file, and device tree. This is separate from
the Linux kernel porting and can be done in parallel.

---

## Yocto / OpenBMC Build System

**Repository:** `ast2050-yocto-openbmc` (based on Facebook OpenBMC)

### Machine Configuration

```
meta-aspeed/conf/machine/include/ast1250.inc:
  PREFERRED_VERSION_linux-aspeed = "2.6.28%"
  KERNEL_IMAGETYPE = "uImage"
  KERNEL_EXTRA_ARGS = "UIMAGE_LOADADDR=0x40008000"
  UBOOT_ENTRYPOINT = "0x40008000"
  UBOOT_MACHINE = "ast1250_config"
  tune-arm926ejs.inc (ARM CPU tuning)

meta-aspeed/conf/machine/include/ast2050.inc:
  UBOOT_MACHINE = "ast2050_config"
  (inherits ast1250.inc)
```

### Kernel Recipe

```
meta-aspeed/recipes-kernel/linux/linux-aspeed_2.6.28.9.bb:
  SRCREV = "f5c25cc2f9..."  (latest Raptor kernel commit)
  SRC_URI = "git://github.com/raptor-engineering/ast2050-linux-kernel.git"
  LINUX_VERSION = "2.6.28.9"
```

### Auto-loaded Modules

The Yocto recipe auto-loads these kernel modules:
`adm1275`, `ads7828`, `at24`, `fbcon`, `max127`, `pca953x`, `pmbus`, `tun`

### ASUS Board Layer (`meta-raptor/meta-asus/`)

Board-specific configuration for KGPE-D16/KCMA-D8:
- `kernel-module-i2c-dev-sysfs`
- `kernel-module-cpld`
- `kernel-module-com-e-driver`
- Uses `eglibc` as C library

### Fan Control

Custom fan daemon at:
`common/recipes-core/fan-ctrl/fan-ctrl/fand.cpp`

Implements a custom fan curve for the KGPE-D16 using:
- PWM channel 1: CPU fans (4-pin)
- PWM channel 2: Chassis fans (3-pin)

**Porting action for Yocto:** For modern OpenBMC, the Yocto
configuration would be completely rewritten using current OpenBMC
meta-layers. The fan control daemon logic is the main piece worth
preserving.

---

## Recommended Porting Order

Assuming ASUS KGPE-D16 hardware is available:

### Phase 1: Boot to Console

1. Create minimal KGPE-D16 device tree using `aspeed-g4.dtsi` as base
2. Enable UART1 (console at 115200)
3. Build kernel with Aspeed G4 defconfig
4. Boot via TFTP using existing U-Boot on the board
5. **Success criterion:** Linux prints boot messages to serial console

### Phase 2: Network

6. Enable MAC0 with RMII PHY mode
7. Test ping/SSH connectivity
8. **Success criterion:** BMC is reachable over the network

### Phase 3: Clocks (if Phase 1 fails)

9. Add `aspeed,ast2050-scu` support to `clk-aspeed.c`
10. Fix H-PLL strap decoding for AST2050 bit positions
11. **Success criterion:** Correct clock frequencies reported

### Phase 4: I2C and Sensors

12. Enable I2C buses 0-6 in the device tree
13. Scan for devices with `i2cdetect`
14. Add temperature sensor, EEPROM, and other I2C device nodes
15. **Success criterion:** `sensors` command shows temperatures

### Phase 5: Management

16. Enable KCS interface for IPMI
17. Test `ipmitool` from the host
18. Enable watchdog
19. Enable GPIO for LED and button control
20. **Success criterion:** Full IPMI functionality

### Phase 6: Proper G3 DTSI

21. Create `aspeed-g3.dtsi` factoring out AST2050-specific definitions
22. Update KGPE-D16 DTS to use G3 dtsi instead of G4
23. Submit upstream patches

---

## Open Questions

1. **SCU70 strap bits:** Are the H-PLL strap bit positions actually
   different, or does the G4 clock driver happen to work on AST2050?
   The only way to know is to boot and check clock frequencies.

2. **I2C engine count:** Does the mainline I2C driver fail gracefully
   when engines 7-13 are referenced in the G4 dtsi but don't exist on
   the AST2050? Or does it crash? The G3 dtsi must only define engines
   0-6.

3. **LPC IRQ storm:** Is the IRQ storm bug (Raptor commit 4d7aca1)
   present in the mainline KCS driver? Needs testing with the host
   powered on.

4. **USB UHCI:** Does the standard Linux UHCI driver work with
   Aspeed's USB controller, or is the custom `astuhci` driver needed?

5. **PECI with AMD:** Does PECI work with AMD Opteron CPUs on the
   KGPE-D16? AMD's implementation may differ from Intel's.

6. **Ethernet PHY:** What specific PHY chip is on the KGPE-D16 BMC
   Ethernet port? This determines whether PHY auto-detection works
   or a specific PHY driver is needed.
