# Device-driver program — running log

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
