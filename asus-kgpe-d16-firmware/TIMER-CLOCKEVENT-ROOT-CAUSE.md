# ROOT CAUSE: the AST2050 timer clockevent interrupt never fires (hrtimers hang)

**This is the real blocker behind the "eth0 ndo_open hang" — and it is NOT a NIC bug.**

## What actually happens
The modern kernel boots on the real AST2050 and reaches `ip_auto_config` → `ftgmac100_open`
(ndo_open). ndo_open calls `usleep_range()` (in `reset_and_config_mac`) — and **hangs
there forever**. Pinpointed by:
1. Reading `__log_buf` from DRAM over P2A (chunked in 0x800 blocks — the P2A read window
   only returns ~2KB reliably per invocation; see `rig/nic-diag/logbuf_chunked_host.py`):
   the log shows `clocksource: Switched to FTTMR010-TIMER2` but **no working clockevent**,
   and ndo_open stops dead at the first `usleep_range`.
2. Replacing `usleep_range` with `udelay` (busy-wait) in the ftgmac100 reset path → ndo_open
   **sails through step3/step4/step5 (phy_start) + adjust_link** (all markers appear).

So: **`usleep_range` / any hrtimer-based sleep hangs** because the AST2050's FTTMR010
timer has a registered clocksource (TIMER2, read-based timekeeping — works) but its
**clockevent interrupt (TIMER1) never reaches the CPU** → hrtimers never fire. The boot
only reaches 4s because early boot is sequential + `udelay`-based (udelay uses the
clocksource, not interrupts). ndo_open is just the first code to call an hrtimer sleep.

**The ftgmac100 NIC driver is fine.** Fix the timer and eth0 (and NFS, and everything that
sleeps) comes up.

## Where the timer setup stands
- DT `timer@1e782000`: `compatible="aspeed,ast2400-timer"`, `interrupts=<0x10 0x11 ...>`
  (0x10=16 = TIMER1), `clocks=<&clk PCLK>`.
- `timer-fttmr010.c` registers the clocksource (before request_irq) AND the clockevent
  (after request_irq at line ~411). No `"FTTMR010-TIMER1 no IRQ"` / `"Can't parse IRQ"` in
  the log → request_irq **succeeded**, clockevent **registered**, aspeed INT bit (BIT2) set.
- Yet the timer interrupt doesn't fire/deliver. Serial (irq 19) + eth (irq 20) IRQs *do*
  work, so the VIC delivers some interrupts — but not the timer's hwirq 16.

## Investigation so far (2026-07-09, on the fresh power-cycled rig)
Read live over P2A while the kernel is hung in ndo_open (udelay build):
- **Timer IS set up + running**: TMC30 control (0x1e782030) = `0x15` = TIMER1 ENABLE|INT +
  TIMER2 ENABLE; TIMER1 counting (count 0x1083a below load 0x7270e, MATCH1=0). So the timer
  counts down toward the match and *should* assert its interrupt.
- **Timer IRQ (16) is CORRECT for the AST2050**: cross-checked Raptor's `ast2100_irqs.h`
  (the AST2050/AST1100 family): MAC0=2, UART1=10, **TIMER0=16** — all match this DT. (The
  older ast2000 family had TIMER0=3, but that's not this SoC; eth@irq2 + uart@irq10 work,
  confirming ast2100.) So the DT `interrupts=<0x10>` is right.
- **No interrupts are being delivered at all**: the boot runs entirely interrupt-free
  (sequential + udelay) to ndo_open; the first hrtimer sleep hangs. VIC (aspeed AVIC @
  0x1e6c0080) INT_ENABLE (+0x20) reads 0, but the driver treats it write-1-to-set and never
  reads it back, so that read is likely write-only / inconclusive.

So the timer asserts but its interrupt never reaches the CPU. The break is in delivery:
VIC enable/mask, the ARM IRQ line, or a G3-specific interrupt quirk.

## Localised further (2026-07-09): timer fires but never reaches the VIC
Live P2A while hung: TIMER1 count is **moving** (0x5491f → 0x39fab), so the timer runs and
reaches its match (MATCH1=0). But the AVIC RAW_STATUS/EDGE_STATUS/IRQ_STATUS (low word,
bit16) all read **0** across repeated reads — the timer's interrupt pulse never appears at
the VIC. Timer IRQ number is confirmed correct (16). So the break is between the timer's
interrupt output and the VIC latching it.

## Prime suspects for the fix (next), most-likely first
1. **VIC edge/level sense mismatch**: the DT VIC uses `#interrupt-cells = <1>` (no
   per-IRQ edge/level flag), so all lines get a fixed sense from `avic_of_init`. The aspeed
   timer's match interrupt is a brief pulse at count==0 (immediately reloads); if the VIC
   treats line 16 as level (not edge-latched), the pulse is missed. Check
   `irq-aspeed-vic.c` `avic_of_init` sense/edge setup + the AST2050 vs AST2400 timer
   interrupt polarity. **Leading candidate.**
2. **Timer interrupt output not routed on the G3**: the AST2050 may need an extra
   enable/route bit beyond `TIMER_1_CR_ASPEED_INT` (BIT2) for the interrupt to reach the
   VIC. Compare vs Raptor's AST2050 timer init (`mach-aspeed`).
3. **PCLK rate**: clocksource timestamps look right, so low priority.

## Tested (2026-07-09), did NOT fix it
- Patched `vic_init_hw` to `writel(0xffffffff, AVIC_INT_SENSE)` (force all level) before
  reading it. After boot the SENSE register still reads `0` over P2A and the boot still
  hangs after ndo_open (only U-Boot tftp packets on the wire, ping fails). So either the
  AVIC_INT_SENSE is read-only / hardware-fixed, or level-vs-edge isn't the mechanism. The
  timer's interrupt still never appears at the VIC (RAW/EDGE/IRQ bit16 = 0) even though the
  timer counts and its INT bit is set.
- Open question narrowing: the timer's match interrupt genuinely isn't reaching VIC bit16.
  Next: (a) confirm the clockevent is actually *armed* (MATCH1 reads 0 — is set_next_event
  running? oneshot vs periodic?), (b) check the AST2050 datasheet timer→VIC interrupt
  routing (the pulse at count==0 with MATCH1=0 may not assert on the G3), (c) compare live
  register-for-register against a booted AST2400 (mainline) timer, (d) try the RTC/other
  aspeed clockevent, or a `arm,arm926` local-timer alternative.

## ⚠️ 2026-07-09 CRITICAL: the P2A window is BLIND to the VIC — prior VIC reads were phantom
Direct test (`rig/nic-diag/vic_probe_host.py`, via `culvert p2a vga read/write`):
- **P2A read+write works for DRAM** (wrote `0xdeadbeef` to `0x41234000`, read it back) and
  for the **SCU** (`0x1e6e207c`=`0x00000202`) and the **Timer** (`0x1e782000` COUNT moving,
  `0x1e782030` CONTROL=`0x15`, LOAD=`0x7270e`). So P2A itself is healthy.
- **P2A canNOT touch the 0x1e6c0000 VIC region**: the whole block `0x1e6c0000..0x1e6c0070`
  reads `0x00000000`; writing `0x00010000` to the R/W `INT_ENABLE` (`0x1e6c00a0`) and
  `0xA5A5A5A5` to `INT_SENSE` (`0x1e6c00c0`) both read back `0`. The Aspeed P2A bridge
  filters the interrupt-controller block (a security-sensitive region) out of the "vga"
  window — reads return 0, writes go nowhere, regardless of the real VIC state.

**Consequence:** every earlier VIC observation in this doc — "RAW/EDGE/IRQ_STATUS bit16 = 0",
"the timer interrupt never reaches the VIC", "INT_SENSE reads 0 so the all-level write didn't
stick" — was reading **phantom zeros**, not the hardware. The "timer IRQ doesn't reach the
VIC" localisation is therefore **UNPROVEN**, and the "all level" SENSE write test result was
meaningless (the write never landed; the readback was blind). The VIC may well be fine.

**The only reliable VIC observer is the ARM core itself.** So we now instrument the kernel:
- `irq-aspeed-vic.c` `vic_init_hw`: `pr_warn` the real `SENSE/EVENT/DUAL/ENABLE/RAW` (ARM-side
  reads — reliable). Prints the true power-on VIC config.
- `timer-fttmr010.c`: an `atomic_t` counter in `fttmr010_timer_interrupt` + a `late_initcall`
  (`fttmr010_irq_check`) that `mdelay(200)`s and prints whether the count advanced —
  **the definitive "does the clockevent fire" test**, read back from `__log_buf` over P2A
  (DRAM, which P2A *can* read). This one build settles: (A) clockevent FIRES → the ndo_open
  `usleep_range` hang is a real ndo_open bug, not the timer; (B) DEAD → confirmed timer/VIC,
  and the `pr_warn` shows exactly how the sense/event is misconfigured so we fix it in-driver
  (writable from the ARM side even though P2A is blind).

## ✅ 2026-07-09 ROOT CAUSE CONFIRMED + FIX (ARM-side evidence, not phantom P2A)
Booted a diagnostic kernel (regular 3.4MB image — the 4.1MB shell image is too big for
the flaky P2A load) with two ARM-side probes, read back from `__log_buf`:
- **`FTTMR010-CHECK: timer IRQ count 0 -> 0 after 200ms (clockevent DEAD)`** — a counter in
  the timer ISR, reported from a `late_initcall` after a 200ms busy-wait. The timer
  interrupt genuinely never reaches the CPU. (Console is dead ~from boot, but the kernel
  runs fine — `__log_buf` shows the full boot incl. ndo_open reaching step5 via the udelay
  hack. "started=False" was only a dead-console artifact.)
- **`AST2050-VIC: SENSE=0x0 EVENT=0x0 DUAL=0x0 ENABLE=0x0 RAW=0x0`** — the VIC powers on
  ALL ZERO. The reset-boot has no firmware to configure it.

**Mechanism:** the mainline `irq-aspeed-vic.c` only *reads* SENSE (=0 → `edge_sources=~0`,
all-edge) and never writes EVENT. EVENT=0 selects the **falling** edge for every source.
The AST2050 timer asserts a **rising** edge on match and holds the line high until the ISR
acks it (via `AVIC_EDGE_CLR`); a falling-edge VIC waits for the line to go low, which only
happens *after* the ack — it never latches. Hence the clockevent is dead.

**Fix (in `vic_init_hw`, ARM-side — the ARM CAN write the VIC even though P2A can't):**
program the VIC per datasheet Table 36:
```
SENSE = 0x903897fe   ; level(1): 1-10,12,15,19,20,21,28,31 ; edge(0): 16-18,22-27
EVENT = 0x983f97fe   ; rising/high(1): the level-high sources + timer(16-18) + WDT(27)
DUAL  = 0x07c00000   ; both-edge: RTC 22-26
```
Verify: rebuild + boot, `FTTMR010-CHECK` should flip to **FIRING**, and the boot should
proceed past ndo_open → NFS → userspace with the *unmodified* ftgmac100 (revert the udelay
hack once confirmed).

## The workaround vs the fix
`uImage-kgpe-d16-udelay` swaps `usleep_range`→`udelay` in the ftgmac100 reset path — that
gets ndo_open through, but the net stack + NFS mount still use hrtimers and will hang.
**The real fix is the timer interrupt reaching the VIC**; once it does, the whole boot
(eth0 + NFS + OpenBMC) works with the *unmodified* ftgmac100 driver.

## Reproduce / continue
- Boot `uImage-kgpe-d16-udelay` (fix3 + `udelay` for `usleep_range` in ftgmac100 — a
  DIAGNOSTIC workaround; the net stack + NFS still hang on hrtimers until the timer is
  fixed). `kgpe-flclk.dtb` (fixed-link + UART clock pin). Then
  `rig/nic-diag/logbuf_chunked_host.py` reads the full dmesg over P2A.
- Real fix target: `drivers/clocksource/timer-fttmr010.c` + the DT timer IRQ, so the
  TIMER1 clockevent interrupt fires on the AST2050.
