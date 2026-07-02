# Aspeed Mainline Driver Quick Reference

**Date**: 2026-02-15  
**Critical Finding**: NO AST2050/AST1100 support in mainline Linux

---

## Quick Raptor → Mainline Mapping

| Raptor Driver | Mainline Driver | Location | Status |
|---------------|-----------------|----------|--------|
| arch/arm/mach-aspeed/ | mach-aspeed/ | arch/arm/mach-aspeed/ | PRESENT (AST2400+) |
| arch/arm/plat-aspeed/ | (removed) | N/A | REMOVED - use device tree |
| drivers/char/aspeed/ast_kcs.c | kcs_bmc_aspeed.c | drivers/char/ipmi/ | PRESENT (AST2400+) |
| drivers/char/aspeed/ast_peci.c | peci-aspeed.c | drivers/peci/controller/ | PRESENT (AST2400+) |
| drivers/i2c/busses/i2c-ast.c | i2c-aspeed.c | drivers/i2c/busses/ | PRESENT (AST2400+) |
| drivers/net/ftgmac100_26.c | ftgmac100.c | drivers/net/ethernet/faraday/ | PRESENT (AST2400+) |
| drivers/watchdog/ast_wdt.c | aspeed_wdt.c | drivers/watchdog/ | PRESENT (AST2400+) |
| drivers/spi/ast_spi.c | spi-aspeed-smc.c | drivers/spi/ | PRESENT (AST2400+) |
| drivers/video/astfb.c | aspeed_gfx (DRM) | drivers/gpu/drm/aspeed/ | PRESENT (AST2400+) |
| drivers/hwmon/ast_adc.c | aspeed_adc.c | drivers/iio/adc/ | PRESENT (AST2400+) |
| drivers/hwmon/ast_pwm_fan.c | aspeed-pwm-tacho.c | drivers/hwmon/ | PRESENT (AST2400+) |
| drivers/hwmon/ast_lcp_80h.c | aspeed-lpc-snoop.c | drivers/soc/aspeed/ | PRESENT (AST2400+) |
| drivers/mtd/maps/ast-nor.c | (via spi-aspeed-smc) | N/A | REMOVED - handled by SPI |
| drivers/usb/astuhci/ | ehci/uhci-platform | drivers/usb/host/ | Generic platform |

---

## All Mainline Aspeed Drivers (Alphabetical)

### Character/IPMI
- drivers/char/ipmi/kcs_bmc_aspeed.c (AST2400+)
- drivers/peci/controller/peci-aspeed.c (AST2400+)

### Clocks/Reset
- drivers/clk/clk-aspeed.c (AST2400, AST2500 only)
- drivers/reset/reset-aspeed.c (AST2400+)

### Crypto
- drivers/crypto/aspeed/aspeed-hace-crypto.c (AST2500+)
- drivers/crypto/aspeed/aspeed-acry.c (AST2500+)

### EDAC
- drivers/edac/aspeed_edac.c (AST2400+)

### FSI
- drivers/fsi/fsi-master-aspeed.c (AST2600+)

### GPIO
- drivers/gpio/gpio-aspeed.c (AST2400+)
- drivers/gpio/gpio-aspeed-sgpio.c (AST2400+)

### Graphics/Video
- drivers/gpu/drm/aspeed/ (AST2400+)
- drivers/media/platform/aspeed/aspeed-video.c (AST2400+)

### Hardware Monitoring
- drivers/hwmon/aspeed-pwm-tacho.c (AST2400, AST2500)
- drivers/hwmon/aspeed-g6-pwm-tach.c (AST2600+)
- drivers/iio/adc/aspeed_adc.c (AST2400+)

### I2C
- drivers/i2c/busses/i2c-aspeed.c (AST2400+)

### Interrupt Controllers
- drivers/irqchip/irq-aspeed-intc.c (AST2400+)
- drivers/irqchip/irq-aspeed-i2c-ic.c (AST2400+)
- drivers/irqchip/irq-aspeed-scu-ic.c (AST2400+)

### MMC/SD
- drivers/mmc/host/sdhci-of-aspeed.c (AST2400+)

### Network
- drivers/net/ethernet/faraday/ftgmac100.c (AST2400+)
- drivers/net/mdio/mdio-aspeed.c (AST2600+)

### Pinctrl
- drivers/pinctrl/aspeed/pinctrl-aspeed-g4.c (AST2400)
- drivers/pinctrl/aspeed/pinctrl-aspeed-g5.c (AST2500)
- drivers/pinctrl/aspeed/pinctrl-aspeed-g6.c (AST2600)

### RTC
- drivers/rtc/rtc-aspeed.c (AST2400+)

### SoC Infrastructure
- drivers/soc/aspeed/aspeed-socinfo.c (AST2400+)
- drivers/soc/aspeed/aspeed-lpc-ctrl.c (AST2400+)
- drivers/soc/aspeed/aspeed-lpc-snoop.c (AST2400+)
- drivers/soc/aspeed/aspeed-p2a-ctrl.c (AST2400+)
- drivers/soc/aspeed/aspeed-uart-routing.c (AST2400+)

### SPI/Flash
- drivers/spi/spi-aspeed-smc.c (AST2400+)

### Serial/UART
- drivers/tty/serial/8250/8250_aspeed_vuart.c (AST2400+)

### USB
- drivers/usb/gadget/udc/aspeed-vhub/ (AST2400+)
- drivers/usb/gadget/udc/aspeed_udc.c (AST2600+)

### Watchdog
- drivers/watchdog/aspeed_wdt.c (AST2400+)

---

## AST2050/AST1100 Status: NOT SUPPORTED

Checked files:
- drivers/soc/aspeed/aspeed-socinfo.c - NO AST2050/AST1100 IDs
- drivers/clk/clk-aspeed.c - NO AST2050/AST1100 clock support
- All 45+ driver files - ZERO references to AST2050 or AST1100

**Earliest supported generation: AST2400 (G4)**

---

## Device Tree Files

- arch/arm/boot/dts/aspeed/aspeed-g4.dtsi (AST2400)
- arch/arm/boot/dts/aspeed/aspeed-g5.dtsi (AST2500)
- arch/arm/boot/dts/aspeed/aspeed-g6.dtsi (AST2600)
- Plus 25+ board-specific .dts files

NO device tree for AST2050/AST1100 (would need aspeed-g3.dtsi or similar)

---

## Key Mainline Features NOT in Raptor Kernel

1. Video capture engine (aspeed-video.c)
2. Cryptographic acceleration (aspeed-hace, aspeed-acry)
3. FSI master interface (fsi-master-aspeed.c)
4. Virtual UART (8250_aspeed_vuart.c)
5. USB virtual hub (aspeed-vhub)
6. Pinctrl framework
7. DRM/KMS graphics (vs old fbdev)
8. EDAC memory error detection
9. Modern IIO subsystem for ADC

---

## To Add AST2050 Support

Minimum work required:
1. Add AST2050 silicon ID to aspeed-socinfo.c
2. Add AST2050 clock support to clk-aspeed.c  
3. Create aspeed-g3.dtsi device tree
4. Update 40+ drivers with AST2050 compatible strings
5. Test all peripherals on actual AST2050 hardware

Estimated effort: 200-400 hours of kernel development work
