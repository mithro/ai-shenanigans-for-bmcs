# Raptor Engineering AST2050 Changes - Executive Summary

## Quick Reference Guide

**Date:** 2026-02-15

---

## Repository Links

1. **Linux Kernel:** https://github.com/raptor-engineering/ast2050-linux-kernel
2. **U-Boot:** https://github.com/raptor-engineering/ast2050-uboot
3. **Yocto OpenBMC:** https://github.com/raptor-engineering/ast2050-yocto-openbmc

All repositories archived 2018-06-05 (read-only)

---

## Linux Kernel Commits (4 total)

### 1. fcbb27b - Initial import of modified Linux 2.6.28 tree (2017-08-23)
**The main commit with all AST2050 support**

#### Architecture Files Added
- `/arch/arm/mach-aspeed/` - Machine-specific code (14 files)
- `/arch/arm/plat-aspeed/` - Platform code (38+ files)
- `/arch/arm/configs/ast*_defconfig` - 8 configuration files

#### Drivers Added
- `/drivers/char/aspeed/` - KCS, PECI (2 drivers)
- `/drivers/i2c/busses/i2c-ast.c` - I2C bus controller
- `/drivers/net/ftgmac100_26.c` - Gigabit Ethernet
- `/drivers/spi/ast_spi.c` - SPI controller
- `/drivers/mtd/maps/ast-nor.c` - NOR flash
- `/drivers/watchdog/ast_wdt.c` - Watchdog

### 2. 30bdf6f - Fix FTBFS from incorrect defined() in timeconst.pl (2017-08-23)
One-line Perl syntax fix to enable kernel compilation.

### 3. 4d7aca1 - Acknowledge LPC reset in KCS module (2017-08-25)
Fixes IRQ storm during host boot. Changes:
- `arch/arm/mach-aspeed/include/mach/ast_kcs.h` (+19/-13)
- `drivers/char/aspeed/ast_kcs.c` (+74/-3)

### 4. f5c25cc - Increase rootfs size (2017-08-26)
Expands rootfs from 12.7MB to 13.7MB in flash partition table.
- `arch/arm/plat-aspeed/dev-spi.c`

---

## U-Boot Commits (3 total)

### 1. 0223e59 - Initial import of modified u-boot tree (2017-08-23)
- Added `/board/aspeed/ast2050/` (34 files)
- Added `/include/configs/ast2050.h`
- Added `/arch/arm/cpu/arm926ejs/aspeed/`

### 2. 323b3ac - Initialize GPIO bank A (2017-08-26)
Prevents spurious host operation during boot.
- `board/aspeed/ast2050/ast2050.c`

### 3. 537b8cc - Add missing compiler-gcc6.h (2017-08-28)
Enables GCC 6.x compilation.

---

## Complete Driver List

### Character Devices
- **KCS** - IPMI keyboard controller interface
- **PECI** - CPU thermal monitoring

### Bus Controllers
- **I2C** - Master/slave with byte/buffer/DMA modes
- **SPI** - Serial peripheral interface
- **LPC** - Low pin count bus

### Network
- **FTGMAC100** - Gigabit Ethernet with NCSI

### Storage
- **NOR Flash** - CFI flash mapping
- **NAND Flash** - NAND support (platform layer)

### GPIO/Interrupts
- **GPIO** - General purpose I/O
- **SGPIO** - Serial GPIO
- **VIC** - Vectored interrupt controller

### Timers/Watchdog
- **Watchdog** - Configurable timeout, dual-boot
- **Timer** - System timer
- **RTC** - Real-time clock

### Power/Thermal
- **PWM/Fan** - Fan control
- **ADC** - Analog to digital converter

### Serial
- **UART** - NS16550-compatible (4 ports)
- **Virtual UART** - BMC virtual console

### USB
- **EHCI** - USB 2.0 host
- **UHCI** - USB 1.1 host
- **UDC** - USB device controller

### Video
- **Framebuffer** - Display support
- **Video Engine** - 2D graphics
- **CRT** - VGA output

### Management
- **Mailbox** - Inter-processor communication
- **Snoop** - LPC snooping
- **Virtual Hub** - Management interface

### System
- **SCU** - System control (clocks, resets, pinmux)
- **SDMC** - SDRAM controller

---

## Hardware Support Matrix

### Supported AST Chips
| Chip | IRMP | PC Extender | RemoteFX | Companion |
|------|------|-------------|----------|-----------|
| AST1100 | ✓ | - | - | - |
| AST2100 | ✓ | - | - | - |
| AST2300 | ✓ | - | - | - |
| AST2400 | ✓ | - | - | - |
| AST2500 | ✓ | - | - | - |
| AST1510 | - | ✓ | - | - |
| AST1520 | - | ✓ | - | - |
| AST3100 | - | - | ✓ | - |
| AST3200 | - | - | ✓ | - |
| AST1070 | - | - | - | ✓ |

### Target Boards
- ASUS KGPE-D16 (server motherboard)
- ASUS KCMA-D8 (server motherboard)

---

## Memory Map

```
Physical Memory:
0x1E600000 - 0x1E7FFFFF  I/O region (2MB)
0x20000000 - 0x20FFFFFF  CS0 (16MB NOR flash)
0x24000000 - 0x24FFFFFF  CS1
0x26000000 - 0x26FFFFFF  CS2
0x28000000 - 0x28FFFFFF  CS3
0x2A000000 - 0x2AFFFFFF  CS4
0x40000000 - 0x43FFFFFF  DRAM (64MB)

Flash Partitions (SPI):
0x000000 - 0x07FFFF  U-Boot (512KB)
0x080000 - 0x23FFFF  Kernel (1.8MB)
0x240000 - 0xFAFFFF  Rootfs (13.7MB)
0x7F0000 - 0x7FFFFF  U-Boot env (64KB)
```

---

## Clock Tree

```
24MHz Crystal
  ├─> H-PLL (384-408MHz)
  │   └─> HCLK (CPU/AHB clock)
  ├─> M-PLL
  │   └─> MCLK (Memory clock)
  └─> V-PLL
      └─> DCLK (Display clock)
```

---

## Boot Configuration (U-Boot)

```
Console: ttyS1 @ 115200 bps
Kernel:  0x14080000 (flash)
Ramdisk: 0x14300000 (flash)
Command: bootm 14080000 14300000
Boot delay: 3 seconds
```

---

## I2C Configuration

**14 I2C buses supported**

Board-specific devices (Yosemite/Wedge100):
- Temperature sensors
- Power supplies
- EEPROMs
- Management controllers

**Transfer modes:**
- Byte mode (single byte)
- Buffer mode (multi-byte via pools)
- DMA mode (direct memory access)

**Clock speeds:** Up to 400 kHz

---

## Ethernet Configuration

**FTGMAC100 features:**
- Dual MAC (MAC0, MAC1)
- 10/100/1000 Mbps
- NCSI support (out-of-band management)
- RMII/RGMII interfaces

**PHY support:**
- Marvell
- Broadcom (BCM54612E, BCM54616S)
- Realtek (RTL8201EL, RTL8211BN, RTL8201N)

---

## Key Files by Function

### System Initialization
- `arch/arm/mach-aspeed/ast2100.c` - Machine init
- `arch/arm/plat-aspeed/devs.c` - Device registration
- `arch/arm/plat-aspeed/ast-scu.c` - Clock/reset/pinmux

### Interrupt Handling
- `arch/arm/plat-aspeed/irq.c` - IRQ management
- `arch/arm/mach-aspeed/include/mach/irqs.h` - IRQ routing
- `arch/arm/mach-aspeed/include/mach/ast2100_irqs.h` - IRQ numbers

### Hardware Definitions
- `arch/arm/mach-aspeed/include/mach/platform.h` - Memory map
- `arch/arm/mach-aspeed/include/mach/hardware.h` - Hardware base
- `arch/arm/plat-aspeed/include/plat/regs-scu.h` - SCU registers

### Device Trees (would need to create for modern kernel)
- None present (predates device tree era)
- See full document for device tree examples

---

## Porting Checklist

### High Priority (Core Boot)
- [ ] Create AST2050 device tree (.dtsi)
- [ ] Port SCU to clock framework
- [ ] Port interrupt controller
- [ ] Verify UART works with 8250 driver
- [ ] Test basic boot to console

### Medium Priority (Networking/Storage)
- [ ] Test FTGMAC100 with mainline driver
- [ ] Port I2C driver to modern API
- [ ] Port SPI driver
- [ ] Port NOR flash driver
- [ ] Verify watchdog works

### Lower Priority (Management)
- [ ] Port KCS driver
- [ ] Port PECI driver
- [ ] Port GPIO driver
- [ ] Port PWM/Fan driver
- [ ] Port ADC driver
- [ ] Port RTC driver

### Optional (Advanced)
- [ ] Port framebuffer to DRM
- [ ] Test USB support
- [ ] Test SDHCI

---

## Build Instructions (Original)

### Kernel
```bash
# Configure
make ARCH=arm ast2300_defconfig  # or ast2400_defconfig

# Build
make ARCH=arm CROSS_COMPILE=arm-linux-gnueabi- uImage modules

# Output: arch/arm/boot/uImage
```

### U-Boot
```bash
# Configure
make ast2050_config

# Build
make CROSS_COMPILE=arm-linux-gnueabi-

# Output: u-boot.bin
```

### Yocto
```bash
# Setup
git clone https://github.com/raptor-engineering/ast2050-yocto-openbmc.git
cd ast2050-yocto-openbmc

# Build
source openbmc-init-build-env
bitbake obmc-phosphor-image

# Output: tmp/deploy/images/
```

---

## Differences from Mainline ASPEED

### Features in Raptor Code NOT in Mainline
1. **AST2050/AST2100 support** - Mainline starts at AST2400
2. **Linux 2.6.28 compatibility** - Very old kernel
3. **Traditional board files** - Mainline uses device tree
4. **Direct SCU access** - Mainline uses clock/pinctrl frameworks
5. **ASUS KGPE-D16 config** - Board-specific to Raptor

### Features in Mainline NOT in Raptor Code
1. **Device tree support** - Modern kernel requirement
2. **Modern driver APIs** - Massive API changes since 2.6.28
3. **Clock framework** - Common Clock Framework
4. **Pinctrl subsystem** - Standard pinmux
5. **Regmap API** - Modern register access
6. **AST2500/AST2600** - Newer chip support

---

## Recommended Modern Approach

1. **Start with mainline kernel 6.x**
2. **Use AST2400 device tree as base** (most similar)
3. **Create ast2050.dtsi** based on AST2400
4. **Test with existing mainline drivers** where possible
5. **Port only AST2050-specific features** as needed
6. **Submit upstream** for community maintenance

**Estimated effort:** 2-4 weeks with hardware access

---

## Critical Insights

### What This Is
✓ Complete, working AST2050 BMC implementation
✓ Production-ready for ASUS KGPE-D16/KCMA-D8
✓ All major peripherals supported
✓ Proven stable (archived after production use)

### What This Isn't
✗ Modern kernel (stuck at 2.6.28.9 from 2009)
✗ Upstream maintainable (uses obsolete APIs)
✗ Device tree based (predates DT adoption)
✗ Portable to new boards without significant work

### Best Use Cases
1. **Reference implementation** for AST2050 hardware details
2. **Feature comparison** with mainline ASPEED drivers
3. **Register documentation** (headers are valuable)
4. **Working baseline** for porting to modern kernel
5. **Historical reference** for ASUS board support

---

## Contact/Author

**Original Author:** Timothy Pearson (madscientist159)
**Organization:** Raptor Engineering
**Timeframe:** August 2017
**Status:** Archived June 2018 (production deployment complete)

---

## Related Documentation

**Full Analysis:** See `RAPTOR_ENGINEERING_AST2050_ANALYSIS.md` (this directory)
- Complete file listings
- Detailed driver analysis
- Porting recommendations
- Device tree examples
- Register definitions

**Upstream ASPEED:** Linux kernel mainline
- `arch/arm/boot/dts/aspeed/`
- `drivers/clk/clk-aspeed.c`
- `drivers/pinctrl/aspeed/`
- `drivers/i2c/busses/i2c-aspeed.c`
- `drivers/net/ethernet/faraday/ftgmac100.c`

---

## Quick Statistics

| Metric | Count |
|--------|-------|
| Linux commits | 4 |
| U-Boot commits | 3 |
| Yocto commits | 21 |
| Architecture files | ~50 |
| Driver files | ~15 |
| Platform files | ~40 |
| Header files | ~80 |
| Supported chips | 10 |
| I2C buses | 14 |
| UART ports | 4 |
| Ethernet MACs | 2 |
| Lines of code | ~50,000+ |

---

**Document Version:** 1.0
**Last Updated:** 2026-02-15
