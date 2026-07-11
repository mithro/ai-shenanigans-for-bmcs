# F9 — Firmware & BIOS update: PROGRESS

Task F9 (branch `claude/bmc-f9-fwupdate`, off `claude/bmc-functionality`): demonstrate
the firmware-update **mechanism** on the KGPE-D16 / AST2050 BMC in QEMU, and
characterize it on real hardware — under a **HARD SAFETY RULE: no real flash writes,
nothing unrecoverable**. Emulated-flash writes in QEMU are fine (disposable model);
on real silicon everything is READ-ONLY / dry-run.

## Ground truth established (2026-07-12)

Two independent SPI-NOR flashes on the board, on two independent buses:

1. **BMC firmware flash** — the AST2050's own SPI-NOR on the **legacy SMC**
   (control regs `0x16000000`; boot device on CE2, data window `0x14000000`;
   optional 2nd SPI on CE0 `0x10000000` = `CONFIG_2SPIFLASH`, "Not ready" in
   Raptor U-Boot). SPI-only silicon (datasheet §11.1 p100). This is what the BMC
   **self-updates**. Modeled in QEMU as ONE flash via `-drive ...,if=mtd`.
2. **Host BIOS flash** — a **separate socketed 2 MB Winbond W25Q16** on the HOST
   x86 SPI bus behind the SP5100 FCH. **Not wired to the BMC** on this board:
   updated host-side by `flashrom` (behind the SP5100 IMC write-guard) or
   externally with a SPI clip. The AST2050 has **no** host-SPI master / BIOS mux
   (that is an AST2400+ feature). See `UPDATE-PATHS.md` for datasheet cites.

## Status

- [x] Ground-truth analysis: BMC SPI + host BIOS SPI, datasheet cites, QEMU model
      coverage — `UPDATE-PATHS.md`.
- [ ] QEMU demo: BMC-update mechanism (UpdateService present + staged Software object).
- [ ] QEMU demo: BMC-side SPI mtd access datapath + chip identity read-back.
- [ ] IPMI firmware info (`mc info`) + HPM.1 capability characterization.
- [ ] CI job `fw-update` mirroring `d16-qemu-stack.yml`.
- [ ] Real-HW characterization (READ-ONLY; explicit "no flash written").

## Honest boundary (up front)

Neither AST2050 OpenBMC image (`-redfish.bb` lean, `-full.bb`) currently installs
the update-staging backend **phosphor-bmc-code-mgmt / phosphor-software-manager**,
and the NFS-root boot path **masks** the `obmc-flash-bmc-*` services (no MTD on that
path). So a full end-to-end BMC self-update does not run on the current lean image —
that is an **F-IMG2 image-content follow-up**. This task demonstrates the mechanism
and the datapaths, and states clearly what a full end-to-end update still needs.
