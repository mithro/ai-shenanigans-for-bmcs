# Starting the AST2050 ARM from DRAM over P2A — sequence spec

**Task #18.** Goal: bring the dead-firmware AST2050 ARM to life running our own code,
using only the culvert **P2A** (PCIe→AHB) back door — no JTAG (header is unwired),
no spispy (on the host BIOS, not the BMC flash). This is the "init DRAM, load code,
make the CPU jump to it" idea. DDR2 bring-up (**M1**) is already hardware-proven
(`ddr2-init-p2a.py`). This doc specifies the *start-the-ARM* half and, critically,
identifies the one datasheet-unresolved question that decides whether it can work
at all.

All register facts below are cited to `hwreg.h` (Raptor's RE) and the
**AST2050/AST1100 A3 datasheet V1.05** (`dell-c410x-firmware/datasheets/`).

## 0. FIRST on power-on: bring up the BMC UART second channel (P2A-only)

Before anything else, establish a **serial channel independent of P2A**. It gives a
second way to observe the BMC (and later interact with U-Boot), and — crucially —
an **independent witness** for every step below: the §4 remap test and the ARM stub
(#19) can be *confirmed over serial*, not just by reading registers back through the
same P2A path we're trying to validate. `RPI4-OPENOCD-JTAG-WIRING.md` says to wire
this first for exactly this reason ("UART proves the BMC is alive before you risk
JTAG").

**Confirmed wiring** (`RPI4-OPENOCD-JTAG-WIRING.md:194‑207`): the BMC console is the
Raptor **`AST_UART1`** 4-pin 3.3 V header, **115200 8N1**, cross-wired to the **Pi
UART0 (GPIO14/15)** → **`/dev/serial0` (`ttyS0`)**:
`GPIO14/TX(p8)→BMC RXD`, `GPIO15/RX(p10)←BMC TXD`, `GND p6`.
(`/dev/ttyUSB0` = a Prolific adapter aliased `serial-com1` — the *host* COM1, not the
BMC; `/dev/ttyUSB1` = the ULX3S/spispy. So watch **`ttyS0`** for BMC output.)

**P2A UART bring-up + identify** — Raptor's `.Done` debug goes to UART2
(`0x1e784000`), but which register-UART is physically `AST_UART1` is confirmed by
test, not assumed. For **each** candidate UART base `U` ∈ {`0x1e783000` (UART1),
`0x1e784000` (UART2)}, over P2A (offsets from `hwreg.h`: RBR/THR=`+0x00`,
IER=`+0x04`, FCR=`+0x08`, LCR=`+0x0C`, LSR=`+0x14`; DLL=`+0x00`/DLH=`+0x04` when
LCR[7]=1):

| Step | Reg | Value | Meaning |
|---|---|---|---|
| 1 | `U+0x0C` (LCR) | `0x83` | DLAB=1, 8N1 |
| 2 | `U+0x00` (DLL) | `0x0D` | divisor 13 → 115200 @ 24 MHz UARTCLK (24e6/(16·13)≈115200) |
| 3 | `U+0x04` (DLH) | `0x00` | |
| 4 | `U+0x0C` (LCR) | `0x03` | DLAB=0, 8N1 |
| 5 | `U+0x08` (FCR) | `0x07` | enable + clear TX/RX FIFOs |
| 6 | `U+0x00` (THR) | ASCII bytes | write a **unique marker** per UART, e.g. `"U1?\r\n"` / `"U2?\r\n"` |

On the Pi: `stty -F /dev/ttyS0 115200 raw && cat /dev/ttyS0` and see which marker
arrives → that base is `AST_UART1`. This is **P2A-only, needs no ARM**, so it works
the instant the board is powered — do it right after `ddr2-init-p2a.py` (or even
before). Success = the marker appears on `ttyS0` → **second channel live.**

> Note on UARTCLK: divisor 13 assumes the 24 MHz reference (the datasheet's
> `SCU2C[12]` "24 MHz/13" option corroborates 13 for 115200). If the marker is
> garbled, the reference/divisor differs — sweep DLL ∈ {13, 1, 12, 24} and pick the
> one that prints clean ASCII on `ttyS0`.

Once live, the ARM test stub (#19) writes its signature to this same UART (as
`platform.S` does with `.Done`), so **the stub's execution shows on `ttyS0`
independently of P2A** — the cleanest possible proof the ARM ran our code.

## 1. The mechanism (well-defined)

The standard ARM bring-up: at reset `0x00000000` is the SPI boot flash (CE2); early
code inits DRAM, then flips a **remap** so writable DRAM appears at `0x0`. Raptor's
`board_init()` (`RAPTOR-UBOOT-ANALYSIS.md:223‑227`) does exactly this:

| Step | Register | Value | Meaning |
|---|---|---|---|
| AHB unlock | `AHB_PROTECTION_KEY_REG` = `0x1E600000` | `0xAEED1A03` | unlock the AHB controller regs |
| DRAM→0x0 remap | `AHB_ADDR_REMAP_REG` = `0x1E60008C` | set **bit 0** | map DRAM into the `0x0` boot region |

Watchdog (to restart the ARM), from `hwreg.h:164‑169` / Raptor `reset.c`:

| Register | Addr | Value |
|---|---|---|
| `WDT_RELOAD_REG` | `0x1E785004` | `0x00000010` (reload) |
| `WDT_CNT_RESTART_REG` | `0x1E785008` | `0x00004755` (magic reload key) |
| `WDT_CONTROL_REG` | `0x1E78500C` | `0x00000023` (Raptor: "full chip reset") |

The intended P2A-only recipe:
1. Init DDR2 (`ddr2-init-p2a.py`) — **done, M1.**
2. Write a payload into DRAM so its reset vector lands at the DRAM base that maps to `0x0`.
3. AHB unlock (`0xAEED1A03`→`0x1E600000`), set remap (`0x1E60008C[0]=1`).
4. Watchdog-reset the ARM (`0x1E785000` sequence).
5. ARM re-fetches `0x0` → now DRAM → runs our code.

## 2. Reset-tree analysis — the decisive part (datasheet §8, V1.05 p84‑96)

**Good news — DDR2 survives a watchdog reset.** *Figure 40 (Memory Controller
Reset, p94):* `MMC_RST_N` is driven only by `pwrstn` (power-on) OR `SCU04[0]`
(software) — **`wdt_rst` is not an input.** The *Reset Tree Control Table (Fig 20,
p86)* agrees: the DRAM Controller row is marked under `SRST#` and the `DRAM`
register-control column, **not under `WDT`.** → a watchdog reset leaves DDR2
initialised. So M1 does not need re-running after a wdt reset.

**The obstacle — the ARM CPU and the remap share one reset domain.** *Figure 39
(AHB Bus Reset, p94)* generates **`HRST_N`** from `pwrstn OR EXTRSTNin OR
(wdt_rst AND SCU3C[3])`. The *Clock/Reset Mapping Table (Fig 19, p85)* lists **both
"ARM CPU" and "AHB Controller" as `HRST_N`.** The AHB Controller is where the remap
register (`0x1E60008C`) lives. And the Reset Control Table has **no `SCU04` column
to reset the ARM CPU by itself** — the ARM resets only via global `SRST#`/`WDT`
(i.e. `HRST_N`). Consequences:

- To make the ARM re-fetch, I must assert `HRST_N` (watchdog, with `SCU3C[3]=1`).
- That same `HRST_N` also resets the AHB Controller.
- `SCU3C[3]` only gates *whether* `wdt_rst` reaches `HRST_N` — it can't reset the
  ARM while sparing the AHB Controller (they are the same net). So there is **no
  "reset only the ARM CPU" mode** on the AST2050.

## 3. THE PIVOTAL OPEN QUESTION

> **Does the remap register `0x1E60008C[0]` reset on `HRST_N`, or is it a
> power-on-only ("sticky") register?**

- **If power-on-only** (common for boot/strap registers): during the watchdog's
  `HRST_N` pulse the remap *holds* the value P2A set, so when `HRST_N` deasserts the
  ARM fetches `0x0` = **DRAM = our code**. ✅ The P2A-only path works.
- **If it resets on `HRST_N`**: the remap clears to its default (flash at `0x0`) the
  instant the watchdog fires, so the ARM re-fetches **flash**, not DRAM. ❌ The
  P2A-only path is blocked; starting the ARM then still needs JTAG (set PC directly,
  no reset) or a writable boot flash (spispy stub at `0x0`).

The datasheet's block-level table says the *AHB Controller* resets on `WDT`, but
individual boot-control registers within a block frequently have a *narrower*
(power-only) reset — the table's granularity doesn't settle it. **This is the one
fact that decides the whole approach, and it is empirically testable.**

## 4. Test procedure to resolve §3 (on the next power-on, carefully)

Non-destructive, one step at a time, each logged to `HARDWARE-COORDINATION.md`:

1. Power on; `ddr2-init-p2a.py` (M1).
2. Write a distinct marker to DRAM `0x40000000` (e.g. `0xB007C0DE`).
3. AHB unlock + set remap (`0x1E60008C[0]=1`).
4. **Read `0x00000000` over P2A.** If it now reads `0xB007C0DE`, the remap works
   live and `0x0` is DRAM (also proving `0x0` is now *safe to write* — see §5).
5. Watchdog-reset (`0x1E785000` sequence).
6. After reset settles, **read `0x1E60008C` and `0x00000000`.**
   - remap bit still 1 / `0x0` still DRAM → **power-only reset → the boot path is
     viable**; proceed to load the stub (task #19).
   - remap bit 0 / `0x0` back to flash → **`HRST_N` clears it → path blocked**; fall
     back to JTAG (wire the header) or spispy-on-BMC-flash.

## 5. HARD safety rule (the host-crash lesson)

Writing `0x00000000` (or the `0x14000000` flash window) over P2A **while the remap
is NOT set** stalls the AHB (no writable slave there) → hangs the AST2050 PCIe/VGA
function → **hangs the x86 host** (2026-07-08 incident: I crashed the PXE host this
way). **NEVER write `0x0` before step 4 confirms the remap points it at DRAM.** Test
the remap with a *read* of `0x0` first; only write `0x0` once it reads back DRAM.

## 6. If §3 comes back "blocked": the honest fallbacks

- **JTAG** — set the ARM PC directly (no reset, no remap dependency). Needs the
  unpopulated `AST_JTAG1` header soldered/wired (physical). TAP scan currently
  all-ones.
- **spispy on the BMC CE2 flash** — write a tiny "set remap + jump to DRAM" stub (or
  a full U-Boot) to the boot flash and let the ARM boot it normally. Needs the ULX3S
  moved from the host BIOS to the BMC boot flash + the spispy load tool (instance-A's
  rig knowledge).

## 7. Summary

- **Establish the UART second channel first (§0).** P2A-only, no ARM needed, works the
  instant the board is powered — an independent witness for every step and the future
  U-Boot console. `AST_UART1` → Pi `ttyS0`, 115200 8N1.
- **Load DRAM: solved (M1).** The hard part was never writing the code — it's PC control.
- **DDR2 survives a watchdog reset** (Fig 40) — a real, useful finding.
- **The P2A-only boot's viability reduces to one testable bit**: the reset domain of
  `0x1E60008C[0]` (§3). Resolve it empirically (§4) before building a full payload.
- If it's power-only-reset, your "write DRAM + jump" idea works entirely over P2A.
  If it's `HRST_N`-reset, we're back to JTAG/spispy — but now with the exact reason
  documented, not a guess.
