# U-Boot Incremental Port for HPE iPDU (NS9360) - Phased Approach

## Purpose

This document is a **self-contained prompt** for a Claude Code session to execute an
incremental U-Boot port to the HPE Intelligent Modular PDU (AF531A). Each phase
produces a testable binary that can be flashed and verified on real hardware before
proceeding to the next phase.

**Strategy**: Build confidence incrementally. Each phase adds one subsystem, with
hardware verification between stages. This minimises debugging surface area - if
something breaks, you know exactly which change caused it.

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
0xA0800000 - 0xA08FFFFF  LCD Controller Module (AHB) [used for palette RAM trick]
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

| Parameter | Register | Value | Meaning |
|-----------|----------|-------|---------|
| tRP | MEM_DYN_TRP | 1 | Precharge command period |
| tRAS | MEM_DYN_TRAS | 4 | Active to precharge |
| tAPR | MEM_DYN_TAPR | 1 | Last data to active |
| tDAL | MEM_DYN_TDAL | 5 | Data-in to active |
| tWR | MEM_DYN_TWR | 1 | Write recovery |
| tRC | MEM_DYN_TRC | 6 | Active to active (same bank) |
| tRFC | MEM_DYN_TRFC | 6 | Auto-refresh period |
| tRRD | MEM_DYN_TRRD | 1 | Active bank A to B |
| tMRD | MEM_DYN_TMRD | 1 | Mode register set delay |
| CAS | RAS_CAS register | 2 | CAS latency (2 cycles) |
| RAS | RAS_CAS register | 3 | RAS latency (3 cycles) |
| Refresh | MEM_DYN_REFRESH | 0x30 | Refresh timer (operational) |

**SDRAM Mode Register (via address-line programming):**
- CAS=2 mode: Read from address 0x00022000 during mode register set command

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
| Erase timeout | Configurable (typically 30s per sector) |
| Write timeout | Configurable (typically 1s per word) |

**Static Memory Controller Settings (per chip select):**

| Register | Value | Meaning |
|----------|-------|---------|
| MEM_STAT_CFG | MW_16 \| PB | 16-bit width, page burst |
| MEM_STAT_WAIT_WEN | 0x2 | Write enable wait states |
| MEM_STAT_WAIT_OEN | 0x2 | Output enable wait states |
| MEM_STAT_RD | 0x6 | Read access time |
| MEM_STAT_WR | 0x6 | Write access time |

**System Chip Select Configuration:**

| Register | CS0 Value | CS1 Value |
|----------|-----------|-----------|
| SYS_CS_STATIC_BASE | 0x40000000 | 0x50000000 |
| SYS_CS_STATIC_MASK | 0xFF000001 | 0xFF000001 |

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

BITRATE register value:
  EBIT (bit 31)      = 1  (enable)
  CLKMUX (bits 25:24)= 01 (BCLK)
  TMODE (bit 30)     = 1  (transmit mode)
  TCDR (bits 20:19)  = 10 (÷16)
  RCDR (bits 18:16)  = 010 (÷16)
  N (bits 14:0)      = 23

Value: 0xE1100017
```

**CTRL_A register value for 8N1:**
```
  CE (bit 31)        = 1  (channel enable)
  WLS (bits 25:24)   = 11 (8-bit)
  STOP (bit 26)      = 0  (1 stop bit)
  PE (bit 27)        = 0  (no parity)

Value: 0x83000000
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
| GPIO Pins | GPIO 50-64 (function 0, Ethernet MII signals) |

### I2C

| Property | Value |
|----------|-------|
| SDA GPIO | GPIO 34 (function 2) |
| SCL GPIO | GPIO 35 (function 2) |
| Speed | 100 kHz (standard) or 400 kHz (fast) |
| Known Devices | EEPROM (address TBD, test point on bus) |

### Key SoC Register Modules

| Module | Base Address | Key Registers |
|--------|-------------|---------------|
| System Control (SYS) | 0xA0900000 | PLL (0x188), GPIO config, timers, interrupts, CS base/mask |
| Memory Controller (MEM) | 0xA0700000 | SDRAM timing, static memory config |
| Ethernet (ETH) | 0xA0600000 | MAC, MII management, DMA, FIFOs |
| Serial (SER) | 0x90200000 | UART control, baud rate, FIFO |
| BBus Utility (BBUS) | 0x90600000 | GPIO control/status, master reset, endian config |

---

## 2. Reference Material Locations

All paths are relative to the `uboot-port/` directory.

### Primary Reference: Digi U-Boot 1.1.4 Source

**Root:** `reference/digi-cc9p9360-uboot/u-boot-1.1.4-digi/U-Boot/`

| File | Description |
|------|-------------|
| `board/cc9c/cc9c.c` | Board init, SDRAM detection, flash CS1 setup, GPIO |
| `board/cc9c/platform.S` | Low-level init: SDRAM timing, memory controller, AHB monitor |
| `board/cc9c/switch_to_le.S` | Endianness switching (big→little), LCD palette RAM trick |
| `board/cc9c/flash.c` | NOR flash driver (sector layout, erase, program sequences) |
| `board/cc9c/nand.c` | NAND flash support (not needed for HPE iPDU) |
| `drivers/ns9750_eth.c` | Ethernet MAC driver (GPIO setup, MAC init, PHY reset/negotiate) |
| `drivers/ns9750_serial.c` | UART driver (GPIO config, baud rate calc, FIFO ops) |
| `drivers/ns9750_i2c.c` | I2C master driver |
| `include/configs/cc9c.h` | CC9C board config (all CONFIG_ values) |
| `include/configs/digi_common.h` | Digi common command definitions |
| `include/ns9750_sys.h` | System control register definitions |
| `include/ns9750_mem.h` | Memory controller register definitions |
| `include/ns9750_bbus.h` | BBus register definitions (GPIO, reset, endian) |
| `include/ns9750_ser.h` | Serial port register definitions |
| `include/ns9750_eth.h` | Ethernet MAC register definitions |

### Secondary Reference: Digi U-Boot 1.1.3 Source

**Root:** `reference/digi-cc9p9360-uboot/u-boot-1.1.3-digi/U-Boot/`

Useful for diffing against 1.1.4 to understand changes.

### Mainline U-Boot v2012.10 (NS9750dev Board)

**Root:** `reference/ns9750dev-uboot/u-boot-v2012.10/` (git submodule)

| File | Description |
|------|-------------|
| `board/ns9750dev/lowlevel_init.S` | Simpler low-level init (reference for memory controller) |
| `board/ns9750dev/ns9750dev.c` | Board init (BBUS reset pattern) |
| `drivers/serial/ns9750_serial.c` | Mainline serial driver |
| `include/configs/ns9750dev.h` | NS9750 board config (clock freq definitions) |
| `include/ns9750_*.h` | Register headers (same definitions as Digi) |

### Linux Kernel mach-ns9xxx (v2.6.39)

**Root:** `reference/linux-mach-ns9xxx/linux-v2.6.39/` (git submodule, shallow)

| File | Description |
|------|-------------|
| `arch/arm/mach-ns9xxx/processor-ns9360.c` | Clock calculation, PLL readback |
| `arch/arm/mach-ns9xxx/gpio-ns9360.c` | GPIO config (pin mux, direction, value) |
| `arch/arm/mach-ns9xxx/time-ns9360.c` | Timer init sequence |
| `arch/arm/mach-ns9xxx/clock.c` | Clock tree management |
| `arch/arm/mach-ns9xxx/include/mach/regs-sys-ns9360.h` | System register macros |
| `arch/arm/mach-ns9xxx/include/mach/regs-bbu.h` | BBU register macros |
| `arch/arm/mach-ns9xxx/include/mach/regs-mem.h` | Memory register macros |

### Hardware Documentation

**Root:** `reference/docs/`

| File | Description |
|------|-------------|
| `connectcore-9p-9360-hardware-reference.pdf` | CC9P9360 module hardware reference |
| `lxnetes-users-guide-cc9p9360-9750.pdf` | Linux BSP guide with U-Boot build info |
| `ns9360-x32-dram-application-note.pdf` | 32-bit SDRAM configuration guide |
| `ns9360-gpio-pin-mux.pdf` | GPIO multiplexing reference |
| `ns9360-gpio-table.pdf` | Complete GPIO function table |
| `digi-uboot-reference-manual.pdf` | Digi U-Boot command reference |

**NS9360 Datasheets (parent directory):**

| File | Description |
|------|-------------|
| `../datasheets/NS9360_datasheet_91001326_D.pdf` | NS9360 datasheet |
| `../datasheets/NS9360_HW_Reference_90000675_J.pdf` | **Definitive register reference** |

### Pre-compiled Binaries (for disassembly/comparison)

| File | Description |
|------|-------------|
| `reference/digi-cc9p9360-uboot/binaries/u-boot-cc9p9360js-v1.1.4e.bin` | U-Boot 1.1.4 binary (238 KB) |
| `reference/digi-cc9p9360-uboot/binaries/u-boot-cc9p9360js-v1.1.6-revf6.bin` | U-Boot 1.1.6 binary (257 KB) |

### Reference Material Index

`REFERENCE-MATERIAL.md` - Complete inventory of all reference material with descriptions.

---

## 3. Key Differences: CC9C Reference → HPE iPDU

These are the critical adaptations needed when porting from the CC9C reference:

| Feature | CC9C (Digi Reference) | HPE iPDU (Target) | Action |
|---------|----------------------|-------------------|--------|
| Boot flash | CS1 @ 0x50000000 | CS0 @ 0x40000000 | Change flash base, CS config, mirror bit |
| Second flash | None | CS1 @ 0x50000000 (8 MB) | Add CS1 static memory init |
| Console baud | 38400 | 115200 | Change CONFIG_BAUDRATE, recalc N |
| Console port | Port A (index 1) | Port A (index 1) @ J25 | Verify GPIO8/9 mapping |
| SDRAM | Variable (16-64 MB) | Fixed 32 MB IS42S32800D | Hardcode or detect, verify timing |
| Ethernet PHY | Various (LXT971A, etc.) | ICS1893AFLF | Add PHY ID, verify MII init |
| PHY Address | 0x0001 | 0x0001 (verify) | Confirm via MDIO scan |
| NAND flash | Optional | Not present | Disable CONFIG_CC9C_NAND |
| Endianness | Big-endian (default) | Big-endian | Keep default (no endian switch needed) |
| I2C EEPROM | M24LC64 @ 0x50 | Unknown | Probe I2C bus to discover |

---

## 4. Cross-Compiler Setup

The NS9360 is an ARM926EJ-S (ARMv5TEJ) running in **big-endian** mode.

### Install ARM Big-Endian Toolchain

```bash
# Option 1: Debian/Ubuntu cross-compiler package
sudo apt install gcc-arm-linux-gnueabi

# Option 2: Download Linaro/ARM toolchain for ARMv5 big-endian
# The Digi toolchain was arm-linux-gnueabi with -mbig-endian flag

# Verify:
arm-linux-gnueabi-gcc -v
```

### U-Boot Build Configuration

```bash
# For the incremental port, we'll create a new defconfig
# The cross-compiler prefix:
export CROSS_COMPILE=arm-linux-gnueabi-

# Build with big-endian:
# U-Boot's ARM926EJS support handles this via board config
# CONFIG_SYS_BIG_ENDIAN=y in the board header
```

### Key Compiler Flags

```
-march=armv5te -mbig-endian -mabi=aapcs-linux
```

---

## 5. Flash Programming Instructions

### Option A: Using Existing NET+OS Bootloader

If the existing NET+OS firmware has a serial download capability:
1. Connect to J25 debug UART at 115200/8/N/1
2. Use the NET+OS bootloader's flash programming commands
3. Program the U-Boot binary to the appropriate flash region

### Option B: JTAG Programming

The NS9360 supports JTAG via the standard ARM debug interface.

```bash
# Using OpenOCD with an appropriate JTAG adapter:
openocd -f interface/ftdi/your-adapter.cfg \
        -f target/arm926ejs.cfg \
        -c "init; halt; flash write_image erase u-boot.bin 0x40000000; resume; shutdown"
```

### Option C: Programming via U-Boot (once running)

Once a minimal U-Boot is running:
```
# Load new image via serial (YMODEM):
loady 0x00200000
# Or via TFTP (once ethernet works):
tftp 0x00200000 u-boot.bin

# Erase and program flash:
protect off all
erase 0x40000000 +${filesize}
cp.b 0x00200000 0x40000000 ${filesize}
```

---

## Phase 1: Minimal Boot - Serial Console "Hello"

**Goal:** Get the CPU running, memory controller initialised, and print "Hello from U-Boot"
to the serial console.

**Produces:** A binary that, when flashed to CS0 (0x40000000), outputs text on UART Port A.

### Files to Create/Modify

Based on modern U-Boot structure (use the latest mainline as the base tree):

1. **`arch/arm/mach-ns9360/`** - New SoC directory
   - `Kconfig` - SoC Kconfig entries
   - `Makefile`
   - `lowlevel_init.S` - Minimal memory controller init (adapted from CC9C platform.S)

2. **`board/hpe/ipdu/`** - New board directory
   - `Kconfig`
   - `Makefile`
   - `ipdu.c` - Board init stub
   - `MAINTAINERS`

3. **`include/configs/hpe_ipdu.h`** - Board configuration header

4. **`configs/hpe_ipdu_defconfig`** - Defconfig

5. **`drivers/serial/serial_ns9360.c`** - Minimal serial driver

### Step-by-Step Implementation

#### 1.1 Create lowlevel_init.S

Adapt from `reference/.../board/cc9c/platform.S`. This must:

1. **Enable memory controller** (MEM_CTRL @ 0xA0700000 + 0x0000):
   ```
   Write 0x00000001 to (MEM_BASE + 0x0000)  ; MEM_CTRL_E
   ```

2. **Set SDRAM refresh** (initial low rate):
   ```
   Write 0x00000006 to (MEM_BASE + 0x0024)  ; DYN_REFRESH
   ```

3. **Set SDRAM read config**:
   ```
   Write 0x00000001 to (MEM_BASE + 0x0028)  ; DYN_READ_CFG delay1
   ```

4. **Set SDRAM timing** (all at MEM_BASE + offset):
   ```
   Write 0x1 to +0x0030  ; TRP
   Write 0x4 to +0x0034  ; TRAS
   Write 0x1 to +0x003C  ; TAPR
   Write 0x5 to +0x0040  ; TDAL
   Write 0x1 to +0x0044  ; TWR
   Write 0x6 to +0x0048  ; TRC
   Write 0x6 to +0x004C  ; TRFC
   Write 0x1 to +0x0054  ; TRRD
   Write 0x1 to +0x0058  ; TMRD
   ```

5. **Issue Precharge All command**:
   ```
   Write 0x00000103 to (MEM_BASE + 0x0020)  ; DYN_CTRL = I_PALL | BIT1 | CE
   ```

6. **Set minimum refresh and wait**:
   ```
   Write 0x00000001 to (MEM_BASE + 0x0024)  ; DYN_REFRESH = 1
   Wait ~80 AHB cycles (delay loop)
   ```

7. **Increase refresh rate**:
   ```
   Write 0x00000030 to (MEM_BASE + 0x0024)  ; DYN_REFRESH = 0x30
   ```

8. **Configure SDRAM CS4** (MEM_DYN_CFG(0) = MEM_BASE + 0x0100):
   ```
   Write 0x00004500 | 0x00004000 to (MEM_BASE + 0x0100)  ; AM | address config
   Write 0x00000203 to (MEM_BASE + 0x0104)  ; CAS=2, RAS=3
   ```

9. **Issue Mode Register Set command**:
   ```
   Write 0x00000083 to (MEM_BASE + 0x0020)  ; DYN_CTRL = I_MODE | BIT1 | CE
   ```

10. **Perform CAS2 mode register read** (dummy read to set mode):
    ```
    ldr r0, =0x00022000  ; CAS=2 latency address encoding
    ldr r0, [r0]         ; Dummy read triggers SDRAM mode register set
    ```

11. **Set Normal operation mode**:
    ```
    Write 0x00000003 to (MEM_BASE + 0x0020)  ; DYN_CTRL = I_NORMAL | BIT1 | CE
    ```

12. **Enable buffer DMA control**:
    ```
    Write (BDMC | AM | addr_config) to (MEM_BASE + 0x0100)  ; DYN_CFG(0)
    ```

13. **Set up AHB monitor** (prevents bus lockup):
    ```
    Write 0x01000100 to (SYS_BASE + AHB_TIMEOUT offset)
    Write (BMTC_GEN_IRQ | BATC_GEN_IRQ) to (SYS_BASE + AHB_MON offset)
    ```

**Critical note:** The code initially runs from flash at 0x40000000 but may be
mirrored to 0x00000000 at reset. The lowlevel_init must handle this address
remapping correctly. See the CC9C platform.S for the mirror-aware branch pattern.

#### 1.2 Create Minimal Serial Driver

Adapt from `reference/.../drivers/ns9750_serial.c`:

```c
// Minimal serial output for Phase 1
// Register base for Port A (channel 1)
#define UART_BASE   0x90200040

// GPIO configuration
// GPIO 8 = TxD (function 0, output): config at BBUS + 0x10 + (8/8)*4
// GPIO 9 = RxD (function 0, input):  config at BBUS + 0x10 + (9/8)*4

// Init sequence:
// 1. Configure GPIO 8 as function 0, output (TxD)
// 2. Configure GPIO 9 as function 0, input (RxD)
// 3. Set CTRL_A = 0x83000000 (CE | WLS_8)
// 4. Set BITRATE = 0xE1100017 (EBIT | CLKMUX_BCLK | TMODE | TCDR_16 | RCDR_16 | N=23)
// 5. Set RX_CHAR_TIMER = 0x80000000 (TRUN, value=0)
// 6. Set CTRL_B = 0x04000000 (RCGT enable)

// Transmit character:
// 1. Poll STAT_A bit 3 (TRDY) until set
// 2. Write character to FIFO register
```

**GPIO Configuration Details:**

Each GPIO uses 4 bits in a config register. GPIO 8 is in the config register at
BBUS + 0x10 + (8/8)*4 = 0x90600014, bits [3:0]:
- Bits [1:0] = 0x00 (function 0)
- Bit [3] = 1 (output direction)
- Value for GPIO 8: 0x08 (function 0, output)

GPIO 9 is at BBUS + 0x10 + (9/8)*4 = 0x90600014, bits [7:4]:
- Bits [5:4] = 0x00 (function 0)
- Bit [7] = 0 (input direction)
- Value for GPIO 9: 0x00 (function 0, input)

#### 1.3 Board Config Header

Create `include/configs/hpe_ipdu.h` with minimal settings:

```c
#define CONFIG_SYS_TEXT_BASE        0x40000000  /* Boot from CS0 flash */
#define CONFIG_SYS_CLK_FREQ        353894400   /* PLL output: 29.4912 MHz × 12 */
#define CONFIG_SYS_SDRAM_BASE      0x00000000
#define CONFIG_SYS_SDRAM_SIZE      0x02000000  /* 32 MB */
#define CONFIG_SYS_INIT_SP_ADDR    (CONFIG_SYS_SDRAM_BASE + CONFIG_SYS_SDRAM_SIZE - 4)
#define CONFIG_BAUDRATE             115200
#define CONFIG_CONS_INDEX           2  /* Serial channel 1 = Port A */
```

### Verification Steps (Phase 1)

1. **Build the binary:**
   ```bash
   make hpe_ipdu_defconfig
   make CROSS_COMPILE=arm-linux-gnueabi- -j$(nproc)
   ```

2. **Flash to CS0 (0x40000000)** using JTAG or existing bootloader

3. **Connect serial terminal** to J25 at 115200/8N1

4. **Expected output:**
   ```
   Hello from U-Boot on HPE iPDU (NS9360)
   ```

5. **If no output:**
   - Verify JTAG connection and flash programming
   - Check if CPU is running (toggle a GPIO/LED if available)
   - Verify baud rate settings (try 38400 as fallback)
   - Check GPIO 8/9 pin assignment against board schematic

---

## Phase 2: SDRAM Initialisation and Memory Test

**Goal:** Properly initialise SDRAM, relocate U-Boot to RAM, and run memory diagnostics.

**Depends on:** Phase 1 (serial console working)

### Implementation

#### 2.1 Full SDRAM Initialisation

The lowlevel_init.S from Phase 1 should already initialise SDRAM. In this phase:

1. **Verify SDRAM is accessible:** Write/read patterns to several addresses
2. **Detect SDRAM size** (adapt from cc9c.c `dram_init()`):
   - Read CS4 base from SYS_CS_DYN_BASE(0) @ SYS_BASE + 0x1D0
   - Read CS4 mask from SYS_CS_DYN_MASK(0) @ SYS_BASE + 0x1D4
   - Size = (mask & ~1) + 2

3. **Enable U-Boot relocation to SDRAM:**
   - Set `CONFIG_SYS_INIT_RAM_ADDR` and relocation address
   - Let U-Boot's `board_init_f` → `board_init_r` relocation sequence work

#### 2.2 Board Init (C code)

In `board/hpe/ipdu/ipdu.c`:

```c
int board_init(void) {
    // Reset BBUS modules
    // (BBUS_MASTER_RESET @ 0x90600000) = 0
    writel(0, 0x90600000);

    // Set boot params location
    gd->bd->bi_boot_params = 0x00000100;

    // Enable I-cache for faster execution
    icache_enable();

    return 0;
}

int dram_init(void) {
    gd->ram_size = CONFIG_SYS_SDRAM_SIZE;  // 32 MB
    return 0;
}
```

### Verification Steps (Phase 2)

1. **Expected serial output:**
   ```
   U-Boot 2024.xx (date) for HPE iPDU

   DRAM:  32 MiB
   ```

2. **Run memory test:**
   ```
   mtest 0x00000000 0x01FFFFFF
   ```
   Should pass with no errors.

3. **Check relocation:**
   ```
   bdinfo
   ```
   Should show relocation address in high SDRAM.

---

## Phase 3: NOR Flash Driver (CFI)

**Goal:** Enable flash read/write/erase for both CS0 and CS1 flash chips.

**Depends on:** Phase 2 (SDRAM working, U-Boot running from RAM)

### Implementation

#### 3.1 Static Memory Controller Setup for Flash

For CS0 (boot device, already configured by hardware at reset):
```c
// CS0 should already be configured since we boot from it
// But verify/reinforce the settings:
// SYS_CS_STATIC_BASE(0) = 0x40000000
// SYS_CS_STATIC_MASK(0) = 0xFF000001
```

For CS1 (secondary flash, needs software setup):
```c
// Adapt from cc9c.c flash__init():
writel(0x50000000, SYS_BASE + CS_STATIC_BASE(1));  // Base address
writel(0xFF000001, SYS_BASE + CS_STATIC_MASK(1));   // 8 MB mask, enable
writel(MW_16 | PB,  MEM_BASE + STAT_CFG(1));        // 16-bit, page burst
writel(0x2, MEM_BASE + STAT_WAIT_WEN(1));
writel(0x2, MEM_BASE + STAT_WAIT_OEN(1));
writel(0x6, MEM_BASE + STAT_RD(1));
writel(0x6, MEM_BASE + STAT_WR(1));
```

#### 3.2 Flash Configuration

Use U-Boot's built-in CFI flash driver (`drivers/mtd/cfi_flash.c`):

```c
// In board config header:
#define CONFIG_SYS_FLASH_CFI
#define CONFIG_FLASH_CFI_DRIVER
#define CONFIG_SYS_FLASH_BASE       0x40000000
#define CONFIG_SYS_FLASH_BANKS_LIST { 0x40000000, 0x50000000 }
#define CONFIG_SYS_MAX_FLASH_BANKS  2
#define CONFIG_SYS_MAX_FLASH_SECT   142  /* 71 sectors × 2 chips */
#define CONFIG_SYS_FLASH_USE_BUFFER_WRITE  /* if supported by Macronix chip */
#define CONFIG_SYS_FLASH_PROTECTION

// Flash is 16-bit wide:
#define CONFIG_SYS_FLASH_CFI_WIDTH  FLASH_CFI_16BIT
```

The Macronix MX29LV640EBXEI is CFI-compatible, so the standard CFI driver should
detect it automatically. The CFI driver will:
1. Issue CFI Query command (write 0x98 to address 0x55)
2. Read CFI data structure
3. Determine sector layout, erase block sizes, timing

### Verification Steps (Phase 3)

1. **Expected output at boot:**
   ```
   Flash: 16 MiB
   ```

2. **Verify flash detection:**
   ```
   flinfo
   ```
   Should show both banks with correct sector layouts:
   - Bank 1 @ 0x40000000: 71 sectors (8×8KB + 63×64KB)
   - Bank 2 @ 0x50000000: 71 sectors (same layout)

3. **Test flash erase/write** (use a safe area, NOT the U-Boot image area):
   ```
   # Test on CS1 (secondary flash, safe to modify)
   erase 0x50000000 +0x10000
   mw.b 0x00100000 0xAA 0x100
   cp.b 0x00100000 0x50000000 0x100
   md.b 0x50000000 0x100
   ```
   Should show 0xAA pattern.

---

## Phase 4: Environment Storage in Flash

**Goal:** Store and retrieve U-Boot environment variables in flash.

**Depends on:** Phase 3 (flash driver working)

### Implementation

Choose a flash sector for environment storage. Use the top of CS1 to avoid
interfering with the boot image on CS0:

```c
#define CONFIG_ENV_IS_IN_FLASH
#define CONFIG_ENV_ADDR         0x507F0000  /* Last 64KB sector of CS1 */
#define CONFIG_ENV_SECT_SIZE    0x10000     /* 64 KB sector */
#define CONFIG_ENV_SIZE         0x10000     /* Use full sector */
#define CONFIG_ENV_OVERWRITE                /* Allow overwriting */
```

### Verification Steps (Phase 4)

1. **Set and save environment:**
   ```
   setenv testvar hello
   saveenv
   ```
   Should print "Saving Environment to Flash..."

2. **Reboot and verify persistence:**
   ```
   reset
   # After reboot:
   printenv testvar
   ```
   Should show `testvar=hello`

3. **Set up useful defaults:**
   ```
   setenv baudrate 115200
   setenv bootdelay 3
   setenv ethaddr XX:XX:XX:XX:XX:XX  # Read from existing firmware if possible
   saveenv
   ```

---

## Phase 5: Ethernet Driver

**Goal:** Enable network booting (TFTP) and network connectivity.

**Depends on:** Phase 4 (environment storage for MAC address, IP config)

### Implementation

#### 5.1 Ethernet GPIO Setup

Configure GPIOs 50-64 for Ethernet MII signals (all function 0):

```c
// In board_init() or board_late_init():
for (int gpio = 50; gpio <= 64; gpio++) {
    // Set GPIO to function 0 (Ethernet)
    // Each GPIO uses 4 bits in its config register
    ns9360_gpio_configure(gpio, NS9750_GPIO_CFG_FUNC_0);
}
```

#### 5.2 Ethernet MAC Driver

Adapt from `reference/.../drivers/ns9750_eth.c`. The init sequence:

1. **MAC Hard Reset:**
   ```c
   // Set MAC_HRST | ERX | ETX in EGCR1
   writel(0x00800200 | 0x80000000 | 0x00800000, ETH_BASE + 0x0000);
   udelay(5);
   // Clear MAC_HRST
   val = readl(ETH_BASE + 0x0000);
   val &= ~0x00000200;
   writel(val, ETH_BASE + 0x0000);
   ```

2. **Configure MAC:**
   ```c
   // MAC2: CRC enable | Pad enable | Full duplex
   writel(0x00000011 | 0x00000020, ETH_BASE + 0x0404);
   // SAFR: Promiscuous (for initial bring-up)
   writel(0x00000008, ETH_BASE + 0x0500);
   ```

3. **Set MAC address** (from environment variable `ethaddr`)

4. **Configure MII management** for PHY access:
   ```c
   // MCFG: Set clock divider for MDIO (AHB_CLK / divisor < 2.5 MHz)
   // AHB = 88.5 MHz, need divisor ≥ 36, use /40
   writel(0x0000001C, ETH_BASE + 0x0420);  // CLKS_40
   ```

5. **Reset and identify PHY:**
   ```c
   // Write PHY_CTRL register 0 via MDIO: bit 15 = reset
   ns9360_mii_write(0x0001, 0x00, 0x8000);
   udelay(3000);
   ns9360_mii_write(0x0001, 0x00, 0x0000);

   // Read PHY ID (registers 2 and 3)
   // ICS1893AFLF should return OUI for ICS
   uint16_t id1 = ns9360_mii_read(0x0001, 0x02);
   uint16_t id2 = ns9360_mii_read(0x0001, 0x03);
   ```

6. **Auto-negotiate link:**
   ```c
   // Set advertise: 10/100 half/full
   ns9360_mii_write(0x0001, 0x04, 0x01E1);  // All capabilities + 802.3
   // Enable auto-negotiation
   ns9360_mii_write(0x0001, 0x00, 0x1200);  // Auto-neg enable + restart
   // Wait for completion (up to 5 seconds)
   ```

7. **Enable DMA and RX/TX**

#### 5.3 MII Read/Write Functions

```c
// MII Write:
// 1. Set MADR = (phy_addr << 8) | reg_addr
// 2. Write data to MWTD
// 3. Poll MIND for busy=0

// MII Read:
// 1. Set MADR = (phy_addr << 8) | reg_addr
// 2. Set MCMD = READ
// 3. Poll MIND for busy=0 and nvalid=0
// 4. Read data from MRDD
// 5. Clear MCMD
```

### Verification Steps (Phase 5)

1. **Check PHY detection:**
   ```
   mdio list
   ```
   Should show ICS1893AFLF at address 0x01

2. **Configure network:**
   ```
   setenv ipaddr 192.168.1.100
   setenv serverip 192.168.1.1
   setenv netmask 255.255.255.0
   ```

3. **Test connectivity:**
   ```
   ping 192.168.1.1
   ```

4. **Test TFTP:**
   ```
   tftp 0x00200000 test.bin
   ```

5. **If ping fails:**
   - Check PHY link status: `mdio read 0x01 0x01` (register 1, bit 2 = link)
   - Verify GPIO 50-64 configuration
   - Check cable connection and switch
   - Try forcing 10Mbps half-duplex: `mdio write 0x01 0x00 0x0000`

---

## Phase 6: Full U-Boot with Boot Commands

**Goal:** Complete U-Boot with all standard commands, ready for loading an OS.

**Depends on:** Phase 5 (all hardware drivers working)

### Implementation

1. **Enable standard commands:**
   ```c
   // In defconfig or board header:
   CONFIG_CMD_MEMORY=y
   CONFIG_CMD_FLASH=y
   CONFIG_CMD_NET=y
   CONFIG_CMD_PING=y
   CONFIG_CMD_DHCP=y
   CONFIG_CMD_TFTP=y
   CONFIG_CMD_BOOTM=y
   CONFIG_CMD_GO=y
   CONFIG_CMD_RUN=y
   CONFIG_CMD_ENV=y
   CONFIG_CMD_ECHO=y
   CONFIG_CMD_I2C=y  // If I2C driver added
   ```

2. **Set up boot commands:**
   ```c
   #define CONFIG_BOOTCOMMAND  "tftp 0x00200000 uImage; bootm 0x00200000"
   #define CONFIG_BOOTARGS     "console=ttyS1,115200 root=/dev/mtdblock2 rootfstype=jffs2"
   ```

3. **Add I2C driver** (optional, for EEPROM access):
   - Adapt from `reference/.../drivers/ns9750_i2c.c`
   - GPIO 34 (SDA), GPIO 35 (SCL), both function 2

4. **Add watchdog support** (if NS9360 has one)

5. **Flash partition layout:**
   ```
   CS0 (0x40000000, 8 MB):
     0x40000000 - 0x4003FFFF: U-Boot (256 KB)
     0x40040000 - 0x4004FFFF: U-Boot environment (64 KB, backup)
     0x40050000 - 0x407FFFFF: Kernel + rootfs

   CS1 (0x50000000, 8 MB):
     0x50000000 - 0x507EFFFF: Application data
     0x507F0000 - 0x507FFFFF: U-Boot environment (primary, 64 KB)
   ```

### Verification Steps (Phase 6)

1. **Full boot test:**
   ```
   # Power on, should auto-boot after delay
   # Or interrupt and test manually:
   version
   bdinfo
   flinfo
   ```

2. **TFTP boot test:**
   ```
   dhcp 0x00200000 uImage
   bootm 0x00200000
   ```

3. **Flash update test:**
   ```
   tftp 0x00200000 u-boot-new.bin
   protect off 0x40000000 +0x40000
   erase 0x40000000 +0x40000
   cp.b 0x00200000 0x40000000 ${filesize}
   protect on 0x40000000 +0x40000
   reset
   ```

---

## Appendix A: Complete Register Quick Reference

### System Control Module (SYS_BASE = 0xA0900000)

| Offset | Name | Description |
|--------|------|-------------|
| 0x0004+x | SYS_BRC(x) | Bus Request Control |
| 0x0044+x | SYS_TRC(x) | Timer Reload Count |
| 0x0084+x | SYS_TR(x) | Timer Read |
| 0x0170 | SYS_TIS | Timer Interrupt Status |
| 0x0184 | SYS_MISC | Miscellaneous Config (bit 3 = endian) |
| 0x0188 | SYS_PLL | PLL Configuration |
| 0x0190+x | SYS_TC(x) | Timer Control |
| 0x01D0+x*8 | SYS_CS_DYN_BASE(x) | Dynamic Memory CS Base |
| 0x01D4+x*8 | SYS_CS_DYN_MASK(x) | Dynamic Memory CS Mask |
| 0x01F0+x*8 | SYS_CS_STAT_BASE(x) | Static Memory CS Base |
| 0x01F4+x*8 | SYS_CS_STAT_MASK(x) | Static Memory CS Mask |
| 0x0210 | SYS_GENID | General ID Register |

### Memory Controller Module (MEM_BASE = 0xA0700000)

| Offset | Name | Description |
|--------|------|-------------|
| 0x0000 | MEM_CTRL | Controller Enable (bit 0) |
| 0x0008 | MEM_CFG | Config (bit 0 = endian strapping) |
| 0x0020 | MEM_DYN_CTRL | Dynamic Control (command mode) |
| 0x0024 | MEM_DYN_REFRESH | Refresh Timer |
| 0x0028 | MEM_DYN_READ_CFG | Read Configuration |
| 0x0030 | MEM_DYN_TRP | Precharge Period |
| 0x0034 | MEM_DYN_TRAS | Active to Precharge |
| 0x003C | MEM_DYN_TAPR | Last Data to Active |
| 0x0040 | MEM_DYN_TDAL | Data-in to Active |
| 0x0044 | MEM_DYN_TWR | Write Recovery |
| 0x0048 | MEM_DYN_TRC | Active to Active |
| 0x004C | MEM_DYN_TRFC | Refresh to Active |
| 0x0054 | MEM_DYN_TRRD | Bank A to Bank B |
| 0x0058 | MEM_DYN_TMRD | Mode Register Delay |
| 0x0100+n*0x20 | MEM_DYN_CFG(n) | Dynamic CS Config |
| 0x0104+n*0x20 | MEM_DYN_RAS_CAS(n) | RAS/CAS Latency |
| 0x0200+n*0x20 | MEM_STAT_CFG(n) | Static CS Config |
| 0x0204+n*0x20 | MEM_STAT_WAIT_WEN(n) | Write Enable Timing |
| 0x0208+n*0x20 | MEM_STAT_WAIT_OEN(n) | Output Enable Timing |
| 0x020C+n*0x20 | MEM_STAT_RD(n) | Read Timing |
| 0x0214+n*0x20 | MEM_STAT_WR(n) | Write Timing |

### BBus Utility Module (BBUS_BASE = 0x90600000)

| Offset | Name | Description |
|--------|------|-------------|
| 0x0000 | BBUS_MASTER_RESET | Module reset (write 0 to activate all) |
| 0x0010+n*4 | GPIO_CFG(n) | GPIO config (8 GPIOs per register, 4 bits each) |
| 0x0030 | GPIO_CTRL1 | GPIO output control (GPIOs 0-31) |
| 0x0034 | GPIO_CTRL2 | GPIO output control (GPIOs 32-63) |
| 0x0040 | GPIO_STAT1 | GPIO input status (GPIOs 0-31) |
| 0x0044 | GPIO_STAT2 | GPIO input status (GPIOs 32-63) |
| 0x0080 | ENDIAN_CFG | Endianness config for bus masters |
| 0x0100+n*4 | GPIO_CFG_B2(n) | GPIO config block 2 (GPIOs 56-72) |
| 0x0120 | GPIO_CTRL3 | GPIO output control (GPIOs 64-72) |
| 0x0130 | GPIO_STAT3 | GPIO input status (GPIOs 64-72) |

### Serial Module (SER_BASE = 0x90200000)

| Channel | Base Address | TxD GPIO | RxD GPIO |
|---------|-------------|----------|----------|
| 0 | 0x90200000 | GPIO 0 | GPIO 1 |
| 1 (Port A) | 0x90200040 | GPIO 8 | GPIO 9 |
| 2 | 0x90300000 | GPIO 40 | GPIO 41 |
| 3 | 0x90300040 | GPIO 44 | GPIO 45 |

| Offset | Name | Description |
|--------|------|-------------|
| 0x00 | CTRL_A | Channel enable, word length, parity, stop |
| 0x04 | CTRL_B | Mode, gap timer enable |
| 0x08 | STAT_A | TX/RX ready, errors |
| 0x0C | BITRATE | Baud rate divisor, clock source |
| 0x10 | FIFO | TX/RX data |
| 0x18 | RX_CHAR_TIMER | Character gap timer |

### Ethernet Module (ETH_BASE = 0xA0600000)

| Offset | Name | Description |
|--------|------|-------------|
| 0x0000 | EGCR1 | Global Control 1 (RX/TX enable, DMA, PHY mode) |
| 0x0004 | EGCR2 | Global Control 2 (statistics, timeout) |
| 0x0008 | EGSR | Global Status (FIFO status, RX init) |
| 0x0400 | MAC1 | MAC Config 1 (reset, RX enable, flow control) |
| 0x0404 | MAC2 | MAC Config 2 (CRC, pad, full duplex) |
| 0x0408 | IPGT | InterPacket Gap TX (0x15 full, 0x12 half) |
| 0x040C | IPGR | InterPacket Gap RX |
| 0x0414 | MAXF | Max Frame Length |
| 0x0420 | MCFG | MII Management Config (clock divisor) |
| 0x0424 | MCMD | MII Management Command (read/scan) |
| 0x0428 | MADR | MII Management Address (PHY addr + reg) |
| 0x042C | MWTD | MII Write Data |
| 0x0430 | MRDD | MII Read Data |
| 0x0434 | MIND | MII Indicators (busy, not-valid) |
| 0x0440 | SA1 | Station Address bytes 5-4 |
| 0x0444 | SA2 | Station Address bytes 3-2 |
| 0x0448 | SA3 | Station Address bytes 1-0 |
| 0x0500 | SAFR | Address Filter (promiscuous, broadcast) |
| 0x0A00 | RXAPTR | RX Descriptor Pointer A |
| 0x0A10 | EINTR | Interrupt Status |
| 0x0A14 | EINTREN | Interrupt Enable |
| 0x0A18 | TXPTR | TX Descriptor Pointer |

---

## Appendix B: Known Errata and Workarounds

1. **SDRAM settling time:** After enabling the memory controller, wait at least 80
   AHB clock cycles (~1 us) before issuing SDRAM mode commands.

2. **Flash address mirroring:** At reset, flash at CS0 (0x40000000) may be mirrored
   to 0x00000000. The lowlevel_init must jump to the real flash address before
   modifying the memory controller to avoid executing from the vanishing mirror.

3. **Serial RX character gap timer:** There is a bug with the gap timer in PLL bypass
   mode. Set the timer value to 0 with TRUN bit set (value 0x80000000).

4. **SDRAM mode register set:** Requires a dummy read from an address that encodes
   the desired mode. For CAS=2: read from base + 0x22000.

5. **Endianness switching:** If switching from big to little endian, the switch code
   must be copied to LCD palette RAM (0xA0800200) and executed from there, as the
   endian change affects instruction fetching from flash.

6. **PHY reset timing:** After asserting PHY reset via MDIO, wait at least 300 us
   (the reference code uses 3000 us for safety) before accessing PHY registers.
