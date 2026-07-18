# D08 — DIMM SPD read by the BMC on the real AST2050 silicon (2026-07-18)

**Result: the BMC read the real DIMM's 256-byte SPD over its own I2C2 engine
through the QU9/QU5 mux fabric, and the `at24` driver bound it** — the
formerly-"impossible" DIMM inventory (#5 in `SILICON-STATUS.md`) is real.

## What was proven

1. **Driver stack works on silicon.** The netboot kernel (patch 0008 = G3
   pinctrl strap-phantom quirk) brings up `i2c-mux-gpio i2cmux: 3 port mux on
   1e78a080.i2c-bus`; child adapters `i2c-14/15/16` = QU5 channels Y0/Y2/Y3.
2. **The BMC drives the correct QU5 selects.** GPIO dump while the mux driver
   held chan 2: E-H data bit12/13 = F4=0,F5=1 = S1:S0=10 = Y2 (DIMM A-D). QU9
   is closed (GPIOB6/SYS_PWRGD=1).
3. **The real SPD** (`dimm-a2-spd.bin`, this dir): DDR3 UDIMM, part
   **`RMR5030EF68F9W1600`**, serial 420B469C — byte-for-byte matching the
   host's `dmidecode -t 17`. CRC-16 over bytes 0-116 = **0xf0b4, verified**.
   byte3=0x02 (UNBUFFERED), byte32=0x00 (**no thermal sensor** — why 0x19 NAKs).
4. **The BMC's `at24` read it**: `at24 15-0051: 256 byte 24c02 EEPROM,
   read-only`, and `hexdump /sys/.../15-0051/eeprom` returned the full SPD
   above (see `bmc-console-tail.txt`).

## The board-arbitration reality (the important finding)

The KGPE-D16 DIMM SPD sits behind the QU9/QU5/U23 fabric
(`schematic-wiring/I2C-MUX-FABRIC-ARBITRATION.md`). Two facts govern access:

- **QU5 selects float/idle to a non-DIMM bank.** At idle the SP5100 parks the
  selects (measured PCI 00:14.0 reg 0x54 = 0x0707 → GPIO59/60 = S1:S0 = **01
  = Y1, unconnected**). So neither the host OS nor the BMC sees the DIMM until
  someone drives the selects to Y2. (Confirmed: the host's own `decode-dimms`
  and 0x50-0x57 scan found nothing at idle — it is the mux, not a dead chip.)
- **U23 hands select-ownership to the SP5100 on this rig.** The BMC owns the
  selects only when `BMC_PRESENT#` low AND `SB_BIOS_POST_COMPLT#` low. The rig
  runs with the **BMC firmware flash socket empty** (JTAG boot), so
  `BMC_PRESENT#` (= `BMC_FW1[7]`, 4.7k pull-up) is **high** → SP5100 owns the
  selects permanently. The BMC's correct Y2 drive is therefore blocked at U23
  and does not reach QU5.

**How the read was obtained:** with the host up, we pointed the mux at Y2 by
writing the SP5100's own select GPIOs — `setpci -s 00:14.0 0x54.w=0x000B`
(GPIO60=I2CS1=1, GPIO59=I2CS0=0 → Y2), fully recoverable (restored to 0x0707
after; a host reboot also resets it). With the physical selects held at Y2 by
the SP5100, the **BMC's I2C2 → QU9(closed) → QU5-Y2 → DIMM** data path reached
0x51 and `at24` read it. The register was traced from the in-repo
`AMD_SP5100_Register_Reference_Guide` (`GPIO_60_to_57_Cntrl`, PCI reg 0x54).

The **only** rig-specific caveat is *who drives the select lines*: on this
flash-socket-empty rig the SP5100 must (U23), whereas a production board — with
the BMC firmware flash present asserting `BMC_PRESENT#` low — has the BMC drive
them itself after POST. The BMC's SPD **data path** proven here is identical in
both cases.

## Faithful QEMU model

`hw/arm/aspeed.c` now carries this exact 256-byte SPD at slot A2 / 0x51 (no
TSOD — the real UDIMM has none, so QEMU 0x19 NAKs like silicon). The
`kgpe-d16-i2c-fabric` device models QU9 (host-power gate), QU5 (GPIO select),
and U23 (`bmc-present-n`/`sb-post-complt-n` ownership), so QEMU reproduces both
the reachable and the blocked cases. `fwtest i2cmux` = 12/12; `spd-test.py`
(full Linux `i2c-mux-gpio`+`at24` stack) reads the same header + part number.

## Files
- `dimm-a2-spd.bin` — the real 256-byte SPD (CRC-verified).
- `bmc-console-tail.txt` — BMC serial console: mux registration, `at24` bind,
  the SPD hexdump.
