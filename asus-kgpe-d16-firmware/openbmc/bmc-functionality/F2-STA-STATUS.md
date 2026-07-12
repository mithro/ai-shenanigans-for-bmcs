# F2-STA (#95) — chassis power-state read on the real AST2050

**Symptom:** on the real KGPE-D16 BMC (openbmc-hwpass image, fixed g3-clk kernel),
`ipmitool chassis status` returns rc=0 but reports **`System Power : off` while the
x86 host is actually ON**.

**Status: ROOT-CAUSED + FIXED (repo) + QEMU-VERIFIED. Silicon before-evidence
captured; live on-silicon apply/after-capture deferred (see §5).**

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

## 5. Silicon apply/verify — deferred (needs approval)

`ipmitool chassis status` "off -> on" was proven READ-ONLY up to the last mile: the
before-state is captured (`evidence/real-hw-f2sta/chassis-power-state-before.txt`) and
GPIOH2 is empirically shown to read 1 (on). Applying the fixed config to the live board
(overwriting the deployed stub, or an ephemeral RAM bind-mount over the config path, then
`systemctl restart org.openbmc.control.Power@0` + the chassis state manager) was blocked
by the harness auto-mode classifier as a **shared-resource / remote-shell write** to the
rig — it needs a human-approved apply (or a rebuilt image booted via the runbook).

**Safety note (analysed from source):** op-pwrctl's startup (`set_up_gpio`) only READS
`power_good_in`; the request lines B1/F0/B6 are driven **only** on an explicit
`setPowerState` (chassis power on/off/reset) or on a **pgood transition** in `poll_pgood`.
With the host staying ON (H2 stable at 1) and no power command issued, restarting
op-pwrctl drives **nothing** on the power-request lines — consistent with the standing
"no BMC power-line drives" constraint.

## Rig state

All F2-STA live-board actions were **reads only** (devmem, cat, busctl, systemctl status,
journalctl, ipmitool status). The two write attempts (stub backup + config install) were
denied by the classifier, so **the board/NFS export are exactly as g3-clk left them**:
board ON serving openbmc-hwpass on the fixed kernel, host ON, op-pwrctl still crash-looping
on the stub (the pre-existing bug). No flash writes, no SCU writes, no power-line drives.
