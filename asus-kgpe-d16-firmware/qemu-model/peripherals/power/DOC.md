# Host power control — KGPE-D16 (AST2050) board power-sequencer glue

OpenBMC feature **F2** (host power on / off / reset). The AST2050 BMC controls
mainboard power over **GPIO**, not a dedicated power-control block, so this
"peripheral" is the small piece of **off-chip board glue** that turns the BMC's
GPIO request lines into a host-power state — modeled in the Aspeed GPIO device so
the whole OpenBMC power path can be demonstrated in QEMU.

Full wiring + evidence:
[`../../../openbmc/bmc-functionality/HW-WIRING-power-sensors.md`](../../../openbmc/bmc-functionality/HW-WIRING-power-sensors.md)
(§1, from Raptor Engineering's real AST2050 OpenBMC port). GPIO register model:
[`../gpio/DATASHEET-GPIO.md`](../gpio/DATASHEET-GPIO.md).

## 1. The 3-request-line protocol

The BMC drives three **active-low request lines** into the board's
power-sequencing logic and senses one **power-state input**, and it must first
reclaim a **BMC-in-control gate line** (all GPIO @ `0x1E78_0000`):

| Function | GPIO | (set,bit) in the Aspeed model | Reg/bit | Board signal |
|---|---|---|---|---|
| BMC-in-control gate | **GPIOA4** | (0, 4) | GPIO00/04 bit 4 | `ASUS_BMC_CTL_LOCKOUT_N` (drive **high**) |
| Power-ON request | **GPIOB1** | (0, 9) | GPIO00/04 bit 9 | `CTL_REQ_POWERUP_N` |
| Force-OFF request | **GPIOF0** | (1, 8) | GPIO20/24 bit 8 | `CTL_REQ_POWERDOWN_N` |
| Warm-RESET request | **GPIOB6** | (0, 14) | GPIO00/04 bit 14 | `CTL_REQ_RESET_N` |
| Power-state input | **GPIOH2** | (1, 26) | GPIO20 bit 26 | `STA_LINE_POWER` (1=on) |

(A set is 4 groups × 8 pins: set 0 = A,B,C,D; set 1 = E,F,G,H.)

### 1a. The GPIOA4 BMC-in-control gate (HW-verified 2026-07-13)

On the **real AST2050** the board only honours `CTL_REQ_POWERUP_N` while
**GPIOA4** (`ASUS_BMC_CTL_LOCKOUT_N`) is driven **HIGH as a real GPIO output**
("BMC in control"). A4's pad defaults to the **PHYLINK** alt-function
(`SCU74[25]=1`), so a **stock image cannot drive it** and the board **IGNORES**
the power-up request — the host can only ever be **force-OFF** (via `GPIOF0`),
never powered **ON**. `GPIOB1`/`GPIOF0`/`GPIOB6` were already GPIO-mode; **A4
alone was the gate**. To power on, the BMC must reclaim A4: clear `SCU74[25]`
(A4 → GPIO), set A4 direction = out, and drive A4 = 1. Force-OFF works
regardless of A4.

The exact sequences (verbatim `asus_power.sh`, HW-WIRING §1.2): power-**on** pulses
`POWERUP_N` low (with `RESET_N` low then released); power-**off** pulses
`POWERDOWN_N` low; **reset** pulses `RESET_N` low while power stays engaged.
Because each line is only *momentarily* pulsed, the **latch** — not the
instantaneous pin level — holds the host power state.

## 2. QEMU model (`hw/gpio/aspeed_gpio.c`)

`aspeed_gpio_kgpe_d16_pwrseq()` is a minimal faithful **set/reset latch**:

- `POWERDOWN_N` (GPIOF0) asserted low → host **off** (force-off wins, no A4 needed).
- else `POWERUP_N` (GPIOB1) asserted low **AND GPIOA4 driven high** → host **on**.
- a `POWERUP_N` assertion while **A4 is not a driven-high output** is **IGNORED**
  (host stays off) — reproducing the silicon "stock image can't power on".
- `RESET_N` (GPIOB6) never changes the latch (warm reset keeps power).
- the latch is reflected on the **GPIOH2** power-state input the BMC reads.

A request line counts as *asserted* only when it is driven as an **output at
logic low** (`direction=out`, `data=0`), matching the active-low wiring; the A4
gate is checked with the mirror helper `aspeed_gpio_out_high()` (`direction=out`,
`data=1`).

It is evaluated at the end of `aspeed_gpio_update()` (i.e. after any GPIO
register write) and re-entrancy-guarded because driving GPIOH2 re-enters the
update path.

### Gating / faithfulness

- Enabled only via the **`kgpe-d16-pwrseq`** qdev property, which the AST2050 SoC
  (`hw/arm/aspeed_ast2400.c`, keyed on `AST2050_A1_SILICON_REV`) sets before GPIO
  realize. Every other Aspeed SoC/machine leaves it **off** → AST2400/2500/2600
  boards are unchanged; the legacy C2 (our kernel) and C4 (Dell C410X vendor
  firmware) boots are unaffected (the Dell board sequences host/slot power over
  I2C expanders, not these AST2050 pins).
- The latch is intentionally *minimal*: it models the observable input/output
  behaviour of the board glue (request pulse → power-state), not the analog PSU
  ramp or the `STA_LINE_POWER` I2C-rail detail. Enough to close the OpenBMC loop;
  no more than the datasheet + Raptor port justify.

## 3. Firmware test — `fwtest.c` (6 checks, all PASS)

Bare-metal `-M kgpe-d16-bmc` test driving the exact `asus_power.sh` register
sequences and reading GPIOH2 back:

| Check | Meaning |
|---|---|
| `power.off_at_reset` | GPIOH2 = 0 out of reset (host off) |
| `power.on_blocked_without_a4` | POWERUP_N pulse with A4 NOT reclaimed → GPIOH2 stays 0 (stock-image negative check) |
| `power.on_after_a4_reclaim` | the SAME pulse after driving GPIOA4 high → GPIOH2 = 1 |
| `power.on_after_powerup` | GPIOH2 = 1 after a fresh POWERUP_N pulse (A4 still high) |
| `power.on_after_reset` | GPIOH2 stays 1 across a RESET_N pulse |
| `power.off_after_powerdown` | GPIOH2 = 0 after the POWERDOWN_N pulse |

The SAME `.elf` can run on the real AST2050 over the RPi rig; the `[FWT]`
transcript diffs byte-for-byte, proving the model matches silicon (deferred to
the hardware phase — another agent holds the rig).

## 4. OpenBMC integration (F2 userspace)

The QEMU latch closes the loop with OpenBMC via the classic
`org.openbmc.control.Power` model: `phosphor-chassis-state-manager` reads `pgood`
(= GPIOH2) and the `obmc-chassis-poweron@0` / `poweroff@0` targets drive the
request lines. See
[`../../../openbmc/bmc-functionality/PROGRESS.md`](../../../openbmc/bmc-functionality/PROGRESS.md)
for the daemon set, masking, and the Redfish `ComputerSystem.Reset` demo.

## 5. Deliverable status

| # | Deliverable | State |
|---|---|---|
| 1 | firmware test (`fwtest.c`) | ☑ 6 checks (off / blocked-no-A4 / A4-reclaim-on / on / reset / off) |
| 2 | doc (this) | ☑ |
| 3 | QEMU model (`aspeed_gpio_kgpe_d16_pwrseq`) | ☑ gated on AST2050 rev + GPIOA4 BMC-in-control; upstream boards unchanged |
| 4 | integration test (`../../integration/test_power.py`) | ☑ |
