# Device-driver program — running log

## 2026-07-18 — D09 in-kernel sbtsi_temp bind + SB-TSI code-review-clean + audit-2 matrix re-sync

- **D09 in-kernel driver DONE (QEMU):** added `CONFIG_SENSORS_SBTSI=y` to
  kernel/kgpe-d16.config, rebuilt. The real Linux `sbtsi_temp` hwmon driver binds
  the `amd,sbtsi` DT nodes on i2c3 and reads the QEMU model:
  `3-004c/hwmon/.../temp1_input`=45500, `3-004d`=43000. `scripts/sbtsi-test.py`
  rewritten to validate the hwmon sysfs path (the real driver + model together) —
  supersedes the raw-i2cget check (which would now collide with the driver-owned
  device). D9 Linux-QEMU (LQ) + userspace now [x]. Evidence d09-sbtsi/00 appended.
- **SB-TSI model code-review CLEAN (gate b):** sub-agent review of hw/sensor/sbtsi.c
  + wiring found no defects (bounds-checked regs[], correct SMBus/pointer contract,
  arithmetically-correct millidegree→INT/DEC at nominal+max, complete VMState, exact
  RW mask, realize-then-property-set matches the existing tmp423 idiom).
- **Second completeness audit (gate a) ran** — confirmed coverage complete + NO
  fabricated `[x]` (every cited file exists), and found the first-audit fixes were
  applied to FULL-TASK-LIST but **not mirrored into DEVICE-MATRIX**, which had
  drifted (C-1..C-10). Re-synced the matrix: **C-1 NC-SI row 11 LS 🔷→⬜** (the
  weasel the first audit removed, still living in the matrix — hard undone RMII2
  pinmux work, not blocked); C-2 VGA-DAC row 12 QE ✅→🔶; C-3 USB row 9 LS 🔶→🔷 /
  LU ✅→🔶; **C-4 WDT row 38 removed the undefined `❓` symbol → 🔶** + honest note;
  C-5 RTC row 39 LS/LU 🔶→⬜; C-6 SOL row 31 QE/LQ ⬜→🔶; C-7 PCI/VGA Zephyr Ⓝ→⬜;
  C-8 straps row 33 reconciled to E4 (UQ/US/LQ/LS ✅); C-9 VIC/timer ZQ ⬜→🔶 (Zephyr
  drivers written+deliver IRQs); added a header note making **FULL-TASK-LIST.md the
  authoritative per-stack doc** (matrix = summary that defers to it on disagreement).
  Row 23 SB-TSI LQ 🔶→✅.

## 2026-07-18 — completeness audit (sub-agent, gate a) + honesty fixes applied

- Ran a sub-agent completeness audit of FULL-TASK-LIST.md vs the authoritative
  schematic + the real code/evidence state. It verified **every `[x]` cites a
  real file** (no fabricated claims — all QEMU models, scripts, CI jobs, evidence
  dirs exist on disk) and coverage is essentially complete, and flagged honesty
  issues which I FIXED (this is the gate: review finds → fix → re-review):
  1. **A3 SMC silicon was `[N]` — the clearest weaseling.** The SPI/SMC IS the
     board's boot device by design; the flash just isn't populated on this rig.
     Re-classed to `[B]` (rig limitation, fixable by populating BMC_FW1), matching
     DEVICE-MATRIX row 2.
  2. **§11 control OUTPUTS had no explicit row.** Added E5 (CLRTC#/BIOSREVRY#/
     CPU1-2DISABLE#/PCI_RST#/ATXPSON#/SYSRESET#) with its own status boxes.
  3. **B3 video rolled a partial DAC-output into a done `[x]`.** Split into B3
     (CAPTURE path — genuinely both-sides PASS) and B3b (DAC output/mode-set/
     PCI-target — `[~]`, self-questioned).
  4. **D9 SB-TSI silicon `[B]` was a weak block** (the rig CAN power the host).
     Re-classed to `[ ]` (achievable, not-done-yet). Same for C2 NC-SI and F2 SOL:
     re-classed the "hard authoring work" parts from `[B]` to `[ ]` (my code to
     write — RMII2 pinmux RE / QU8 mux / registerSOLService — not external blocks).
  5. **D8 TSOD `[x]`** clarified: the jc42 model is complete but deliberately
     not-placed (faithful to this rig's TSOD-less DIMM).
  6. **Coverage assertion** now names the host chips SU1/OU1/NU1 (reached through
     the controller rows, not BMC-internal).
  7. **DEVICE-MATRIX drift fixed:** W83601G rows 21/22 had `LQ=⬜` while `LS/LU=✅`
     (contradiction) and a stale "LED-drive-on-silicon pending" note though it was
     done — reconciled (LQ/LS/LU all ✅ via userspace; note now says both-sides
     done). Row 23 SB-TSI updated to QE=✅/LU=✅/LQ=🔶.
- Next: re-run the completeness audit to confirm the fixes leave nothing flagged
  (the gate wants MULTIPLE clean reviews).

## 2026-07-18 — D09 SB-TSI CPU thermal: faithful QEMU model + validation (QEMU PASS)

- `hw/sensor/sbtsi.c` — AMD SB-TSI processor thermal sensor, register file
  matching the Linux `sbtsi_temp` driver (TEMP_INT 0x01, STATUS 0x02, CONFIG
  0x03, hi/lo-limit 0x07/0x08/0x13/0x14, TEMP_DEC 0x10 bits[7:5]=0.125C); a
  `temperature` QOM property (millidegrees) drives TEMP_INT/TEMP_DEC. Wired P0
  @0x4c (45.5C) + P1 @0x4d (43.0C) on the machine's i2c bus 3 (DT i2c3 =
  schematic I2C4). DTS `&i2c3` enabled with `amd,sbtsi` nodes; DTB rebuilt.
- `scripts/sbtsi-test.py` boots kgpe-d16-bmc and reads both sensors over Linux
  i2c-3 via raw SMBus: **8/8 PASS** (int/dec temps for both sockets, CONFIG/
  STATUS resets, RW-limit accepts a write, RO TEMP_INT rejects one). Evidence
  `evidence/d09-sbtsi/00-qemu-pass.txt`; CI job `boot-sbtsi` added.
- FULL-TASK-LIST D9: QEMU [x], Linux userspace(raw) [x]; in-kernel sbtsi_temp
  bind needs CONFIG_SENSORS_SBTSI (kernel rebuild, TODO); silicon [B]
  host-CPU-power-dependent (SB-TSI *is* the AMD processor interface). QEMU
  submodule 512d56d217.

## 2026-07-18 — complete schematic read + formal per-device/per-stack task list

- Read the **complete** `AST2050-BMC-WIRING.md` end-to-end again (all 597 lines,
  §§1–16: block diagram, power, DDR2, SPI, LPC, PCI, Ethernet, VGA, USB, the full
  §10 I²C device-by-device breakdown + mux fabric + bus-assignment tables, GPIO
  power/reset, Serial/SOL, JTAG/LED/clock/strap, neighbour chips, connectors,
  per-pin table).
- Created **FULL-TASK-LIST.md** — the formal task list in the exact required
  structure: for EVERY device/function block a task for {QEMU emulation; U-Boot
  driver → validate QEMU + silicon; Linux driver → validate QEMU + silicon +
  userspace; Zephyr driver → validate QEMU + silicon}, each box marked with an
  honest status (`[x]` done+evidenced / `[~]` partial / `[ ]` todo / `[N]` N/A
  WITH reason / `[B]` blocked WITH the precise blocker + confidence). Rows A1–A8
  (core SoC), B1–B5 (host interfaces), C1–C2 (Ethernet), D1–D13 (I²C + on-bus),
  E1–E4 (GPIO/LED/strap), F1–F2 (serial/SOL), G1 (JTAG harness). Ends with a
  §-by-§ coverage assertion proving nothing in the schematic is skipped.
- This supersedes the loose "honestly remaining" prose from the prior cycle with
  the required formal structure; DEVICE-MATRIX.md remains the compact grid view.

## 2026-07-18 — silicon I2C inventory + an unidentified 0x69 responder

- Silicon i2c buses present: i2c-1 (W83795 engine, schematic I2C2), i2c-4 (I2C5:
  FRU + W83601G), and the QU5 mux children i2c-14/15/16 — same as QEMU. The other
  schematic engines (I2C1/I2C4→SB-TSI, I2C7→SALT, etc.) are not DT-enabled yet.
- `i2cdetect -y -r` on the mux children shows the W83795 (0x2f, UU=driver-bound)
  AND a device at **0x69** on all three channels (so both are on the shared
  sensor segment past QU5; the mux itself is proven-switching by the SPD test,
  evidence d08-spd-silicon). 0x69 answers a read of reg 0x00 = 0x08 but NAKs regs
  0xfe/0x4f/0x58 → a simple/limited responder, NOT a bank-switched register file.
- **0x69 is NOT in the authoritative schematic §10 I2C table** (which lists only
  W83795G@0x2F on this segment). Candidates: a clock/aux device, a W83795 alias,
  or an i2cdetect artifact. Logged as an open completeness item to identify
  (needs the schematic's sensor-bus sub-detail or a scope) — low priority, weak
  responder; not claiming it as a modeled device.

## 2026-07-18 — origin/main merge check

- `git fetch origin` + `git merge --no-ff origin/main` → **"Already up to date"**.
  origin/main tip `85bd82a` (PR #29 schematic-wiring) is an ANCESTOR of the
  working branch HEAD (`git merge-base --is-ancestor origin/main HEAD` = yes);
  the branch is 378 commits ahead / 0 behind. So the authoritative schematic
  `AST2050-BMC-WIRING.md` that DEVICE-MATRIX.md is verified against IS the latest
  main. Nothing to integrate.

## 2026-07-18 — D14 Zephyr RUNS AN APPLICATION ("Hello World") + M1 VIC/timer 🎉

- The AST2050 Zephyr port now **boots and runs application code** under QEMU:
  `*** Booting Zephyr OS ***` + `Hello World! kgpe_d16_bmc/ast2050`. The kernel
  reaches and runs the sample's main(). Evidence `evidence/d14-zephyr/03`.
- **Faithfulness win (my instinct was right):** I had *wrongly* concluded the
  boot "hangs before main() → upstream ARM9 core bug." A `-d exec` trace proved
  the kernel actually reaches z_thread_entry → bg_thread_main → main() → idle
  cleanly. The real bug was MINE: the sample uses printf() (stdout) but the SoC
  console only hooked printk, so main()'s output went nowhere. Fix = also
  `__stdout_hook_install(ast2050_console_out)` in console.c. Never blame the
  hardware/upstream while my own code is in the loop.
- **M1 VIC + system timer written** (soc/aspeed/ast2050/vic.c real G3 VIC at
  0x1e6c0000 using the Linux irq-aspeed-g3-vic SENSE/DUAL/EVENT constants;
  aspeed_timer.c tickful Timer1 @ 1 MHz, VIC src 16). With SYS_CLOCK=y the timer
  DELIVERS interrupts through the cortex_a_r isr_wrapper and the app still prints
  Hello World — but sustained ticking then data-aborts at the arm_mmu L1 table
  (0x40008ffc), the SAME brand-new-ARM9 arm_mmu dynamic-mapping breakage that
  forced the static M0 console (now via timer-driven thread-switch page-table
  updates). So SYS_CLOCK left OFF by default (clean cooperative Hello World, no
  crash); timer/VIC code committed + re-armed once the upstream arm_mmu is fixed.
- Matrix row 30 ZQ = 🔶 now means a RUNNING APP, not just a banner.

## 2026-07-18 — D14 Zephyr M0 BANNER RUNS in QEMU 🎉

- The AST2050 Zephyr port now **boots and prints** under `qemu-system-arm -M
  kgpe-d16-bmc`: `*** Booting Zephyr OS build v4.4.0-8379-g0a6208b97bff ***`.
  The canonical Zephyr proof-of-life — reset vector → ARM926 arch init → MMU
  enable → C runtime → kernel init → console all work. Evidence
  `evidence/d14-zephyr/02-m0-banner-RUNS.txt`.
- Root cause of the old blocker was TWO stacked bugs (both mine): (1) the
  ns16550 CONFIG_MMU DEVICE_MMIO_MAP z_phys_map path is broken on the brand-new
  ARM9 arm_mmu (resolves the UART VA to 0x1e7ff000, not 0x1e784000); (2) my
  first console workaround used 32-bit UART accesses where QEMU's serial_mm
  (regshift=2) needs BYTE accesses. Fix = a SoC polling console
  (`soc/aspeed/ast2050/console.c`) writing UART5 at its physical address via a
  STATIC identity MMU region in soc.c, byte-wide, installed as the printk hook
  with CONFIG_UART_CONSOLE=n so the broken ns16550 poll_out never runs.
- Diagnostic technique worth keeping: write marker values to a deliberately
  UNIMPLEMENTED SFR (0x1e7ff0f0/f4) so QEMU `-d unimp` surfaces them — proved the
  printk hook WAS called with the banner text and that the LSR read returned the
  real UART's 0x60, separating "hook called?" from "write lands?".
- Honest boundary: only the banner prints, not hello_world's "Hello World!" —
  the app thread is blocked by the absent system timer (SYS_CLOCK_EXISTS=n).
  That is M1 (the aspeed timer driver), the documented next step. Matrix row 30
  ZQ → 🔶; the Zephyr column is no longer "entirely pending" — the port RUNS.

## 2026-07-18 — D08 W83601G: BOTH-SIDES done (silicon LED-drive + datasheet fix)

- Silicon reset-default reads (U27 @0x18) match the datasheet AND the model
  exactly: CR20=0x60, CR02=0xf0, CR03=0xff, CR09=0x00, CR0A=0x70, CR0B=0x7f.
- **Silicon resolved a datasheet inconsistency**: CR21 (chip-ID low) reads
  **0x13** on silicon, not the §7.1-table 0x12 (the §7.2 text's 0x13 is right).
  Per "QEMU models real hardware", set the model's `W83601G_ID_LOW` = 0x13 and
  the test expectation to 0x13; QEMU re-run still PASS.
- **Silicon LED-drive path proven on BOTH expanders** (the exact BMC DIMM-error-
  LED sequence, live over i2c-4, fully reversible):
    U27 @0x18: CR03=0xfe, CR01=0x01 -> readback DRV03=0xfe DRV01=0x01 -> restore.
    U28 @0x19: same -> DRV03=0xfe DRV01=0x01 -> restore.
  The write takes effect on real hardware (readback-confirmed) and restores to
  reset defaults. Evidence `evidence/d08-w83601g/03-silicon-both-sides.txt`.
- Matrix rows 21/22: LS ✅ (silicon LED-drive), QE ✅, LU ✅. D08 W83601G is
  fully both-sides (QEMU + silicon) for both expanders. QEMU submodule updated.

## 2026-07-18 — D08 W83601G: faithful QEMU model + validation (QEMU PASS)

- Obtained the official Nuvoton W83601G datasheet V1.31 (register map in
  `evidence/d08-w83601g/01-datasheet-register-map.md`); it cross-checks the
  silicon capture (CR01 reset 0x00 == the `0x18 reg01` I read), so the part is
  confirmed and can be modelled faithfully rather than guessed.
- Wrote `hw/gpio/w83601g.c` — a datasheet-faithful SMBus GPIO-expander: full
  CR00-CR21 file, correct resets (out 0x00, iocfg all-input 0xff/0x7f, polarity
  0xf0/0x70, ID 0x60/0x12), read-only + reserved(open-bus 0xff) semantics, and a
  per-instance `port1-input` seeded from silicon. Wired both U27/U28 on the
  machine's I2C5 (bus 4) at 0x18/0x19 (inputs 0x0f / 0xb5).
- Bug found + fixed during bring-up (honest note): the 34-register file (0x22)
  is NOT a power of two, so the `& (NR_REGS-1)` pointer mask I copied from the
  8-register jc42 model aliased CR02->CR00 (QEMU test caught it: CR02 read 0x0f
  instead of 0xf0). Replaced with an explicit range check; pointer is a plain
  uint8_t wrapping mod 256 like the hardware.
- `scripts/w83601g-test.py` boots kgpe-d16-bmc and drives both expanders over
  Linux i2c-4 exactly as firmware does (raw SMBus, no driver): **19/19 assertions
  PASS**, including the DIMM-error-LED sequence (CR03 output-enable -> CR01 drive
  -> readback -> clear) and the Port-2 CR0B/CR09 path. Evidence
  `evidence/d08-w83601g/02-qemu-pass.txt`; CI job `boot-w83601g` added.
- Also had to rebuild the KGPE-D16 DTB: the cached `kernel/out` dtb was stale and
  did not enable `&i2c4`, so Linux never registered the I2C5 adapter. Rebuilt
  from the current DTS (`make dtbs`) — i2c-4 now enumerates.
- Matrix rows 21/22: QE ✅, LU ✅ (raw userspace), LS 🔶 (silicon reach proven;
  LED-drive-on-silicon next). QEMU submodule commit d0556622ed.

## 2026-07-18 — D08 W83601G DIMM-LED expanders characterized on silicon

- Read the two W83601G I2C GPIO expanders (U27/U28, §10.2 DIMM-error-LED
  drivers) live on the BMC's I2C5 engine (Linux i2c-4), read-only:
  `0x18` reg0=`0x0f` reg1=`0x00` reg7=`0xff`; `0x19` reg0=`0xb5`. Both are
  **present and register-readable by the BMC** — the schematic wiring is
  confirmed on real silicon and the BMC's DIMM-LED expander access path works.
  Evidence: `evidence/d08-w83601g/00-silicon-present.txt`.
- Matrix rows 21/22 moved ⬜→🔶 (LS/Linux-silicon partial): silicon reach
  proven, but a **faithful QEMU model + full LED bit-map** needs the Winbond
  W83601G datasheet (register semantics: direction vs. output vs. GP10-GP26),
  which is **not in-repo** (unlike the W83795G/W83667HG datasheets). Honestly
  left as an open D08 item (task #135) — NOT claimed done, since "all
  functionality" requires the datasheet-backed register map to model the LED
  drive faithfully. Next: locate the W83601G datasheet (try the 15h.org
  mirror / Winbond archives), then write the QEMU expander model seeded with
  the observed defaults and validate LED-drive on silicon.

## 2026-07-18 — fresh complete read of AST2050-BMC-WIRING.md + task-list verification

- Re-merged origin/main (up to date). Read the **complete** authoritative
  schematic doc end-to-end (all 597 lines, §§1–16) and did a deliberate
  section-by-section cross-check of every function block, the §14
  neighbour-chip table, and the §15 connector list against DEVICE-MATRIX.md.
- Appended a "Completeness verification" table to DEVICE-MATRIX.md mapping
  every doc section → matrix rows, and explicitly justifying the only
  spec elements without their own driver row: passive power/glue (LDOs,
  series-R nets, FET switches/buffers — modeled where behaviour-relevant, e.g.
  the QU9/QU5/U23 fabric device), the JTAG header (silicon test harness, Ⓝ),
  and the host chips SU1/OU1/NU1 (reached via the LPC/PCI/I²C rows, not
  BMC-internal). **Verdict: the 40-row matrix is comprehensive against the
  authoritative schematic — nothing skipped.** This is the fresh-read +
  task-list-creation deliverable.

## 2026-07-18 — D08 FRU EEPROM done both sides; W83601G located on silicon

- Enabled I2C5 (i2c-4) in the DTS + added the FRU node (at24 24c08 @0x54).
  Rebuilt the realhw kernel, JTAG-booted on silicon, and **read the real board
  FRU**: U25 is present + at24-bindable across 0x54-0x57 (1 KB 24c08) but
  **BLANK (0xff)** — ASUS shipped it unprogrammed. The BMC's I2C5 FRU path
  works; E2 strap high confirms the 0x54 base (§10.2's 0x50-0x53 was wrong).
  `evidence/d08-fru/`.
- **Bonus**: `i2cdetect -y -r 4` also shows 0x18/0x19 responding = the two
  W83601G DIMM-LED expanders (U27/U28) on I2C5 — the next D08 sub-device,
  now reachable (bus enabled).
- Modeled the FRU faithfully in QEMU (blank 24c08 at 0x54-0x57 on i2c bus 4);
  qtree confirms, integration suite 114/114. DEVICE-MATRIX FRU row → ✅ both
  sides. A tractable break from the Zephyr banner that closed a real audit
  gap (#4) with a silicon read.

## 2026-07-18 — D14 Zephyr M0 BUILD SUCCEEDS (run/banner debug pending)

- Iterated the Zephyr AST2050 port to a **successful build+link** of
  `hello_world` for `kgpe_d16_bmc` (RAM 136 KB / 64 MB, zephyr.elf entry
  0x40002068, -mcpu=arm926ej-s). Evidence `evidence/d14-zephyr/01-...`.
- Bring-up sequence (each a small, real fix — the port structure was sound):
  1. Board recognized (`qualifiers: ast2050`) — SoC/board/module files valid.
  2. Fixed the SDK-1.0-vs-0.17 gate by using the 0.17 arm-zephyr-eabi as a
     cross-compiler (`ZEPHYR_TOOLCHAIN_VARIANT=cross-compile`).
  3. DTS compiled clean (zephyr.dts generated).
  4. Added `soc/aspeed/Kconfig` (the missing family arch selects: ARM,
     CPU_ARM926EJ_S, ARM_CUSTOM_INTERRUPT_CONTROLLER, MMU, ATOMIC_OPERATIONS_C
     — mirrors sam9's `Kconfig`).
  5. Added a SYS_CLOCK_HW_CYCLES_PER_SEC default (24 MHz).
  6. Provided the SoC glue the linker needed: `vic.c` (M0 stubs for
     z_soc_irq_*), `soc_reset_hook`, and `SYS_CLOCK_EXISTS=n` for M0.
  → links cleanly.
- **RUN**: `qemu -M kgpe-d16-bmc -kernel zephyr.elf` gives NO banner yet — the
  kernel hangs in early boot before console. Confidence HIGH it is a
  bring-up/config detail (MMU-enable / CP15 path), NOT the port or hardware:
  the fwtests link at the same 0x40000000 and print to the same UART5, so the
  load addr + UART are proven-good. Next: `qemu -d int,mmu,cpu_reset` to find
  the early fault → banner completes M0.
- **This is the milestone that was the real risk** (brand-new upstream ARMv5
  support + a from-scratch SoC/board port). Zephyr for the AST2050 now BUILDS.
  The Zephyr column in DEVICE-MATRIX.md stays ⬜ (honestly) until the banner
  runs.

## 2026-07-18 — D14 Zephyr port: real foundation files authored + committed

- Fetched upstream PR #103557 (the ARM926 arch core + sam9x7/sam9x75_curiosity
  precedent) and read every template file (soc.yml, Kconfig.soc/defconfig,
  soc.c/h, CMakeLists, board.yml/dts/defconfig/yaml, armv5.dtsi).
- **Authored the real AST2050 Zephyr port** (16 files, `asus-kgpe-d16-firmware/
  zephyr/`) modeled precisely on that precedent: an out-of-tree module
  (`zephyr/module.yml`), the SoC (`soc/aspeed/ast2050/` — Kconfig selects
  `CPU_ARM926EJ_S`, reuses the cortex_a_r linker, minimal MMU map covering the
  0x1e600000 APB window + vectors, `soc_early_init` no-op since the loader
  brings up DRAM/console), the SoC DTSI (`dts/aspeed/ast2050.dtsi` — arm926ej-s
  cpu, 64 MB memory@40000000, ns16550 serial@1e784000), and the board
  (`boards/aspeed/kgpe_d16_bmc/` — chosen console/sram, 115200). The ARM9 arch
  core comes from upstream; this module is only the SoC+board. PORT-PLAN.md
  records the approach + milestone ladder. Committed `a480a99`.
- **M0 build environment being set up**: west workspace initialized on the PR
  branch; SDK `/home/tim/zephyr-sdk-0.17.0` (arm-zephyr-eabi); `west update`
  of the essential modules running. Next: `west build -b kgpe_d16_bmc
  samples/hello_world` → banner under the repo's faithful QEMU AST2050.
- Honest state: the port FILES are real + committed, but no Zephyr build has
  succeeded yet — the whole Zephyr column in DEVICE-MATRIX.md stays ⬜ until
  M0 (hello_world banner) actually runs. This is a genuine start on the
  biggest gap, not a claim of completion.

## 2026-07-18 — explicit per-device task matrix created (DEVICE-MATRIX.md)

- Re-merged origin/main (already up to date). Re-read the authoritative
  wiring doc §§2–15 fresh and enumerated **every device** (40 rows incl. the
  §14 neighbour chips + SoC-internal peripherals) into a new
  **DEVICE-MATRIX.md** — an explicit grid with the exact deliverable columns
  the goal demands: QEMU / U-Boot(QEMU,silicon) / Linux(QEMU,silicon,
  userspace) / Zephyr(QEMU,silicon). Each cell carries the honest current
  status (reflecting the completeness audit — USB-Si scoped, NC-SI-Si 🔷
  blocked, WDT-Si uncited, 6 I2C far-ends absent, SOL/DDC/mailbox ⬜, whole
  Zephyr column ⬜). TASKLIST now points to it as the authoritative checklist.
- This makes the per-device coverage inspectable at a glance and is the
  master checklist for the remaining work.

## 2026-07-18 — D07 silicon NC-SI attempt 2 FAIL; deep G3-pinmux diagnosis; BREAK

- Added the RMII2 pinctrl to mac1 + rebuilt + re-tested on silicon → STILL
  "No channel found to configure!". Read the g4 pinctrl source and found the
  REAL blocker: **the AST2050 (G3) RMII2 pinmux is fundamentally different
  from the AST2400 (G4)** and mainline's aspeed-g4 pinctrl can't route it:
  - `RMII2_DESC = SIG_DESC_BIT(HW_STRAP1, 7, 0)` gates RMII2 on SCU70[7]==0
    (G4 semantics); on the G3, strap 110 has bit7=1 → g4 pinctrl thinks RMII2
    is off (same class as the patch-0008 GPIOF5 bug, deeper).
  - the g4 RMII2 pins (D9/A10/B10/C9/A9/E8/D8, GPIOT/V group) are the G4's;
    the G3's RMII2 balls are A5/B5/B6/C4/D4/D5 = the **GPIOE group**.
  - empirically set SCU74[27]=1 on the live board → still no channel, so that
    single bit isn't the enable. Restored SCU74.
  - Confidence HIGH this is config/RE, not hardware (NVMs are NC-SI-enabled).
  Evidence `evidence/d07-ncsi/03-...`.
- **Taking a break from NC-SI silicon** (per the "get stuck → work elsewhere"
  guidance). It needs the AST2050 datasheet's exact RMII2/GPIOE routing for
  strap=110 + a G3 pinctrl group — a focused follow-up. NC-SI is validated in
  QEMU; the NICs are confirmed enabled; the silicon step is well-characterized
  and open. Bug #4 (RMII2 pinmux) was mine; the deeper G3-pinmux gap is a real
  mainline limitation, honestly documented.

## 2026-07-18 — D07 silicon NC-SI attempt 1 FAILED (my missing RMII2 pinmux)

- Ran BMC-side NC-SI discovery on real silicon (addresses audit #3). Booted
  the NET_NCSI realhw kernel with mac1 enabled (`kgpe-ncsi.dtb`). eth1 bound
  `Using NCSI interface`, but `ip link set eth1 up` →
  **`NCSI: No channel found to configure!`** + `Wrong NCSI state 0x100`. The
  real 82574Ls did NOT respond.
- **Root cause = MY DTS, not the hardware** (the principle holds). The
  mainline aspeed-g4 `mac1` node has NO `pinctrl-0`, so the RMII2 data pins
  (GPIOE group, §7 balls A5/B5/B6/C4/D4/D5) were never muxed to the RMII2
  function → NC-SI frames never physically reached the NICs. The g4 pinctrl
  HAS the group (`pinctrl_rmii2_default`) and SCU70[8:6]=110 strap-enables
  RMII2 — the node just never referenced it. Confidence HIGH this is the
  bug (not a hardware issue): the NVMs are confirmed NC-SI-enabled.
- **Fix**: added `pinctrl-0 = <&pinctrl_rmii2_default>` to `&mac1`. Rebuilding
  realhw kernel; will re-test on silicon. Honest failure captured in
  `evidence/d07-ncsi/02-silicon-discovery-attempt1-FAIL-pinmux.txt`. This is
  my bug #4 this session (all four: console baud, cross-worktree stale
  artifact, test string compare, now the RMII2 pinmux) — the hardware has
  been correct every time.

## 2026-07-18 — completeness audit + Zephyr feasibility; honesty fixes

- **Completeness audit (skeptical sub-agent)** — key findings ACTED ON:
  - SILICON-STATUS row #5 still said "no DIMM SPDs / unreachable by BMC"
    (contradicted its own D08 banner) → FIXED to ✅/✅ with honest scope.
  - SILICON-STATUS row #9 said NC-SI "implementation not started" (stale) →
    FIXED to reflect D07 QEMU pass + the honest silicon caveat.
  - Header date "2026-07-16" stale → bumped to 2026-07-18.
  - D07 evidence file `01-silicon-82574L-nvm-...` renamed to
    `01-host-ethtool-82574L-nvm-...` — it's a HOST ethtool NVM dump, NOT a
    BMC-side silicon discovery (the audit rightly flagged the name as
    inviting miscount).
  - D02 U-Boot SPI was understated ⬜ → the Raptor U-Boot QEMU log shows
    `Flash: SPI Flash ID` working → marked ✅ QEMU.
  - D02 SPI silicon "Ⓝ" corrected to "rig-blocked" (socket populated by
    design; empty only on this bench — not n/a).
  - D11 WDT-silicon "✅ 120 s reset observed" has NO evidence transcript →
    marked UNCITED pending a captured reset log.
  - Audit's honest scope reminders recorded: D05 USB-silicon = usbip-vudc
    (not the real vhub datapath); D08 SPD-silicon select-drive came from the
    SP5100 (data path proven, BMC-owns-fabric not); NC-SI-silicon not run.
  - Real functional gaps confirmed: SOL end-to-end, LPC mailbox/snoop/vUART,
    5 D08 far-end I2C devices, DDC/EDID, MTD write path, and the whole
    Zephyr column.
- **Zephyr feasibility (research sub-agent) — BREAKTHROUGH:** Zephyr now has
  ARM926EJ-S (ARMv5TEJ) support from Microchip's SAM9X7 work — scaffolding
  merged in `main` (PR #101016), arch core (~770 LOC) in open PR #103557, and
  the existing `uart_ns16550.c` fits the AST2050 UART. So D14 is a tractable
  SoC/board port (reuse the ARM9 core), not a from-scratch arch port.
  Smallest milestone: `hello_world` banner under the faithful QEMU AST2050.
  TASKLIST D14 rewritten with the concrete milestone ladder.

## 2026-07-18 — D15/U-Boot reframed HONESTLY: Raptor U-Boot meets the requirement

- Re-merged origin/main (already up to date — merged at start via a981389;
  main tip 85bd82a unchanged).
- **Built the Raptor AST2050 U-Boot from source** (vintage gcc-4.9.4, fetched
  by build-raptor-uboot.sh) and **booted it first-hand in QEMU** with the
  faithful G3 SCU (`g3-resets=on`): `DRAM Init-DDR` → `U-Boot 2013.07` →
  `DRAM: 64 MiB` → `aspeednic#0: PHY at 0x20` → `boot#`. Its OWN AST2050 DDR2
  init runs against the faithful SDMC model. Evidence `evidence/d15-uboot/`.
- **Correction to my earlier "U-Boot column is empty" claim:** a proper,
  working U-Boot with a real AST2050 board port (`board/aspeed/ast2050/`,
  drivers libserial/libnet/libi2c/libgpio/libspi_flash) ALREADY EXISTS and is
  validated BOTH sides for boot-critical devices — QEMU (this build + CI
  `boot-uboot-scu`) and silicon (the `boot#` I JTAG-netbooted from this
  session for D07/D08). So the "proper U-Boot driver, validated QEMU+silicon"
  requirement is MET for D01(ram)/D06(net)/D10(serial)/D02(spi). U-Boot has no
  runtime need for the non-boot blocks. **D15 "modern U-Boot" is an
  ENHANCEMENT, not a functional gap.** TASKLIST updated to reflect this.
- Consequence: the ONLY true greenfield column left is **Zephyr (D14)** — no
  code exists. That's the next focus.

## 2026-07-18 — code review of D07/D08 QEMU code (1 issue found + fixed)

- Dispatched a code-review sub-agent over all new C: `kgpe_d16_i2c_fabric.c`,
  `jc42.c`, the `aspeed_gpio.c` kgpe outputs, the `aspeed.c` fabric/strap/SPD/
  MAC2 changes, and kernel patch 0008. Verdict: **all clean except ONE Medium**:
  `kgpe_d16_host_on` (host-power latch) was absent from VMState and not
  re-synced on reset → after loadvm/migration (or transiently after a warm
  reset) the next GPIO write could clobber the GPIOH2 power bit back to "off".
- **Fixed**: `VMSTATE_BOOL_V(kgpe_d16_host_on, …, 2)` + reset re-syncs GPIOH2
  and the board-glue outputs from the persisted latch (the latch is board
  glue, outside the BMC GPIO reset domain). Verified `qemu_set_irq` is
  NULL-safe so the reset-time output drive is safe regardless of connect
  order. Integration 114/114 after the fix. The reviewer verified jc42's
  word-swapped register logic, the fabric's bounded channel select + VMState,
  the pinctrl patch's enable-path-untouched skip, and the SPD array (256 bytes,
  CRC bytes, g_memdup2 ownership) all correct; build wiring (Kconfig/meson) OK.

## 2026-07-18 — D07 NC-SI Phase 1: Linux stack validated in QEMU

- **`NCSI RESULT: PASS`** — the kernel's net/ncsi discovered + configured a
  channel on eth1 (MAC2/0x1e680000) and brought carrier up:
  `ftgmac100 1e680000.ethernet: Using NCSI interface` →
  `NCSI: ... configuring channel 0` → carrier=1. Evidence
  `evidence/d07-ncsi/`, CI job `boot-ncsi`.
- Changes: kgpe-d16-bmc now wires BOTH MACs (`macs_mask=MAC0|MAC1`, faithful
  to schematic §7 — MAC1 unpeered unless a 2nd -nic is given, so oracles are
  safe); kernel +CONFIG_NET_NCSI +NCSI_OEM_CMD_{GET_MAC,KEEP_PHY}; QEMU DTS
  gains a `&mac1 { use-ncsi; status="disabled" }` node (test enables it via
  fdtput + runs QEMU with a 2nd slirp NIC that answers NC-SI).
- **Regression clean:** C2 SSH boot still PASS; integration 114/114.
- Honest scope: Phase 1 proves the LINUX NC-SI software path against the
  generic slirp responder (returns MFR-ID 0x0). Phase 2 = a faithful 82574L
  responder (2 packages, Intel OEM mfr 0x157 cmds 0x06/0x20) — belongs in the
  MAC model since libslirp is an external subproject. Silicon needs the ASUS
  NIC NVMs to have NC-SI (MNGM) enabled — open question, checkable via
  `ethtool -e` on the host NICs.

## 2026-07-18 — 🎉 D08: BMC read the REAL DIMM SPD on silicon

- **The BMC's at24 read the real 256-byte SPD** over I2C2 → QU9 → QU5-Y2 →
  DIMM 0x51: `at24 15-0051: 256 byte 24c02 EEPROM`, part `RMR5030EF68F9W1600`,
  serial 420B469C (== host `dmidecode -t 17`), CRC-16 0xf0b4 verified. The
  formerly-"impossible" #5 DIMM inventory is REAL. Evidence:
  `evidence/d08-spd-silicon/`.
- **Full diagnosis chain** (every step is my code/driving, never the hardware):
  1. patch 0008 makes the mux driver load on silicon (3 adapters).
  2. GPIO dump proved the BMC drives the correct Y2 selects; QU9 closed.
  3. But 0x51 didn't ACK → the physical QU5 selects weren't at Y2.
  4. Root cause A: the mux **floats/parks at a non-DIMM bank at idle** —
     measured SP5100 reg 0x54=0x0707 = selects at Y1 (unconnected). Even the
     HOST's decode-dimms found nothing at idle → NOT a dead chip, it's the mux.
  5. Root cause B: **U23 arbitration gives the SP5100 select-ownership** on
     this rig because the BMC flash socket is EMPTY → BMC_PRESENT# high. So the
     BMC's correct Y2 drive is blocked at U23 (netlist-traced: D27/QQ9/QQ10).
  6. Obtained the read by pointing the mux at Y2 from the SP5100 side
     (`setpci 00:14.0 0x54.w=0x000B`, GPIO59/60 = SB_I2CS0/1, register found in
     the in-repo SP5100 RRG `GPIO_60_to_57_Cntrl`), fully recoverable
     (restored 0x0707). BMC then read through the shared closed QU9.
  - Honest scope: the SPD **data path** is proven on the BMC; the select-drive
    was provided by the SP5100 (rig has empty flash socket → BMC can't own
    selects). A production board (BMC_PRESENT# low) has the BMC drive them.
- **Faithful model updated**: real 256-byte SPD baked into `hw/arm/aspeed.c`
  (replacing the provisional image); TSOD REMOVED (real UDIMM has byte32=0 =
  no thermal sensor → QEMU 0x19 NAKs like silicon); temp@19 dropped from both
  DTS; fwtest/spd-test/test assert real SPD (0x92/0x0b/0x02 UDIMM) + TSOD NAK.
  fwtest 12/12, integration 114/114. jc42.c kept (available for TS DIMMs).
- **My bugs this session so far: still just the earlier 3** — the hardware
  read the real SPD perfectly once I drove the mux correctly.

## 2026-07-18 — silicon rerun with patch 0008: mux ALIVE; SPD not yet ACKing

- Fixed kernel netbooted on silicon: **`i2c-mux-gpio i2cmux: 3 port mux`
  registered, adapters i2c-14/15/16 present, pin-45 error GONE** — patch
  0008 works on the real chip.
- SPD probe loop: at24 on 15-0051 not binding yet. Live facts:
  - `HOST_POWER_BEFORE=1` — GPIOH2 (line power) already high; plug ~49 W.
    NOTE: H2 = STA_LINE_POWER; **SYS_PWRGD is a different net (ball D9)**
    — QU9's gate follows SYS_PWRGD, so H2=1 does not prove the bridge is
    closed. Register dump queued behind the script's wait loop.
  - G3 SCU74 = 0x4204D000 decoded from datasheet §18: bit23 (VP[17:12]
    pad enable) = **0** → W3/W4 pads are NOT in video mode (good);
    bit25 PHYLINK set (the known A4 alt-func), bit18 DDC, bit15 VGA,
    bit14 I2C#7, bit12 I2C#5 enabled.
  - Hypotheses ranked: (1) SYS_PWRGD low → QU9 open (host half-on state);
    (2) host mid-POST → SP5100 owns selects → misroute; (3) something
    about GPIO drive on F4/F5 not reaching the pins. Discriminators queued:
    GPIO A-D data bit14 (B6 = SYS_PWRGD net), E-H data/dir F4/F5 state.

## 2026-07-18 — SILICON SESSION: boot OK; pinctrl blocker root-caused QEMU-first

- **Silicon boot chain worked end-to-end**: JTAG 3-step (reset-halt → DDR2
  train MCR04=0x585 → U-Boot @0x40000000) → `boot#` → TFTP kernel 3463384 B
  + initramfs + dtb → Linux 6.6.70 up, eth0 192.168.66.2, dropbear,
  BMC-READY on serial.
  - My-bug #2 this session: drove the serial at 1200 baud; the evidence
    file for THIS U-Boot build (186096 B) says its console is 115200 — the
    1200-baud build was a different binary. 7 bytes of framing garbage =
    the banner. Fixed; `bmc-serial.sh` helper deployed on the Pi.
- **D08 silicon blocker found**: `aspeed-g4-pinctrl: pin-45
  (1e780000.gpio:557) status -1` → `i2c-mux-gpio: probe failed` → no mux
  adapters. Root cause chain, fully evidenced:
  - G4 pinctrl table: ball A19 (its pin 45) has SIOSCI/ACPI function gated
    on `HW_STRAP1[19]==0` (`ACPI_DESC`, pinctrl-aspeed-g4.c:385).
  - Real G3 SCU70 = **0x00819582** (JTAG + devmem agree), bit19=0 → driver
    thinks an un-deconfigurable strap function owns the pad → -EPERM.
  - G3 datasheet §18: SCU70 bit19 = **"Bypass all PLL (test mode only)"** —
    the G4 interpretation is a phantom; and setting bit19 on silicon would
    be catastrophic, so no devmem workaround (ruled out BEFORE trying).
  - **Bonus silicon facts from the strap decode**: SCU70[8:6]=0b110 =
    "RMII(MAC#1) and RMII(MAC#2)" — MAC1 is RMII (settles the N-vs-CP/
    MII-vs-RMII tension: balls are MII-capable, strap selects RMII) and
    the MAC2/NC-SI channel is STRAP-ENABLED on this board (D07 evidence);
    [1:0]=10 = SPI boot (G3 has no DRAM-size strap in SCU70); [3:2]=00 =
    8 MB VGA; [23]=1 LPC reset on B10; SCU74=0x4204D000, SCU40=0x000020C0.
- **QEMU-first loop executed**:
  1. Machine strap constant replaced with the measured 0x00819582
     (was palmetto-derived guesswork) → submodule `4ff6a74`.
  2. Integration suite still 114/114.
  3. `spd-test.py` now FAILS in QEMU with the byte-identical
     `pin-45 status -1` — faithful repro (the old constructed strap had
     been masking this real kernel bug).
  4. Kernel fix: `g3_strap_phantoms` quirk — strap-only G4-table
     expressions are skippable on the DISABLE path only (enable-path strap
     evaluation untouched — eth0's RMII1 mux depends on it), gated by new
     compatible `aspeed,ast2050-pinctrl`; both DTS switched. Will become
     patch 0008 once validated.
- C4/C-UBOOT oracle re-validation with the new strap: not yet run locally
  (CI covers on push) — flagged, not forgotten.

## 2026-07-18 — silicon session prep; NC-SI facts pinned; docs reconciled

- **Stale-artifact trap found & fixed:** `build-realhw-kernel.py` built from
  the `.worktrees/d16-qemu` tree (not this worktree) — the artifact would
  have silently lacked ALL my changes. Fixed to worktree-relative + DTS
  refresh; committed. Realhw kernel rebuilding correctly now.
- **DTS lineage identified:** the proven silicon dtb
  (`kgpe-hwpass-vgafix-video.dtb`) is the *QEMU-DTS lineage* (built by
  build-kernel.sh from `qemu-firmware/dts/aspeed-bmc-asus-kgpe-d16.dts`),
  NOT `dts/aspeed-bmc-asus-kgpe-d16-realhw.dts`. Diff of my new kernel dtb
  vs proven = my i2cmux node + kcs `clocks` (patch-0004 pair, desired) +
  **vhub `okay` vs proven `disabled`**. For the SPD silicon run I forced
  vhub back to disabled in a boot-only copy (`kgpe-i2cmux-novhub.dtb`,
  via fdtput) — the vhub silicon retest is D05 Test B, a separate
  controlled experiment; one variable at a time.
- **Rig state:** plug 49 W, old kernel still up at 192.168.66.2 (its
  dropbear rejects our key — irrelevant, JTAG reboot planned). claude on
  the Pi has passwordless sudo; JTAG workspace copied to
  `/home/claude/openocd-bmc-new` (paths patched); TFTP dir writable,
  dnsmasq active, eth-bmc 192.168.66.1 up, serial console free.
- **Docs-reconciliation agent landed 3 commits** (F7-NCSI corrected with
  MAC2 facts; SILICON-STATUS #9 → REOPENED(D07); MODERN-KERNEL-STATUS
  resolved-banner). Its flags: SILICON-STATUS intro still carries the old
  #9 verdict (queued); **MAC1 MII-vs-RMII strap question** — read SCU70 on
  silicon this session (added to checklist).
- **82574L NC-SI research complete** (datasheet rev 2.7): true DMTF NC-SI
  1.0.0a over RMII, NVM-gated (word 0x0F MNGM), package-ID word 0x2E,
  multi-drop-by-float + Select Package, no hw arbitration, Intel OEM cmds
  in mainline net/ncsi, QEMU responder = libslirp. Open: ASUS NVM MNGM
  state — dump on silicon. TASKLIST D07 updated.

Newest entries at the top. Every work session appends here and commits.
Format: `## YYYY-MM-DD HH:MM` + what was done / found / failed (with honest
confidence about whether a failure was our own mistake).

## 2026-07-18 — D08 Linux stack VALIDATED in QEMU: `SPD RESULT: PASS`

- `scripts/spd-test.py` boots the machine and drives the REAL driver chain:
  i2c-mux-gpio child adapters appear (chan 2 = i2c-15); with host OFF the
  DT-declared at24/jc42 probes fail (faithful QU9 gating — asserted, not
  worked around); host powered on in-guest via the modeled sequencer;
  re-probe binds at24 → `/sys/.../eeprom` header `92 11 0b` and jc42 →
  hwmon `temp1_input=35000`; host powered OFF → device unbinds and cannot
  re-probe (gating is live). Evidence:
  `openbmc/bmc-functionality/evidence/d08-spd/00-qemu-linux-stack-PASS.txt`.
- **My bug count this session: 1** — the first run failed on a
  trailing-space string comparison in MY test (command substitution strips
  it); the model/drivers were right. ("It is always your code.")
- Learned/documented: deferred probe does NOT retry on power events — the
  silicon procedure needs the same explicit `drivers_probe` re-bind after
  host power-on (recorded in peripherals/i2cmux/DOC.md).
- CI: new `boot-spd-mux` job in d16-qemu-stack.yml.
- realhw kernel inherits the new config via the merge order (verified
  build-realhw-kernel.py merges kgpe-d16.config).
- Next: silicon half — JTAG boot the realhw kernel with the new DTS, power
  host on, wait POST, read SPD/TSOD; then bake the REAL A2 SPD dump into
  the QEMU model replacing the provisional image.

## 2026-07-18 — D08 fabric IMPLEMENTED in QEMU; fwtest 11/11 PASS first run

- **QEMU submodule (`be673b2`):** new `kgpe-d16-i2c-fabric` device
  (transparent GPIO-selected mux, pca954x `match_and_add` pattern, gated on
  the modeled host power), new `jc42` TSOD device (MCP98244 IDs — corrected
  from my first MCP9805 guess after checking Linux jc42.c's ID table:
  MCP9805's real devid is the 0x0000-family, 98244=0x2200 is cleanly in the
  table), board glue instantiates SPD @0x51 (CRC-valid provisional
  DDR3-1333 ECC RDIMM image) + TSOD @0x19 on bank Y2 = rig slot A2.
  `aspeed_gpio` grew `kgpe-host-on` + `kgpe-i2cs[2]` named outputs (per-pin
  sysbus-IRQ indexes shift with skipped pins, so named outputs are the
  robust wiring; pull-up semantics "undriven ⇒ high" preserved).
- **Parent repo (`61ae28e`):** `/i2cmux` i2c-mux-gpio DTS nodes in BOTH the
  QEMU DTS and the realhw DTS (GPIOF4/F5 = Linux lines 44/45; no enable
  GPIO — none exists in hardware), kernel config +I2C_MUX_GPIO +AT24 +JC42.
  Both DTS verified compiling with dtc (phandles resolve).
- **fwtest `peripherals/i2cmux` + `integration/test_i2cmux.py`: 11/11 checks
  PASS on the first run** — host-off NAK / host-on Y3-idle NAK / Y2 SPD+TSOD
  ACK / SPD bytes 0x92,0x0B read / live re-routing / mid-session power-off
  disconnect, with the pre-fabric W83795G unaffected throughout.
- Full integration suite regression run in progress.
- Compatibles verified against the vendored kernel source (at24
  "atmel,24c02" ✓, jc42 "jedec,jc-42.4-temp" ✓, cap high-byte==0 detect
  requirement ✓).
- NOTE (D09 reconciliation item): schematic §11 names vs the silicon-verified
  pwrseq GPIO map disagree on some lines (e.g. GPIOB6 = SYS_PWRGD in the
  schematic vs CTL_REQ_RESET_N in asus_power.sh RE). Power control is
  plug-verified working, so both facts are real — the naming must be
  reconciled with net-level evidence in D09, not papered over.

## 2026-07-18 — fabric FULLY decoded from netlist; audits folded in

- **D08 fabric control/arbitration completely traced** from the extracted
  netlist (`.worktrees/kcma-d8-bmc-wiring/tmp/kgpe/kgpe.json`) → new doc
  `schematic-wiring/I2C-MUX-FABRIC-ARBITRATION.md`. Headlines:
  - QU9 enable = !SYS_PWRGD (automatic, no BMC GPIO); QU5 E# grounded
    (always on); U23 ownership = hardware mutex via D27/QQ9/QQ10
    (BMC owns iff BMC_PRESENT# low AND SB_BIOS_POST_COMPLT# low);
    only BMC-driven controls anywhere = GPIOF4/F5 selects; idle select = 11.
  - **Doc gap found & recorded:** the QU9-switched 4th segment reaches the
    TPM1 header (pins 13/14) and PCIe slots 1–5 SMBus (`I2C13*` nets) —
    §10 only mentioned the aux panel.
  - **LU1/LU2 (82574L) confirmed on +3V3_AUX** → D07 silicon testable host-off.
  - **U25 FRU EEPROM E2 pin strapped high** → address likely 0x54-0x57 (doc
    said 0x50-0x53); silicon i2cdetect to settle.
- **Audit agents (4) returned; corrections folded into TASKLIST:**
  - UNDERSTATED: modern U-Boot v2019.04 (`evb-ast2400_defconfig`) already
    boots→Linux→SSH in QEMU (CI `boot-uboot-ssh`); still zero board port.
  - OVERSTATED: FRU EEPROM "QEMU eeprom exists" — no DTS node/model wired
    anywhere → reset to ⬜.
  - D06 naming conflict: schematic says RTL8201**N** (U5); model/tests say
    RTL8201**CP** (PHYID 0x8201). Reconcile via silicon PHYID + datasheets.
  - F7-NCSI.md "not wired" verdict was MAC1-scoped — must be reconciled with
    schematic §7 (MAC2/RMII2 to LU1+LU2). QEMU MAC2 exists but unwired
    (`macs_mask=ASPEED_MAC0_ON`); DTS mac2 disabled; NET_NCSI not built.
  - Stale doc: `MODERN-KERNEL-STATUS.md` still lists the RMII-TX blocker
    superseded by the VIC + cur_speed fixes — needs updating.
  - "108 tests" = 67 test functions parametrized to 108 cases (accurate but
    now stated precisely).
  - Zephyr: confirmed zero code exists anywhere (D14 all-⬜ accurate).
- Push hiccups to GitHub (2 timeouts, then success) — network, not repo state;
  branch now synced at `2e10f8a`.

## 2026-07-18 — D03 BIOS-flash path SETTLED; D08 fabric facts gathered

- **D03/#8 settled by sub-agent research with schematic citations:** host BIOS
  flash `FU1` (W25Q16) is on the **SP5100 SPI controller** (`SB_SPI_*`, SU1
  D1/D2/G6/F3/F4/D6→FU1); BMC `AST_SPI*` nets reach only `BMC_FW1`; no shared
  node; AST2050 has no host-facing SPI master; BIOS fetch is FCH-SPI (not LPC
  cycles). Prior "no path" claim was RIGHT — now Ⓝ *with evidence* instead of
  assumption. TASKLIST updated.
- **D08 mux-fabric facts established (schematic):**
  - `AST_I2CS0` = GPIOF4 (ball W4), `AST_I2CS1` = GPIOF5 (ball W3) → U23[5]/[2].
  - `I2CMUX_ENABLE#` = inverted `SYS_PWRGD` (U8 74LVC14A: pin13 in = SYS_PWRGD
    per QU1_pins.md:315, pin12 out = I2CMUX_ENABLE#). So QU9 bridges I2C2↔I2C7
    **only while host power is good** — SPD unreachable with host off; QEMU
    model must enforce this.
  - U23 OE# nets (`N51800495`/`N51800497`) driver still untraced (BMC pinmap
    only shows U23[2]/[5]) — must come from the FZ netlist dumps; open item
    before silicon SPD access (multi-master hazard vs SP5100).
- Launched 4 read-only audit/research agents (statuses D01-D06, D07-D15 +
  U-Boot/Zephyr inventory, BIOS path [done ↑], NC-SI facts). 3 still running.

## 2026-07-18 — program start

- Merged `origin/main` (schematic-wiring PR #29) into `claude/bmc-functionality`
  → merge commit `a981389`, pushed.
  - **Mistake made & fixed:** a persisted `cd` caused the first merge attempt to
    land on the *local `main` checkout* (repo rule: never commit on main).
    Reset local main to `origin/main` (the stray commit contained only
    origin/main content — nothing lost), redid the merge in this worktree.
- Read `schematic-wiring/AST2050-BMC-WIRING.md` in full (597 lines).
- Created `TASKLIST.md`: 15 device blocks (D01–D15) × QEMU/U-Boot/Linux/Zephyr
  × validation environments, statuses seeded from prior program evidence.
- **REOPENED prior wrong claims** (schematic contradicts them):
  - NC-SI: RMII2 *is* wired to both 82574L NICs → D07.
  - DIMM SPD/TSOD: reachable via QU9/QU5/U23 fabric → D08.
  - SOL: UART1 → QU8 PI5C3257 → Super-I/O → D10.
  - Host-BIOS-flash path: to be settled from SP5100 doc, not assumed → D03.
- Next: commit program docs; audit pass over existing tree to firm up seeded
  statuses; then start execution with D08 mux fabric + D07 NC-SI (QEMU-first),
  per the QEMU-first faithfulness workflow.
