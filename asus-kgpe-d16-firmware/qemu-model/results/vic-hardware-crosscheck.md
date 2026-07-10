# VIC faithfulness — real-silicon cross-check over JTAG (2026-07-11)

The QEMU G3 VIC model (`TYPE_ASPEED_2050_VIC` in `aspeed_vic.c`) was validated
against the **real ASUS KGPE-D16 AST2050 BMC** over JTAG (RPi4 + OpenOCD
`0.12.0+dev`, IDCODE `0x07926f0f`, per [`../../JTAG-USAGE-GUIDE.md`](../../JTAG-USAGE-GUIDE.md)).
Access path: `ssh rpi4 → openocd -f rpi4-jtag.cfg -f kgpe-d16-bmc.cfg`, halt, `mdw`/`mww`.
The stock BMC firmware on this board is dead (never runs meaningfully), so the VIC
holds its **hardware reset values** — exactly what the model's reset path claims.

VIC base **0x1E6C0000**. Sanity anchor: `SCU7C` (0x1e6e207c) read `0x00000202`
over JTAG — matches the P2A/culvert path and the datasheet silicon-rev, proving
the AHB read path is valid.

## 1. Reset values — sense/dual/event reset to 0 (CONFIRMED)

`mdw` of the whole region `0x1e6c0000..0x1e6c00ff`, both as-found and after
`reset halt`, read **all zeros**:

```
### RESET-HALT: VIC region 0x1e6c0000 x64 words ###
0x1e6c0000: 00000000 00000000 00000000 00000000 00000000 00000000 00000000 00000000
0x1e6c0020: 00000000 00000000 00000000 00000000 00000000 00000000 00000000 00000000
... (entire 0x1e6c0000..0xff = 0) ...
### RESET-HALT: VIC trigger-config words (0x24/0x28/0x2c) ###
0x1e6c0024: 00000000 00000000 00000000
```

→ **`sensitivity(0x24)=0`, `both-edge(0x28)=0`, `event(0x2c)=0` at reset.**
The G3 model's `aspeed_vic_reset()` (`s->sense=s->dual_edge=s->event=0` when
`ast2050`) is **faithful**. The stock `aspeed_vic.c` AST2400 path resets these to
`0x1F07FFF8FFFF / 0xF800070000 / 0x5F07FFF8FFFF` (low words `0xfff8ffff /
0x00070000 / 0xfff8ffff`) — **unfaithful** for the AST2050.

## 2. Writability — sense/dual/event are fully RW (CONFIRMED)

Wrote the firmware trigger words, read them back, then restored:

```
### originals (expect 0 0 0) ###
0x1e6c0024: 00000000 00000000 00000000
### wrote 0x903897fe / 0x07c00000 / 0x983f97fe ; readback ###
0x1e6c0024: 903897fe 07c00000 983f97fe        <- writes STICK => fully writable
```

→ **`0x24/0x28/0x2c` are fully writable on real AST2050.** The G3 model (stores
the written word, re-evaluates) is faithful. The AST2400 path treats `0x24/0x28`
as **read-only** and `0x2c` as only-top-4-bits-writable — **unfaithful** for G3.

## 3. Control-register behaviour (CONFIRMED as modelled)

| Reg | Test | Real silicon | Model (`aspeed_vic.c`) | Verdict |
|---|---|---|---|---|
| `enable(0x10)` | write `0xffff` | reads `0xffff` (set) | `s->enable \|= data` (write-1-set) | ✓ |
| `enable(0x10)` | then write `0x0` | **stays `0xffff`** (not cleared) | write-0 is a no-op (OR) | ✓ |
| `enable-clear(0x14)` | write `0xffffffff` | `enable` → `0` | `s->enable &= ~data` | ✓ |
| `status(0x00)` | write `0xffffffff` | **stays** (read-only) | logged read-only | ✓ |

`enable(0x10)` is **write-1-to-set** (a companion `enable-clear(0x14)` clears) —
writing `0` does not clear, exactly as the model's `|=` implements. Hardware was
restored to the as-found all-zero state via `0x14` after the test.

## 4. Consequence for the C4 oracle

This is the crux the earlier revert hinged on. My G3 VIC model matches silicon on
**every** measured point (reset 0, fully RW, write-1-set enable, RO status). The
AST2400 VIC model does **not**. Therefore the previous conclusion — "wiring the G3
VIC breaks the C4 vendor firmware, so keep the AST2400 VIC" — was **treating a
false green as the oracle**: the C4 vendor boot only survived because QEMU's
AST2400 VIC hands the firmware non-zero `sensitivity`/`event` reset values that
the *real* AST2050 does not have (it resets them to 0, and something in the real
boot chain must program them).

The faithful fix is therefore **not** to keep the unfaithful AST2400 VIC. It is to
(a) keep the faithful G3 VIC model, and (b) make the C4 boot harness faithful —
i.e. ensure the vendor VIC-init that runs on real hardware also runs under QEMU
(next: inspect the C4 boot harness to see whether it skips the stage that
programs `0x24/0x28/0x2c`). Tracked under the HW-cross-reference task.

## 5. Why C4 crashed on the G3 VIC — vendor-firmware trace (QEMU, 2026-07-11)

Booted the C4 vendor firmware on the **current AST2400-VIC** model with
`-trace aspeed_vic_write`/`aspeed_vic_read` to see exactly how the vendor C410X
kernel drives the VIC. Over 60 s it:

- **writes the trigger config** — `0x24 sense = 0xfff8ffff` (×10), `0x28 dual =
  0x00070000` (×1), `0x2c event = 0xfff8ffff` (×11). These are the **AST2400
  hardwired values** ("all level except timers 16–18"), *not* the precise AST2050
  Table-36 words (`0x903897fe/0x07c00000/0x983f97fe`). So the vendor kernel *does*
  program the VIC — it just programs the coarse AST2400-style config.
- **hammers the ack path** — reads `0x14` (enable-clear) 28 190×, reads `0x38`
  (edge-clear) 13 341×, writes `0x14` 16 483× and `0x38` 7 492× (hot IRQ handler).

**Consequence.** Because the vendor writes the same values the AST2400 hardwires,
the **steady-state** `sense/dual/event` are identical on both models — so the C4
crash on the faithful G3 VIC is **not** a steady-state trigger-config difference.
The only difference is the **reset transient**: on the G3 model `sense` resets to
`0` (edge) until the vendor programs it, whereas the AST2400 model has `sense`
non-zero (level) from t=0. QEMU's `aspeed_vic_set_irq` only updates `s->raw` on
*line transitions*; it does **not** re-evaluate `raw` when `sense`/`event` change.
So a level-high source asserted-and-static across the `sense: 0→level` write is
never latched into `raw` → its IRQ is lost → the vendor's ftgmac100/SPI-NOR path
waits on that IRQ, times out with a 0 geometry, and divides by zero (`__div0` in
`aess_write_spi_nor_flash` during `ftgmac100_open`).

**Fix applied + tested; root cause NARROWED but not yet pinned.** Made level
sensitivity **combinational** in the G3 model (on a write to `sense(0x24)`/
`event(0x2c)`, re-derive `raw` for level sources from `s->level`) and wired
`TYPE_ASPEED_2050_VIC`. Result: with the G3 VIC, C4 boots to BusyBox `rcS`
(line 151) then **hangs — the main thread stops progressing and the watchdog
resets it at ~16 s** (WDT installed mid-boot, 10 s, `nowayout=1`). What the
investigation **ruled OUT** (each tested, not inferred):

| Hypothesis | Verdict | Evidence |
|---|---|---|
| div0 in `aess_write_spi_nor_flash` is the VIC | ruled out | it's the **unmodelled legacy SMC** (`SPI Flash ID: 0x0`); fires on the AST2400 VIC too, non-fatal — boot continues past it |
| the combinational-level fix causes it | ruled out | disabling the reeval gave **identical** behaviour (line 151, exit 16.6 s) |
| `0x14`/`0x38` read aliases enable / edge-status | ruled out | **JTAG-confirmed**: both read `0` on silicon (the model already matches) |
| irqmap hides a vendor IRQ (lines 32-39 > G3 bank) | ruled out | the AST2400 irqmap maps **every vendor-used device** to Table-36 lines ≤31 (console=10, ETH=2/3, timers=16/17/18, WDT=27, I2C=12); UART2-4/TIMER4-8 on 32-39 exist but the vendor never uses them |
| timer interrupt storm | ruled out | the timer ticks at a **normal** rate; the *main thread* blocks, not an IRQ flood |

**Honest status:** the G3 VIC presents **identical vendor-visible register state**
to the AST2400 VIC (the vendor programs `sense/dual/event = 0xfff8ffff`, matching
the AST2400 hardwired values), yet the vendor's main thread blocks after line 151
(around `waitforaim` / network bring-up) **only** on the G3 VIC.

**gdb probe + vendor symbols (recovered via `vmlinux-to-elf` from the kernel's
kallsyms — 20 318 syms):**
- At the ~13 s hang the CPU is the **idle task**: `start_kernel → rest_init →
  cpu_idle → default_idle → cpu_arm926_do_idle` (WFI). So init/rcS is **sleeping**
  and nothing wakes it — a **lost wakeup**, not a crash.
- **The timer is NOT the cause.** Breakpoints show `asm_do_IRQ →
  aspeed_timer_interrupt → timer_tick` all fire regularly on the G3 VIC → jiffies
  advances, timer-based sleeps would wake.
- **At the hang the only IRQ dispatched to the kernel is IRQ 16 (timer)** — the
  system is fully quiescent. So the blocked task waits on a **non-timer interrupt /
  completion that was dropped *earlier* in boot**, leaving it stuck at the
  `waitforaim` step (line 151→152) that the AST2400 boot passes.

**Narrowed a lot further (still not fully root-caused):**
- **Differential VIC-line trace (G3 vs AST2400).** On the working AST2400 VIC the
  vendor fires IRQ **12 (I2C, 1434×)**, **20 (GPIO, 2634×)**, **15 (PECI, 1×)**; on
  the G3 VIC **none of those ever fire**. But that is a *consequence*: the boot
  blocks in the `aess_*` driver-init chain **before** those drivers get active.
- **Blocking phase pinned.** `rcS → preinit.sh (line 151 = its jffs2 mount of an
  empty MTD) → I_SYS_Drv.sh` which `insmod`s 12 `aess_*` drivers in order. Counting
  `sys_init_module` calls: **9 modules load, then it blocks on the ~9th** (≈
  `aess_pecisensordrv` by rcS order, if there are no earlier loads).
- **Block context (gdb backtraces).** The block sits in the **module-load uevent /
  usermodehelper path**: `sys_init_module → mod_sysfs_setup → kobject_uevent →
  call_usermodehelper_exec → wait_for_completion` (waiting for the spawned hotplug
  helper), alongside a userspace `sys_poll → schedule_timeout`. So the wait is for a
  usermode-helper completion, not a bare device IRQ — deeper and more tangled than a
  single dropped interrupt.

- **Refinement (module disassembly):** `aess_pecisensor_init` just `request_irq`s
  IRQ 15, inits a waitqueue, and creates debugfs nodes — it **returns, it does not
  block**. So the hang is not the PECI init body; per the backtraces it is the
  **module-load `uevent` → `call_usermodehelper_exec` → `wait_for_completion`**
  (waiting for the spawned hotplug helper to finish) around that load. A genuinely
  tangled multi-process interaction (kernel load thread + khelper workqueue + the
  helper process), not a single driver's IRQ wait.

**Still open:** why this module's load + helper never completes on the G3 VIC when
the VIC presents *identical vendor-visible register state* to the AST2400 VIC. Next
step: isolate the *permanent* wait from the transient ones (e.g. break on the
specific completion and check who should `complete()` it), and confirm the exact
`aess_*` module (read its name from the module list) — feasible with the recovered
symbols (`tmp/c4work/vendor-vmlinux.elf`) but a further focused effort. The
diagnostic scripts (`tmp/c4work/*_diag.py`) are saved for resumption. Until solved
the machine keeps the AST2400 VIC (all legacy boots green; C4 PASS); the G3 register
model is hardware-confirmed faithful and the combinational-level fix stays in-tree.
**This corrects the two earlier wrong conclusions — the div0 (SMC, not VIC) and the
irqmap-visibility theory.**

## 6. MAJOR REFRAMING (2026-07-11): it's a watchdog-timing issue, NOT a lost interrupt

Recovered the vendor kernel's symbols (`vmlinux-to-elf`) and, at the G3-VIC hang,
called the kernel's own task dumper from gdb: `set {int}0xc031e7a0 = 8` (raise
`console_loglevel`, found via `do_syslog`'s CONSOLE_LEVEL store) then
`call (void)show_state_filter(0)`. It printed **every task's state + symbolized
backtrace**. Findings that overturn the earlier "blocked in aess driver init":

- **The boot fully PROGRESSES.** All aess modules load; **AIM starts** (pids 400/401),
  `waitforaim` runs (pid 399), shells/init are alive. **No task is in D-state**
  (uninterruptible / device-blocked) — every task is in a normal interruptible sleep
  (`nanosleep`, `sys_poll`, `sys_wait4`). So there is **no dropped-interrupt device
  hang**. `rsyslogd` was momentarily `R` but had used only 1.78 s of 14 s (not hogging).
- **The killer is the watchdog.** WDT trace shows it *is* petted (`@0x8 = 0x4755`, the
  reload magic) a few times, then petting falls behind and the WDT resets at ~16 s.
- **`/sbin/watchdog` is a trivial daemon** (disassembled): `open(/dev/watchdog);
  daemon(); loop { write(fd,1); sleep(5); }` — **no health check, no device/VIC
  access** that could block. It just pets every **5 s** while the WDT heartbeat is
  **10 s** — which should *never* expire.
- **Conclusion: the guest's time runs slow on the G3 VIC.** For a 5 s pet loop to miss
  a 10 s WDT, `sleep(5)` must stretch past 10 s of wall time — i.e. `jiffies` advance
  too slowly, so the whole boot (and every timeout) is slower and the watchdog daemon
  starts/pets too late to beat the wall-clock WDT deadline. The AST2400 VIC boots the
  same firmware because it's slightly faster and the daemon keeps up.

**Measured, and the "jiffies drift" mechanism is REFUTED.** Counting timer IRQs
(line 16) over a fixed 12 s wall window: **AST2400 = 926, G3 = 932** — identical; both
reach the same boot point (116 console lines) in 12 s. So the guest's time is NOT
slow and the boot is NOT slower on the G3 VIC.

**What IS different — the watchdog pet count.** WDT trace over the full boot: the
watchdog is petted (`@0x8 = 0x4755`) **5× on the AST2400 VIC (survives 20 s)** but only
**3× on the G3 VIC (WDT-resets at ~16 s)**. So on the G3 VIC the pets fall behind /
stop a couple seconds early and the 10 s WDT expires. The daemon pets every 5 s and
the timer rate is identical, so this is a **marginal, still-unexplained watchdog-timing
difference** — the boot fully progresses (AIM up, no D-state task) but the WDT wins by
a few seconds on the G3 VIC. Note the trace also shows the driver toggling WDT_CTRL
(0x0c) between 0x16 (disable) and 0x17 (enable) around each pet, so the aspeed_wdt
reload-on-enable behaviour may matter.

**Still open (next session):** timestamp the WDT trace to see exactly when the pets vs
the expiry fall on G3 vs AST2400, and whether it's the daemon starting later, an extra
disable/enable that restarts the count differently, or an aspeed_wdt reload-timing
subtlety. The CONFIRMED, valuable result is the reframing: **the G3-VIC failure is a
watchdog-timing race, NOT a dropped interrupt** — the "IRQ 15/12/20 dispatch" framing
is superseded (those IRQs never happen only because the boot is WDT-reset first).
Tooling: `tmp/c4work/{showstate,logflood,wdt}_diag.py` + the gdb `show_state_filter`
recipe + `console_loglevel@0xc031e7a0`.

## Provenance

- Rig: bridge Pi `rpi4-asus-aspeed2050-dev`, AST2050 over JTAG, 2026-07-11.
- All fenced blocks are verbatim OpenOCD `-c "mdw …/mww …"` output.
- §5 trace blocks are verbatim `-trace aspeed_vic_write` histograms from the C4
  vendor-firmware boot on the AST2400-VIC model.
- Board left in its as-found state (VIC region all-zero; enable cleared via 0x14).
