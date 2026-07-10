# GPIO — AST2050 driver + faithfulness doc

**Base 0x1E780000.** Banks **A–H only** (max 64 pins; "8 dedicated + 56 shared"),
register window **0x00–0x58**. OpenBMC uses GPIO for host power control, power-good /
presence sensing, and LEDs. Full detail: **[`DATASHEET-GPIO.md`](DATASHEET-GPIO.md)**
(datasheet §23 p262–269, pin summary §3.5, VIC routing §10).

## 1. Registers (all reset 0)

| Off | Register (banks A–D) | Off | (banks E–H) |
|---|---|---|---|
| 0x00 | data value | 0x20 | data value |
| 0x04 | direction (0=in, 1=out) | 0x24 | direction |
| 0x08 | interrupt enable | 0x28 | interrupt enable |
| 0x0C/0x10/0x14 | sensitivity type0/1/2 | 0x2C.. | sensitivity |
| 0x18 | interrupt status (W1C) | 0x38 | int status |
| 0x1C | reset-tolerant | 0x3C | reset-tolerant |
| 0x40–0x4C | debounce selects | 0x50/54/58 | debounce timers [23:0] |

**Data read** = `(output_latch & direction) | (input_pin & ~direction)`. Single data
register per block (no separate read-input register — that is an AST2400+ addition).
**Interrupts:** sensitivity type2/1/0 truth table = falling/rising/level-lo/level-hi/
dual-edge; status W1C; all 64 OR into **VIC source 20 (active-high level)**.

## 2. Driver notes

- Set a pin to output: direction bit = 1, then write the data register (latches the
  output). Set to input: direction bit = 0, read the data register (returns the pin).
- Only the *bonded* pins are physically present (§3.5): bank A = A4/A5, D = D6/D7,
  G = G0/G1; B/C/E/F/H fully bonded (8 each). The register file is a documented superset
  — "only partial GPIO bits are supported".

## 3. QEMU faithfulness

`peripherals/gpio/fwtest.c` (5 checks) vs the current model — **all PASS**: direction,
data, and interrupt-enable reset to 0; the direction register is RW; and an output pin
**latches** the written value (banks A–D `0xA5A5A5A5`, banks E–H `0x5A5A5A5A` read back).
The core datapath is faithful. **No model change needed** (oracle safe).

**Gap (documented, low impact):** the AST2400-based model (a) exposes **all 32 bits** in
each direction register and (b) exposes GPIO banks/registers **beyond H / above 0x58**
that the AST2050 does not have (§23 says A–H only). A strictly-faithful G3 GPIO would
mask writes to the bonded pins and abort above 0x58. G3 firmware never touches those, so
this is cosmetic; wiring a stricter model is oracle-gated.

## 4. Deliverable status

| # | Deliverable | State |
|---|---|---|
| 1 | firmware test (`fwtest.c`) | ☑ 5 checks (reset + direction RW + output latch) |
| 2 | doc (this + `DATASHEET-GPIO.md`) | ☑ |
| 3 | QEMU model | ◐ datapath faithful; exposes more banks/bits than G3 (cosmetic) |
| 4 | integration test (`../../integration/test_gpio.py`) | ☑ |
