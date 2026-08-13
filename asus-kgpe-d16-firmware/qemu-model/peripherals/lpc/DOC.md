# LPC host interface — AST2050 driver + faithfulness doc

**Base 0x1E789000.** The host↔BMC interface: **KCS** (IPMI Keyboard-Controller-Style
channels), **BT** (Block Transfer), SuperIO, and the **iLPC2AHB** bridge (host reaches
the BMC AHB — the culvert `ilpc` path). Full detail: **[`DATASHEET-LPC.md`](DATASHEET-LPC.md)**.

## 1. G3 register layout (datasheet §)

| Group | Offsets | Notes |
|---|---|---|
| KCS IDR1-3 (data-in) | 0x24 / 0x28 / 0x2C | H8S/2168-compatible |
| KCS ODR1-3 (data-out) | 0x30 / 0x34 / 0x38 | |
| KCS STR1-3 (status) | 0x3C / 0x40 / 0x44 | OBF/IBF/C-D bits |
| BT | 0x48–0x68 | BTCR ctrl @0x58, BTDTR data @0x5C |
| iLPC2AHB | HICR5-8 @0x80–0x8C | `ENL2H` + HWMBASE/ADRBASE/ADRMASK |

OpenBMC: IPMI KCS/BT drivers + port-80h POST-code snoop.

## 2. QEMU faithfulness — G3 LAYOUT MODELLED (register-accurate)

**Fixed 2026-07-10.** A G3-only `aspeed.lpc-ast2050` device replaces the AST2400
`aspeed_lpc` for the AST2050 SoC (gated on `silicon_rev == AST2050_A1_SILICON_REV`,
mapped at 0x1E789000). It presents the **G3 register layout** — HICR0-4, LADR,
KCS IDR/ODR/STR (0x24-0x44), BT (0x48-0x68), SERIRQ, iLPC2AHB HICR5-8 (0x80-0x8C),
snoop — with datasheet resets. `test_g3_lpc_layout` PASSES (`str1.reset`,
`hicr0.rw`, the iLPC2AHB `hicr5.rw`), proving the KCS/BT/iLPC2AHB registers are
addressable at the G3 offsets, **not** the AST2400 0x140.

**KCS state machine modelled 2026-07-12 (F5b M2).** The three KCS channels now
implement the faithful H8S/2168-style OBF/IBF/C-D handshake per the STRn access
tables (datasheet p.315-316):

* host write to the data/command port → IDRn latched, `IBF`=1, `C/D` = port
  (command=1/data=0); BMC read of IDRn → `IBF` clears (receive completion);
* BMC write to ODRn → `OBF`=1; host read of the data port → `OBF` clears;
* STRn slave access per the datasheet columns: bits 7:4,2 ("defined by user",
  where the kernel keeps the IPMI KCS state/`SMS_ATN` bits) are Slave **RW**,
  `OBF` is Slave **RW0C**, `IBF`/`C/D` are Slave **R**; IDRn is Slave R / Host W
  (BMC writes dropped);
* `IBF` asserts VIC #8 (high-level, §10 p.99) while the channel's HICR2
  IBFIF/IBFIE enable is set and the channel is enabled (HICR0 LPCnE, + HICR4
  KCSENBL for ch3); no OBE interrupt exists on this silicon (drivers poll).

Since the machine has no LPC host CPU, the **host half** of each channel (the
LPC I/O cycles at LADRn) is exposed as QOM properties on `/machine/soc/lpc-g3`
(mirroring mainline `aspeed_lpc.c`'s QOM-exposed KCS registers, but keeping the
C/D distinction a real IPMI transaction needs): `host-kcs<N>-data` (write = OUT
data port; read = IN ODR, clears OBF) and `host-kcs<N>-cmdsts` (write = OUT
command port; read = IN STR). The properties replace **only the bus wires**;
driving a channel the BMC hasn't enabled fails loudly. Proven end-to-end by
`openbmc/bmc-functionality/f5b-kcs-m2-transaction-test.py`: a host-side Get
Device ID over this state machine is answered by stock OpenBMC
(`kcs_bmc_aspeed`/`kcs_bmc_cdev_ipmi` → `kcsbridged` → `ipmid`) at 64 MB.

Refinements (documented, not yet modelled): the BT state machine and the
iLPC2AHB→AHB bridging (the culvert `ilpc` data path). C2/C4 oracle boots stay
green (re-verified 2026-07-12 with the KCS state machine wired: F5b M1 PASS,
C4 vendor web PASS).

## 3. Faithful-model plan (oracle-gated)

A G3 `aspeed.lpc-ast2050`: KCS IDR/ODR/STR at 0x24–0x44, BT at 0x48–0x68, iLPC2AHB
(HICR5-8) at 0x80–0x8C bridging host LPC reads/writes to the BMC AHB. Coordinate with
the AST2400 aspeed_lpc so the legacy boots (which use the AST2400 layout, if at all) stay
green — oracle-gated.

## 4. Deliverable status

| # | Deliverable | State |
|---|---|---|
| 1 | firmware test (`fwtest.c`) | ☑ observes the G3 offsets (unmodelled) |
| 2 | doc (this + `DATASHEET-LPC.md`) | ☑ |
| 3 | QEMU model | ◐ **G3 register layout + KCS OBF/IBF/C-D state machine + host QOM ports modelled** (`aspeed.lpc-ast2050`, ☑); BT state machine + iLPC2AHB bridging still ☐ |
| 4 | integration test (`../../integration/test_lpc.py`) | ☑ layout checks + `TestKCS3HostHandshake` (qtest MMIO + QMP host ports, incl. the VIC #8 line) PASS |
