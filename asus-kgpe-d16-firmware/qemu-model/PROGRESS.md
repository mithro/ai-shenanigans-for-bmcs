# Progress log — AST2050 faithful QEMU model

Newest entries at the bottom of each day. Committed after every change (repo rule).
Dates are ISO 8601 (YYYY-MM-DD).

## 2026-07-10 — Phase 0: program setup

- **Pivot recorded.** New goal: OpenBMC booting via TFTP + NFS root inside a QEMU
  that faithfully emulates the AST2050 (G3) hardware, with a comprehensive
  per-peripheral test suite proving emulation ≡ silicon. See `README.md`.
- **Reconnaissance done.** Audited existing QEMU work: the `kgpe-d16-bmc` machine
  (PR #16) boots U-Boot/kernel/Raptor/vendor firmware but is **G4/AST2400-based**,
  not faithful to the G3. Modern OpenBMC+Redfish (PR #22) runs only on
  `romulus`/AST2500. Neither is a faithful AST2050 nor TFTP+NFS. → this program is
  genuinely new work. The `firmware-testbench` module (PR #17, two backends:
  qemu + hil) is the integration-test substrate.
- **Workspace.** New isolated worktree `.worktrees/ast2050-qemu` on branch
  `claude/ast2050-qemu-faithful`, branched off `main` (has firmware-testbench,
  datasheets, culvert submodule), then `git merge --no-ff` of
  `claude/d16-qemu-firmware-stack` to pull in the QEMU fork + machine + build
  scripts. Only conflict was `.gitmodules` (resolved: union of both submodules).
  A prebuilt `qemu-system-arm` with the custom machine exists in the d16-qemu
  worktree — fast local iteration is possible without a full rebuild.
- **Authoritative register base addresses** taken from Raptor `hwreg.h`: VIC
  `0x1E6C0000` (compact G3 bank), SCU `0x1E6E2000`, SDRAM `0x1E6E0000`, MAC1
  `0x1E660000`, timer `0x1E782000`, UART2 `0x1E784000`, WDT `0x1E785000`, GPIO
  `0x1E780000`, AHB `0x1E600000`, SMC `0x16000000`.
- **Plan + matrix written** (`README.md`): 20-row peripheral inventory, the
  4-deliverable definition of done, golden-reference validation methodology, and a
  6-phase incremental roadmap (Phase 1 SoC identity/boot → Phase 6 OpenBMC over
  TFTP/NFS).
- **Dispatched** a subagent to extract the datasheet-cited authoritative memory map
  into `AST2050-MEMORY-MAP.md` (confirms/corrects the matrix's TBD rows).

### Datasheet map returned — authoritative corrections (fold into matrix)
From `AST2050-MEMORY-MAP.md` (datasheet A3 V1.05 §9, pp.97–98):
- **SCU7C rev-id = `0x00000202`** for AST2050-A3 (§18.2 p220), matching the culvert
  HW read. QEMU returns `0x01000303` → confirmed unfaithful.
- **VIC** is a single 32-bit bank (0x00–0x38), 32 sources; **no** G4 second bank.
- **Flash** = legacy **SMC regs @`0x16000000`, flash data @`0x10000000`** (not G4 FMC).
- **Conventional PCI**: A2P bridge `0x1E720000`, arbiter `0x1E78C000`; culvert P2A
  rides the PCI-slave BAR (not PCIe/XDMA).
- **ABSENT on AST2050** but present in the reused G4 memmap: **ADC**, SD/eMMC, eSPI,
  UARTs 3–5, graphics-display controller, USB1.1 host. 16-bit DRAM, ≤128 MB, no ECC.
  → the faithful machine must *remove/abort* these, not return 0.

### Harness built + first finding (DONE)
- `fwtest/` harness complete: crt0 + linker (DRAM 0x40000000), console UART
  `0x1E784000`, deterministic `[FWT]` report protocol, `build.py` (compile + boot
  under `-M kgpe-d16-bmc`, capture serial). Builds with `arm-none-eabi-gcc` 14.2.
- **Smoke test ran end-to-end on QEMU.** Console works; identity registers read:
  `scu.protect=1688a8a8`, `scu.revid=01000303`, `scu.strap=0a08e416`,
  `scu.clksel=f3f40000`, `scu.hpll=00000291`, `scu.mpll=00030291`,
  `sdmc.config=00000041`, `vic.irqstat/rawstat=0`.
- **Finding #1 (rev-id):** `scu.revid.is_ast2050_a3` FAIL got=`01000303`
  want=`00000202`. The harness mechanically reproduced the datasheet+HW-backed gap.

### Next
- Fold the corrections above into the `README.md` matrix (ADC→absent, SMC data addr,
  PCI/A2P, rev-id note). *(done in same commit)*
- Init + build the QEMU fork submodule in this worktree so device models are editable.
- **Template peripheral #1 = SCU**: DOC.md (datasheet-cited) + a full `scu` fwtest +
  fix the SoC rev-id (`0x01000303`→`0x00000202`) + straps/PLL faithfulness +
  `integration/test_scu.py`. Exit: smoke + scu tests PASS on the faithful build.
