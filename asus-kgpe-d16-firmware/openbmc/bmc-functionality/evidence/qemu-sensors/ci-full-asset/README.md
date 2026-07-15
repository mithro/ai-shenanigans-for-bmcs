# Sensors CI on the published (quanta-q71l) asset — tier split

The new `f3-sensors` CI job (in `d16-qemu-stack.yml`) runs `f3-sensor-test.py` over
the published OpenBMC rootfs asset (`openbmc-full-rootfs.tar`, MACHINE=quanta-q71l),
deploying the KGPE-D16 W83795G phosphor-hwmon config (`recipes/hwmon/files/hwmon@2f.conf`)
onto it first (the generic quanta-q71l asset does not carry it).

## Result on that asset (this evidence)
- **Tier 1 — QEMU W83795 model + kernel hwmon bind (sysfs): PASS.**
  `f3-openbmc-full-tier1pass-tier2warn.txt`: `w83795 at /sys/class/hwmon/hwmon0:
  6 spinning fans` — `fans(RPM): [5113, 4963, 4804, 3901, 3750, 3600]`. This is the
  enforced gate: it proves the modeled W83795G feeds real values through the modeled
  I2C bus and the kernel `w83795` driver binds and reads them.
- **Tier 2 — full IPMI SDR with KGPE-D16 rail names: WARN (not enforced here).**
  `ipmi-sensor-generic-na.txt`: the generic quanta-q71l static SDR shows `fan1..fan8 = na`.
  Surfacing the W83795 readings over IPMI with the proper KGPE-D16 rail names
  (`CPU_DIODE`, `VCORE0`, `P12V`, …) needs the kgpe-d16 IPMI **sensor map**
  (`q71l-ipmi-sensor-map-native`), which is COMPILED into the kgpe-d16 image — not a
  runtime-deployable file. On the kgpe-d16 image (local `openbmc-img2` build) BOTH
  tiers PASS with real values (`CPU_DIODE 41.9 °C`, `VCORE0 0.960 V`), and that full
  IPMI-SDR result is what the real-silicon side proved (18 live sensors over IPMI).

## Follow-up (build, out-of-band)
For the CI job to enforce tier 2 as well, the published asset must be rebuilt to
include the kgpe-d16 sensor recipes (`kgpe-d16-hwmon-config` + `q71l-ipmi-sensor-map`)
— a `build-openbmc-rootfs.yml` change. Until then the CI job enforces the sensor
MODEL + kernel bind (tier 1); the full IPMI-SDR surfacing is proven locally on the
kgpe-d16 image and on real silicon, and documented in `../README.md` / `../../F3-SENSORS.md`.
