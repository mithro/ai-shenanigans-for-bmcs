# F2 — OpenBMC host power control on the KGPE-D16 (AST2050)

How the OpenBMC power stack wires the Redfish `ComputerSystem.Reset` action all
the way down to the AST2050 GPIO request lines and back — and how the faithful
QEMU model closes that loop. Wiring reference:
[`HW-WIRING-power-sensors.md`](HW-WIRING-power-sensors.md); QEMU model:
[`../../qemu-model/peripherals/power/DOC.md`](../../qemu-model/peripherals/power/DOC.md).

## The loop

```
 Redfish POST .../Actions/ComputerSystem.Reset {ResetType: On|ForceOff|ForceRestart}
   │  bmcweb
   ▼
 xyz.openbmc_project.State.Host  RequestedHostTransition
   │  phosphor-host-state-manager  ->  obmc-host-start@0 / obmc-host-stop@0
   ▼
 xyz.openbmc_project.State.Chassis  (obmc-chassis-poweron@0 / poweroff@0 targets)
   │  obmc-power-start@0 / obmc-power-stop@0  ->  busctl call ... setPowerState 1|0
   ▼
 org.openbmc.control.Power  @ /org/openbmc/control/power0   [op-pwrctl]
   │  drives the GPIO request lines, polls pgood
   ▼
 AST2050 GPIO  (Linux gpio-aspeed driver / sysfs)
   │  B1 power-up-req-n ↓ , F0 power-down-req-n ↓ , B6 reset-req-n ↓
   ▼
 QEMU aspeed_gpio_kgpe_d16_pwrseq()  ── host-power set/reset latch ──►  GPIOH2 = pgood
   │
   ▼
 op-pwrctl reads GPIOH2 -> pgood property -> phosphor-chassis-state-manager
   -> State.Chassis CurrentPowerState -> Redfish PowerState
```

Every link is real OpenBMC (bmcweb + phosphor-state-manager, both in the F0
fuller image); the only board glue is:

1. **the GPIO request-line semantics**, modeled faithfully in QEMU
   (`aspeed_gpio_kgpe_d16_pwrseq`, gated on the AST2050 silicon rev), and
2. **the `org.openbmc.control.Power` provider** (op-pwrctl) that translates
   `setPowerState` into GPIO writes and pgood reads.

## Two demonstrations

### (a) GPIO path through the real driver — `f2-power-control-test.py` (no rebuild)

Proves the modeled hardware works with the real Linux `gpio-aspeed` driver:
boots the fuller image (F2 mask set, `mem=64`), logs in over the serial console,
runs `kgpe-power.sh {init,on,off,reset}` (Raptor's `asus_power.sh` sequences over
sysfs GPIO), and reads GPIOH2 back **independently over QMP**
(`qom-get /machine/soc/gpio gpioH2`):

| step | request line driven | modeled GPIOH2 |
|---|---|---|
| init | all de-asserted | **off** (False) |
| on | GPIOB1 power-up pulse | **on** (True) |
| off | GPIOF0 power-down pulse | **off** (False) |
| reset | GPIOB6 reset pulse | **on** (stays True) |

It also GETs the Redfish `ComputerSystem` and POSTs `ComputerSystem.Reset`
(ForceOff/On/ForceRestart) to confirm bmcweb accepts each action. Evidence:
`evidence/qemu/f2-power-results.json`.

### (b) Fully-automated Redfish loop — op-pwrctl (`org.openbmc.control.Power`)

Wires (a) automatically so **Redfish `PowerState` itself** tracks the modeled
host power. Add op-pwrctl (`phosphor-skeleton-control-power`) to the image and
install `gpio_defs.json`:

- Recipe: `phosphor-skeleton-control-power` in
  `obmc-phosphor-image-ast2050-full.bb` `OBMC_IMAGE_EXTRA_INSTALL`.
- Config: [`gpio_defs.json`](gpio_defs.json) -> `/etc/default/obmc/gpio/gpio_defs.json`.

**Key config detail** — op-pwrctl drives each `power_up_out` to `state XOR
!polarity`, so with `power_up_outs = [{B1, pol 0}, {F0, pol 1}]`:

| setPowerState | GPIOB1 (pol LOW) | GPIOF0 (pol HIGH) | modeled latch |
|---|---|---|---|
| 1 (on) | 0 = POWERUP_N asserted | 1 = de-asserted | **on** (B1↓ sets) |
| 0 (off) | 1 = de-asserted | 0 = POWERDOWN_N asserted | **off** (F0↓ clears) |

That maps op-pwrctl's held-level drive exactly onto the modeled set/reset latch,
with no daemon patch. op-pwrctl polls `power_good_in` (GPIOH2) → publishes
`pgood` → phosphor-chassis-state-manager sets `CurrentPowerState` → Redfish
`PowerState`.

> **Proven vs. designed.** The *forward* path (a) is proven — each Redfish action
> returns HTTP 204 and GPIOH2 tracks it over QMP. This op-pwrctl wiring is meant
> to make the Redfish `PowerState` *readback* track too, **by design**, but in
> the 64 MB QEMU run bmcweb returned `PowerState: null` for every action (memory
> pressure — see `evidence/qemu/F2-README.md`), so the readback half of the loop
> is **not yet demonstrated**. GPIOH2 over QMP + the CI fwtest remain the
> authoritative power-state signal.

> On **real silicon** use the pulse sequences in `kgpe-power.sh` /
> `asus_power.sh` (§1.2), not a permanently-held level — the request lines are
> momentary. The QEMU latch accepts either (it keys on the active-low
> assertion), which is why the held-level op-pwrctl config is a valid emulation
> expedient while the pulse form is the hardware-faithful driver.

### (c) IPMI front-end — `ipmitool chassis power` (real 64-MB board)

The Redfish and IPMI front-ends share the **same** backend: `ipmitool chassis
power on|off|cycle|reset` sets the identical `xyz.openbmc_project.State.Host` /
`.State.Chassis` transition that bmcweb's `ComputerSystem.Reset` sets, so it
flows through the same phosphor-state-manager → op-pwrctl → GPIO → GPIOH2 loop.

- **Over LAN (RMCP+, netipmid):**
  `ipmitool -I lanplus -H <bmc-ip> -U root -P 0penBmc chassis power on|off|cycle|reset|status`
- **Host-side (in-band, from the managed host's OS/BIOS):** the same commands over
  the LPC **KCS** or **BT** channel (`ipmitool -I open ...` / `-I bt`); the F0
  image ships the host-IPMI bridge (`phosphor-ipmi-kcs`/`btbridged` +
  `phosphor-ipmi-host`). On the KGPE-D16 the host reaches the BMC KCS at LPC
  I/O `0xCA2` (coreboot `drivers/ipmi device pnp ca2.0`).

`ipmitool chassis power status` maps to the chassis `CurrentPowerState`
(= GPIOH2/pgood), so the same modeled latch is observable over IPMI.

## 64 MB daemon budget — two profiles

The Redfish (bmcweb) and IPMI (netipmid) front-ends need different daemons, and
**F1 found the fuller image with bmcweb does not fit the real 64 MB** (its TLS
handshakes reset and it crash-loops). So `f2_masked_daemons.py` has two profiles:

| profile | front-end | keep | mask |
|---|---|---|---|
| **qemu** | Redfish (bmcweb) | bmcweb + state managers + op-pwrctl | IPMI, sensors, EM, LPC snoop |
| **realhw** | IPMI (netipmid, lightweight) | IPMI host+LAN+SEL + state managers + op-pwrctl | **bmcweb**, sensors, EM, LPC snoop |

Both keep the host + chassis **state managers** +
`phosphor-discover-system-state@0` + `org.openbmc.control.Power@0`. On the real
64-MB board use the **realhw** profile (Redfish dropped, power over IPMI); the
QEMU Redfish loop uses the **qemu** profile.

## Real-hardware DRIVE result (2026-07-13, user-authorized live off→on)

Driven on the real AST2050 via op-pwrctl (`busctl … setPowerState i 0|1`), observed
on the plug power meter + GPIOH2 + pings. Full transcript:
`evidence/real-hw-f2sta/chassis-power-drive.txt`.

- **Power-OFF WORKS on silicon** (proven by three independent signals): `setPowerState
  i 0` → op-pwrctl drove `POWER_DOWN`(F0)→0 → plug **50 W → 4 W** (PSU standby / S5),
  host stopped pinging, `GPIO20` H-byte `0xF4→0x80` (**GPIOH2 1→0**). The standby-powered
  **BMC survived** the host power-off (kept pinging) — confirming the BMC/DDR2 is on the
  always-on rail.
- **Power-ON — SOLVED on silicon (2026-07-13): the A4-lockout gate.** The board only grants
  the BMC power-ON control when the control-lockout line **GPIOA4 (`ASUS_BMC_CTL_LOCKOUT_N`)**
  is a real GPIO output driven **HIGH** (=1, "BMC in control"). A4's pad defaults to the
  **PHYLINK** alt-function (`SCU74[25]=1`), so a stock image left A4 un-controllable → the
  board never handed over power-on authority → `CTL_REQ_POWERUP_N` (B1) was silently ignored
  (PSU stayed at standby) while force-OFF (F0) always worked. B1/F0/B6 were already GPIO-mode
  (`SCU74[2]=0`, `SCU80[14]=0`) — A4 alone was the gate. **Fix:** reclaim A4 (unlock SCU
  `0x1e6e2000=0x1688A8A8`; clear `SCU74[25]`), drive A4=1, then the Raptor **pulse**
  (`F0=1; B6=0+B1=0; sleep 1; B6=1+B1=1`) — NOT op-pwrctl's held level (which deadlocks by
  holding `RESET_OUT` asserted until pgood). The board *does* hold the reset net low while
  off, but that's normal S5 behavior — once A4 grants control and POWERUP pulses, the board
  raises the rail and releases reset itself. **Result on the real AST2050: plug 3 W → 103 W,
  GPIOH2 → 1, host PXE-booted, and the BMC stayed alive throughout — a full BMC on↔off toggle
  with NO AC-cycle.** eth0 is unaffected by the `SCU74[25]` clear (ftgmac100 polls the
  RTL8201CP over MDIO, `irq=POLL`, not the PHYLINK pin). Evidence:
  `evidence/real-hw-f2sta/power-on-A4-fix.txt`. Wired into the image via
  `recipes/power/` (kgpe-power-gpio-init.service + kgpe-power.sh + the
  obmc-power-{start,stop}@ drop-ins). Raptor never HW-validated power-on (its
  `asus_power_on_board` wrapper is also buggy), so this A4 requirement was undocumented.
- **Also observed:** phosphor `CurrentPowerState`/IPMI front-end did **not** track op-pwrctl's
  live `pgood` 1→0 transition (stayed "On" through the off) — a separate state-manager wiring
  gap; op-pwrctl `pgood` + plug/GPIOH2 are the ground truth.

QEMU still demonstrates the full on/off/reset drive (the modeled latch accepts the held
level); real silicon needs the pulse fix for the ON direction.

## Real-hardware bring-up — the intended IPMI path

On the real 64-MB board boot the **realhw** profile (bmcweb masked) and drive
power over **IPMI**:

```sh
ipmitool -I lanplus -H 192.168.66.2 -U root -P 0penBmc chassis power status
ipmitool -I lanplus -H 192.168.66.2 -U root -P 0penBmc chassis power on
ipmitool -I lanplus -H 192.168.66.2 -U root -P 0penBmc chassis power off
ipmitool -I lanplus -H 192.168.66.2 -U root -P 0penBmc chassis power cycle
```

This exercises exactly the phosphor-state-manager → op-pwrctl → GPIO path proven
in QEMU. `chassis power status` reflects GPIOH2/pgood. Confirm the modeled loop
first in QEMU (`f2-power-control-test.py`, both `--driver redfish` and
`--driver sysfs`), then repeat on hardware over IPMI. The KGPE-D16 `qemu` profile
Redfish loop is the API-path proof; the `realhw` IPMI path is the one that fits
the 64-MB board.

Two cautions on the request lines themselves:

- **The GPIO request lines drive the real board's power.** GPIOB1/F0/B6 engage /
  force-off / reset mainboard power; a wrong drive powers the host on or off for
  real. Recoverable only by a power-cycle. Bring up with the board **off** and
  verify GPIOH2 (`STA_LINE_POWER`) tracks the front-panel state first (read-only)
  before driving any request line.
- **Validate the SCU pinmux + polarity** (HW-WIRING §1.4) over P2A/JTAG AHB
  before trusting the lines: GPIOB1/B6/A4/H2 share pins with SPI-flash / PHY /
  I2C7, so a wrong SCU write can disturb boot flash or the NIC.

The bare-metal `peripherals/power/fwtest.c` `.elf` runs unchanged on the rig
(RPi JTAG/serial) to diff the `[FWT]` transcript against QEMU — the register-level
equality proof.
