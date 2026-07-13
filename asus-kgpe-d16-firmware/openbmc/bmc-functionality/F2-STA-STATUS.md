# F2-STA (#95) — chassis power-state read on the real AST2050

**Symptom:** on the real KGPE-D16 BMC (openbmc-hwpass image, fixed g3-clk kernel),
`ipmitool chassis status` returns rc=0 but reports **`System Power : off` while the
x86 host is actually ON**.

**Status: ROOT-CAUSED + FIXED (repo) + QEMU-VERIFIED + VERIFIED ON SILICON
(2026-07-13). The fix was applied ephemerally to the live AST2050 and
`CurrentPowerState` flipped `Off -> On`; see §5 and
`evidence/real-hw-f2sta/chassis-power-state-after.txt`.**

## 1. The STATE-IN line is correct (empirical, read-only, host ON)

Read directly on the live board (dropbear devmem, host ON):

| Reg | Value | Meaning |
|---|---|---|
| `0x1E780020` (GPIO20 data, banks E-H) | `0xF403FFFF` | **H2 = bit26 = 1 => HIGH** |
| `0x1E780024` (GPIO24 dir, banks E-H)  | `0x0301000E` | **H2 = bit26 = 0 => INPUT** |
| `0x1E6E2074` (SCU74 multi-fn pin ctl) | `0x4204D000` | bit14 = SDA7/GPIO mux |

`/sys/kernel/debug/gpio` shows `gpio-570 (power-state-in)` = base 512 + **offset 58**
= bank H pin 2 (H2). So **GPIOH2 physically reads 1 (on) with the host on**, active-high
(1=on) — exactly matching Raptor's `STA_LINE_POWER`, the DTS `power-state-in` line name,
and the QEMU model (`GPIO20 bit26, 1=on`). **The DTS line index (H2=58) and polarity
(active-high) are RIGHT — the bug is NOT in the DTS or the pin mapping.**

## 2. Root cause: op-pwrctl crash-loops on an empty stub config

The chassis power-state loop on this image is:

```
GPIOH2 --(op-pwrctl reads)--> org.openbmc.control.Power `pgood`
       --> phosphor-chassis-state-manager CurrentPowerState --> ipmitool/Redfish
```

`op-pwrctl` (`org.openbmc.control.Power@0`, `power_control.exe`) reads its GPIO map from
the hardcoded path `/etc/default/obmc/gpio/gpio_defs.json`. **The deployed file is the
empty upstream stub** (`{"_comments":"This file should be overridden ..."}`), shipped by
`meta-phosphor/recipes-phosphor/skeleton/obmc-libobmc-intf_git.bb`. With no
`gpio_configs` object, op-pwrctl aborts at startup:

```
ERROR:gpio_configs.c:195:read_gpios: assertion failed: (configs != NULL)
Bail out! ... (core-dump; restart counter 60+)
```

Because op-pwrctl never runs, there is no `pgood` property, so
`phosphor-chassis-state-manager` keeps `CurrentPowerState =
xyz.openbmc_project.State.Chassis.PowerState.Off` — and IPMI/Redfish report the host as
off, regardless of the (correct) GPIOH2 read. The repo already contained the *correct*
`gpio_defs.json` (`bmc-functionality/gpio_defs.json`, PGOOD=H2, B1/F0/B6 out) and the
image pulled in `phosphor-skeleton-control-power`, but **nothing installed that config
over the stub** — the missing half of the loop.

Verified against the upstream `openbmc/skeleton` source
(`op-pwrctl/power_control_obj.c`, `libopenbmc_intf/{gpio_configs,gpio,gpio_json}.c`):
`read_gpios` requires the top-level `gpio_configs` object; `power_good_in` is read as a
**raw active-high input** (no inversion); the pin string `"H2"` resolves to gpiochip0
offset 58; and the config schema (`power_config.power_good_in` + `power_up_outs`
[required] + `reset_outs`/`latch_out`/`pci_reset_outs` [optional]) matches the repo file
exactly.

## 3. Fix (repo, persistent)

`recipes/power/obmc-libobmc-intf_%.bbappend` + `recipes/power/files/gpio_defs.json`
(byte-identical to `bmc-functionality/gpio_defs.json`) override the stub via the standard
`FILESEXTRAPATHS:prepend` pattern (the base recipe already has `file://gpio_defs.json` in
`SRC_URI`). Wired into `recipes/sync-to-openbmc-tree.sh` and documented in
`recipes/README.md` row (e). No DTS/model/kernel change — the state-in line was already
right.

## 4. QEMU verification (F2 model, current g3-clk build)

The F2 fwtests pass against the current QEMU (`.../bmc-g3-clk/.../qemu-system-arm`,
`-M kgpe-d16-bmc`):

```
power: off_at_reset PASS / on_after_powerup PASS (H2=1 after B1 pulse,
       h2.after_on=0x04000100 => bit26 set) / on_after_reset PASS /
       off_after_powerdown PASS  ->  RESULT: PASS (0 fails)
gpio:  RESULT: PASS (0 fails)
```

(The `integration/runner.py` default auto-selected a **stale Jul-1 sibling** QEMU
`.../d16-qemu/tmp/qemu-dev/build/qemu-system-arm` in which the modeled power latch does
not fire — an environment/harness artifact, unrelated to this fix and pre-existing on the
base branch. Pointing `build.py --qemu` at the current g3-clk build passes. This F2-STA
change touches only `openbmc/recipes/` — the QEMU model, DTS, and fwtests are untouched,
`git diff 49d2ca7 HEAD -- qemu-model qemu-firmware/dts` is empty.)

## 5. Silicon apply/verify — DONE (2026-07-13, user-approved)

The apply/after-capture was deferred in the earlier session (harness classifier blocked
the shared-rig write). With the user's explicit go-ahead ("Finish verifying the
power-state control & config on the real hardware") it was completed on the live AST2050.
Full transcript: `evidence/real-hw-f2sta/chassis-power-state-after.txt`. Summary:

1. **Ephemeral apply** (the shared NFS export is NOT touched; reverts on BMC reboot):
   streamed the repo `recipes/power/files/gpio_defs.json` to `BMC:/run/gpio_defs.json`,
   then `mount --bind /run/gpio_defs.json /etc/default/obmc/gpio/gpio_defs.json`,
   `systemctl reset-failed` + `restart org.openbmc.control.Power@0`.
2. **op-pwrctl went `active`, `NRestarts=0`** — the 793-restart crash-loop (assertion on
   the empty stub) is gone; it logged `Pgood state: 1` and `Started Phosphor Power0
   Control` with no assertion.
3. **`CurrentPowerState` flipped `Off -> On`** (busctl + obmcutil); `pgood = i 1`;
   `BMCState` advanced `NotReady -> Ready`. The bug is fixed on silicon.
4. **No power drive — empirically proven.** The request-line registers (`GPIO00 =
   0xF0FDDF10`, `GPIO20 = 0xE403FFFD`; B1/F0/B6 de-asserted) were **byte-identical before
   and after** the restart, and `GPIO04/24` show op-pwrctl never even configured the
   outputs (they stayed inputs) — matching the source contract below. Host `.138` kept
   pinging; plug telemetry steady ~50 W (no power event).

**Safety basis (source + empirical):** op-pwrctl's `set_up_gpio` performs **no
`gpio_write()`** at startup — it only `gpio_read`s `power_good_in` and sets its internal
pgood/state. Outputs are driven **only** on an explicit `setPowerState` or a **pgood
transition** in `poll_pgood` (`if (pgood_state != current)`). With H2 stable at 1 and no
power command, restarting the daemon drives nothing — confirmed by the guard reads in (4).

## Rig state

The only mutating action was the **ephemeral tmpfs bind-mount** of the corrected config
+ a userspace daemon restart. **No flash writes, no SCU writes, no power-line drives, no
change to the shared NFS export.** A BMC reboot reverts to the stub; the *persistent* fix
is the repo bbappend (`recipes/power/`) which bakes this config into the next image build.
Board left ON serving openbmc-hwpass (fixed g3-clk kernel), host ON, op-pwrctl now healthy
and reporting `PowerState.On`.
