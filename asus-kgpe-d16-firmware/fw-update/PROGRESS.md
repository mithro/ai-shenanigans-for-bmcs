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

## Status — ALL DELIVERABLES DONE

- [x] Ground-truth analysis: BMC SPI + host BIOS SPI, datasheet cites, QEMU model
      coverage — `UPDATE-PATHS.md`.
- [x] QEMU demo: BMC-update mechanism — **UpdateService `ServiceEnabled:true`,
      dummy image POST → HTTP 202 + Redfish Task, phosphor-software-manager
      running, D-Bus `Software.Version` objects present** — `DEMO-RESULTS.md`,
      `evidence/qemu/`.
- [x] QEMU demo: BMC-side flash datapath characterized — `/proc/mtd` empty +
      no `/dev/mtd` on NFS boot documented (the MTD write-target gap); emulated
      16 MB BMC SPI attached. (No faithful *host-BIOS* mtd exists — §2–§3.)
- [x] IPMI firmware info (`mc info` rc=0) + HPM.1 (`compcode d4` = unsupported)
      characterized — `evidence/qemu/ipmi-*.txt`.
- [x] CI job `fw-update` mirroring `f5-ipmi-lan` in `d16-qemu-stack.yml`.
- [x] Real-HW characterization (READ-ONLY; explicit "no flash written") —
      `REAL-HW-CHARACTERIZATION.md`.

## Corrected finding (measured, not assumed)

The **full image DOES ship + run** the update-staging backend
**phosphor-bmc-code-mgmt** (`/usr/libexec/phosphor-code-mgmt/phosphor-software-manager`,
running as `xyz.openbmc_project.Software.Manager`; a first-pass `ls /usr/bin` grep
missed it). bmcweb accepts a firmware POST (HTTP 202 + Task) and the D-Bus software
tree carries `/xyz/openbmc_project/software/{039d44e1,bmc}`. The **only** end-to-end
gap is the **MTD write target**: the NFS-root boot masks `obmc-flash-bmc-*` and has
no `/dev/mtd`, so activation can't write a flash bank. Closing it needs a real MTD
boot layout (F-IMG2), not a code change. Host-BIOS-via-BMC is absent by hardware.
