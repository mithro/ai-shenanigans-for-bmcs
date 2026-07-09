# ROOT CAUSE: the AST2050 timer clockevent interrupt never fires (hrtimers hang)

**This is the real blocker behind the "eth0 ndo_open hang" — and it is NOT a NIC bug.**

---
## ✅✅✅ SOLVED (2026-07-09): wrong VIC driver — G3 needs `aspeed,ast2050-vic` @ 0x1e6c0000
The AST2050 interrupt controller is a **compact VIC at 0x1e6c0000** (datasheet §16:
VIC00 STATUS / VIC10 ENABLE / VIC14 ENABLE_CLR / VIC24 SENSE(1=level) / VIC28 DUAL /
VIC2C EVENT(1=high/rising) / VIC38 EDGE_CLEAR), NOT the AST2400 interleaved map at
0x1e6c0080 that mainline `irq-aspeed-vic.c` drives. Wrote a dedicated driver
`drivers/irqchip/irq-aspeed-g3-vic.c` (compatible `aspeed,ast2050-vic`) that programs
sense/event/dual per datasheet Table 36 (timers 16-18 + WDT 27 = edge/rising, RTC 22-26
= both-edge, peripherals = level/high) and ACKs edge sources via VIC38. Enabled via
`select ARM_VIC`… no — via `obj-$(CONFIG_ARCH_ASPEED)` in the irqchip Makefile. DT node
switched to `compatible="aspeed,ast2050-vic" reg=<0x1e6c0000 0x1000>`.

**Verified on the real AST2050** (`uImage-kgpe-d16-g3vic` + `kgpe-g3vic.dtb`):
```
FTTMR010-CHECK: timer IRQ count 274 -> 316 after 200ms (clockevent FIRING)   <- ~1kHz tick
ftgmac100 1e660000.ethernet eth0: Link is Up - 100Mbps/Full
IP-Config: Complete ;  random: crng init done
```
The clockevent fires, hrtimers work, the boot sails past `local_irq_enable`, **eth0 comes
up with real interrupts**, and kernel IP-config completes → the NFS-root mount. Everything
below is the investigation trail that led here.

### Post-fix: NIC hacks reverted + NFS-root userspace
- **ftgmac100 reverted to stock** (kernel commit): the G3 "skip the MAC software reset +
  udelay-instead-of-usleep_range" hack was built on the FALSE premise "any MAC write during
  ndo_open hangs the AHB" — that hang was the dead timer clockevent all along. With the timer
  fixed, the stock MAC reset + usleep_range run fine. **Skipping the MAC reset left eth0 on
  U-Boot's config, which destabilised it under sustained NFS traffic** → a hard hang at the
  NFS-root mount (eth0 stops answering ARP). Restoring the stock reset is the fix (kept only
  the plausible G3 MACCLK-left-at-default tweak). This proves the NIC was never broken.
- **NFS root** (`/srv/nfs/bmc` on the Pi, `no_root_squash,rw`, vers=3/tcp): the modern kernel
  **mounts it and execs init** on a good boot (confirmed: reached `Run /sbin/init` → panic
  "No working init found"). That panic was because the staged busybox is **static-PIE**, which
  fails to exec as a real NFS root on this kernel — swapped in a **plain static (non-PIE)**
  ARMv5 busybox (`.worktrees/d16-qemu/tmp/inspect/bin/busybox`) + added an SSH key to
  `root/.ssh/authorized_keys`; boot with `init=/init` (brings up dropbear on :22).
- **Gating issue = P2A reset-boot flakiness** (NOT the fix): after ~20 boot/kill cycles the
  reset-boot degrades (kernel TFTPs fine but `bootm` never reaches userspace); a power-cycle
  (`tmp/power.py off/on` + `tmp/host_repair.py` to rebuild culvert) clears it. Verify a clean
  boot-to-userspace with `tmp/boot_until_ping.py` (retries the load, stops when the BMC pings
  192.168.66.2), then `ssh -i scratchpad/bmc_key root@192.168.66.2` from the Pi.

### NEW blocker (2026-07-09): eth0 hard-hangs at the NFS-root mount under load
Even the clean-fix kernel (pristine MAC reset) reliably reaches `IP-Config: Complete`
(eth0 works for light BOOTP) then **hard-hangs at the NFS-root mount**: the BMC is
ARP-dead (no ICMP/ARP response — a hard CPU hang, not an I/O wait) and **no NFS mount RPC
ever reaches the Pi** (empty `journalctl -u nfs-server`, mountd never hit). So eth0 dies
the instant the mount's sustained TCP traffic starts. ipconfig keeps the root device open
(no re-open), so it's eth0 RX/TX under load — prime suspect is **ftgmac100 DMA on the
non-coherent ARM926 (VIVT cache, no HW coherency)**: descriptors go stale under sustained
transfer. This is INDEPENDENT of the timer fix (which is solid).
**PATH FORWARD = boot an initramfs (rootfs in RAM, no eth0 needed to mount root)** — gives
a userspace shell to (1) prove the full stack, (2) debug eth0-under-load interactively
(cat /proc/interrupts, ping, then reproduce the NFS hang), (3) run culvert in-band. This is
exactly how the Raptor 2.6.28 chain reached a shell + in-band culvert. Load kernel + a
separate `initrd=<addr>,<size>` raw cpio.gz (bootm won't pass ATAG_INITRD2), `rdinit=/init`.

### ✅ REAL blocker ISOLATED (2026-07-09): eth0 RX DMA corrupts memory → init SIGILL
Instrumented `/init` with `/dev/kmsg` markers + a per-second heartbeat (readable in
`__log_buf`). Result: **the kernel is NOT hanging** — it runs userspace fine, `/init`
prints ~26 heartbeats over ~28s, then **`Kernel panic: Attempted to kill init! exitcode=0x4`
(0x4 = SIGILL)**. Decisive A/B test:
- **eth0 UP** (`ip=...`, Pi ARPs it → sustained RX): init SIGILLs/panics at ~HB 26 (up≈48s).
- **eth0 DOWN** (no `ip=`, no RX): init sails past — **HB 42+ (up≈72s), no panic**, CPU idle.

=> **eth0 RX DMA writes into the wrong memory (init's code → illegal instruction)** on the
non-coherent ARM926 (VIVT cache). The NFS-mount case crashed faster (far heavier RX). The
timer/VIC fix is unrelated and solid. This is now a specific ftgmac100/AST2050 DMA bug:
suspects = a `dma-ranges` / DMA-address translation error (RX desc → wrong phys addr) or a
cache-line-alignment issue in the RX buffers. ftgmac100+ARM926 works on the AST2400, so find
the G3 difference (DT dma-ranges / memory node / the ast2050-mac path). Diagnostic tooling:
`tmp/{boot_diag.py,init-diag}` (heartbeat trace), `tmp/boot_initramfs.py`.

### The initramfs boots — and reveals the REAL remaining blocker (2026-07-09)
Built the hybrid boot path (`linux-boot.py`: `bootm K - D` + `initrd=<RADDR>,<size>` raw
cpio.gz — committed) and an in-RAM rootfs (cpio of `/srv/nfs/bmc`, non-PIE busybox,
`uInitrd-nfsbmc` / raw `initrd-nfsbmc.cpio.gz` on the Pi; size **0x15083a**). On a fresh
rig `__log_buf` shows the full chain working:
```
Unpacking initramfs.....            (SUCCESS — earlier "invalid magic" was a size typo + rig corruption)
IP-Config: Complete ipaddr=192.168.66.2
Freeing unused kernel image (initmem) memory: 1024K
Run /init as init process
```
…then the kernel **HARD-HANGS** (BMC ARP-dead, no route). **This is the SAME hard-hang as
the NFS-root mount** — and `/init` does no heavy I/O — so the blocker is **not** NFS-specific
and **not** heavy-load: it's a hard CPU hang the instant the kernel enters full multitasking
(userspace running + all IRQ sources live). Prime suspects: (a) **ftgmac100 RX DMA on the
non-coherent ARM926** (VIVT cache) corrupting under any sustained RX incl. ARP replies, or
(b) an **interrupt-handling edge case in irq-aspeed-g3-vic under concurrent load** (e.g. a
level source that momentarily fails to clear → `g3vic_handle_irq` spins). NEXT (focused
session, stable rig): get a working interactive console (try `console=ttyS4,1200` matching
the Pi capture, or the `/dev/serial-bmc-console` path) OR add markers in `/init`'s first
lines + the IRQ handlers, read `__log_buf`, to bisect whether the hang is the first eth0 RX
interrupt, a specific /init command, or the g3vic handler. The timer/VIC fix itself is SOLID
and unaffected.
---


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

## 🎯 2026-07-09 TRUE ROOT CAUSE: wrong VIC driver — G3 IC is PL190 @ 0x1e6c0000
Applied the SENSE/EVENT/DUAL config fix and booted — but the ARM-side readback showed
`AST2050-VIC: after cfg SENSE=0x0 EVENT=0x0 DUAL=0x0`: **the writes had no effect**. The
registers at base `0x1e6c0080+0x40/0x48/0x50` are not writable on the AST2050 (and neither
is INT_ENABLE at +0x20 — hence the earlier ENABLE=0). The mainline `irq-aspeed-vic.c` uses
the AST2400's *newer* interleaved register map at `0x1e6c0080` (SENSE/EVENT/DUAL/EDGE); the
**AST2050 (G3) does not have that map**.

The AST2050 IC is at **`0x1e6c0000`** with the classic **ARM PL190 VIC** layout (Raptor
`hwreg.h`): IRQ_STATUS 0x00, FIQ_STATUS 0x04, RAW_INT_STATUS 0x08, IRQ_SELECT 0x0C,
IRQ_ENABLE 0x10, IRQ_CLEAR 0x14, SOFT_INT 0x18, SOFT_INT_CLEAR 0x1C, PROTECT 0x20 — exactly
PL190 (VICIRQSTATUS/…/VICPROTECTION). Raptor's U-Boot `platform.S` already drives it there
(polls Timer3 at `0x1e6c0008`), and `RAPTOR-PORTING-GUIDE.md` §6 says the VIC is at
`0x1e6c0000` — it even flagged the reused-G4-node assumption as unverified ("if they match,
likely"). It does NOT match.

**So the whole aspeed-vic driver writes to registers the G3 lacks → no IRQ is ever enabled
→ the timer (and every) interrupt is dead.** Fix: use the mainline ARM PL190 VIC driver
(`irq-vic.c`, `compatible="arm,pl190-vic"`) at `reg=<0x1e6c0000 0x1000>` instead of
`aspeed,ast2400-vic` @ `0x1e6c0080`. (Earlier "VIC all-zero / EVENT=0 falling-edge" analysis
was a red herring caused by reading the non-existent new-map registers.)

## 🚀 2026-07-09 BREAKTHROUGH: interrupts now reach the CPU (PL190 @ 0x1e6c0000)
Switched the DT to `compatible="arm,pl190-vic"` `reg=<0x1e6c0000 0x1000>` + enabled
`CONFIG_ARM_VIC` (via `select ARM_VIC` on `MACH_ASPEED_G4`). Booted; `__log_buf` shows:
- `VIC @...: id 0x00000000, vendor 0x0000` — the PL190 driver probes (no AMBA ID regs on
  the G3 → "unknown vendor, continuing anyways" → ARM path). Good.
- The boot then hangs **right after `Switching to timer-based delay loop`** — i.e. at
  `local_irq_enable()` in `start_kernel`, the moment the timer IRQ is unmasked. Previously
  (aspeed-vic) the boot sailed to ndo_open. So the timer interrupt **now reaches the CPU** —
  the base 0x1e6c0000 is correct — but it is never **cleared** → an interrupt storm hangs
  the CPU in the ISR.

**How the AST2050 clears a timer interrupt:** Raptor `platform.S` writes **`0x1e6c0038`**
("Clear Timer3 ISR") — an IC-level edge/ISR-clear at `IC_base + 0x38` (it polls the status
at `IC_base + 0x08`). Neither the pure-PL190 `irq-vic.c` (`handle_level_irq`, no ack write)
nor `irq-aspeed-vic.c` (wrong base) performs it. **The AST2050 IC is a HYBRID:** PL190 base
registers (STATUS 0x00, RAW 0x08, ENABLE 0x10, ENABLE_CLR 0x14, SELECT 0x0C ...) PLUS an
aspeed edge-clear at 0x38. Need a small irqchip driver (or an aspeed-vic G3 variant) that
ENABLEs at 0x10, masks via 0x14, and for the fixed edge sources (timers 16-18, RTC 22-26,
WDT 27 — per datasheet Table 36) ACKs by writing `IC_base + 0x38`.

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
