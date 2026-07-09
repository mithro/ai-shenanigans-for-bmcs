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

## Prime suspects for the fix (next)
1. **Timer VIC line wrong for the G3**: the DT uses the AST2400 timer IRQ (16). The
   AST2050 (G3) VIC may map TIMER1 to a different hwirq → request_irq unmasks the wrong
   line → the timer's real interrupt stays masked. Cross-check vs Raptor's AST2050 timer
   IRQ + the AST2050 datasheet interrupt map. This is the leading candidate.
2. **PCLK rate**: clocksource works (timestamps look right), so tick_rate is ~right — but
   verify the exact PCLK vs the G3 (a small error would still tick, so lower priority).
3. **aspeed count-down match logic** (`set_next_event`, lines 142-160) vs the G3 timer.

## Reproduce / continue
- Boot `uImage-kgpe-d16-udelay` (fix3 + `udelay` for `usleep_range` in ftgmac100 — a
  DIAGNOSTIC workaround; the net stack + NFS still hang on hrtimers until the timer is
  fixed). `kgpe-flclk.dtb` (fixed-link + UART clock pin). Then
  `rig/nic-diag/logbuf_chunked_host.py` reads the full dmesg over P2A.
- Real fix target: `drivers/clocksource/timer-fttmr010.c` + the DT timer IRQ, so the
  TIMER1 clockevent interrupt fires on the AST2050.
