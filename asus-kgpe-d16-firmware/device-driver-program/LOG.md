# Device-driver program — running log

Newest entries at the top. Every work session appends here and commits.
Format: `## YYYY-MM-DD HH:MM` + what was done / found / failed (with honest
confidence about whether a failure was our own mistake).

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
