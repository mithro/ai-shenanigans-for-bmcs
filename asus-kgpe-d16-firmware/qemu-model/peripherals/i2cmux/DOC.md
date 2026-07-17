# KGPE-D16 I2C mux fabric (QU9 / QU5 / U23) — model + test notes

Board-level (not SoC) peripheral: the switching fabric between the AST2050's
I2C2 engine and the DIMM SPD/TSOD buses on the ASUS KGPE-D16. Netlist decode:
[`schematic-wiring/I2C-MUX-FABRIC-ARBITRATION.md`](../../../schematic-wiring/I2C-MUX-FABRIC-ARBITRATION.md).
QEMU model: `hw/i2c/kgpe_d16_i2c_fabric.c` (+ `hw/sensor/jc42.c` for the
TSOD), wired in `hw/arm/aspeed.c` `kgpe_d16_bmc_i2c_fabric_init()`.

## What the hardware does (traced, not inferred)

| Element | Control | Effect |
|---|---|---|
| QU9 SN74CBTLV3125 FET switch | `I2CMUX_ENABLE#` = **inverted `SYS_PWRGD`** (74LVC14A U8 pin 13→12) | Bridges I2C2↔I2C7 (and I2C8↔I2C13) only while host power is good. **No BMC GPIO controls this.** |
| QU5 74HC4052 dual mux | `E#` strapped to GND; `S1:S0` from `I2CS1/0` nets | Always enabled; Y0=aux/TPM/PCIe, Y1 n/c, **Y2=DIMM A–D**, **Y3=DIMM E–H**. Selects idle high (4.7k pull-ups) → Y3. |
| U23 74LVC125 buffers | OE# pair via D27/QQ9/QQ10 chain | Hardware mutex: BMC's GPIOF4/F5 drive the selects **iff `BMC_PRESENT#` low AND `SB_BIOS_POST_COMPLT#` low**; otherwise the SP5100 owns them (host BIOS reads SPD during POST). |

Rig DIMM population: slot **A2** → SPD `0x51`, TSOD `0x19`, bank **Y2**
(SA-strap map, fabric doc §5b).

## Model mapping

- Fabric = transparent `I2CSlave` with `match_and_add` forwarding into the
  selected channel bus (pca954x pattern, but GPIO-selected and gated).
- GPIO inputs: `select[2]` (from `aspeed_gpio`'s `kgpe-i2cs` outputs, which
  encode the pull-up rule "undriven ⇒ high"), `sys-pwrgd` (from
  `kgpe-host-on`, the modeled power-sequencer latch), `sb-post-complt-n`
  (tests only; board glue ties POST-complete to power-good since the machine
  has no host-firmware timeline).
- SPD = `smbus-eeprom` @0x51 with a CRC-valid DDR3-1333 ECC RDIMM image
  (**provisional** — to be replaced by the real A2 DIMM dump from silicon).
- TSOD = new `jc42` device (JC-42.4 registers, MCP98244 IDs, big-endian
  words matching Linux `i2c_smbus_read_word_swapped`).

## Test coverage (`fwtest.c` → `integration/test_i2cmux.py`)

1. Host OFF → SPD 0x51 NAKs; W83795G 0x2f (pre-fabric) still ACKs.
2. Host ON via the modeled sequencer; idle selects = Y3 (empty) → NAK.
3. GPIOF4 driven low → Y2: 0x51 + 0x19 ACK; empty 0x50 NAKs.
4. SPD random-read: byte0 = 0x92, byte2 = 0x0B (DDR3) — full data path.
5. Reselect Y3 → 0x51 vanishes (live routing).
6. Force host OFF → fabric vanishes mid-session; hwmon unaffected.

## Silicon procedure (Test on real hardware)

Boot the JTAG/netboot kernel with the `/i2cmux` DTS node; power the host on
(`kgpe-power.sh`) and wait for POST completion; then
`i2cdetect -y <mux-child-bus>` and `hexdump /sys/.../spd@51/eeprom`;
`sensors` shows the jc42 TSOD. Expect: nothing with host off (QU9 open);
possible misrouting only mid-POST (SP5100 owns selects; U23 prevents drive
fights). Replace the provisional SPD image in `aspeed.c` with the real dump.
