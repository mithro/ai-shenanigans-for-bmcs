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
