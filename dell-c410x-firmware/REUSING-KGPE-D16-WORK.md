# Reusing the ASUS KGPE-D16 Work for the Dell PowerEdge C410X

## Overview

Both the ASUS KGPE-D16 and the Dell PowerEdge C410X use the same BMC
chip: the **Aspeed AST2050** (ARM926EJ-S). The kernel-level SoC support
ported from Raptor Engineering's work on the KGPE-D16 applies directly
to the C410X -- only the board-level configuration differs.

In Linux kernel terms:
- **SoC support** = device tree include (`aspeed-g3.dtsi`) + drivers
  with `aspeed,ast2050-*` compatible strings. **Shared between boards.**
- **Board support** = device tree source (`aspeed-bmc-dell-c410x.dts`)
  describing the specific I2C topology, GPIO assignments, sensors, flash
  layout, and peripherals wired up on this particular board. **Unique
  per board.**

```
  aspeed-g3.dtsi              (SoC -- from KGPE-D16 porting work)
      │
      ├── aspeed-bmc-asus-kgpe-d16.dts   (KGPE-D16 board)
      └── aspeed-bmc-dell-c410x.dts      (C410X board -- already exists)
```

## What We Get For Free

Once the KGPE-D16 porting work is done (see `../asus-kgpe-d16-firmware/
RAPTOR-PORTING-GUIDE.md`), the following components work on the C410X
with **zero additional driver work**:

| Component | Mainline Driver | Notes |
|---|---|---|
| CPU boot | ARM926EJ-S + aspeed machine | Same SoC |
| Clock tree | `clk-aspeed.c` with AST2050 support | Same 24 MHz input, same PLLs |
| Pin muxing | `pinctrl-aspeed-g3.c` | Same SCU registers |
| Reset controller | `reset-aspeed.c` | Same |
| I2C controller | `i2c-aspeed.c` | Same 7 engines (0-6) |
| GPIO controller | `gpio-aspeed.c` | Same register layout |
| Ethernet MAC | `ftgmac100.c` | Same 10/100 RMII |
| SPI/FMC flash | `spi-aspeed-smc.c` | Same controller |
| Watchdog | `aspeed_wdt.c` | Same |
| UART | 8250 serial | Same NS16550 at 24 MHz |
| Interrupt controller | ARM VIC | Same |
| Timer | `timer-fttmr010.c` | Same |

## What Needs Board-Specific Work

The C410X has a completely different board design from the KGPE-D16.
The KGPE-D16 is a dual-socket server motherboard; the C410X is a
headless 16-slot PCIe GPU expansion chassis with no host CPU. Every
board-level detail differs.

### 1. Device Tree (Already Done)

The file `aspeed-bmc-dell-c410x.dts` already exists in this directory,
reverse-engineered from the v1.35 firmware. It currently uses
`aspeed-g4.dtsi` as a base:

```dts
#include "aspeed-g4.dtsi"
/ {
    model = "Dell PowerEdge C410X BMC";
    compatible = "dell,poweredge-c410x-bmc", "aspeed,ast2400";
    ...
};
```

**Action required:** Once `aspeed-g3.dtsi` exists from the KGPE-D16
work, update the C410X DTS to use it instead:

```dts
#include "aspeed-g3.dtsi"
/ {
    model = "Dell PowerEdge C410X BMC";
    compatible = "dell,poweredge-c410x-bmc", "aspeed,ast2050";
    ...
};
```

And update the SCU override (currently at line 128):
```dts
&syscon {
    /* Remove the explicit override -- aspeed-g3.dtsi will have the
     * correct ast2050-scu compatible natively */
};
```

### 2. I2C Device Topology

The C410X I2C topology is completely different from any server
motherboard. It manages 16 GPU slots, not CPUs and DIMMs.

| I2C Bus | C410X Usage | KGPE-D16 Usage |
|---|---|---|
| Bus 0 | 16x INA219 power monitors (one per PCIe slot) | Temperature sensors, misc |
| Bus 1 | PCA9544A mux → 2x ADT7462 fan/thermal + PCA9555 system GPIO | Temperature/voltage sensors |
| Bus 2 | FRU EEPROM | PCA9548 mux → GPU sensors |
| Bus 3 | PLX PEX8696/PEX8647 PCIe switches (I2C management) | PCA9548 mux → INA219 sensors |
| Bus 4 | 2x PCA9548 mux → 16x TMP75 per-slot temperature | PCA9555 GPIO expanders |
| Bus 5 | (unused) | PMBus PSUs |
| Bus 6 | 4x PCA9555 GPIO (presence, power good, attention, MRL) + LM75 | IPMB |

The I2C devices on the C410X are fully documented in the existing DTS
and in `io-tables/IO_fl.bin.md`. The device tree nodes for all 48+
I2C devices are already written and need no changes beyond the dtsi
switch.

**Specific C410X I2C devices (all already in DTS):**
- 16x TI INA219 current/power monitors at 0x40-0x4F
- 2x ADT7462 fan/thermal controllers at 0x58, 0x5C (behind PCA9544A mux)
- 16x TI TMP75 temperature sensors at 0x5C (behind 2x PCA9548 muxes)
- 5x NXP PCA9555 16-bit I/O expanders at 0x20-0x23 and 0x20
- 2x NXP PCA9548 8-channel I2C muxes at 0x70, 0x71
- 1x NXP PCA9544A 4-channel I2C mux at 0x70
- 1x Atmel 24C256 EEPROM at 0x50
- 1x LM75 temperature sensor at 0x4F

### 3. GPIO Pin Assignments

The C410X uses a completely different set of GPIO pins from the
KGPE-D16. The C410X GPIO mapping is fully documented in
`io-tables/gpio-pin-mapping.md` and already encoded in the DTS.

**C410X on-chip GPIO usage (38 pins):**

| Port | Pins Used | Function |
|---|---|---|
| A | A4, A5 | GPU presence IRQ, PSU presence IRQ |
| B | B0-B7 | ADT7462 IRQs, PMBus alert, TMP alert, slot IRQs, PEX IRQs |
| E | E0-E5 | BMC ready, PS_ON buffer, PWRGD, INA219 bus enable, power button, ID LED |
| F | F6 | PEX8696 reset |
| I | I0-I7 | Multi-host configuration data bus |
| J | J0-J7 | System status data bus |
| M | M0-M1 | PS_ON#, system reset |
| N | N4-N6 | PEX8647 reset, slot power enable, fan tach mux select |

**C410X PCA9555 GPIO expander usage (80 pins across 5 chips):**

| Chip | Address | Bus | Function |
|---|---|---|---|
| PCA9555 #1 | 0x20 | I2C6 | Slot 1-16 presence detect (all inputs) |
| PCA9555 #2 | 0x21 | I2C6 | Slot 1-16 power good feedback (all inputs) |
| PCA9555 #3 | 0x22 | I2C6 | Slot 1-16 attention buttons (all inputs) |
| PCA9555 #4 | 0x23 | I2C6 | Slot 1-16 MRL sensors (all inputs) |
| PCA9555 #5 | 0x20 | I2C1 | PSU status, fan LEDs, system control |

All of this is already in the DTS. No additional reverse engineering
needed.

### 4. IPMI Sensor Definitions

The C410X has 72 IPMI sensors, fully documented in
`io-tables/IS_fl.bin.md`:

| Type | Count | Details |
|---|---|---|
| Temperature | 23 | 6 board zones (ADT7462) + 16 per-slot (TMP75) + 1 front board (LM75) |
| GPU Power | 16 | One INA219 per PCIe slot |
| PSU Power | 4 | PMBus power reading per PSU |
| Fan Speed | 8 | 2x ADT7462 tachometer inputs |
| Discrete | 21 | 16 GPU presence + 4 PSU presence + 1 system power |

On a modern OpenBMC system, these sensors would be exposed through:
- **hwmon** sysfs for temperature, voltage, current, fan speed
- **ipmid** or **phosphor-host-ipmid** for IPMI SDR/sensor mapping
- **dbus-sensors** for entity-manager based sensor discovery

The C410X sensor definitions are board-specific and would need their
own OpenBMC configuration (entity-manager JSON or equivalent). The
KGPE-D16 sensor configuration would not apply.

### 5. Flash Partition Layout

The C410X uses a different flash layout from the KGPE-D16:

| Region | C410X | KGPE-D16 (Raptor) |
|---|---|---|
| U-Boot | 0x000000, 512 KB (est.) | 0x000000, 512 KB |
| U-Boot env | 0x080000, 512 KB (est.) | 0x7F0000, 64 KB |
| Kernel | 0x100000, 2 MB | 0x080000, 1.8 MB |
| Root FS | 0x300000, 13 MB | 0x240000, 13.7 MB |

Flash partitions are defined in the board DTS (already done for C410X).
A new OpenBMC image would use its own partition layout anyway.

### 6. Ethernet Configuration

Both boards use RMII mode for the BMC Ethernet port. The C410X
configuration is already in the DTS:

```dts
&mac0 {
    status = "okay";
    phy-mode = "rmii";
};
```

The specific Ethernet PHY chip on the C410X may differ from the
KGPE-D16 -- this needs verification with physical hardware. The PHY
should be auto-detected by the `ftgmac100` driver regardless.

### 7. Power Sequencing (C410X-Specific)

The C410X has a unique 12-step power sequencing flow for its 16 GPU
slots, managed entirely through GPIO pins and PCA9555 expanders. This
is specific to the C410X chassis and has no equivalent on the KGPE-D16.

The power sequence (from `io-tables/gpio-pin-mapping.md`):
1. Assert `bmc-ready` (GPIOE0)
2. Enable PS_ON buffer (GPIOE1)
3. Assert PS_ON# to PSUs (GPIOM0)
4. Wait for PWRGD (GPIOE2)
5. Enable INA219 bus (GPIOE3)
6. Enable slot power (GPION5)
7. De-assert PEX8696 reset (GPIOF6)
8. De-assert PEX8647 reset (GPION4)
9. Power on GPU groups in 4 staggered phases
10-12. Monitor and manage per-slot power

This sequencing logic would need to be implemented as a userspace
service or a custom kernel driver for the C410X. It is entirely
board-specific.

### 8. PCIe Switch Management (C410X-Specific)

The C410X manages two PLX/Broadcom PCIe switches via I2C (bus 3):
- **PEX8696** -- 96-lane primary switch, controls 16 downstream GPU slots
- **PEX8647** -- 48-lane upstream switch, handles host iPass connections

The firmware uses vendor-specific I2C protocols for:
- Hot-plug controller management (per-slot power enable/disable)
- Multi-host configuration (1:2, 1:4, 1:8 iPass-to-slot mapping)
- Link training and error recovery

There is no standard Linux driver for managing PLX PCIe switches via
I2C. The Avocent firmware handles this with raw I2C transactions in
the `fullfw` binary. A modern replacement would need a custom userspace
tool or a new kernel driver.

The KGPE-D16 has no equivalent -- it's a standard server motherboard
with direct PCIe slots.

### 9. Fan Control

Both boards use different fan controllers:

| | C410X | KGPE-D16 |
|---|---|---|
| Controller | 2x ADT7462 on I2C | AST2050 on-chip PWM |
| Channels | 8 fans via ADT7462 tach inputs | 2 PWM channels (CPU + chassis) |
| Control method | I2C register writes to ADT7462 | PWM duty cycle via SoC registers |

The C410X fan control is done through the ADT7462 hwmon driver
(`adt7462` in mainline). The KGPE-D16 uses the Aspeed PWM/tach
controller directly. Different fan daemons would be needed for each
board.

### 10. KCS/IPMI

Both boards use the same AST2050 KCS interface for IPMI. The LPC
host interface controller is identical. However:

- The **KGPE-D16** uses KCS for communication with the host AMD
  Opteron CPUs running in the same chassis.
- The **C410X** has no host CPU -- it is a standalone chassis. The
  KCS interface connects to the host servers via iPass cables, and
  IPMI management is done primarily over the Ethernet network
  (RMCP/RMCP+), not via in-band KCS.

The KCS driver and IRQ storm fix from the KGPE-D16 work still apply,
but the C410X may not need KCS enabled at all if managed purely over
the network.

## Step-by-Step: Bringing Up the C410X After KGPE-D16 Work

### Prerequisites

- The KGPE-D16 porting work is complete (AST2050 boots mainline Linux)
- `aspeed-g3.dtsi` exists with all AST2050 peripheral nodes
- Mainline drivers have `aspeed,ast2050-*` compatible strings
- Physical access to a Dell PowerEdge C410X chassis

### Step 1: Update the C410X Device Tree

Update `aspeed-bmc-dell-c410x.dts` to use the new G3 dtsi:

```diff
-#include "aspeed-g4.dtsi"
+#include "aspeed-g3.dtsi"

 / {
     model = "Dell PowerEdge C410X BMC";
-    compatible = "dell,poweredge-c410x-bmc", "aspeed,ast2400";
+    compatible = "dell,poweredge-c410x-bmc", "aspeed,ast2050";
```

Remove the SCU compatible override (lines 114-129 in current DTS)
since the G3 dtsi will have the correct `ast2050-scu` natively.

Remove comments about AST2050 vs AST2400 compatibility (lines 15-20)
since the proper dtsi now exists.

### Step 2: Build and Boot

Build the kernel with the C410X DTS:

```bash
make ARCH=arm aspeed_g4_defconfig   # or a new aspeed_g3_defconfig
make ARCH=arm CROSS_COMPILE=arm-linux-gnueabi- dtbs
# Output: arch/arm/boot/dts/aspeed/aspeed-bmc-dell-c410x.dtb
```

Boot via TFTP using the existing C410X U-Boot (see `tftp_boot.py` in
this directory for the TFTP boot automation script).

### Step 3: Verify Serial Console

Connect to the C410X BMC serial port (ttyS0 at 115200). The BMC serial
console is on UART1 (the same AST2050 UART used on the KGPE-D16).

### Step 4: Verify Network

The C410X BMC has a dedicated Ethernet port (RMII PHY on MAC0).
Default factory IP is 192.168.0.120 with DHCP enabled.

### Step 5: Verify I2C Devices

Scan all 7 I2C buses and compare against the expected device map:

```bash
for bus in 0 1 2 3 4 5 6; do
    echo "=== I2C bus $bus ==="
    i2cdetect -y $bus
done
```

Expected results:
- **Bus 0:** 16 devices at 0x40-0x4F (INA219 power monitors)
- **Bus 1:** Devices at 0x20 (PCA9555) and 0x70 (PCA9544A mux)
- **Bus 2:** Device at 0x50 (FRU EEPROM)
- **Bus 3:** PLX PCIe switch addresses (to be confirmed)
- **Bus 4:** Devices at 0x70 and 0x71 (PCA9548 muxes)
- **Bus 5:** Empty (unused)
- **Bus 6:** Devices at 0x20-0x23 (PCA9555 expanders) and 0x4F (LM75)

### Step 6: Verify Sensors

With I2C working, the mainline hwmon drivers should automatically
bind to the I2C devices declared in the DTS:

```bash
# Temperature sensors
cat /sys/class/hwmon/hwmon*/temp1_input

# Power sensors
cat /sys/class/hwmon/hwmon*/power1_input

# Fan speeds (via ADT7462)
cat /sys/class/hwmon/hwmon*/fan*_input
```

### Step 7: GPIO and Power Sequencing

Test GPIO access:

```bash
# Read GPU presence
gpioget gpiochip1 0 1 2 3 4 5 6 7   # PCA9555 #1 port 0 (slots 1-8)

# Read PSU presence
gpioget gpiochip5 0 1 2 3            # PCA9555 #5 port 0 bits 0-3
```

Power sequencing is the most complex C410X-specific feature and should
be tested incrementally with extreme care (incorrect sequencing can
damage GPUs or PSUs).

### Step 8: IPMI (Optional)

If in-band IPMI is needed (unlikely for standalone C410X operation):
- Enable KCS in the DTS
- Configure `ipmid` or OpenBMC IPMI stack

For network-only management, IPMI-over-LAN (RMCP+) is sufficient.

## Summary

| Work Item | Source | Effort for C410X |
|---|---|---|
| AST2050 SoC drivers | KGPE-D16 porting | **Zero** -- direct reuse |
| `aspeed-g3.dtsi` | KGPE-D16 porting | **Zero** -- direct reuse |
| Board device tree | Already exists (`aspeed-bmc-dell-c410x.dts`) | **Small** -- switch dtsi include, remove workarounds |
| I2C device mapping | Already reverse-engineered | **Zero** -- already in DTS |
| GPIO mapping | Already reverse-engineered | **Zero** -- already in DTS |
| Flash partitions | Already documented | **Zero** -- already in DTS |
| Sensor definitions | Already documented (`IS_fl.bin.md`) | **Medium** -- OpenBMC sensor config needed |
| Fan control daemon | Must write new | **Medium** -- ADT7462 hwmon + custom fan curves |
| Power sequencing | Must write new | **Large** -- C410X-specific, safety-critical |
| PCIe switch management | Must write new | **Large** -- vendor-specific I2C protocol |
| Port mapping (iPass) | Must write new | **Medium** -- OEM IPMI command replacement |

The SoC-level work from the KGPE-D16 gives us a bootable Linux kernel
on the C410X. The board-specific reverse engineering is already done.
The remaining effort is writing userspace daemons for power sequencing,
fan control, and PCIe switch management -- tasks that are independent
of the kernel porting work and can proceed in parallel.
