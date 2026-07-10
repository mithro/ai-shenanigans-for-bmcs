# Hardware validation checklist (the single gated real-AST2050 session)

**Do not touch real hardware without explicit permission.** This checklist is
written *before* any hardware is requested so that, once permission is granted,
**one** session validates every emulation claim at once — the QEMU-vs-silicon
transcript diff that turns "faithful by datasheet" into "faithful, proven".

## Principle

Every `peripherals/<p>/fwtest.c` is built into a **freestanding `.elf`** that runs
**unmodified on QEMU and on real silicon**. The `[FWT]` transcript is deterministic,
so validation = capture the transcript on hardware and **diff it byte-for-byte**
against the QEMU transcript (and the datasheet golden). Any divergence is either a
real silicon fact the model got wrong (fix the model) or a datasheet ambiguity
(update the golden with the citation "real silicon").

## How to run a bare-metal fwtest on the real AST2050

The rig (see project memory: `rpi4-asus-aspeed2050-dev`, culvert P2A, BMC serial
console `/dev/serial-bmc-console`) reaches the BMC over P2A + serial. Three load
paths, in order of preference:

1. **U-Boot `tftp` + `go`** (cleanest, if U-Boot is up over the P2A/TFTP path the
   culvert session established): `tftp 0x40000000 <name>.bin; go 0x40000000`. The
   `[FWT]` lines appear on the BMC UART console. *Note:* real U-Boot has already
   unlocked the SCU and set up DRAM — so `scu.protect` and `sdram.config` reset
   checks read the post-U-Boot state, not cold reset (see per-peripheral notes).
2. **P2A DRAM load + PC redirect** (cold-ish): write the `.elf`'s program bytes to
   DRAM at 0x40000000 over the P2A `vga` window, then vector the ARM to it (the
   SCU70[1:0] freeze-across-reset boot trick from the culvert session). This gives a
   nearer-to-cold state for the lock/strap checks.
3. **JTAG** (`rpi4` OpenOCD wiring) — halt, load to DRAM, set PC, resume; most
   control over reset state.

Capture: `cat /dev/serial-bmc-console` (proven @1200 baud, wiring-swap fixed) into a
per-peripheral log; then `diff` normalised `[FWT]` lines vs the QEMU capture in
`tmp/fwtest/<name>.serial.log`.

## Per-peripheral checklist

For each, confirm the QEMU-green checks reproduce on silicon, and resolve the items
QEMU could not test:

- [ ] **smoke** — `scu.revid == 0x00000202` on silicon (already matches the culvert
      SCU7C=0x202 capture; re-confirm end-to-end through the fwtest path).
- [ ] **scu** — all 8 reset values (SCU04/08/0C/20/24/3C/74 + rev-id). **Plus the
      items QEMU can't test:** (a) **lock-state** — via a *cold* load (path 2/3),
      confirm `SCU00` reads `0` before unlock, `1` after writing `0x1688A8A8`;
      (b) **SCU70 strap** — capture the real strap word and decode `[11:9]` H-PLL
      sel, `[13:12]` CPU:AHB ratio, `[8:6]` MAC mode, `[3:2]` VGA — feed back into
      the machine `hw-strap1` (SCU deferral, task #55); (c) **PLL post-divider** —
      measure the real timer tick / CPU clock to confirm 133 MHz (validates the
      deferred SCU24/20 `[14:12]` model).
- [ ] **vic** — 13 checks. Confirm `sense/dual/event` are writable and read back the
      firmware words `0x903897FE/0x07C00000/0x983F97FE` (already matched to silicon
      in the culvert capture; re-confirm via the fwtest). Optionally assert an actual
      timer IRQ latches with the programmed edge/level config.
- [ ] **sdram** — protect lock-latch (`0xFC600309` → reads 1). **Cold-load** to read
      the true `MCR04` reset (should be `0` before firmware writes it) and `MCR100`
      (`0xA8`); confirm the DDR2 geometry the board actually straps
      (`[3:2]`=cap, `[9:8]`=width, `[11]`=bank). Validates the boot-gated DDR2 model.
- [ ] **timer / uart / wdt / ...** — add rows as each peripheral lands.

## Sign-off

A peripheral is **HW-validated** when its fwtest transcript on silicon equals the
QEMU transcript for every `check`, and any HW-only items above are resolved. Record
the silicon transcript under `peripherals/<p>/golden/hw-<date>.log` and flip the
peripheral's row in `README.md` from ☑ (QEMU-faithful) to ✅ (HW-proven).

**Only request hardware once every peripheral below has its QEMU side ☑** — i.e. all
work that can be done without hardware is complete.
