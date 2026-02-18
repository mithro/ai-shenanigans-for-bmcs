# U-Boot Full-Featured Port for HPE iPDU (NS9360) - QEMU-Based Approach

## Purpose

This document is a **self-contained prompt** for a Claude Code session to execute a
complete U-Boot port to the HPE Intelligent Modular PDU (AF531A) using QEMU for
development and automated testing. The entire port is built as a single coherent
effort with modern U-Boot conventions (Kconfig, device tree, driver model).

**Strategy**: Develop and test the complete port in QEMU before touching real hardware.
This enables rapid iteration with automated test suites, CI/CD integration, and
comprehensive validation. Use QEMU's ARM926EJS emulation to test everything except
hardware-specific timing.

---

## 1. Target Hardware Specification

### SoC and CPU

| Property | Value |
|----------|-------|
| SoC | Digi NS9360B-0-C177 |
| CPU Core | ARM926EJ-S |
| CPU Clock | 176.9 MHz |
| Endianness | Big-endian (default, confirmed by gpio[44]=0) |
| Architecture | ARMv5TEJ |

### Clock Tree

```
Crystal (Y1): 29.4912 MHz
         │
    ┌────▼────┐
    │   PLL   │  ND=11 (multiply by 12), FS=1 (divide by 2)
    └────┬────┘
         │
    Raw PLL Output: 29.4912 MHz × 12 = 353.8944 MHz
    (This is CONFIG_SYS_CLK_FREQ)
         │
    ┌────┼──────────────────────────┐
    │    │                          │
  ÷2   ÷4                         ÷8
    │    │                          │
  CPU  AHB Bus                   BBus
176.9  88.5 MHz                 44.2 MHz
 MHz
```

**PLL Register (SYS_PLL @ 0xA0900188):**
- ND (bits [20:16]) = 11 (multiply by ND+1 = 12)
- FS (bits [24:23]) = 1 (divide by 2^FS = 2)
- Result: 29.4912 × 12 / 2 = 176.9472 MHz

### Memory Map

```
0x00000000 - 0x01FFFFFF  SDRAM (32 MB, CS4/CS5)
0x40000000 - 0x407FFFFF  NOR Flash CS0 (8 MB, boot device)
0x50000000 - 0x507FFFFF  NOR Flash CS1 (8 MB, secondary)
0x90200000 - 0x902FFFFF  Serial Interface Module (BBus)
0x90600000 - 0x906FFFFF  BBus Utility Module (GPIO, DMA, etc.)
0xA0600000 - 0xA06FFFFF  Ethernet MAC Module (AHB)
0xA0700000 - 0xA07FFFFF  Memory Controller Module (AHB)
0xA0800000 - 0xA08FFFFF  LCD Controller Module (AHB)
0xA0900000 - 0xA09FFFFF  System Control Module (AHB)
```

### SDRAM

| Property | Value |
|----------|-------|
| Chip | ISSI IS42S32800D-7BLI |
| Size | 32 MB (256 Mbit) |
| Width | 32-bit |
| Organisation | 8M × 32 bit × 4 banks |
| Speed Grade | -7 (143 MHz / 7ns CAS latency) |
| Base Address | 0x00000000 (CS4) |

**SDRAM Timing Parameters (in AHB clock cycles @ 88.5 MHz, ~11.3 ns/cycle):**

| Parameter | Register Offset | Value | Meaning |
|-----------|----------------|-------|---------|
| tRP | 0x0030 | 1 | Precharge command period |
| tRAS | 0x0034 | 4 | Active to precharge |
| tAPR | 0x003C | 1 | Last data to active |
| tDAL | 0x0040 | 5 | Data-in to active |
| tWR | 0x0044 | 1 | Write recovery |
| tRC | 0x0048 | 6 | Active to active (same bank) |
| tRFC | 0x004C | 6 | Auto-refresh period |
| tRRD | 0x0054 | 1 | Active bank A to B |
| tMRD | 0x0058 | 1 | Mode register set delay |
| CAS | 0x0104 | 2 | CAS latency |
| RAS | 0x0104 | 3 | RAS latency |
| Refresh | 0x0024 | 0x30 | Refresh timer (operational) |

### NOR Flash

| Property | Value |
|----------|-------|
| Chips | 2× Macronix MX29LV640EBXEI-70G |
| Type | NOR Flash, CFI compatible, bottom boot |
| Size per chip | 8 MB (64 Mbit) |
| Bus width | 16-bit per chip |
| CS0 base | 0x40000000 (primary, boot device) |
| CS1 base | 0x50000000 (secondary) |
| Sector layout | 8× 8KB + 63× 64KB (bottom boot) |
| Total sectors | 71 per chip (142 total) |

**Static Memory Controller Settings (per chip select):**

| Register | Value | Meaning |
|----------|-------|---------|
| MEM_STAT_CFG | MW_16 \| PB | 16-bit width, page burst |
| MEM_STAT_WAIT_WEN | 0x2 | Write enable wait states |
| MEM_STAT_WAIT_OEN | 0x2 | Output enable wait states |
| MEM_STAT_RD | 0x6 | Read access time |
| MEM_STAT_WR | 0x6 | Write access time |

### Debug UART

| Property | Value |
|----------|-------|
| Port | Serial Port A (channel index 1) |
| Base Address | 0x90200040 |
| Baud Rate | 115200 |
| Format | 8N1 (8 data, no parity, 1 stop) |
| Connector | J25 header on HPE iPDU board |
| TxD GPIO | GPIO 8 (function 0, output) |
| RxD GPIO | GPIO 9 (function 0, input) |

**UART Register Addresses (Port A @ base 0x90200040):**

| Register | Address | Purpose |
|----------|---------|---------|
| CTRL_A | 0x90200040 | Channel enable, word length, parity, stop bits |
| CTRL_B | 0x90200044 | Mode (UART/SPI/HDLC), RX gap timer |
| STAT_A | 0x90200048 | TX/RX ready, errors, FIFO status |
| BITRATE | 0x9020004C | Baud rate divisor, clock source |
| FIFO | 0x90200050 | TX/RX data FIFO |
| RX_CHAR_TIMER | 0x90200058 | Character gap timer |

**Baud Rate Calculation for 115200:**
```
Clock source: BCLK (BBus clock) = CONFIG_SYS_CLK_FREQ / 8 = 44,236,800 Hz
Prescaler: TCDR_16 = ÷16, RCDR_16 = ÷16
Divisor N: (44,236,800 / (115,200 × 16)) - 1 = 24 - 1 = 23

BITRATE register value: 0xE1100017
  EBIT=1, CLKMUX=BCLK, TMODE=1, TCDR=÷16, RCDR=÷16, N=23

CTRL_A register value: 0x83000000
  CE=1 (enable), WLS=8bit, no parity, 1 stop bit
```

### Ethernet

| Property | Value |
|----------|-------|
| MAC | NS9360 integrated Ethernet MAC |
| MAC Base Address | 0xA0600000 |
| PHY | ICS1893AFLF |
| PHY Interface | MII (Media Independent Interface) |
| PHY Crystal | 25 MHz (Y2) |
| PHY Address | 0x0001 (on MDIO bus) |
| GPIO Pins | GPIO 50-64 (function 0) |

### I2C

| Property | Value |
|----------|-------|
| SDA GPIO | GPIO 34 (function 2) |
| SCL GPIO | GPIO 35 (function 2) |
| Speed | 100 kHz or 400 kHz |

---

## 2. Reference Material Locations

All paths are relative to the `uboot-port/` directory.

### Primary Reference: Digi U-Boot 1.1.4 Source

**Root:** `reference/digi-cc9p9360-uboot/u-boot-1.1.4-digi/U-Boot/`

| File | Description |
|------|-------------|
| `board/cc9c/cc9c.c` | Board init, SDRAM detection, flash CS1 setup |
| `board/cc9c/platform.S` | Low-level init: SDRAM timing, memory controller |
| `board/cc9c/switch_to_le.S` | Endianness switching code |
| `board/cc9c/flash.c` | NOR flash driver (erase/program sequences) |
| `drivers/ns9750_eth.c` | Ethernet MAC driver |
| `drivers/ns9750_serial.c` | UART driver |
| `drivers/ns9750_i2c.c` | I2C master driver |
| `include/configs/cc9c.h` | CC9C board configuration |
| `include/ns9750_sys.h` | System control registers |
| `include/ns9750_mem.h` | Memory controller registers |
| `include/ns9750_bbus.h` | BBus registers (GPIO, reset, endian) |
| `include/ns9750_ser.h` | Serial port registers |
| `include/ns9750_eth.h` | Ethernet MAC registers |

### Mainline U-Boot v2012.10

**Root:** `reference/ns9750dev-uboot/u-boot-v2012.10/` (git submodule)

| File | Description |
|------|-------------|
| `board/ns9750dev/lowlevel_init.S` | Simpler low-level init |
| `drivers/serial/ns9750_serial.c` | Mainline serial driver |
| `include/configs/ns9750dev.h` | Clock frequency definitions |

### Linux Kernel mach-ns9xxx (v2.6.39)

**Root:** `reference/linux-mach-ns9xxx/linux-v2.6.39/` (git submodule)

| File | Description |
|------|-------------|
| `arch/arm/mach-ns9xxx/processor-ns9360.c` | Clock calculation, PLL |
| `arch/arm/mach-ns9xxx/gpio-ns9360.c` | GPIO driver (pin mux) |
| `arch/arm/mach-ns9xxx/time-ns9360.c` | Timer init |
| `arch/arm/mach-ns9xxx/include/mach/regs-sys-ns9360.h` | System register macros |

### Hardware Documentation

- `reference/docs/` - Application notes, schematics, GPIO tables
- `../datasheets/NS9360_HW_Reference_90000675_J.pdf` - **Definitive register reference**
- `../datasheets/NS9360_datasheet_91001326_D.pdf` - NS9360 datasheet
- `REFERENCE-MATERIAL.md` - Complete inventory with descriptions

### Pre-compiled Binaries

- `reference/digi-cc9p9360-uboot/binaries/u-boot-cc9p9360js-v1.1.4e.bin` (238 KB)
- `reference/digi-cc9p9360-uboot/binaries/u-boot-cc9p9360js-v1.1.6-revf6.bin` (257 KB)

---

## 3. Key Differences: CC9C Reference → HPE iPDU

| Feature | CC9C (Digi Reference) | HPE iPDU (Target) | Action |
|---------|----------------------|-------------------|--------|
| Boot flash | CS1 @ 0x50000000 | CS0 @ 0x40000000 | Change flash base, CS config |
| Second flash | None | CS1 @ 0x50000000 | Add CS1 init in board code |
| Console baud | 38400 | 115200 | Update CONFIG_BAUDRATE |
| SDRAM | Variable (16-64 MB) | Fixed 32 MB IS42S32800D | Hardcode or auto-detect |
| Ethernet PHY | Various | ICS1893AFLF | Add PHY ID, verify MII init |
| NAND flash | Optional | Not present | Disable |
| Endianness | Big-endian | Big-endian | No change needed |

---

## 4. QEMU Setup for ARM926EJS Emulation

### Approach

QEMU does not have a built-in NS9360 machine type. We have two options:

### Option A: Custom QEMU Machine (Recommended)

Create a minimal QEMU machine type that emulates the NS9360 memory map. This gives
accurate register addresses and allows testing the actual driver code.

**Files to create in QEMU source tree:**

1. `hw/arm/ns9360.c` - Machine definition with:
   - ARM926EJS CPU (big-endian)
   - 32 MB SDRAM at 0x00000000
   - 8 MB pflash at 0x40000000 (CS0)
   - 8 MB pflash at 0x50000000 (CS1)
   - NS9360 UART at 0x90200040 (mapped to QEMU serial backend)
   - System control stub at 0xA0900000 (PLL readback, GPIO)
   - Memory controller stub at 0xA0700000

2. `hw/char/ns9360_uart.c` - UART device model:
   - CTRL_A, STAT_A, BITRATE, FIFO registers
   - FIFO TX/RX with QEMU CharBackend
   - Status register (TRDY, RRDY flags)

3. `hw/net/ns9360_eth.c` - Ethernet device model (optional for QEMU):
   - EGCR1/EGCR2, MAC registers
   - MII management (MDIO) interface
   - Connect to QEMU network backend

**Build and run:**
```bash
# Build QEMU with NS9360 support
cd qemu
mkdir build && cd build
../configure --target-list=arm-softmmu
make -j$(nproc)

# Run U-Boot in QEMU
./qemu-system-arm -M ns9360-ipdu \
    -cpu arm926 \
    -m 32M \
    -drive if=pflash,file=u-boot.bin,format=raw \
    -serial stdio \
    -nographic
```

### Option B: Use Existing Versatile/VExpress Machine (Quick Start)

Use QEMU's existing `versatilepb` or `vexpress-a9` machine with a shim layer that
remaps addresses. This is faster to set up but less accurate.

```bash
# Quick test with versatile machine (ARM926EJS)
qemu-system-arm -M versatilepb \
    -cpu arm926 \
    -m 32M \
    -kernel u-boot \
    -serial stdio \
    -nographic
```

**Limitation:** Register addresses won't match NS9360, so hardware-specific drivers
won't work. Useful only for testing generic U-Boot framework code.

### Option C: Renode Emulation (Alternative)

[Renode](https://renode.io/) supports custom platform definitions via `.repl` files
and may be easier to configure than custom QEMU:

```
# ns9360-ipdu.repl
cpu: CPU.ARM926 @ sysbus
    cpuType: "arm926"

sdram: Memory.MappedMemory @ sysbus 0x00000000
    size: 0x02000000

flash0: Memory.MappedMemory @ sysbus 0x40000000
    size: 0x00800000

flash1: Memory.MappedMemory @ sysbus 0x50000000
    size: 0x00800000

uart: UART.NS16550 @ sysbus 0x90200040
    # Would need custom UART model for NS9360
```

### Recommended Path

Start with **Option A** (custom QEMU machine) for the most accurate testing.
The UART model is the critical component - if serial works in QEMU, the rest
of the bring-up can proceed with confidence.

---

## 5. Modern U-Boot Structure

### Directory Layout

```
u-boot/
├── arch/arm/
│   ├── dts/
│   │   └── ns9360-hpe-ipdu.dts          # Device tree source
│   ├── mach-ns9360/                      # New SoC support
│   │   ├── Kconfig
│   │   ├── Makefile
│   │   ├── lowlevel_init.S              # SDRAM, memory controller init
│   │   ├── clock.c                      # Clock tree management
│   │   └── soc.c                        # SoC-level init (GPIO mux, resets)
│   └── Kconfig                          # Add NS9360 to ARM SoC list
│
├── board/hpe/ipdu/                       # Board support
│   ├── Kconfig
│   ├── Makefile
│   ├── ipdu.c                           # Board init, dram_init
│   ├── MAINTAINERS
│   └── Makefile
│
├── configs/
│   └── hpe_ipdu_defconfig               # Board defconfig
│
├── drivers/
│   ├── serial/
│   │   └── serial_ns9360.c              # NS9360 UART driver (driver model)
│   ├── net/
│   │   └── ns9360_eth.c                 # NS9360 Ethernet driver (driver model)
│   ├── gpio/
│   │   └── ns9360_gpio.c               # NS9360 GPIO driver (driver model)
│   ├── clk/
│   │   └── clk_ns9360.c                # NS9360 clock driver (driver model)
│   └── i2c/
│       └── ns9360_i2c.c                # NS9360 I2C driver (driver model)
│
├── include/
│   ├── configs/
│   │   └── hpe_ipdu.h                  # Board configuration header
│   └── dt-bindings/
│       └── clock/
│           └── ns9360-clock.h          # Clock binding constants
│
└── doc/board/hpe/
    └── ipdu.rst                         # Board documentation
```

### Kconfig Configuration

#### SoC Kconfig (`arch/arm/mach-ns9360/Kconfig`)

```kconfig
if ARCH_NS9360

config SYS_SOC
    default "ns9360"

config NS9360
    bool
    select ARM926EJS
    select SYS_BIG_ENDIAN
    help
      Support for the Digi NS9360 SoC (ARM926EJ-S core).

config TARGET_HPE_IPDU
    bool "HPE Intelligent Modular PDU (AF531A)"
    select NS9360
    help
      HPE Intelligent Modular PDU with NS9360B SoC,
      32 MB SDRAM, 16 MB NOR flash, Ethernet.

endif
```

#### Board Defconfig (`configs/hpe_ipdu_defconfig`)

```
CONFIG_ARM=y
CONFIG_ARCH_NS9360=y
CONFIG_TARGET_HPE_IPDU=y
CONFIG_SYS_TEXT_BASE=0x40000000
CONFIG_DEFAULT_DEVICE_TREE="ns9360-hpe-ipdu"
CONFIG_BAUDRATE=115200
CONFIG_SYS_CLK_FREQ=353894400

# Serial
CONFIG_NS9360_SERIAL=y
CONFIG_CONS_INDEX=2

# Flash
CONFIG_SYS_FLASH_CFI=y
CONFIG_FLASH_CFI_DRIVER=y
CONFIG_SYS_MAX_FLASH_BANKS=2
CONFIG_ENV_IS_IN_FLASH=y

# Network
CONFIG_NS9360_ETH=y
CONFIG_CMD_PING=y
CONFIG_CMD_DHCP=y

# Memory
CONFIG_CMD_MEMORY=y
CONFIG_CMD_MTEST=y

# Standard commands
CONFIG_CMD_FLASH=y
CONFIG_CMD_NET=y
CONFIG_CMD_ENV=y
CONFIG_CMD_RUN=y
CONFIG_CMD_BOOTM=y
CONFIG_CMD_GO=y
```

---

## 6. Device Tree

### Device Tree Source (`arch/arm/dts/ns9360-hpe-ipdu.dts`)

```dts
/dts-v1/;

/ {
    model = "HPE Intelligent Modular PDU (AF531A)";
    compatible = "hpe,ipdu-af531a", "digi,ns9360";

    #address-cells = <1>;
    #size-cells = <1>;

    chosen {
        stdout-path = &uart1;
    };

    aliases {
        serial0 = &uart1;
        ethernet0 = &ethernet;
    };

    cpus {
        #address-cells = <1>;
        #size-cells = <0>;

        cpu@0 {
            device_type = "cpu";
            compatible = "arm,arm926ej-s";
            reg = <0>;
            clock-frequency = <176947200>;  /* 176.9 MHz */
        };
    };

    clocks {
        crystal: crystal {
            compatible = "fixed-clock";
            #clock-cells = <0>;
            clock-frequency = <29491200>;  /* 29.4912 MHz */
        };

        pll: pll {
            compatible = "digi,ns9360-pll";
            #clock-cells = <0>;
            clocks = <&crystal>;
            /* ND=11, FS=1: 29.4912 MHz × 12 / 2 = 176.9 MHz */
            clock-mult = <12>;
            clock-div = <2>;
        };

        cpu_clk: cpu-clk {
            compatible = "fixed-factor-clock";
            #clock-cells = <0>;
            clocks = <&pll>;
            clock-div = <1>;
            clock-mult = <1>;
        };

        ahb_clk: ahb-clk {
            compatible = "fixed-factor-clock";
            #clock-cells = <0>;
            clocks = <&pll>;
            clock-div = <2>;
            clock-mult = <1>;
        };

        bbus_clk: bbus-clk {
            compatible = "fixed-factor-clock";
            #clock-cells = <0>;
            clocks = <&pll>;
            clock-div = <4>;
            clock-mult = <1>;
        };
    };

    memory@0 {
        device_type = "memory";
        reg = <0x00000000 0x02000000>;  /* 32 MB SDRAM */
    };

    soc {
        compatible = "simple-bus";
        #address-cells = <1>;
        #size-cells = <1>;
        ranges;

        syscon: system-controller@a0900000 {
            compatible = "digi,ns9360-syscon";
            reg = <0xa0900000 0x100000>;
        };

        memctrl: memory-controller@a0700000 {
            compatible = "digi,ns9360-memctrl";
            reg = <0xa0700000 0x100000>;
        };

        bbus: bus@90600000 {
            compatible = "digi,ns9360-bbus", "simple-bus";
            reg = <0x90600000 0x100000>;
            #address-cells = <1>;
            #size-cells = <1>;
            ranges;

            gpio: gpio@90600010 {
                compatible = "digi,ns9360-gpio";
                reg = <0x90600010 0x160>;
                gpio-controller;
                #gpio-cells = <2>;
                /* 73 GPIOs (0-72) */
                ngpios = <73>;
            };
        };

        uart0: serial@90200000 {
            compatible = "digi,ns9360-uart";
            reg = <0x90200000 0x40>;
            clocks = <&bbus_clk>;
            status = "disabled";
        };

        uart1: serial@90200040 {
            compatible = "digi,ns9360-uart";
            reg = <0x90200040 0x40>;
            clocks = <&bbus_clk>;
            status = "okay";
            /* GPIO 8 = TxD, GPIO 9 = RxD */
        };

        uart2: serial@90300000 {
            compatible = "digi,ns9360-uart";
            reg = <0x90300000 0x40>;
            clocks = <&bbus_clk>;
            status = "disabled";
        };

        uart3: serial@90300040 {
            compatible = "digi,ns9360-uart";
            reg = <0x90300040 0x40>;
            clocks = <&bbus_clk>;
            status = "disabled";
        };

        ethernet: ethernet@a0600000 {
            compatible = "digi,ns9360-eth";
            reg = <0xa0600000 0x100000>;
            clocks = <&ahb_clk>;
            phy-mode = "mii";
            phy-handle = <&phy0>;

            mdio {
                #address-cells = <1>;
                #size-cells = <0>;

                phy0: ethernet-phy@1 {
                    compatible = "ethernet-phy-id0015.f441";  /* ICS1893AFLF OUI */
                    reg = <1>;
                };
            };
        };

        i2c: i2c@90400000 {
            compatible = "digi,ns9360-i2c";
            reg = <0x90400000 0x100>;
            clocks = <&bbus_clk>;
            clock-frequency = <100000>;
            #address-cells = <1>;
            #size-cells = <0>;
            /* GPIO 34 = SDA, GPIO 35 = SCL */
            status = "okay";
        };
    };

    flash@40000000 {
        compatible = "cfi-flash";
        reg = <0x40000000 0x00800000>;  /* 8 MB CS0 */
        bank-width = <2>;               /* 16-bit */
        #address-cells = <1>;
        #size-cells = <1>;

        partition@0 {
            label = "u-boot";
            reg = <0x00000000 0x00040000>;  /* 256 KB */
            read-only;
        };

        partition@40000 {
            label = "u-boot-env-backup";
            reg = <0x00040000 0x00010000>;  /* 64 KB */
        };

        partition@50000 {
            label = "kernel";
            reg = <0x00050000 0x00300000>;  /* 3 MB */
        };

        partition@350000 {
            label = "rootfs";
            reg = <0x00350000 0x004B0000>;  /* ~4.7 MB */
        };
    };

    flash@50000000 {
        compatible = "cfi-flash";
        reg = <0x50000000 0x00800000>;  /* 8 MB CS1 */
        bank-width = <2>;               /* 16-bit */
        #address-cells = <1>;
        #size-cells = <1>;

        partition@0 {
            label = "data";
            reg = <0x00000000 0x007F0000>;  /* ~8 MB - 64 KB */
        };

        partition@7f0000 {
            label = "u-boot-env";
            reg = <0x007F0000 0x00010000>;  /* 64 KB */
        };
    };
};
```

---

## 7. Driver Implementation

### 7.1 Serial Driver (Driver Model)

**File:** `drivers/serial/serial_ns9360.c`

The NS9360 UART driver using U-Boot's driver model (DM_SERIAL):

```c
// Key structures and operations:

struct ns9360_serial_priv {
    void __iomem *base;      // Channel base address
    unsigned long clk_rate;   // BBus clock frequency
};

// Register offsets (from channel base):
#define NS9360_CTRL_A      0x00
#define NS9360_CTRL_B      0x04
#define NS9360_STAT_A      0x08
#define NS9360_BITRATE     0x0C
#define NS9360_FIFO        0x10
#define NS9360_RX_CHAR_TMR 0x18

// CTRL_A bits:
#define CTRL_A_CE          BIT(31)    // Channel Enable
#define CTRL_A_WLS_8       (3 << 24)  // 8-bit word
#define CTRL_A_STOP        BIT(26)    // Stop bit (0=1bit, 1=2bits)

// STAT_A bits:
#define STAT_A_TRDY        BIT(3)     // TX Ready
#define STAT_A_RRDY        BIT(11)    // RX Ready (data available)

// BITRATE bits:
#define BITRATE_EBIT       BIT(31)    // Enable
#define BITRATE_CLKMUX_BCLK (1 << 24) // Use BBus clock
#define BITRATE_TMODE      BIT(30)    // Transmitter mode
#define BITRATE_TCDR_16    (2 << 19)  // TX clock ÷16
#define BITRATE_RCDR_16    (2 << 16)  // RX clock ÷16
#define BITRATE_N_MASK     0x7FFF     // Divisor mask

// Driver operations:
// probe():  Read clock rate from DT, configure GPIO, set CTRL_A
// setbrg(): Calculate N = (bbus_clk / (baud * 16)) - 1, write BITRATE
// putc():   Poll STAT_A for TRDY, write char to FIFO
// getc():   Read from FIFO (check RRDY first)
// pending(): Check STAT_A RRDY bit
```

### 7.2 GPIO Driver (Driver Model)

**File:** `drivers/gpio/ns9360_gpio.c`

```c
// NS9360 has 73 GPIOs (0-72) in two blocks:
// Block 1: GPIO 0-55,  config regs at BBUS + 0x10 + (gpio/8)*4
// Block 2: GPIO 56-72, config regs at BBUS + 0x100 + ((gpio-56)/8)*4

// Each GPIO uses 4 bits:
//   [1:0] = function select (0-2: special, 3: GPIO mode)
//   [2]   = invert
//   [3]   = direction (0: input, 1: output) [only when func=3]

// Control registers:
//   GCTRL1 (0x30): GPIOs 0-31 output values
//   GCTRL2 (0x34): GPIOs 32-63 output values
//   GCTRL3 (0x120): GPIOs 64-72 output values

// Status registers:
//   GSTAT1 (0x40): GPIOs 0-31 input values
//   GSTAT2 (0x44): GPIOs 32-63 input values
//   GSTAT3 (0x130): GPIOs 64-72 input values
```

### 7.3 Ethernet Driver (Driver Model)

**File:** `drivers/net/ns9360_eth.c`

Adapt from `reference/.../drivers/ns9750_eth.c` using U-Boot's DM_ETH:

```c
// Init sequence:
// 1. Configure GPIOs 50-64 for MII (function 0)
// 2. MAC hard reset (EGCR1 bit 9)
// 3. Configure MAC2 (CRC, pad, full-duplex)
// 4. Set SAFR (promiscuous for bring-up, then unicast+broadcast)
// 5. Load MAC address from DT/environment
// 6. Configure MDIO clock (MCFG: AHB/40 < 2.5 MHz)
// 7. Reset PHY via MDIO register 0 bit 15
// 8. Auto-negotiate link
// 9. Set up RX/TX buffer descriptors
// 10. Enable DMA (EGCR1: ERXDMA | ETXDMA)

// MII access functions:
// ns9360_mii_write(phy_addr, reg, value):
//   1. Write (phy_addr << 8 | reg) to MADR (0x0428)
//   2. Write value to MWTD (0x042C)
//   3. Poll MIND (0x0434) until busy=0
//
// ns9360_mii_read(phy_addr, reg):
//   1. Write (phy_addr << 8 | reg) to MADR (0x0428)
//   2. Write READ to MCMD (0x0424)
//   3. Poll MIND until busy=0 and nvalid=0
//   4. Read value from MRDD (0x0430)
//   5. Write 0 to MCMD (clear read command)
```

### 7.4 Clock Driver (Driver Model)

**File:** `drivers/clk/clk_ns9360.c`

```c
// Read PLL configuration from SYS_PLL register (0xA0900188):
//   ND = (pll_reg >> 16) & 0x1F  (multiply by ND+1)
//   FS = (pll_reg >> 23) & 0x3   (divide by 2^FS)
//   sys_clk = crystal_freq * (ND + 1) / (1 << FS)
//
// Derived clocks:
//   cpu_clk  = sys_clk      (÷1)
//   ahb_clk  = sys_clk / 2  (÷2)
//   bbus_clk = sys_clk / 4  (÷4)
//
// Note: CONFIG_SYS_CLK_FREQ = crystal * (ND+1) = raw PLL before FS divider
//       This is 353.89 MHz for the HPE iPDU (29.4912 * 12)
```

---

## 8. Implementation Plan

### Phase 1: Build Infrastructure

1. **Set up U-Boot source tree** (clone latest mainline)
2. **Create directory structure** (mach-ns9360, board/hpe/ipdu)
3. **Write Kconfig and Makefiles**
4. **Create device tree** (`ns9360-hpe-ipdu.dts`)
5. **Create defconfig** (`hpe_ipdu_defconfig`)
6. **Write board configuration header** (`include/configs/hpe_ipdu.h`)
7. **Verify build compiles** (empty stubs)

### Phase 2: lowlevel_init and Memory

1. **Write lowlevel_init.S** - SDRAM controller init (from CC9C platform.S)
   - Memory controller enable
   - SDRAM timing parameters
   - Precharge-all → mode register set → normal operation
   - AHB monitor setup
2. **Write dram_init()** - Report SDRAM size
3. **Verify in QEMU** - U-Boot starts and reports RAM

### Phase 3: Serial Driver

1. **Write serial_ns9360.c** using DM_SERIAL
2. **GPIO pin mux** for UART TxD/RxD
3. **Baud rate calculation** using BBus clock
4. **Test in QEMU** - U-Boot console interactive

### Phase 4: Flash Support

1. **Configure CFI flash driver** (use U-Boot built-in)
2. **Static memory controller init** for CS0 and CS1
3. **Flash partition table** via device tree
4. **Environment in flash** (`CONFIG_ENV_IS_IN_FLASH`)
5. **Test in QEMU** - `flinfo`, `erase`, `cp.b` commands

### Phase 5: Ethernet Driver

1. **Write ns9360_eth.c** using DM_ETH
2. **MDIO/MII management** functions
3. **PHY reset and auto-negotiate**
4. **TX/RX buffer descriptor management**
5. **Test in QEMU** - `ping`, `tftp` commands (with QEMU network backend)

### Phase 6: GPIO and Clock Drivers

1. **Write ns9360_gpio.c** using DM_GPIO
2. **Write clk_ns9360.c** using CLK framework
3. **Update all drivers** to use clock and GPIO frameworks
4. **Test** - `gpio` command in U-Boot

### Phase 7: Integration Testing

1. **Run full automated test suite**
2. **Verify all commands work**
3. **Test boot sequence with sample kernel**
4. **Generate final binary for hardware flashing**

---

## 9. Automated Testing with QEMU + pytest

### Test Framework

U-Boot has a built-in test framework using pytest. Tests run U-Boot in QEMU and
interact via the serial console.

### Test Configuration

**File:** `test/py/conftest.py` additions and `test/py/board_env/hpe_ipdu.py`:

```python
# Board environment for QEMU testing
env__net = True
env__net_dhcp = False
env__net_static_ip = "192.168.1.100"
env__net_static_gateway = "192.168.1.1"
env__net_static_netmask = "255.255.255.0"
```

### Test Scripts

#### Serial Driver Tests

```python
# test/py/tests/test_ns9360_serial.py

def test_serial_output(u_boot_console):
    """Verify serial console produces output."""
    response = u_boot_console.run_command("version")
    assert "U-Boot" in response

def test_serial_echo(u_boot_console):
    """Verify serial input/output."""
    response = u_boot_console.run_command("echo hello")
    assert "hello" in response

def test_baudrate_change(u_boot_console):
    """Verify baud rate can be changed and restored."""
    u_boot_console.run_command("setenv baudrate 9600")
    # Note: actual baud rate change test requires QEMU serial reconfiguration
```

#### Memory Tests

```python
# test/py/tests/test_ns9360_memory.py

def test_dram_size(u_boot_console):
    """Verify DRAM is detected as 32 MB."""
    response = u_boot_console.run_command("bdinfo")
    assert "32 MiB" in response or "0x02000000" in response

def test_memory_read_write(u_boot_console):
    """Verify memory read/write works."""
    u_boot_console.run_command("mw.l 0x00100000 0xDEADBEEF 1")
    response = u_boot_console.run_command("md.l 0x00100000 1")
    assert "deadbeef" in response.lower()

def test_memory_range(u_boot_console):
    """Verify full SDRAM range is accessible."""
    # Write to near-end of RAM
    u_boot_console.run_command("mw.l 0x01FFFFF0 0x12345678 1")
    response = u_boot_console.run_command("md.l 0x01FFFFF0 1")
    assert "12345678" in response
```

#### Flash Tests

```python
# test/py/tests/test_ns9360_flash.py

def test_flash_info(u_boot_console):
    """Verify flash banks are detected."""
    response = u_boot_console.run_command("flinfo")
    assert "Bank" in response
    # Should detect 2 banks at 0x40000000 and 0x50000000

def test_flash_erase_write(u_boot_console):
    """Test flash erase and write cycle on CS1."""
    # Use CS1 to avoid overwriting U-Boot
    u_boot_console.run_command("erase 0x50700000 +0x10000")
    u_boot_console.run_command("mw.b 0x00100000 0xAB 0x100")
    u_boot_console.run_command("cp.b 0x00100000 0x50700000 0x100")
    response = u_boot_console.run_command("md.b 0x50700000 0x10")
    assert "ab" in response.lower()

def test_environment_save_load(u_boot_console):
    """Test environment persistence."""
    u_boot_console.run_command("setenv test_var qemu_test_123")
    u_boot_console.run_command("saveenv")
    # Would need reboot to fully test persistence
```

#### Network Tests

```python
# test/py/tests/test_ns9360_network.py

def test_eth_init(u_boot_console):
    """Verify Ethernet initialises without errors."""
    response = u_boot_console.run_command("mdio list")
    # Should show PHY at address 1

def test_ping(u_boot_console):
    """Test network connectivity."""
    u_boot_console.run_command("setenv ipaddr 10.0.2.15")
    u_boot_console.run_command("setenv serverip 10.0.2.2")
    response = u_boot_console.run_command("ping 10.0.2.2")
    assert "alive" in response.lower()
```

### Running Tests

```bash
# Run all HPE iPDU tests
./test/py/test.py --bd-type hpe_ipdu --build-dir build

# Run specific test
./test/py/test.py --bd-type hpe_ipdu -k test_serial_output

# Run with verbose output
./test/py/test.py --bd-type hpe_ipdu -v
```

---

## 10. CI/CD Integration

### GitHub Actions Workflow

```yaml
# .github/workflows/uboot-ns9360.yml
name: U-Boot NS9360 Build and Test

on:
  push:
    paths:
      - 'arch/arm/mach-ns9360/**'
      - 'board/hpe/ipdu/**'
      - 'drivers/serial/serial_ns9360.c'
      - 'drivers/net/ns9360_eth.c'
      - 'drivers/gpio/ns9360_gpio.c'
      - 'configs/hpe_ipdu_defconfig'

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install cross-compiler
        run: |
          sudo apt-get update
          sudo apt-get install -y gcc-arm-linux-gnueabi

      - name: Build U-Boot
        run: |
          make CROSS_COMPILE=arm-linux-gnueabi- hpe_ipdu_defconfig
          make CROSS_COMPILE=arm-linux-gnueabi- -j$(nproc)

      - name: Upload binary
        uses: actions/upload-artifact@v4
        with:
          name: u-boot-hpe-ipdu
          path: u-boot.bin

  test:
    runs-on: ubuntu-latest
    needs: build
    steps:
      - uses: actions/checkout@v4

      - name: Install QEMU
        run: |
          sudo apt-get update
          sudo apt-get install -y qemu-system-arm

      - name: Download binary
        uses: actions/download-artifact@v4
        with:
          name: u-boot-hpe-ipdu

      - name: Run tests
        run: |
          pip install pytest
          ./test/py/test.py --bd-type hpe_ipdu --build-dir .
```

---

## 11. Board Configuration Header

### `include/configs/hpe_ipdu.h`

```c
#ifndef __HPE_IPDU_H
#define __HPE_IPDU_H

/* CPU and SoC */
#define CONFIG_ARM926EJS
#define CONFIG_NS9360
#define CONFIG_SYS_BIG_ENDIAN

/* Clock frequencies */
#define CRYSTAL_FREQ            29491200    /* 29.4912 MHz */
#define CONFIG_SYS_CLK_FREQ     353894400   /* PLL output: 29.4912 × 12 */
#define CPU_CLK_FREQ            176947200   /* PLL / 2 */
#define AHB_CLK_FREQ            88473600    /* PLL / 4 */
#define BBUS_CLK_FREQ           44236800    /* PLL / 8 */

/* Memory layout */
#define CONFIG_SYS_SDRAM_BASE   0x00000000
#define CONFIG_SYS_SDRAM_SIZE   0x02000000  /* 32 MB */
#define CONFIG_SYS_TEXT_BASE    0x40000000  /* Boot from CS0 */
#define CONFIG_SYS_INIT_SP_ADDR (CONFIG_SYS_SDRAM_BASE + CONFIG_SYS_SDRAM_SIZE - 4)
#define CONFIG_SYS_LOAD_ADDR    0x00200000  /* Default load address */
#define CONFIG_SYS_MALLOC_LEN   (256 * 1024)

/* Serial console */
#define CONFIG_BAUDRATE          115200
#define CONFIG_CONS_INDEX        2           /* Channel 1 = Port A */

/* NOR Flash */
#define CONFIG_SYS_FLASH_CFI
#define CONFIG_FLASH_CFI_DRIVER
#define CONFIG_SYS_FLASH_BASE           0x40000000
#define CONFIG_SYS_FLASH_BANKS_LIST     { 0x40000000, 0x50000000 }
#define CONFIG_SYS_MAX_FLASH_BANKS      2
#define CONFIG_SYS_MAX_FLASH_SECT       142     /* 71 × 2 chips */
#define CONFIG_SYS_FLASH_CFI_WIDTH      FLASH_CFI_16BIT
#define CONFIG_SYS_FLASH_PROTECTION

/* Environment in flash (last 64KB sector of CS1) */
#define CONFIG_ENV_IS_IN_FLASH
#define CONFIG_ENV_ADDR                 0x507F0000
#define CONFIG_ENV_SECT_SIZE            0x10000     /* 64 KB */
#define CONFIG_ENV_SIZE                 0x10000

/* Ethernet */
#define NS9360_ETH_PHY_ADDRESS          0x0001

/* Boot configuration */
#define CONFIG_BOOTDELAY                3
#define CONFIG_BOOTCOMMAND              "run bootcmd_flash"
#define CONFIG_EXTRA_ENV_SETTINGS \
    "bootcmd_flash=bootm 0x40050000\0" \
    "bootcmd_tftp=tftp 0x200000 uImage; bootm 0x200000\0" \
    "bootargs=console=ttyNS1,115200 root=/dev/mtdblock3 rootfstype=jffs2\0"

#endif /* __HPE_IPDU_H */
```

---

## Appendix A: Complete Register Quick Reference

### System Control Module (SYS_BASE = 0xA0900000)

| Offset | Name | Description |
|--------|------|-------------|
| 0x0044+n*4 | SYS_TRC(n) | Timer Reload Count |
| 0x0084+n*4 | SYS_TR(n) | Timer Read |
| 0x0170 | SYS_TIS | Timer Interrupt Status |
| 0x0184 | SYS_MISC | Miscellaneous Config (bit 3 = endian) |
| 0x0188 | SYS_PLL | PLL Configuration |
| 0x0190+n*4 | SYS_TC(n) | Timer Control |
| 0x01D0+n*8 | SYS_CS_DYN_BASE(n) | Dynamic Memory CS Base |
| 0x01D4+n*8 | SYS_CS_DYN_MASK(n) | Dynamic Memory CS Mask |
| 0x01F0+n*8 | SYS_CS_STAT_BASE(n) | Static Memory CS Base |
| 0x01F4+n*8 | SYS_CS_STAT_MASK(n) | Static Memory CS Mask |

### Memory Controller Module (MEM_BASE = 0xA0700000)

| Offset | Name | Description |
|--------|------|-------------|
| 0x0000 | MEM_CTRL | Controller Enable (bit 0) |
| 0x0008 | MEM_CFG | Config (bit 0 = endian) |
| 0x0020 | MEM_DYN_CTRL | Dynamic Control (PALL, MODE, NOP, NORMAL) |
| 0x0024 | MEM_DYN_REFRESH | Refresh Timer |
| 0x0028 | MEM_DYN_READ_CFG | Read Config |
| 0x0030-0x0058 | MEM_DYN_T* | SDRAM timing registers |
| 0x0100+n*0x20 | MEM_DYN_CFG(n) | Dynamic CS Config |
| 0x0104+n*0x20 | MEM_DYN_RAS_CAS(n) | RAS/CAS Latency |
| 0x0200+n*0x20 | MEM_STAT_CFG(n) | Static CS Config |
| 0x0204-0x0218 | MEM_STAT_WAIT_*(n) | Static CS Timing |

### BBus Utility Module (BBUS_BASE = 0x90600000)

| Offset | Name | Description |
|--------|------|-------------|
| 0x0000 | MASTER_RESET | Module reset (0 = activate all) |
| 0x0010+n*4 | GPIO_CFG(n) | GPIO config (8 per reg, 4 bits each) |
| 0x0030 | GPIO_CTRL1 | Output control (GPIO 0-31) |
| 0x0034 | GPIO_CTRL2 | Output control (GPIO 32-63) |
| 0x0040 | GPIO_STAT1 | Input status (GPIO 0-31) |
| 0x0044 | GPIO_STAT2 | Input status (GPIO 32-63) |
| 0x0080 | ENDIAN_CFG | Bus endianness config |
| 0x0100+n*4 | GPIO_CFG_B2(n) | Config block 2 (GPIO 56-72) |
| 0x0120 | GPIO_CTRL3 | Output control (GPIO 64-72) |
| 0x0130 | GPIO_STAT3 | Input status (GPIO 64-72) |

### Serial Module

| Channel | Base | TxD GPIO | RxD GPIO |
|---------|------|----------|----------|
| 0 | 0x90200000 | 0 | 1 |
| 1 (Port A) | 0x90200040 | 8 | 9 |
| 2 | 0x90300000 | 40 | 41 |
| 3 | 0x90300040 | 44 | 45 |

| Offset | Register | Key Bits |
|--------|----------|----------|
| 0x00 | CTRL_A | CE[31], WLS[25:24], STOP[26], PE[27] |
| 0x08 | STAT_A | TRDY[3], RRDY[11], TEMPTY[0] |
| 0x0C | BITRATE | EBIT[31], CLKMUX[25:24], N[14:0] |
| 0x10 | FIFO | TX/RX data |

### Ethernet Module (ETH_BASE = 0xA0600000)

| Offset | Register | Purpose |
|--------|----------|---------|
| 0x0000 | EGCR1 | Global control (RX/TX/DMA enable, PHY mode, reset) |
| 0x0004 | EGCR2 | Statistics, timeout |
| 0x0008 | EGSR | Status (RX init complete) |
| 0x0400 | MAC1 | RX enable, flow control, soft reset |
| 0x0404 | MAC2 | CRC, pad, full-duplex |
| 0x0408 | IPGT | InterPacket Gap TX |
| 0x0420 | MCFG | MDIO clock divisor |
| 0x0424 | MCMD | MDIO read/scan command |
| 0x0428 | MADR | MDIO address (PHY + register) |
| 0x042C | MWTD | MDIO write data |
| 0x0430 | MRDD | MDIO read data |
| 0x0434 | MIND | MDIO busy/valid indicators |
| 0x0440-0x0448 | SA1-SA3 | Station (MAC) address |
| 0x0500 | SAFR | Address filter (promiscuous, broadcast) |

---

## Appendix B: QEMU Machine Model Specification

### Minimal QEMU NS9360 Machine

The QEMU machine needs to model these components:

1. **CPU**: ARM926EJ-S, big-endian mode
2. **RAM**: 32 MB at 0x00000000
3. **Flash**: Two 8 MB pflash devices at 0x40000000 and 0x50000000
4. **UART**: Custom NS9360 UART at 0x90200040 (Port A)
5. **System registers**: Stub at 0xA0900000 (return PLL config when read)
6. **Memory controller**: Stub at 0xA0700000 (accept writes silently)
7. **BBus**: Stub at 0x90600000 (GPIO config, master reset)

### UART Model Requirements

The UART must correctly implement:
- STAT_A register with TRDY and RRDY flags
- FIFO register for character TX/RX
- CTRL_A register (accept writes, return stored value)
- BITRATE register (accept writes, return stored value)

### Network Model (Optional)

For TFTP/ping testing:
- Implement enough of the Ethernet MAC to send/receive frames
- Connect to QEMU's user-mode networking (`-net user`)
- MDIO interface returning ICS1893AFLF PHY ID

---

## Appendix C: Known Errata and Workarounds

1. **SDRAM settling time:** Wait ~80 AHB cycles after memory controller enable
   before issuing SDRAM commands.

2. **Flash address mirroring:** At reset, CS0 flash (0x40000000) is mirrored to
   0x00000000. The lowlevel_init must branch to the real address before modifying
   the memory controller.

3. **Serial RX gap timer bug:** In PLL bypass mode, the gap timer value must be 0
   with TRUN bit set (register value 0x80000000).

4. **SDRAM mode register set:** Requires a dummy read at an address encoding the
   mode. For CAS=2: read from base + 0x22000.

5. **PHY reset timing:** Wait at least 300 us (use 3000 us) after MDIO PHY reset
   before accessing PHY registers.

6. **Endian switching:** If needed, must be done from LCD palette RAM (0xA0800200)
   since the endian change affects instruction fetching. The HPE iPDU runs
   big-endian natively, so this is not needed unless switching to little-endian.
