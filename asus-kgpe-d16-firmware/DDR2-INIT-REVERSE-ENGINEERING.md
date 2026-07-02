# AST2050 DDR2 SDRAM Controller Initialization — Reverse Engineering Analysis

## Document Overview

This document is a line-by-line reverse engineering of the DDR2 SDRAM controller
initialization code in `platform.S` from the
[raptor-engineering/ast2050-uboot](https://github.com/raptor-engineering/ast2050-uboot)
repository. The code runs as `lowlevel_init` — the very first code after the ARM
reset vector, before any C runtime, stack, or heap exist.

**Source files analysed:**
- `board/aspeed/ast2050/platform.S` — Raptor Engineering (primary, 603 lines)
- `board/aspeed/ast2300/platform-ast2100.S` — ya-mouse/AMI variant (cross-reference,
  299 lines, from [ya-mouse/openbmc-uboot](https://github.com/ya-mouse/openbmc-uboot))
- `board/aspeed/ast2050/hwreg.h` — Register address definitions
- `include/configs/ast2050.h` — Board configuration

**Attribution:**
- Original code: ASPEED Technology Inc. (Gary Hsu)
- AST2050 adaptation: Raptor Engineering, LLC (Audrey Pearson), 2014/2017
- AMI variant: American Megatrends Inc.

---

## Table of Contents

1. [Execution Context](#1-execution-context)
2. [Hardware Overview](#2-hardware-overview)
3. [Register Map Reference](#3-register-map-reference)
4. [Code Walkthrough](#4-code-walkthrough)
   - [4.1 Calibration Macros and Data Tables](#41-calibration-macros-and-data-tables)
   - [4.2 LPC Patch Code](#42-lpc-patch-code)
   - [4.3 Entry Point and Init Timer](#43-entry-point-and-init-timer)
   - [4.4 SCU Unlock and Skip Check](#44-scu-unlock-and-skip-check)
   - [4.5 MPLL Configuration](#45-mpll-configuration)
   - [4.6 UART2 Debug Console Setup](#46-uart2-debug-console-setup)
   - [4.7 SDRAM Controller Register Programming](#47-sdram-controller-register-programming)
   - [4.8 DDR2 Mode Register Initialization Sequence](#48-ddr2-mode-register-initialization-sequence)
   - [4.9 Completion and Lock](#49-completion-and-lock)
5. [DDR2 JEDEC Mode Register Decoding](#5-ddr2-jedec-mode-register-decoding)
6. [AC Timing Parameter Analysis](#6-ac-timing-parameter-analysis)
7. [Cross-Reference: Raptor vs AMI Implementation](#7-cross-reference-raptor-vs-ami-implementation)
8. [Control Flow Diagram](#8-control-flow-diagram)

---

## 1. Execution Context

This code runs in the most constrained possible environment:

- **CPU state:** ARM926EJ-S just came out of reset, running in SVC (Supervisor) mode
- **Memory:** No DRAM available — the whole point of this code is to initialize it
- **Stack:** No stack — cannot use `push`/`pop` or call C functions
- **Available storage:** Only ARM registers (r0-r14) and on-chip SRAM (64KB at
  `0x1E720000`)
- **Code location:** Running from SPI NOR flash, memory-mapped at `0x00000000`
  (before AHB remap) or `0x14000000` (physical flash address)
- **Calling convention:** Called by U-Boot's `start.S` via `bl lowlevel_init`.
  The link register (`lr`) is saved into `r4` since there's no stack.

**Register allocation throughout the code:**

| Register | Usage |
|----------|-------|
| `r0` | Memory-mapped I/O address (always the target register address) |
| `r1` | Value to write to registers |
| `r2` | Temporary: delay counter, bit manipulation scratch |
| `r4` | Saved link register (return address) — **preserved across entire function** |
| `r3, r5-r11` | Available for calibration macros (not used in main DDR init) |

---

## 2. Hardware Overview

### 2.1 The AST2050 SoC

The ASPEED AST2050 (and its pin-compatible variants AST2100, AST1100) is a BMC
(Baseboard Management Controller) SoC built around an ARM926EJ-S core.

| Parameter | Value |
|-----------|-------|
| CPU Core | ARM926EJ-S (ARMv5TEJ) |
| CPU Clock | ~200 MHz (from HPLL) |
| Memory Bus | 32-bit DDR2 SDRAM |
| Memory Clock | 200 MHz (from MPLL) → 400 MT/s DDR2-400 |
| Max DRAM | 512 MB or 1 GB (config-selectable) |
| SPI Flash | Memory-mapped at `0x14000000` via SMC at `0x16000000` |
| SRAM | 64 KB at `0x1E720000` (used for LPC patch, calibration) |

### 2.2 DDR2 SDRAM Basics

DDR2 SDRAM (Double Data Rate 2 Synchronous Dynamic RAM) transfers data on both
edges of the clock, so a 200 MHz clock gives 400 MT/s (megatransfers per second).
A 32-bit bus at 400 MT/s = 1.6 GB/s peak theoretical bandwidth.

The initialization process follows the JEDEC standard (JESD79-2):
1. Apply power and clock, wait for stabilization
2. Issue PRECHARGE ALL to put all banks in idle state
3. Program Extended Mode Register 2 (EMRS2)
4. Program Extended Mode Register 3 (EMRS3)
5. Program Extended Mode Register 1 (EMRS1) — enable DLL
6. Program Mode Register (MRS) — with DLL reset
7. Issue PRECHARGE ALL
8. Issue at least 2× AUTO REFRESH
9. Program MRS again — without DLL reset, sets operating parameters
10. Program EMRS1 — OCD calibration default
11. Program EMRS1 — OCD calibration exit
12. DDR2 is now ready for normal read/write access

---

## 3. Register Map Reference

All registers below are relative to the SDRAM controller base at `0x1E6E0000`.

### 3.1 SDRAM Controller Registers (MCR)

| Offset | Symbol | Name |
|--------|--------|------|
| `0x00` | `SDRAM_PROTECTION_KEY_REG` | Protection Key (unlock: `0xFC600309`) |
| `0x04` | `SDRAM_CONFIG_REG` | Configuration (memory size, type, banks) |
| `0x08` | `SDRAM_GRAP_MEM_PROTECTION_REG` | Graphics Memory Protection |
| `0x0C` | `SDRAM_REFRESH_TIMING_REG` | Refresh Timing |
| `0x10` | `SDRAM_NSPEED_REG1` | Normal Speed AC Timing #1 |
| `0x14` | `SDRAM_LSPEED_REG1` | Low Speed AC Timing #1 |
| `0x18` | `SDRAM_NSPEED_REG2` | Normal Speed AC Timing #2 |
| `0x1C` | `SDRAM_LSPEED_REG2` | Low Speed AC Timing #2 |
| `0x20` | `SDRAM_NSPEED_DELAY_CTRL_REG` | Normal Speed Delay Control |
| `0x24` | `SDRAM_LSPEED_DELAY_CTRL_REG` | Low Speed Delay Control |
| `0x28` | `SDRAM_MODE_SET_CTRL_REG` | Mode Set Control (triggers MRS/EMRS commands) |
| `0x2C` | `SDRAM_MRS_EMRS2_MODE_SET_REG` | MRS/EMRS2 Mode Register Value |
| `0x30` | `SDRAM_MRS_EMRS3_MODE_SET_REG` | EMRS1/EMRS3 Mode Register Value |
| `0x34` | `SDRAM_PWR_CTRL_REG` | Power Control |
| `0x38` | `SDRAM_PAGE_MISS_LATENCY_MASK_REG` | Page Miss Latency Mask |
| `0x3C` | `SDRAM_PRIORITY_GROUP_SET_REG` | Priority Group Setting |
| `0x40` | `SDRAM_MAX_GRANT_LENGTH_REG1` | Max Grant Length #1 |
| `0x44` | `SDRAM_MAX_GRANT_LENGTH_REG2` | Max Grant Length #2 |
| `0x48` | `SDRAM_MAX_GRANT_LENGTH_REG3` | Max Grant Length #3 |
| `0x4C` | *(unnamed)* | Max Grant Length #4 (?) |
| `0x50` | `SDRAM_ECC_CTRL_STATUS_REG` | ECC Control/Status |
| `0x54` | `SDRAM_ECC_SEGMENT_EN_REG` | ECC Segment Enable |
| `0x58` | `SDRAM_ECC_SCRUB_REQ_MASK_CTRL_REG` | ECC Scrub Request Mask |
| `0x5C` | `SDRAM_ECC_ADDR_FIRST_ERR_REG` | ECC First Error Address |
| `0x60` | `SDRAM_IO_BUFF_MODE_REG` | I/O Buffer Mode |
| `0x64` | `SDRAM_DLL_CTRL_REG1` | DLL Control #1 |
| `0x68` | `SDRAM_DLL_CTRL_REG2` | DLL Control #2 |
| `0x6C` | `SDRAM_DLL_CTRL_REG3` | DLL Control #3 |
| `0x70` | `SDRAM_TEST_CTRL_STATUS_REG` | Test Control/Status |
| `0x74` | `SDRAM_TEST_START_ADDR_LENGTH_REG` | Test Start Address/Length |
| `0x78` | `SDRAM_TEST_FAIL_DQ_BIT_REG` | Test Fail DQ Bit |
| `0x7C` | `SDRAM_TEST_INIT_VALUE_REG` | Test Initial Value |
| `0x120` | `AST2100_COMPATIBLE_SCU_MPLL_PARA` | AST2000 Backward-Compatible MPLL |

### 3.2 SCU Registers Used

| Address | Symbol | Name |
|---------|--------|------|
| `0x1E6E2000` | `SCU_KEY_CONTROL_REG` | SCU Protection Key (unlock: `0x1688A8A8`) |
| `0x1E6E2020` | `SCU_M_PLL_PARAM_REG` | M-PLL Parameter (SDRAM clock) |
| `0x1E6E2028` | `SCU_FREQ_CNTR_CTRL_RANGE_REG` | Frequency Counter Control |
| `0x1E6E2040` | `SCU_SOC_SCRATCH1_REG` | SoC Scratch Register #1 |
| `0x1E6E2070` | `SCU_HW_STRAPPING_REG` | Hardware Strapping Register |
| `0x1E6E207C` | `SCU_REV_ID_REG` | Silicon Revision ID |

### 3.3 Timer and Interrupt Registers Used

| Address | Symbol | Purpose |
|---------|--------|---------|
| `0x1E782024` | Timer3 Reload | Calibration delay timer |
| `0x1E782030` | `TIMER_CONTROL_REG` | Timer Control (enable/disable) |
| `0x1E782044` | Timer4 Reload | DRAM init performance timer |
| `0x1E6C0008` | IRQ Raw Status | Check Timer3 interrupt |
| `0x1E6C0038` | IRQ Clear | Clear Timer3 interrupt |

### 3.4 UART2 Registers (Debug Console)

| Address | Symbol | Purpose |
|---------|--------|---------|
| `0x1E784000` | `UART2_REC_BUFF_REG` / THR | Transmit Hold Register (write to send char) |
| `0x1E784004` | `UART2_INT_EN_REG` / DLL | Interrupt Enable / Divisor Latch Low (when DLAB=1) |
| `0x1E784008` | `UART2_INT_IDENT_REG` / FCR | FIFO Control Register |
| `0x1E78400C` | `UART2_LINE_CTRL_REG` / LCR | Line Control Register |

---

## 4. Code Walkthrough

### 4.1 Calibration Macros and Data Tables

**Lines 46–93**

```asm
PATTERN_TABLE:
    .word   0xff00ff00
    .word   0xcc33cc33
    .word   0xaa55aa55
    .word   0x88778877
    .word   0x92cc4d6e       @ 5
    .word   0x543d3cde
    .word   0xf1e843c7
    .word   0x7c61d253
    .word   0x00000000       @ 8
```

This is a table of 9 test patterns used for DRAM calibration (DLL tuning). The
patterns are chosen to exercise different bit patterns:
- `0xff00ff00` / `0xcc33cc33` / `0xaa55aa55` / `0x88778877`: Walking patterns that
  test all data lines with various switching frequencies
- `0x92cc4d6e` through `0x7c61d253`: Pseudo-random patterns that test for
  inter-signal crosstalk and SSO (Simultaneous Switching Output) noise
- `0x00000000`: All-zeros baseline

**Note:** These patterns are defined here but are **not used** in the Raptor AST2050
init sequence. They exist for the DRAM calibration macros (`init_delay_timer`,
`check_delay_timer`, `clear_delay_timer`) which the AST2300/AST2400 platform code
uses for DLL delay calibration. The AST2050 code uses fixed DLL values instead.

#### Timer Macros (Lines 57–90)

Three macros implement a hardware timer delay mechanism using Timer3:

**`init_delay_timer`**: Loads Timer3 with a countdown value from `r2`, clears any
pending Timer3 interrupt, and enables Timer3 in auto-reload+countdown mode
(control bits `0x700` = bits 8,9,10 for Timer3 enable, external clock, auto-reload).

**`check_delay_timer`**: Reads the interrupt controller raw status register and
checks bit 18 (Timer3 overflow interrupt). Returns comparison result in CPSR flags.

**`clear_delay_timer`**: Disables Timer3 and clears its interrupt flag.

These macros are used by the DRAM calibration loops in AST2300+ code but are
**not invoked** in the AST2050 init path.

### 4.2 LPC Patch Code

**Lines 95–109**

```asm
LPC_Patch:                                       @ load to SRAM base 0x1e720400
    str   r1, [r0]
    str   r3, [r2]
    bic   r1, r1, #0xFF
LPC_Patch_S1:
    subs  r5, r5, #0x01
    moveq pc, r8
    ldr   r3, [r2]
    tst   r3, #0x01
    movne pc, r8
    mov   pc, r7
LPC_Patch_S2:                                    @ load to SRAM base 0x1e720480
    str   r1, [r0]
    mov   pc, r9
LPC_Patch_E:
```

This is a small relocatable code fragment designed to be copied into SRAM at
`0x1E720400`. It implements an LPC (Low Pin Count) bus reset handler — a hardware
workaround where the BMC needs to respond to LPC reset signals from the host
during DRAM initialization. The code:

1. Writes `r1` to `[r0]` (an LPC register) and `r3` to `[r2]` (another register)
2. Clears low byte of `r1` (acknowledge sequence)
3. Loops `r5` times, checking bit 0 of `[r2]` (completion flag)
4. Returns via `r7`, `r8`, or `r9` (function pointers set by caller)

**This patch is defined but never installed or called in the AST2050 init.**
It exists because the code was adapted from the AST2300 platform which requires
LPC bus handling during its longer DDR3 calibration sequence.

### 4.3 Entry Point and Init Timer

**Lines 111–129**

```asm
.globl lowlevel_init
lowlevel_init:
init_dram:
    mov r4, lr                      @ Save return address (no stack available)

    @ Start a performance timer (Timer4) to measure DRAM init duration
    ldr r0, =0x1e782044             @ Timer4 Reload Register
    ldr r1, =0xFFFFFFFF             @ Maximum countdown value
    str r1, [r0]

    ldr r0, =TIMER_CONTROL_REG     @ 0x1E782030
    ldr r1, [r0]
    bic r1, r1, #0x0000F000        @ Clear Timer4 control bits [15:12]
    str r1, [r0]                    @ Disable Timer4 first
    mov r2, #3
    orr r1, r1, r2, lsl #12        @ Set bits [13:12] = 0b11 (enable + auto-reload)
    str r1, [r0]                    @ Start Timer4 counting down
```

This starts Timer4 as a performance counter to measure how long DRAM initialization
takes. Timer4 counts down from `0xFFFFFFFF` — after init completes, reading the
timer shows elapsed time. The timer control bits for Timer4 are in bits [15:12]:
- Bit 12: Enable
- Bit 13: Auto-reload (ignored here since we only count once)
- Bit 14: External clock select
- Bit 15: Interrupt enable

### 4.4 SCU Unlock and Skip Check

**Lines 131–148**

```asm
    @ Set Scratch register Bit 7 — "DRAM init in progress" flag
    ldr r0, =AST_SCU_BASE           @ 0x1E6E2000
    ldr r1, =0x1688a8a8             @ SCU unlock key
    str r1, [r0]

    ldr r0, =SCU_SOC_SCRATCH1_REG   @ 0x1E6E2040
    ldr r1, [r0]
    orr r1, r1, #0x80               @ Set bit 7 = "init in progress"
    str r1, [r0]

    @ Check Scratch Register Bit 6 — "DRAM already initialized" flag
    ldr r0, =SCU_SOC_SCRATCH1_REG
    ldr r1, [r0]
    bic r1, r1, #0xFFFFFFBF         @ Isolate bit 6
    mov r2, r1, lsr #6              @ Shift to bit 0
    cmp r2, #0x01
    beq reg_lock                     @ If set, skip init entirely
```

The SCU (System Control Unit) is protected by a write-lock. Writing the magic
key `0x1688A8A8` to offset `0x00` unlocks all SCU registers for writing.

The scratch register `SCU40` is used as inter-boot communication between the
bootloader and later stages (including the Linux kernel):

| Bit | Meaning |
|-----|---------|
| 6 | DRAM initialization complete (set after successful init) |
| 7 | DRAM initialization in progress |
| 31:8 | Used by Raptor for Linux boot key (`0x5A` in upper bits) |

**The skip check (bit 6) is critical:** If the BMC does a warm reboot (watchdog
reset, software reset), the DRAM contents may still be valid. Re-running the full
DDR2 initialization sequence would **destroy DRAM contents** (because it resets
the DLL, changes mode registers, and issues PRECHARGE ALL). By checking bit 6,
the code can skip re-initialization on warm reboot, preserving any crash dump data
or persistent storage in DRAM.

### 4.5 MPLL Configuration

**Lines 149–159**

```asm
    @ Load PLL parameter for 24MHz CLKIN
    ldr r2, =0x033103F1              @ Unused — loaded but overwritten below
    ldr r0, =SCU_REV_ID_REG         @ 0x1E6E207C
    ldr r1, [r0]
    mov r1, r1, lsr #8              @ Shift to get chip revision byte
    cmp r1, #0x02
    beq set_MPLL                     @ Branch if AST2050/AST1100

set_MPLL:
    ldr r0, =SCU_M_PLL_PARAM_REG    @ 0x1E6E2020
    ldr r1, =0x00004c81             @ MPLL = 200 MHz (initial coarse setting)
    str r1, [r0]
```

**Chip revision detection:** SCU register `0x7C` contains the silicon revision:
- Bits [31:24]: Chip generation (0=AST2050/AST2100/AST2150, 1=AST2300)
- Bits [23:16]: Silicon revision within generation (0=A0, 1=A1, 2=A2, ...)
- Bits [7:0]: Legacy revision ID (for AST2050 generation)

The code checks if bits [15:8] equal `0x02`, which would identify a specific
revision. However, **the branch is unconditional in practice**: `beq set_MPLL`
jumps to the very next instruction, so all paths converge to `set_MPLL` regardless.

**The MPLL (Memory PLL)** generates the DDR2 clock. SCU register `0x20` controls
the PLL parameters:

**First MPLL write: `0x00004c81`** — This is a coarse initial setting to get the
MPLL running at approximately 200 MHz from the 24 MHz crystal input. This
happens early to give the PLL time to lock before SDRAM registers are programmed.

The precise PLL register format is proprietary to Aspeed and not publicly
documented. Based on analysis of multiple values across different implementations:

| Value | Source | Stated Frequency |
|-------|--------|-----------------|
| `0x00004c81` | Raptor (initial) | ~200 MHz |
| `0x000041f0` | Raptor (final) | 200 MHz |
| `0x00004120` | AMI/ya-mouse | 200 MHz |
| `0x00004c41` | Raptor (backward compat) | ~200 MHz |

Raptor's source comment for `0x000041f0` provides partial decoding:
> "output denumerator=0b0000; output divider=1; numerator=0b001111;
> post divider=div by 2"

Using a standard PLL formula:
`MPLL = CLKIN × (Numerator + 2) / (Denominator + 1) / PostDivider`
= 24 MHz × (15 + 2) / (0 + 1) / 2 = 24 × 17 / 2 = **204 MHz** ≈ 200 MHz

### 4.6 UART2 Debug Console Setup

**Lines 161–226**

This section configures UART2 (at `0x1E784000`) as a debug console and prints
the message `"\r\nDRAM Init-DDR\r\n"`. This is the first visible output from
the BMC after power-on.

The UART setup follows the standard NS16550 initialization sequence:

```
1. Set LCR.DLAB=1 (0x83 → LCR)    — Enable divisor latch access
2. Read SCU 0x2C bit 12            — Check if UART clock is divided by 13
3. Set divisor latch:
   - If not div13: DLL=0x0D (13)   → 24MHz / (16 × 13) = 115200 baud
   - If div13:     DLL=0x01 (1)    → (24MHz/13) / (16 × 1) = 115384 ≈ 115200
4. Set DLM=0x00                     — High byte of divisor = 0
5. Set LCR=0x03                     — 8N1 (8 data, no parity, 1 stop), DLAB=0
6. Set FCR=0x07                     — Enable FIFO, reset TX/RX FIFOs
7. Write message characters one at a time to THR (0x1E784000)
```

The baud rate calculation:
- UART clock = 24 MHz (from `CONFIG_SYS_NS16550_CLK`)
- Divisor = 13 (0x0D)
- Baud = 24,000,000 / (16 × 13) = **115,384** ≈ 115,200 baud (0.16% error, well
  within tolerance)

If `CONFIG_DRAM_UART_38400` is defined (as it is in `ast2050.h`), the divisor is
set to 39 (0x27) instead: 24,000,000 / (16 × 39) = 38,461 ≈ 38,400 baud.

**Note:** The actual config defines `CONFIG_DRAM_UART_38400`, so the ASUS KGPE-D16
board outputs DRAM init messages at 38400 baud, **not** 115200. This is a different
baud rate from the normal U-Boot console (115200).

**After UART setup, a ~100µs delay:**

```asm
    ldr r2, =0x00000100     @ 256 iterations
delay0:
    nop
    nop
    subs r2, r2, #1
    bne delay0
```

At ~200 MHz (5ns per cycle), each loop iteration is ~4 instructions ≈ 20ns,
so 256 × 20ns ≈ 5µs. This is less than the stated 100µs but provides enough
settling time after UART configuration before proceeding.

### 4.7 SDRAM Controller Register Programming

This is the core of the DRAM initialization — programming all SDRAM controller
registers before issuing the DDR2 mode register set commands.

#### 4.7.1 Unlock SCU and SDRAM Controller (Lines 237–331)

```asm
    ldr r0, =SCU_KEY_CONTROL_REG
    ldr r1, =0x1688A8A8             @ Unlock SCU
    str r1, [r0]

    @ Verify SCU unlocked (reads back 0x01 when unlocked)
    ldr r1, [r0]
    cmp r1, #0x01
    bne SCU_regs_locked              @ Print "SCU LOCKED\r\n" and halt

    @ Set scratch register: Linux boot key + DRAM-init-in-progress flag
    ldr r0, =SCU_SOC_SCRATCH1_REG   @ SCU40
    ldr r1, =0x5a000080             @ Bit 7 = init in progress, 0x5A = Linux boot key
    str r1, [r0]

    ldr r0, =SDRAM_PROTECTION_KEY_REG
    ldr r1, =0xfc600309             @ Unlock SDRAM controller
    str r1, [r0]

    @ Verify SDRAM unlocked
    ldr r1, [r0]
    cmp r1, #0x01
    bne SDRAM_regs_locked            @ Print "SDRAM LOCKED\r\n" and halt
```

Both register blocks use hardware write-protection:
- **SCU:** Write `0x1688A8A8` → reads back `0x01` when unlocked
- **SDRAM:** Write `0xFC600309` → reads back `0x01` when unlocked

If either fails to unlock, the code prints an error message to UART2 and jumps
to `reg_lock` (which locks both and returns, leaving DRAM non-functional). This
would indicate a serious hardware problem.

The scratch register value `0x5A000080` serves dual purposes:
- `0x5A` in bits [31:24]: A magic key that the Linux kernel checks to determine
  if it was booted via U-Boot (vs. direct JTAG load or other method)
- Bit 7: Indicates DRAM initialization is in progress

#### 4.7.2 Final MPLL Setting (Lines 333–348)

```asm
    ldr r0, =SCU_M_PLL_PARAM_REG    @ SCU20
    ldr r1, =0x000041f0             @ Final MPLL setting: 200 MHz
    str r1, [r0]

    @ Delay ~400µs for PLL to lock
    ldr r2, =0x00000400             @ 1024 iterations
delay1:
    nop
    nop
    subs r2, r2, #1
    bne delay1
```

The MPLL is now set to its final operating value. The 400µs delay allows the PLL
to achieve phase lock at the new frequency before the SDRAM controller uses it.

At this point the SDRAM controller re-unlock is performed (in case the MPLL
change caused a transient that reset the lock).

#### 4.7.3 DLL Pre-Configuration (Lines 354–360)

```asm
    ldr r0, =SDRAM_DLL_CTRL_REG3    @ MCR6C
    ldr r1, =0x00909090
    str r1, [r0]

    ldr r0, =SDRAM_DLL_CTRL_REG1    @ MCR64
    ldr r1, =0x00050000
    str r1, [r0]
```

The DLL (Delay-Locked Loop) is a critical circuit that aligns the internal SDRAM
clock phases with the data strobe (DQS) signals. It must be pre-configured before
the main SDRAM parameters are set.

**MCR6C = `0x00909090`** — DLL Control Register #3:
- Three identical byte values `0x90` = `1001_0000` suggesting per-byte-lane DLL
  delay settings. The value `0x90` represents a mid-range delay tap position for
  each of the three delay elements (read DQS delay for byte lanes 0, 1, 2 — the
  32-bit bus has 4 byte lanes but the 4th may be handled separately or have a
  default).

**MCR64 = `0x00050000`** — DLL Control Register #1:
- Bits [17:16] = `0b01` — likely DLL mode selection
- Bit 18 = 1 — DLL enable or bypass control
- This configures the DLL operating mode before the main timing parameters are
  programmed.

#### 4.7.4 VGA Memory Reservation (Lines 362–377)

```asm
    ldr r0, =SCU_HW_STRAPPING_REG   @ SCU70
    ldr r1, [r0]
    ldr r2, =0x0000000c             @ Mask bits [3:2]
    and r1, r1, r2                   @ Extract VGA memory size field
    mov r2, r1, lsl #2              @ Shift left 2 → into bits [5:4]

    ldr r0, =SDRAM_CONFIG_REG       @ MCR04
#ifdef CONFIG_1G_DDRII
    ldr r1, =0x00000d89             @ 1 GB DDR2 config
#endif
#ifdef CONFIG_512M_DDRII
    ldr r1, =0x00000585             @ 512 MB DDR2 config
#endif
    orr r1, r1, r2                  @ OR in VGA memory size
    str r1, [r0]
```

The hardware strapping register (SCU70) contains board-level configuration set
by physical resistors on the PCB. Bits [3:2] encode the VGA memory reservation:

| SCU70[3:2] | VGA Memory | MCR04[5:4] |
|------------|-----------|-------------|
| `00` | 8 MB | `00` |
| `01` | 16 MB | `01` |
| `10` | 32 MB | `10` |
| `11` | 64 MB | `11` |

**MCR04 Configuration Register** — decoding the two memory configurations:

```
1 GB DDR2:  0x00000d89 = 0000_0000_0000_0000_0000_1101_1000_1001
512 MB DDR2: 0x00000585 = 0000_0000_0000_0000_0000_0101_1000_0101
```

Cross-referencing the two values to identify bit fields:

| Bits | 1GB Value | 512MB Value | Probable Meaning |
|------|-----------|-------------|------------------|
| [0] | 1 | 1 | SDRAM controller enable |
| [2] | 0 | 1 | Row address width bit 0 (0=14 rows, 1=13 rows) |
| [3] | 1 | 0 | Row address width bit 1 |
| [5:4] | 00 | 00 | VGA memory reservation (filled from SCU70) |
| [7] | 1 | 1 | DDR2 mode (vs DDR1) |
| [8] | 1 | 1 | Enable auto-precharge |
| [9] | 0 | 0 | *(reserved or bus width)* |
| [10] | 1 | 1 | 8 banks (vs 4 banks) |
| [11] | 1 | 0 | Memory size bit (1=1GB, 0=512MB) |

The key difference between 1GB and 512MB configs: bit 11 (size), bit 3 (more row
address bits for 1GB), and bit 2 (fewer row address bits for 512MB needing fewer
rows but potentially more columns).

#### 4.7.5 Graphics Memory Protection (Line 379–381)

```asm
    ldr r0, =SDRAM_GRAP_MEM_PROTECTION_REG   @ MCR08
    ldr r1, =0x0011030f
    str r1, [r0]
```

**MCR08 = `0x0011030F`** — configures the memory protection region for the VGA
frame buffer. This prevents the CPU and DMA engines from accidentally corrupting
the display memory:

```
0x0011030F = 0000_0000_0001_0001_0000_0011_0000_1111
```

- Bits [3:0] = `0xF` — Protection enable for all 4 memory masters
- Bits [11:8] = `0x03` — Protection region size encoding
- Bits [23:16] = `0x11` — Protection region base address (upper bits)

This likely protects a 16 MB or 32 MB region starting at the top of physical
DRAM for the VGA controller's exclusive use.

#### 4.7.6 AC Timing Registers (Lines 383–405)

These are the most critical registers — they define the electrical timing
parameters that must match the DDR2 SDRAM chip's specifications.

```asm
    @ Normal Speed AC Timing #1 (MCR10)
    ldr r1, =0x22201725
    str r1, [r0]

    @ Normal Speed AC Timing #2 (MCR18)
    ldr r1, =0x1e29011a
    str r1, [r0]

    @ Normal Speed Delay Control (MCR20)
    ldr r1, =0x00c82222
    str r1, [r0]

    @ Low Speed AC Timing #1 (MCR14) — same as normal speed
    ldr r1, =0x22201725

    @ Low Speed AC Timing #2 (MCR1C) — same as normal speed
    ldr r1, =0x1e29011a

    @ Low Speed Delay Control (MCR24) — same as normal speed
    ldr r1, =0x00c82222
```

**Important observation:** In the Raptor build, the normal-speed and low-speed
timing registers are set to **identical values**. This means the memory controller
does not use a separate low-speed mode — it always runs at the normal 200 MHz speed.

The AMI/ya-mouse variant uses **different** values for normal and low speed,
confirming these are indeed separate speed grade configurations. See
[Section 7](#7-cross-reference-raptor-vs-ami-implementation) for the comparison.

**Full AC timing decode is in [Section 6](#6-ac-timing-parameter-analysis).**

#### 4.7.7 Bus Arbitration and Priority (Lines 407–434)

```asm
    @ MCR38: Page Miss Latency Mask
    ldr r1, =0xffffff82

    @ MCR3C: Priority Group Setting — all zero (equal priority)
    ldr r1, =0x00000000

    @ MCR40-4C: Max Grant Length — all zero (unlimited)
    ldr r1, =0x00000000    @ MCR40
    ldr r1, =0x00000000    @ MCR44
    ldr r1, =0x00000000    @ MCR48
    ldr r1, =0x00000000    @ MCR4C
```

**MCR38 = `0xFFFFFF82`:**
- Bits [7:0] = `0x82` = `1000_0010` — Page miss latency counter and control
- Bits [31:8] = `0xFFFFFF` — Latency mask for all memory requestors
  (all masters masked = no special latency treatment)

This register controls how the SDRAM controller handles page misses (when a
memory access targets a different row than the currently open one). A page miss
incurs the penalty of tRP (precharge) + tRCD (row activate) additional latency.

The priority and grant length registers are all zero, meaning:
- All memory masters (CPU, VGA, DMA, MAC, etc.) have equal priority
- No master has a maximum grant length limit (any master can hold the bus
  indefinitely)

#### 4.7.8 ECC Disabled (Lines 431–445)

```asm
    @ MCR50-5C: All ECC registers cleared to zero
    ldr r1, =0x00000000     @ ECC Control/Status
    ldr r1, =0x00000000     @ ECC Segment Enable
    ldr r1, =0x00000000     @ ECC Scrub Request
    ldr r1, =0x00000000     @ ECC First Error Address
```

ECC (Error Correcting Code) is **disabled**. The AST2050 supports SECDED
(Single Error Correct, Double Error Detect) ECC on the DRAM bus, but it requires
either a wider memory bus or sacrifices some capacity for ECC storage. For the
KGPE-D16 BMC application, ECC is unnecessary overhead.

#### 4.7.9 I/O Buffer and DLL Final Configuration (Lines 447–469)

```asm
    @ MCR60: IO Buffer Mode
    ldr r1, =0x032aa02a

    @ MCR64: DLL Control #1 (final setting)
    ldr r1, =0x002d3000

    @ MCR68: DLL Control #2
    ldr r1, =0x02020202
```

**MCR60 = `0x032AA02A`** — I/O Buffer Mode Register:

```
0x032AA02A = 0000_0011_0010_1010_1010_0000_0010_1010
```

This register configures the DDR2 I/O pad drivers and receivers:
- Controls output drive strength (impedance matching to PCB traces)
- Controls ODT (On-Die Termination) in the I/O buffers
- Sets slew rate for data/address/command signals
- The repeating pattern `0x2A` = `0010_1010` in multiple byte positions suggests
  per-byte-lane configuration of drive strength and termination

**MCR64 = `0x002D3000`** — DLL Control #1 (final setting):
- Different from the initial value of `0x00050000` set earlier
- Bits [15:12] = `0x3` — DLL bandwidth/response setting
- Bits [21:16] = `0x2D` (45) — DLL delay tap count or phase offset
- This is the production DLL setting after the PLL has locked

**MCR68 = `0x02020202`** — DLL Control #2:
- Four identical byte values `0x02` — per-byte-lane fine DLL delay adjustment
- Each byte lane's DQS (data strobe) capture delay is individually trimmable
- Value `0x02` = minimal positive delay offset from the coarse DLL setting

#### 4.7.10 Test Registers Cleared (Lines 459–473)

```asm
    @ MCR70-7C: Test registers all cleared
    ldr r1, =0x00000000     @ Test Control/Status
    ldr r1, =0x00000000     @ Test Start Address/Length
    ldr r1, =0x00000000     @ Test Fail DQ Bit
    ldr r1, =0x00000000     @ Test Initial Value
```

The built-in memory test engine is disabled. It can be used to verify DRAM
integrity by writing/reading patterns, but is not used during normal boot.

#### 4.7.11 Power Control — CKE Assert (Lines 475–484)

```asm
    ldr r0, =SDRAM_PWR_CTRL_REG     @ MCR34
    ldr r1, =0x00000001
    str r1, [r0]

    @ Delay ~400µs for DDR2 power-up sequence
    ldr r2, =0x00000400
delay2:
    nop
    nop
    subs r2, r2, #1
    bne delay2
```

**MCR34 = `0x00000001`:**
- Bit 0 = 1 — Assert CKE (Clock Enable) to the DDR2 SDRAM
- All other bits = 0 — No self-refresh, no power-down

Per JEDEC DDR2 specification, CKE must be held high for at least 400µs after
the clock is stable before any commands can be issued to the DRAM. The delay
loop provides this waiting period. This is the beginning of the JEDEC-specified
DDR2 initialization sequence.

### 4.8 DDR2 Mode Register Initialization Sequence

**Lines 486–548**

This is the heart of the DDR2 initialization — programming the DRAM chip's
internal mode registers through the Aspeed SDRAM controller's indirect mechanism.

The SDRAM controller uses three registers to issue mode register commands:
- **MCR2C** holds the value for MRS (Mode Register Set) or EMRS2
- **MCR30** holds the value for EMRS1 (Extended Mode Register 1) or EMRS3
- **MCR28** triggers the actual command — different bit patterns issue different
  mode register commands to the DDR2 SDRAM

#### MCR28 Mode Set Control Register Bit Definitions

Based on analysis of the command sequence and JEDEC DDR2 requirements:

| MCR28 Value | Binary | Commands Issued |
|-------------|--------|-----------------|
| `0x05` | `0101` | EMRS2 (from MCR2C) + EMRS3 (from MCR30) |
| `0x07` | `0111` | MRS (from MCR2C) + EMRS1 (from MCR30) + implied PRECHARGE ALL |
| `0x03` | `0011` | EMRS1 (from MCR30) + MRS trigger |
| `0x01` | `0001` | MRS only (from MCR2C) |

#### Step-by-Step Mode Register Sequence

**Step 1: Load initial MRS and EMRS1 values**
```asm
    @ MCR2C = 0x00000732  (MRS value: CL=3, BL=4, DLL reset, WR=4)
    @ MCR30 = 0x00000040  (EMRS1 value: DLL enable, 150Ω ODT)
```

**Step 2: Issue EMRS2 + EMRS3** (JEDEC steps 5-6)
```asm
    @ MCR28 = 0x00000005  → Issues EMRS(2) and EMRS(3) commands
```
These are typically zero/default for DDR2-400 (no high-temperature refresh
or partial array self-refresh needed).

**Step 3: Issue all mode registers** (JEDEC steps 7-8)
```asm
    @ MCR28 = 0x00000007  → Issues EMRS(1) + MRS with DLL reset
```
This enables the DRAM's internal DLL and programs the main operating parameters
(CAS latency, burst length, write recovery time).

**Step 4: Issue EMRS1 + MRS** (JEDEC step 9 equivalent)
```asm
    @ MCR28 = 0x00000003  → Additional EMRS1/MRS cycle
```

**Step 5: Issue MRS** (JEDEC PRECHARGE ALL + AUTO REFRESH)
```asm
    @ MCR28 = 0x00000001  → MRS trigger (controller handles PRECHARGE + REFRESH)
```
The SDRAM controller automatically issues the required PRECHARGE ALL and
2× AUTO REFRESH commands before the MRS command.

**Step 6: Enable auto-refresh**
```asm
    @ MCR0C = 0x00005A08  → Refresh timing: enable with initial fast refresh
```

**Step 7: MRS without DLL reset** (JEDEC step 11)
```asm
    @ MCR2C = 0x00000632  (MRS: same as 0x732 but bit 8 cleared = no DLL reset)
    @ MCR28 = 0x00000001  → Issue MRS
```
Bit 8 (DLL reset) is now cleared — the DLL has finished resetting and the DRAM
operates normally from this point.

**Step 8: OCD calibration default** (JEDEC step 12)
```asm
    @ MCR30 = 0x000003C0  (EMRS1: OCD calibration default — bits 9:7 = 111)
    @ MCR28 = 0x00000003  → Issue EMRS1
```

**Step 9: OCD calibration exit**
```asm
    @ MCR30 = 0x00000040  (EMRS1: OCD exit — bits 9:7 = 000, back to 150Ω ODT)
    @ MCR28 = 0x00000003  → Issue EMRS1
```

**Step 10: Normal refresh timing**
```asm
    @ MCR0C = 0x00005A21  → Normal refresh period
```

**Step 11: Final power control**
```asm
    @ MCR34 = 0x00007C03  → Enable self-refresh, configure power-down modes
```

**Step 12: Backward-compatible MPLL register**
```asm
    @ MCR120 = 0x00004C41  → Legacy MPLL parameter for AST2000 compatibility
```

**DDR2 SDRAM is now fully initialized and ready for read/write access.**

### 4.9 Completion and Lock

**Lines 558–603**

```asm
set_scratch:
    @ Set Scratch register Bit 6 = "DRAM init complete"
    ldr r0, =SCU_SOC_SCRATCH1_REG
    ldr r1, [r0]
    orr r1, r1, #0x40               @ Set bit 6
    str r1, [r0]

    @ Print "...Done\r\n" to UART2
    @ (character-by-character output)

reg_lock:
    @ Lock SCU registers (write 0 to key register)
    ldr r0, =SCU_KEY_CONTROL_REG
    ldr r1, =0x00000000
    str r1, [r0]

    @ Lock SDRAM registers
    ldr r0, =SDRAM_PROTECTION_KEY_REG
    ldr r1, =0x00000000
    str r1, [r0]

    @ Restore link register and return to caller
    mov lr, r4
    mov pc, lr
```

After successful initialization:
1. Bit 6 of `SCU40` is set — subsequent warm boots will skip DRAM init
2. `"...Done\r\n"` is printed to UART2
3. Both SCU and SDRAM registers are re-locked (writing 0 to key registers)
4. The saved link register is restored and execution returns to U-Boot's `start.S`

**The total UART output from a cold boot is:**
```
\r\nDRAM Init-DDR\r\n...Done\r\n
```
This appears on UART2 at 38400 baud (per `CONFIG_DRAM_UART_38400` in `ast2050.h`).

---

## 5. DDR2 JEDEC Mode Register Decoding

### 5.1 MRS (Mode Register Set) — MCR2C Values

The DDR2 MRS follows JEDEC JESD79-2. Bits A0-A12 of the DRAM address bus
encode the mode register during an MRS command.

#### MCR2C = `0x00000732` (Initial MRS — with DLL reset)

```
0x732 = 0111_0011_0010

A[2:0]  = 010  → Burst Length = 4
A[3]    = 0    → Burst Type = Sequential
A[6:4]  = 011  → CAS Latency = 3 (CL=3)
A[7]    = 0    → Test Mode = Normal
A[8]    = 1    → DLL Reset = YES
A[11:9] = 011  → Write Recovery (tWR) = 4 clock cycles
```

| Parameter | Value | Meaning |
|-----------|-------|---------|
| Burst Length | 4 | 4-beat burst (standard for DDR2) |
| Burst Type | Sequential | Data arrives in sequential address order |
| CAS Latency | 3 | 3 clock cycles from READ command to first data |
| DLL Reset | Yes | Resets the DRAM's internal DLL (required on init) |
| Write Recovery | 4 cycles | 4 clocks from last write data to precharge (tWR) |

**CAS Latency 3 at 200 MHz** = 15 ns access latency. This is the standard CL
for DDR2-400 speed grade.

#### MCR2C = `0x00000632` (Final MRS — DLL reset cleared)

```
0x632 = 0110_0011_0010

A[8] = 0 → DLL Reset = NO (cleared)
```

All other bits identical to `0x732`. The DLL reset bit must be cleared after the
initial reset cycle to allow normal operation.

### 5.2 EMRS1 (Extended Mode Register 1) — MCR30 Values

EMRS1 controls DLL enable/disable, output drive strength, ODT (On-Die
Termination), additive latency, and OCD (Off-Chip Driver) calibration.

#### MCR30 = `0x00000040` (Normal operation)

```
0x040 = 0000_0100_0000

A[0]    = 0    → DLL Enable (0 = DLL enabled)
A[1]    = 0    → Output Drive Strength = Full
A[2]    = 0    → RTT(Nom) A2 = 0
A[5:3]  = 000  → Additive Latency = 0 (no AL)
A[6]    = 1    → RTT(Nom) A6 = 1
A[9:7]  = 000  → OCD Program = OCD Exit / Normal Operation
A[10]   = 0    → DQS# Enable (complementary DQS enabled)
A[11]   = 0    → RDQS Disable
A[12]   = 0    → Output Enable (all outputs active)
```

**ODT (On-Die Termination) decoding:**

| A6 | A2 | RTT (Nom) |
|----|-----|-----------|
| 0 | 0 | Disabled |
| 0 | 1 | 75 Ω |
| 1 | 0 | **150 Ω** ← Selected |
| 1 | 1 | 50 Ω (DDR2-800 only) |

**150 Ω ODT** is the standard choice for DDR2-400 with a single DIMM/device.
It provides good signal integrity without excessive power consumption.

#### MCR30 = `0x000003C0` (OCD calibration default)

```
0x3C0 = 0011_1100_0000

A[9:7] = 111 → OCD Calibration Default
A[6]   = 1   → RTT(Nom) A6 = 1 (150Ω maintained)
```

The OCD (Off-Chip Driver) calibration sequence is a JEDEC-required step that
sets the DRAM output driver impedance to its factory-calibrated default value.
A[9:7] = `111` triggers the "OCD default" mode.

After this command, EMRS1 is re-written with A[9:7] = `000` (OCD exit) to
complete the calibration and enter normal operation.

### 5.3 Comparison: Raptor vs AMI MRS Values

| Register | Raptor (AST2050) | AMI (AST2100) | Difference |
|----------|-----------------|---------------|------------|
| MRS (init) | `0x732` | `0x942` | Different CL and WR |
| MRS (final) | `0x632` | `0x842` | Different CL and WR |
| EMRS1 | `0x040` | `0x040` | **Identical** |
| EMRS1 (OCD) | `0x3C0` | `0x3C0` | **Identical** |

**Decoding the AMI MRS value `0x942`:**
```
0x942 = 1001_0100_0010

A[2:0]  = 010  → Burst Length = 4 (same)
A[3]    = 0    → Sequential (same)
A[6:4]  = 100  → CAS Latency = 4 (CL=4, vs CL=3 for Raptor)
A[8]    = 1    → DLL Reset = YES (same)
A[11:9] = 100  → Write Recovery = 5 (vs WR=4 for Raptor)
```

The AMI version uses **more conservative timing** (CL=4, WR=5) compared to
Raptor's (CL=3, WR=4). This suggests Raptor optimized their board for lower
latency, possibly because they verified the specific DRAM chips on the KGPE-D16
can sustain CL=3 at 200 MHz.

---

## 6. AC Timing Parameter Analysis

### 6.1 MCR10: Normal Speed AC Timing Register #1

**Raptor: `0x22201725`**

```
Byte 3: 0x22 = 0010_0010
Byte 2: 0x20 = 0010_0000
Byte 1: 0x17 = 0001_0111
Byte 0: 0x25 = 0010_0101
```

Cross-referencing with the AMI value (`0x32302926`), which has comments suggesting
timing at a different speed grade:

| Bits | Raptor | AMI | Probable DDR2 Parameter |
|------|--------|-----|------------------------|
| [3:0] | 0x5 (5) | 0x6 (6) | **tRCD** (RAS-to-CAS Delay): 5 or 6 clocks |
| [7:4] | 0x2 (2) | 0x2 (2) | **tRP** (Row Precharge): 2 or 3 clocks (offset encoding) |
| [11:8] | 0x7 (7) | 0x9 (9) | **tRAS** (Row Active Time): 7 or 9 clocks (offset encoded) |
| [15:12] | 0x1 (1) | 0x2 (2) | **tRRD** (Row-to-Row Delay): min 2 clocks |
| [19:16] | 0x0 (0) | 0x0 (0) | Reserved or **tWTR** |
| [23:20] | 0x2 (2) | 0x3 (3) | **tRC** (Row Cycle) high bits or **tRFC** partial |
| [27:24] | 0x2 (2) | 0x2 (2) | Additional timing parameter |
| [31:28] | 0x2 (2) | 0x3 (3) | Additional timing parameter |

At DDR2-400 (200 MHz, 5ns per clock):
- **tRCD = 5 clocks = 25 ns** — within DDR2-400 spec (typically 15-25ns)
- **tRP = ~15 ns** — row precharge time
- **tRAS = ~35-45 ns** — row active time

### 6.2 MCR18: Normal Speed AC Timing Register #2

**Raptor: `0x1E29011A`**

```
Byte 3: 0x1E = 0001_1110
Byte 2: 0x29 = 0010_1001
Byte 1: 0x01 = 0000_0001
Byte 0: 0x1A = 0001_1010
```

| Bits | Raptor | AMI | Probable DDR2 Parameter |
|------|--------|-----|------------------------|
| [7:0] | 0x1A (26) | 0x22 (34) | **tRFC** (Refresh-to-Active): 26 or 34 clocks |
| [15:8] | 0x01 | 0x01 | **tWR** or mode control |
| [23:16] | 0x29 (41) | 0x4C (76) | **tRC** (Row Cycle Time): scaled value |
| [31:24] | 0x1E (30) | 0x27 (39) | Additional cycle count |

**tRFC** (Refresh Cycle Time) is chip-density-dependent:
- For 1 Gbit DDR2 chips: tRFC = 127.5 ns = ~26 clocks at 200 MHz → **matches `0x1A`**
- For 2 Gbit DDR2 chips: tRFC = 195 ns = ~39 clocks

This confirms the KGPE-D16 uses **1 Gbit DDR2 chips** (e.g., 8× 1Gbit = 1GB total
with a 32-bit bus, consistent with `CONFIG_1G_DDRII`).

### 6.3 MCR20: Normal Speed Delay Control

**Raptor: `0x00C82222`**

```
Byte 3: 0x00
Byte 2: 0xC8 = 1100_1000
Byte 1: 0x22 = 0010_0010
Byte 0: 0x22 = 0010_0010
```

This register controls the signal delay elements in the SDRAM controller's
I/O interface:
- Bytes 0-1: Per-byte-lane read DQS delay settings (`0x22` = mid-range)
- Byte 2: Additional timing control (`0xC8` = command/address delay)
- Byte 3: Reserved

### 6.4 MCR0C: Refresh Timing Register

Two values are used during initialization:

**Initial: `0x00005A08`**
```
Bits [15:0] = 0x5A08 = 23048
```

**Final: `0x00005A21`**
```
Bits [15:0] = 0x5A21 = 23073
```

The refresh timing register controls the auto-refresh interval. DDR2 requires
a refresh command every 7.8µs (for standard temperature) or 3.9µs (for extended
temperature). At 200 MHz:

7.8µs × 200 MHz = **1560 clock cycles** per refresh interval.

The register value is much larger than 1560, suggesting it encodes the total
refresh period for all rows rather than a per-row interval. For a 1 Gbit DDR2
device with 8192 rows: 8192 × 7.8µs = 63.9ms total refresh window.

The initial value (`0x5A08`) likely has bit 5 clear (reduced refresh rate
during initialization), while the final value (`0x5A21`) sets bit 5 to enable
the full refresh rate for normal operation.

### 6.5 MCR34: Power Control Register

**Initial: `0x00000001`** — CKE asserted, no power saving.

**Final: `0x00007C03`:**
```
0x7C03 = 0000_0000_0000_0000_0111_1100_0000_0011

Bit 0  = 1 → CKE enabled
Bit 1  = 1 → Self-refresh enable (allows entering self-refresh on idle)
Bits [14:10] = 11111 → Power-down idle timer or self-refresh configuration
```

This enables power management features: the SDRAM controller can automatically
put the DDR2 into self-refresh mode when the bus is idle for a configured period,
reducing power consumption. The DDR2 will automatically exit self-refresh when
a new access arrives.

---

## 7. Cross-Reference: Raptor vs AMI Implementation

The ya-mouse/openbmc-uboot repository contains an independent AST2100 DDR2
init implementation from AMI (American Megatrends Inc.), in
`board/aspeed/ast2300/platform-ast2100.S`. Comparing the two implementations
validates our register analysis and reveals tuning differences.

### 7.1 Identical Registers

These registers have **identical values** in both implementations, confirming
they are SoC-level requirements rather than board-specific tuning:

| Register | Value | Meaning |
|----------|-------|---------|
| MCR00 (unlock) | `0xFC600309` | SDRAM protection key |
| MCR6C (DLL3) | `0x00909090` | DLL initial delay taps |
| MCR64 (DLL1 init) | `0x00050000` | DLL pre-config |
| MCR08 (GFX prot) | `0x0011030F` | VGA memory protection |
| MCR38 (page miss) | `0xFFFFFF82` | Page miss latency mask |
| MCR50-5C (ECC) | `0x00000000` | ECC disabled |
| MCR60 (IO buf) | `0x032AA02A` | I/O buffer mode |
| MCR64 (DLL1 final) | `0x002D3000` | DLL final setting |
| MCR68 (DLL2) | `0x02020202` | Per-lane DLL trim |
| MCR70-7C (test) | `0x00000000` | Test engine disabled |
| MCR34 (initial) | `0x00000001` | CKE assert |
| MCR30 (EMRS1) | `0x00000040` | DLL enable, 150Ω ODT |
| MCR28 sequence | 5,7,3,1 | Mode register command order |
| MCR0C (initial) | `0x00005A08` | Initial refresh |
| MCR30 (OCD) | `0x000003C0` | OCD calibration |
| MCR0C (final) | `0x00005A21` | Normal refresh |
| MCR34 (final) | `0x00007C03` | Power control |

### 7.2 Different Registers (Board/Speed-Specific Tuning)

| Register | Raptor (AST2050/KGPE-D16) | AMI (AST2100) | Analysis |
|----------|--------------------------|---------------|----------|
| MCR04 (config) | `0x00000D89` or `0x585` | Same (compile-time) | Both support 1GB/512MB |
| MCR10 (AC timing1 normal) | `0x22201725` | `0x32302926` | AMI more conservative |
| MCR14 (AC timing1 low) | `0x22201725` (=normal) | `0x01001523` | AMI has separate low-speed |
| MCR18 (AC timing2 normal) | `0x1E29011A` | `0x274C0122` | AMI more conservative |
| MCR1C (AC timing2 low) | `0x1E29011A` (=normal) | `0x1024010D` | AMI has separate low-speed |
| MCR20 (delay normal) | `0x00C82222` | `0x00CE2222` | Slightly different delay |
| MCR24 (delay low) | `0x00C82222` (=normal) | `0x00CB2522` | AMI has separate low-speed |
| MCR40 (grant1) | `0x00000000` | `0x00F00000` | AMI limits VGA grant |
| MCR2C (MRS) | `0x00000732` (CL=3) | `0x00000942` (CL=4) | Raptor lower latency |
| MCR120 (compat MPLL) | `0x00004C41` | `0x00005061` | Different PLL compat value |

### 7.3 Key Differences Explained

1. **CAS Latency: Raptor CL=3 vs AMI CL=4**
   Raptor runs tighter timing, suggesting they verified the specific DDR2 chips
   on the KGPE-D16 support CL=3 at 200 MHz (DDR2-400). AMI uses the safer CL=4,
   which works with a wider range of DDR2 chips.

2. **Separate Low-Speed Timing: Raptor=identical, AMI=different**
   Raptor sets normal and low-speed timing to the same values, indicating
   the KGPE-D16 always runs at full speed. The AMI version has relaxed
   low-speed timing for a power-saving mode where the SDRAM clock is reduced.

3. **VGA Grant Length: Raptor=unlimited, AMI=limited**
   AMI sets `MCR40 = 0x00F00000`, which limits the VGA controller's maximum
   bus grant length. This prevents the VGA from starving the CPU and other
   peripherals during large framebuffer operations. Raptor leaves this
   unlimited, possibly because the KGPE-D16's VGA usage is minimal (BMC
   text console only, not heavy graphics).

---

## 8. Control Flow Diagram

```
lowlevel_init entry
     │
     ├─ Save lr to r4
     ├─ Start Timer4 (performance counter)
     │
     ├─ Unlock SCU (key 0x1688A8A8)
     ├─ Set SCU40 bit 7 (init in progress)
     │
     ├─ Check SCU40 bit 6 (already initialized?)
     │   ├─ YES → Jump to reg_lock (skip init)
     │   └─ NO  → Continue
     │
     ├─ Set MPLL to 0x4c81 (initial ~200 MHz)
     │
     ├─ Configure UART2 (38400 baud)
     ├─ Print "\r\nDRAM Init-DDR\r\n"
     ├─ Delay ~100µs
     │
     ├─ Unlock SCU (again)
     │   ├─ Verify → FAIL: Print "SCU LOCKED", halt
     │   └─ Verify → OK: Continue
     │
     ├─ Set SCU40 = 0x5A000080 (Linux key + init flag)
     │
     ├─ Unlock SDRAM controller (key 0xFC600309)
     │   ├─ Verify → FAIL: Print "SDRAM LOCKED", halt
     │   └─ Verify → OK: Continue
     │
     ├─ Unlock SCU (redundant safety)
     ├─ Set MPLL to 0x41f0 (final 200 MHz)
     ├─ Delay ~400µs (PLL lock)
     │
     ├─ Re-unlock SDRAM controller
     │
     ├─ ═══════════════════════════════════
     │  SDRAM Controller Register Programming
     ├─ ═══════════════════════════════════
     │   ├─ MCR6C: DLL Control #3 (pre-config)
     │   ├─ MCR64: DLL Control #1 (pre-config)
     │   ├─ MCR04: SDRAM Config (1GB/512MB + VGA size from SCU70)
     │   ├─ MCR08: Graphics Memory Protection
     │   ├─ MCR10: Normal Speed AC Timing #1
     │   ├─ MCR18: Normal Speed AC Timing #2
     │   ├─ MCR20: Normal Speed Delay Control
     │   ├─ MCR14: Low Speed AC Timing #1
     │   ├─ MCR1C: Low Speed AC Timing #2
     │   ├─ MCR24: Low Speed Delay Control
     │   ├─ MCR38: Page Miss Latency Mask
     │   ├─ MCR3C: Priority Group (all equal)
     │   ├─ MCR40-4C: Grant Length (unlimited)
     │   ├─ MCR50-5C: ECC (disabled)
     │   ├─ MCR60: IO Buffer Mode
     │   ├─ MCR64: DLL Control #1 (final)
     │   ├─ MCR68: DLL Control #2
     │   └─ MCR70-7C: Test (disabled)
     │
     ├─ ═══════════════════════════════════
     │  DDR2 JEDEC Initialization Sequence
     ├─ ═══════════════════════════════════
     │   ├─ MCR34 = 0x01 (Assert CKE)
     │   ├─ Delay ~400µs (JEDEC tXPR)
     │   │
     │   ├─ MCR2C = 0x732 (MRS: CL=3, BL=4, WR=4, DLL reset)
     │   ├─ MCR30 = 0x040 (EMRS1: DLL enable, 150Ω ODT)
     │   ├─ MCR28 = 0x05  → Issue EMRS2 + EMRS3
     │   ├─ MCR28 = 0x07  → Issue EMRS1 + MRS (DLL reset)
     │   ├─ MCR28 = 0x03  → Issue EMRS1 + MRS
     │   ├─ MCR28 = 0x01  → Issue MRS (+ auto PRECHARGE + REFRESH)
     │   │
     │   ├─ MCR0C = 0x5A08 (Enable refresh — initial rate)
     │   │
     │   ├─ MCR2C = 0x632 (MRS: CL=3, BL=4, WR=4, NO DLL reset)
     │   ├─ MCR28 = 0x01  → Issue MRS (normal operation)
     │   │
     │   ├─ MCR30 = 0x3C0 (EMRS1: OCD calibration default)
     │   ├─ MCR28 = 0x03  → Issue EMRS1
     │   ├─ MCR30 = 0x040 (EMRS1: OCD exit, 150Ω ODT)
     │   ├─ MCR28 = 0x03  → Issue EMRS1 (OCD complete)
     │   │
     │   ├─ MCR0C = 0x5A21 (Normal refresh rate)
     │   ├─ MCR34 = 0x7C03 (Power control: self-refresh enabled)
     │   └─ MCR120 = 0x4C41 (Backward-compatible MPLL)
     │
     ├─ ═══════════════════════════════════
     │
     ├─ Set SCU40 bit 6 (init complete)
     ├─ Print "...Done\r\n"
     │
     ├─ Lock SCU (write 0 to key)
     ├─ Lock SDRAM (write 0 to key)
     │
     └─ Restore lr from r4, return to caller
```

---

## Sources

- [Raptor Engineering ast2050-uboot](https://github.com/raptor-engineering/ast2050-uboot) — Primary source code
- [ya-mouse/openbmc-uboot](https://github.com/ya-mouse/openbmc-uboot) — AMI variant for cross-reference
- [JEDEC JESD79-2B DDR2 SDRAM Standard](https://cs.baylor.edu/~maurer/CSI5338/JESD79-2B.pdf) — DDR2 mode register definitions
- [Aspeed AST2500 Datasheet](https://vgamuseum.info/images/doc/aspeed/ast2520a2gp_datasheet.pdf) — Related SoC register documentation
- [Aspeed AST2600 Datasheet](https://www2.vgamuseum.info/images/doc/aspeed/ast2600_datasheet.pdf) — Related SoC register documentation
- [QEMU Aspeed Machine Emulation](https://www.qemu.org/docs/master/system/arm/aspeed.html) — Aspeed SoC memory map reference
