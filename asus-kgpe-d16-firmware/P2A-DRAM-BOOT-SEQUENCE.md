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

### ✅ VALIDATED ON HARDWARE (2026-07-08) — read this, the rest of §0 is the method

- **The BMC debug UART is UART2 = `0x1e784000`** (matches Raptor's `.Done`). UART1
  (`0x1e783000`) is **not connected** (0 edges when driven).
- **The docs' pin table was WRONG.** The two jumpers were **crossed**: BMC-TXD landed on
  Pi **GPIO14 (pin 8 = Pi TX)** instead of GPIO15. Found by a `gpiomon` bitbang probe
  (60 edges @ ~829 µs = 1200 baud showed up on GPIO14). **Now swapped** to the correct
  cross: **BMC-TXD → Pi GPIO15/pin10 (RX)**, **BMC-RXD → Pi GPIO14/pin8 (TX)**, **GND pin6**.
- **Proven working:** driving UART2 over P2A at **1200 8N1** reads byte-perfect on the Pi.
  Named **`/dev/serial-bmc-console`** (udev `99-bmc-console.rules`, `-> ttyS0`).
- **UARTCLK = 24 MHz** confirmed (`SCU0C[15]=0` clock on, `SCU2C[12]=0`), so **1200 baud
  → divisor 1250** (DLL=`0xE2`, DLH=`0x04`). For **115200** (real U-Boot) use divisor 13
  (DLL=`0x0D`) — but `ttyS0` is the flaky mini-UART; switch the Pi to the **PL011**
  (`dtoverlay=disable-bt`, drop `console=serial0`, reboot → `ttyAMA0`) before trusting 115200.
- `/dev/ttyUSB0` = a Prolific adapter (`serial-com1`) = the *host* COM1; `/dev/ttyUSB1` =
  ULX3S. Watch **`/dev/serial-bmc-console`** for BMC output.

**Original (incorrect) doc wiring** for reference — do NOT use: `RPI4-OPENOCD-JTAG-WIRING.md`
claimed BMC-TXD→GPIO15 already; in reality it was on GPIO14 until the 2026-07-08 swap.

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

## 2. Reset-tree analysis — the decisive part (datasheet §8, **V1.02** p82‑96)

> Register facts below are re-verified against the in-repo datasheet
> (`AST2050_AST1100_A3_Datasheet_V1.02.pdf`, the actual file — the "V1.05" cited
> earlier does not exist here). Two claims in the first draft were **corrected**
> (marked ⚠) after reading the register definitions, per "verify before believing."

**Good news — DDR2 survives a watchdog reset.** *Figure 39 (Memory Controller
Reset, p92):* `MMC_RST_N = pwrstn OR SCU04[0]` — **`wdt_rst`/`hrstn` are not
inputs.** *Clock/Reset Mapping Table (Fig 18, p83):* DRAM Controller → `MMC_RST_N`.
→ a watchdog reset leaves DDR2 initialised. **Empirically confirmed** in STAGE 2
(DRAM held `0xeafffffe` through the reset).

**The obstacle — the ARM CPU and the remap share one reset domain.** *Figure 38
(AHB Bus Reset, p92)* generates **`HRST_N`** from `wdt_rst OR EXTRSTNin(gated) OR
PWRSTNin`. *Clock/Reset Mapping Table (Fig 18)* lists **both "ARM CPU" and "AHB
Controller" as `HRST_N`.** The AHB Controller is where the remap register
(`AHBC8C` = `0x1E60008C`) lives → a watchdog `HRST_N` hits both. There is **no
"reset only the ARM CPU" mode** on the AST2050.

⚠ **Correction (was wrong in the first draft):** `SCU3C[3]` is **"Enable external
SOC reset (GPIOB7/EXTRST#)"** (datasheet SCU3C p215) — it gates the *external reset
pin*, **not** `wdt_rst`. So `wdt_rst → HRST_N` is **unconditional**; no SCU3C
change is needed to make the watchdog reset the ARM. (`SCU3C[1]` is the read-back
**"watchdog reset flag"**, set by the wdt reset — a handy post-reset witness.)

**Host stays alive across the reset (why STAGE 2 is safe).** The host reaches the
BMC over P2A through the **VGA/PCI-slave endpoint** (`PCI_RST_N`, *Fig 47*:
`BRSTNin OR SCU04[8] OR PWRSTNin` — **not** `hrstn`) → it **survives** a watchdog
`HRST_N`, so the x86 host keeps the PCIe device. Only the internal **A2P bridge**
(`A2P_RST_N`, *Fig 55*, includes `hrstn`) resets — but a fresh `culvert` invocation
re-inits it (== `ahb_reinit_bridge`). **Confirmed:** after the reset, P2A read
`SCU7C=0x202` immediately.

## 3. THE PIVOTAL QUESTION — ✅ ANSWERED (STAGE 2, 2026-07-08)

> **Does the remap register `0x1E60008C[0]` reset on `HRST_N`, or is it a
> power-on-only ("sticky") register?**

**ANSWER: it resets on `HRST_N`.** `remap-test-p2a.py stage2` set the remap, armed
WDT1 (2 s @ 1 MHz, `WDT0C=0x13`), let the BMC `HRST_N`, then read back over P2A:

| Read (post-reset) | Value | Meaning |
|---|---|---|
| `SCU7C` | `0x00000202` | chip alive, **P2A survived** (host safe) |
| `SCU3C` | `0x00000003` | bit1 set = **watchdog reset fired** (witness) |
| `0x1E60008C` (remap) | `0x00000000` | **remap CLEARED by `HRST_N`** |
| `0x00000000` | `0x00000000` | `0x0` reverted to (dead) flash |
| `0x40000000` (DRAM) | `0xeafffffe` | **DDR2 survived** the reset |

So the naive **"set remap + watchdog reset" P2A-only boot is BLOCKED**: any
ARM-restarting reset also clears the remap, so the ARM re-fetches `0x0` = flash
(which reads `0` on this rig → dead). The datasheet block-level table (AHB
Controller → `HRST_N`) predicted this; STAGE 2 proves it at the register level.

**What still works / what this bought us:**
- A **host-safe P2A watchdog reset** of the AST2050 (host + P2A recover; DDR2
  survives) — reusable for any future reboot control.
- The **remap-live** mechanism (STAGE 1) and **DDR2 init** (M1) remain valid.
- It rules out the easy path cleanly, pointing at the real options in §6 — **and**
  at one more P2A-only idea worth testing: **§6a, the clock-gate-across-reset trick.**

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

### ✅ STAGE 1 RESULT (2026-07-08) — the remap goes LIVE over P2A

Steps 1–4 ran on the real AST2050 (`remap-test-p2a.py stage1`), **no reset**:

| Step | Action | Result |
|---|---|---|
| M1 | `ddr2-init-p2a.py` | DRAM `0x40000000`=`0xdeadbeef` (DDR2 alive; board had been power-cycled so M1 was re-run) |
| 1 | seed DRAM `0x40000000..1c` = `0xeafffffe` (`b .`) | read back `0xeafffffe` |
| 3a | AHB unlock `0xaeed1a03` → `0x1e600000` | (enables the write below) |
| 3b | set `0x1e60008c` bit0 | reads back **`0x00000001`** (register writable ⇒ unlock correct) |
| 4 | **read `0x00000000` over P2A** | **`0xeafffffe`** — i.e. `0x0` *is* the DRAM |

So **the DRAM→`0x0` remap works live over P2A** (the AHB key + remap bit from
Raptor's `board_init()` are correct on real silicon), and **`0x0` is now backed by
writable DRAM** (retires the §5 crash hazard for `0x0`). The **host did not crash**
flipping the remap. This answers *half* of §3 (the remap goes live); the other half
— does it **survive `HRST_N`** — is STAGE 2, which needs a working G3 reset (see below).

**STAGE 2 blocker found:** `culvert reset soc wdtN` does **not** work on G3 yet —
`g3.dts` declares the watchdog nodes `compatible = "aspeed,ast2400-wdt"` but
culvert's `wdt.c` driver only matches `"aspeed,ast2500-wdt"`, so it never binds.
And `wdt_perform_reset`'s reset-**mask** register (`0x1c`) and `RESET_SOC/CPU` mode
bits are AST2500 additions — the AST2050 reset tree (§2) has only a single
`wdt_rst` gated by `SCU3C[3]`. So STAGE 2 requires porting the wdt reset to G3
(bind `ast2400-wdt`, use the AST2050 `WDT_CTRL`=`0x23` semantics, verify against the
datasheet) **and** it should carry a **UART-signature ARM stub** (#19) as the
witness — so the ARM running our code shows on `/dev/serial-bmc-console`
*independently of whether the reset disturbs P2A/the host*.

## 5. HARD safety rule (the host-crash lesson)

Writing `0x00000000` (or the `0x14000000` flash window) over P2A **while the remap
is NOT set** stalls the AHB (no writable slave there) → hangs the AST2050 PCIe/VGA
function → **hangs the x86 host** (2026-07-08 incident: I crashed the PXE host this
way). **NEVER write `0x0` before step 4 confirms the remap points it at DRAM.** Test
the remap with a *read* of `0x0` first; only write `0x0` once it reads back DRAM.

## 6a. ✅ SOLVED — P2A-only ARM boot works (freeze-across-reset via SCU70[1:0])

**Achieved 2026-07-08** (`arm-stub/boot-p2a.py --mode reset-boot`): the ARM booted our
stub from DRAM over P2A alone — the BMC UART printed `AST2050-ARM-ALIVE-P2A-DRAM-BOOT`.
The winning primitive is **`SCU70[1:0]` = "ARM CPU boot code selection"** (datasheet
p215): `10` = boot from SPI, **`11` = "Disable ARM CPU operation"** — a *live* ARM
enable/disable. Because the SCU is `PWRSTNin`-only reset, the disable **survives
`HRST_N`**, so it holds the ARM at the reset vector while we re-establish the remap.

**The working sequence (all over culvert P2A, no spispy/JTAG):**
1. `ddr2-init-p2a.py` — DDR2 up (M1).
2. Seed the payload into DRAM (reset vector at the DRAM base).
3. Set the DRAM→`0x0` remap (AHB unlock + `0x1E60008C[0]=1`).
4. **Disable the ARM**: SCU-unlock (`0x1688A8A8`→`SCU00`), `SCU70 |= 0x1` (→`[1:0]=11`), relock. *(RMW — preserves the strap `0x00819582`; culvert's bare `SCU70=0x1` would corrupt it.)*
5. **Watchdog `HRST_N`**: arm WDT1 (`WDT0C=0x13`, 2 s @ 1 MHz), wait. HRST_N resets the ARM's PC→`0x0` but it is **held disabled**; the remap clears; **DDR2 and the SCU survive**.
6. **Re-set the remap** (AHB unlock + `0x1E60008C[0]=1`) → `0x0` = DRAM = payload again.
7. **Enable the ARM**: SCU-unlock, `SCU70 &= ~0x1` (→`[1:0]=10`), relock → the ARM fetches `0x0` = DRAM and **runs our code**.

Why the simpler variants failed (documented so we don't retry them):
- *remap-while-live* (`--mode live`): the firmware-dead ARM NOP-slid off `0x0` at
  power-on and **stalled high** — it never re-fetches `0x0`, so seeding+remap alone
  never runs. Only a reset forces `PC=0x0`.
- *SCU70 toggle with no reset* (`--mode arm-restart`): toggling `[1:0]` `10→11→10`
  changes the register but does **not** restart the ARM (its PC isn't `0x0`; a live
  enable/disable doesn't reset PC). The `HRST_N` is what makes `PC=0x0`.

This is the mechanism for booting **U-Boot** the same way (§8): DDR2 is already up, so
a U-Boot that runs from DRAM needs only to be bulk-loaded into DRAM and started by
this trick.

## 6b. (historical) The clock-gate-across-reset trick — superseded by §6a

§3 says `HRST_N` clears the remap *and* the ARM in the same pulse — so the ARM
always re-fetches `0x0`=flash. But the **ARM clock gate lives in the SCU**, and the
SCU is **`PWRSTNin`-only reset** (Fig 37: *"All registers in SCU reset by PWRSTNin
only; no other reset input can affect them"*). So the gate **survives `HRST_N`.**
That opens a P2A-only sequence that side-steps the cleared remap:

1. M1 (DDR2 up); load the payload into DRAM (reset vector at the DRAM base).
2. **Gate the ARM clock** (freeze the core) — culvert `clk_disable(clk_arm)` writes
   the SCU strap (G3 `ast2400` path: set `SCU70[0]`, clear via `SCU7C[0]`).
3. **Watchdog `HRST_N`.** This resets the ARM (PC→`0x0`) and clears the remap, but
   the ARM is **clock-gated → frozen at `0x0`, not fetching**; the SCU gate and DDR2
   both survive.
4. **Re-set the remap over P2A** (AHB unlock + `0x1E60008C[0]=1`) → `0x0` = DRAM again.
5. **Un-gate the ARM clock** → the ARM's first fetch at `0x0` = DRAM = **our code**.

**Liveness test result (2026-07-08, `arm-stub/boot-p2a.py --mode live`):** seeded the
UART stub (`arm-stub/uart-hello.S`, all 8 vectors → `_start`, prints
`AST2050-ARM-ALIVE-P2A-DRAM-BOOT`) into DRAM and set the remap **with no reset**.
Read-back confirmed `0x0`=`0xea000006` (stub at the reset vector). **No signature
appeared** on `/dev/serial-bmc-console` in 20 s. → The ARM is **not** cycling back
to the low vectors: it NOP-slid up from `0x0` at power-on, hit unmapped AHB space and
**stalled (hung high)** — it never re-fetches `0x0`. So a plain remap-while-live can
**not** boot it; **only a reset forces `PC=0x0`** — and that clears the remap. This
makes §6a (freeze-across-reset) **the** remaining P2A-only route.

**Unverified assumptions to test (in order):** (a) find a **safe** ARM-clock-stop —
**not** culvert's bare `SCU70=0x1` write (AST2050 `SCU70` is plain RW, that would
wipe the live strap `0x00819582`); the ARM clock is in the SCU **clock-stop /
CPU-divider** path (`SCU0C`, datasheet §... — investigate, use read-modify-write).
(b) verify it *gates the running ARM live* (witness: the stub stops/starts printing).
(c) the gate **survives `HRST_N`** (SCU is `PWRSTNin`-only, so it should). (d) after
the reset the ARM holds at `0x0`, and once un-gated fetches the re-mapped DRAM. If a
safe live gate doesn't exist, this path is dead and we're on §6 (JTAG/spispy).

## 6. If the P2A-only paths are all blocked: the honest fallbacks

- **JTAG** — set the ARM PC directly (no reset, no remap dependency). Needs the
  unpopulated `AST_JTAG1` header soldered/wired (physical). TAP scan currently
  all-ones.
- **spispy on the BMC CE2 flash** — write a tiny "set remap + jump to DRAM" stub (or
  a full U-Boot) to the boot flash and let the ARM boot it normally. Needs the ULX3S
  moved from the host BIOS to the BMC boot flash + the spispy load tool (instance-A's
  rig knowledge).

## 🎉 GOAL ACHIEVED (2026-07-08): U-Boot runs on the AST2050 over P2A alone

The full Raptor AST2050 **U-Boot booted on the real BMC via culvert/P2A** — no
spispy, no JTAG. The BMC UART (`/dev/serial-bmc-console`, 1200 8N1) printed:

```
U-Boot 2013.07 (Jul 08 2026 - 18:25:48)
I2C:   ready
DRAM:  64 MiB
WARNING: Caches not enabled
Flash: SPI Flash ID: 0
Can't support this SPI Flash!!
```

`DRAM: 64 MiB` proves the ARM ran our code and probed real DRAM. The SPI-flash line
is expected (the boot flash isn't served over P2A on this dead-firmware rig; U-Boot
halts there for lack of an environment — a downstream concern, not a boot failure).

**The complete P2A-only recipe (what got us here):**
1. `ddr2-init-p2a.py` — DDR2 up. **Three geometry/timing fixes were required and
   hardware-verified:** 4-bank (`MCR04` bit11=0), 64 MB (`MCR04[3:2]=01`, value
   `0x585`), and the **FINAL DLL block** (`MCR64=0x002d3000` + `MCR68=0x02020202`;
   platform.S writes MCR64 twice and the final value is the real DQS delay — omitting
   it caused 0.29% data errors that corrupted the payload). Also sets `SCU40[6]`.
2. Build `u-boot.bin` (`RAPTOR-UBOOT-BUILD.md`): board `ast2050`, TEXT_BASE 0x0, baud
   1200, init-SP moved +16 MB (stock `+0x1000` collides with the DRAM-loaded image),
   `SUBDIR_TOOLS=` to skip the unbuildable vintage host tools.
3. `p2a-image-boot.py --image u-boot.bin --baud 1200` — siphon into DRAM, verify
   byte-perfect, then the **reset-boot trick (§6a)**: disable ARM (`SCU70[1:0]=11`,
   survives `HRST_N`), watchdog `HRST_N`, re-set the remap, enable ARM (`=10`).
   `lowlevel_init` sees `SCU40[6]` and **skips the DDR2 re-init** (which would crash
   the running-from-DRAM code).

## 7. Summary (updated 2026-07-08 after STAGE 1 + STAGE 2)

- **UART second channel (§0): DONE + validated** — BMC UART2 `0x1e784000` → Pi
  `/dev/serial-bmc-console`, 1200 8N1 proven. Independent witness for the ARM stub.
- **DDR2 init (M1): DONE + hardware-verified**, and **survives a watchdog reset**
  (Fig 39; confirmed empirically in STAGE 2).
- **Remap goes live over P2A (STAGE 1): YES** — `0x0` becomes DRAM after the AHB
  unlock + `0x1E60008C[0]=1`.
- **Remap survives `HRST_N` (STAGE 2): NO** — it clears on any ARM-restarting reset,
  so the "set remap + reset" P2A boot is **blocked** (the pivotal question, answered).
- **Bonus:** a **host-safe P2A watchdog reset** now exists (host + P2A recover), and
  `SCU3C[1]` witnesses it.
- **✅ P2A-only ARM boot SOLVED (§6a):** freeze the ARM across a watchdog `HRST_N`
  using **`SCU70[1:0]=11` ("Disable ARM CPU operation")** — which survives the reset —
  then re-set the remap and re-enable (`=10`). The ARM ran our stub from DRAM; the BMC
  UART printed `AST2050-ARM-ALIVE-P2A-DRAM-BOOT`. No spispy, no JTAG.
- **Next: U-Boot the same way (§8)** — bulk-load a DRAM-runnable U-Boot over P2A and
  start it with the §6a trick. JTAG/spispy (§6) are no longer needed.
