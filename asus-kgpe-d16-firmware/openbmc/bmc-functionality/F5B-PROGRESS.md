# F5b — host-side IPMI over LPC KCS (local host<->BMC channel)

Branch `claude/bmc-f5b-hostkcs` (off `claude/bmc-functionality`). Sibling of F5,
which proved the **remote** half (netipmid RMCP+/LAN, QEMU + real AST2050). This
task is the **local** half: a host OS/BIOS talking IPMI to the BMC over the
AST2050 **LPC KCS** interface on the same board.

## Ground truth (datasheet + models)

- **LPC controller @ 0x1E789000**, IRQ = **VIC #8** (AST2050/AST1100 A3 datasheet
  §30, §10 Table 36 p.99; `qemu-model/peripherals/lpc/DATASHEET-LPC.md`).
- **KCS = H8S/2168 layout**: three channels, each an IDRn/ODRn/STRn triple
  (datasheet p.315): ch1 `0x24/0x30/0x3c`, ch2 `0x28/0x34/0x40`, ch3
  `0x2c/0x38/0x44`. STR1-3 (status) are read-only.
- **These offsets are identical on the AST2400**, so mainline
  `drivers/char/ipmi/kcs_bmc_aspeed.c` binds unchanged (`LPC_IDR1=0x024 …
  LPC_STR3=0x044`, verified in the v6.6.70 tree). Channels 1-3 need no G3-specific
  driver — the AST2400 driver *is* the G3 KCS driver for these channels.
- **BT differs and is NOT usable via mainline on the G3**: the AST2050 BT block is
  at `0x48-0x68`, but mainline `aspeed,ast2400-ibt-bmc` / `bt-bmc.c` hardcode the
  AST2400 `0x140` offset — beyond the G3 SoC's LPC register file (QEMU model window
  `0x00-0x9F`, `ASPEED_LPC_AST2050_NR_REGS = 0xA0/4`) and unimplemented on real
  AST2050 silicon. **KCS is the only mainline-drivable host-IPMI channel here.**

## QEMU model (`qemu/hw/misc/aspeed_lpc_ast2050.c`)

Register-file model at the G3 layout: config/data registers RW, KCS status STR1-3
read-only (reset 0), `LADR12L` resets to `0x60`. Instantiated as `lpc-g3` /
`TYPE_ASPEED_LPC_AST2050` in `hw/arm/aspeed_ast2400.c`, MMIO-mapped at 0x1E789000,
single IRQ -> VIC #8. It does **not** implement the KCS OBF/IBF state machine or an
LPC host peer (there is no host CPU in the `kgpe-d16-bmc` machine) — see M2 below.

## The gap and the fix

The KGPE-D16 DTB inherited `lpc@1e789000` from `aspeed-g4.dtsi` with only
`lpc-ctrl`/`lpc-snoop` children — **no KCS node** — so the kernel bound no KCS
driver and created no `/dev/ipmi-kcs*`. Also the built kernel had
`CONFIG_IPMI_KCS_BMC_CDEV_IPMI` **off**, so even a bound KCS channel would expose
no `/dev` node.

Changes on this branch:
1. `dts/aspeed-bmc-asus-kgpe-d16.dts`: add `&lpc { kcs3: kcs@2c … }` — channel 3
   (`0x2c/0x38/0x44`), `aspeed,lpc-io-reg = <0xca2>` (IPMI SMS system interface),
   `interrupts = <8>`, `compatible = "aspeed,ast2400-kcs-bmc-v2"`.
2. `kernel/kgpe-d16.config`: add `CONFIG_IPMI_KCS_BMC_CDEV_IPMI=y` (plus the two
   already-on symbols for documentation) so the driver creates `/dev/ipmi-kcs3`.

## Milestones

- **M1 (QEMU-achievable):** kernel creates `/dev/ipmi-kcs3`, `kcs_bmc_aspeed` binds
  the G3 LPC model, channel enabled — demonstrated in QEMU at 64 MB.
- **M2 (host peer — honest boundary):** a full host->BMC KCS *transaction* needs
  something driving the LPC I/O-port (host) side. The `kgpe-d16-bmc` machine has no
  host CPU and the LPC model is a pure register file (no OBF/IBF handshake), so a
  real round-trip cannot be carried in QEMU today. Requires either extending
  `aspeed_lpc_ast2050.c` with the KCS state machine + a host back-channel, or a
  paired host-CPU QEMU / real silicon (where the powered host is the KCS peer).

## Status log

- (in progress) DTS KCS node + kernel CDEV_IPMI config added; building kernel.
