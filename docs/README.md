# docs — planning documents

Project planning documents, kept in-repo so plans stay versioned next to the
work they describe.

## `plans/`

Design documents and implementation plans, named
**`YYYY-MM-DD-<slug>.md`** (ISO 8601 date first — a repo-wide convention).
A `-design` suffix distinguishes a design document from its companion
implementation plan.

Current plans, oldest first:

- [`2026-02-16-pex-i2c-reverse-engineering-design.md`](plans/2026-02-16-pex-i2c-reverse-engineering-design.md)
  / [`2026-02-16-pex-i2c-reverse-engineering.md`](plans/2026-02-16-pex-i2c-reverse-engineering.md)
  — design + implementation plan for reverse-engineering the C410X PLX PEX
  switch I2C command protocol (results:
  [`../dell-c410x-firmware/pex-i2c-analysis/`](../dell-c410x-firmware/pex-i2c-analysis/README.md)).
- [`2026-07-01-open-bmc-firmware-program.md`](plans/2026-07-01-open-bmc-firmware-program.md)
  — the umbrella program plan: QEMU, kernel, U-Boot, OpenBMC, WallaBMC and the
  docs site, and how the pieces relate.
- [`2026-07-07-culvert-ast2050-g3-support.md`](plans/2026-07-07-culvert-ast2050-g3-support.md)
  — extending culvert to the AST2050/G3 (results:
  [`../asus-kgpe-d16-firmware/CULVERT-G3-HARDWARE-RESULTS.md`](../asus-kgpe-d16-firmware/CULVERT-G3-HARDWARE-RESULTS.md)).
- [`2026-07-08-ast2050-live-bmc-boot.md`](plans/2026-07-08-ast2050-live-bmc-boot.md)
  — booting a live BMC on the real KGPE-D16 AST2050.
- [`2026-07-08-openbmc-ast2050-full-buildout.md`](plans/2026-07-08-openbmc-ast2050-full-buildout.md)
  — master plan for the full modern-OpenBMC bring-up on the AST2050.

Plans are historical records as much as roadmaps: once executed, they are
*not* rewritten to match the outcome — the outcome is documented in the board
directories, and the plan links forward to it.
