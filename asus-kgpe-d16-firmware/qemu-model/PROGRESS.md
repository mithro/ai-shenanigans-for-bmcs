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

### Next
- Fold the datasheet memory map into the matrix once the subagent returns.
- Build the shared bare-metal firmware-test harness (`fwtest/`): ARM926EJ-S crt0,
  linker script, UART2 output, a deterministic register-dump/report protocol.
- Template the first peripheral end-to-end (SCU — identity/clocks decide whether
  the machine is really an AST2050): DOC + fwtest + model-diff + integration test.
