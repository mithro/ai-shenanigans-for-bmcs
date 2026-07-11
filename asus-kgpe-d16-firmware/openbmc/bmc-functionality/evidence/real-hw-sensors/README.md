# F3 real-hardware sensor status (AST2050 @ 192.168.66.2)

Captured **non-disruptively** on 2026-07-12 while the rig was running F5's IPMI
image and F4 (SOL) was actively (non-disruptively) using it — so the board was
**not** rebooted onto the F3 kernel.

- `ipmi-sdr-list.txt` / `ipmi-sdr-{fan,temp,volt}.txt` — `ipmitool -I lanplus`
  from the Pi to the live board. Every sensor reads **disabled / ns**, exactly
  like the QEMU baseline (`../qemu-sensors/ipmi-sdr-baseline.txt`): the kernel the
  board is currently running (F5/rxfix `uImage`) has **no `&i2c1` w83795 DTS
  node** and the un-modernised w83795 driver, so no hwmon device backs the SDRs.

## Full real-HW sensor read — deferred (rig in use), tool ready

The real Nuvoton/Winbond **W83795G is present** on this board — the
hardware-inventory `sensors.txt` shows `w83795g-i2c-14-2f` on the host-side
SP5100 SMBus, and it is dual-homed to the BMC's I2C bus 1 @ 0x2f (Raptor's
AST2050 OpenBMC port taps it there; `HW-WIRING-power-sensors.md` §2.1, high
confidence). Reading it through OpenBMC on the real board is identical to the
proven QEMU flow and needs the board booted on the **F3 kernel** (CONFIG_SENSORS_
W83795 + the `hwmon@2f` DTS node + the 0003 modern-hwmon patch) with the W83795
phosphor-hwmon config in the NFS export — a **state-mutating P2A cold-boot** that
would displace F5's live IPMI evidence and interrupt F4. Deferred until the rig
is free; run:

```
uv run f3-realhw-sensors.py deploy  --pi asus-bmc --export /srv/nfs/openbmc-full
#  (then P2A-boot the board with uImage-kgpe-d16 + aspeed-bmc-asus-kgpe-d16.dtb,
#   64 MB, F5 'realhw' masks so phosphor-hwmon + IPMI fit)
uv run f3-realhw-sensors.py capture --pi asus-bmc --board 192.168.66.2
uv run f3-realhw-sensors.py revert  --pi asus-bmc --export /srv/nfs/openbmc-full
```

Expected (from the QEMU proof): the real W83795G answers at i2c-1/0x2f, the same
SDRs flip from `disabled` to real fan RPM / rail volts / die degC.
