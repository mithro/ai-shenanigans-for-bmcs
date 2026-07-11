# F3 — Sensors: the KGPE-D16 W83795G, modelled in QEMU and read via OpenBMC

Goal: expose the KGPE-D16's fan / voltage / temperature sensors on OpenBMC over
IPMI (`ipmitool sdr`/`sensor`) and Redfish, in **QEMU** and on the **real
AST2050**. The board's sole hardware monitor is a **Nuvoton/Winbond W83795G** on
the BMC's I2C bus 1 at 0x2f (see `HW-WIRING-power-sensors.md` §2).

## Pieces

| Layer | Artifact | State |
|---|---|---|
| QEMU device model | `qemu-firmware/qemu/qemu/hw/sensor/w83795.c` (submodule branch `claude/w83795-sensor`) wired on `kgpe-d16-bmc` i2c1@0x2f | done, proven |
| Device tree | `qemu-firmware/dts/aspeed-bmc-asus-kgpe-d16.dts` — `&i2c1` + `hwmon@2f { compatible="winbond,w83795g"; }` | done |
| Kernel | `kernel/kgpe-d16.config` — `CONFIG_SENSORS_W83795[_FANCTRL]`; plus `kernel/patches/0003-*` modernising the driver's hwmon registration | done |
| OpenBMC | `w83795-hwmon.conf` — phosphor-hwmon channel→sensor map, installed at the device's OF path | done |
| Tests | `f3-sensor-test.py` (QEMU), `f3-realhw-sensors.py` (real board) | done |

## The QEMU W83795G model

`hw/sensor/w83795.c` is an I2C slave that faithfully implements the register-level
behaviour the mainline `drivers/hwmon/w83795.c` relies on:

* **Bank-switched register file** — index 0x00 is the Bank-Select register (low 3
  bits pick bank 0-3; bit 7 flips the vendor-ID readback), exactly what
  `w83795_detect()` probes.
* **Identification** — vendor 0xA3 (0x5C when bank bit 7 set), chip-id 0x79,
  device-id 0x50 (rev A), so both auto-detect and an explicit `w83795g`
  instantiation bind.
* **Channel-present control registers** pre-loaded with the KGPE-D16 coreboot
  configuration (`devicetree.cb`: `fanin_ctl1=0xff`, `volt_ctl1=0xff`/
  `volt_ctl2=0xf7`, `temp_ctl1=0x2a`/`temp_ctl2=0x01`, `DTSE=0x03`) → the driver
  enables fan1-8, the populated rails, the CPU thermal diode and the two
  per-socket DTS (AMD SB-TSI) die temperatures.
* **Measurement registers** pre-loaded with plausible readings for a running
  dual-Opteron board.
* **Shared VRLSB register (0x3C)** — on real silicon this latches the low bits of
  the most-recently-read measurement register; the model shadows the last read so
  the driver's `read(high byte)` then `read(VRLSB)` sequence reconstructs the full
  fan (12-bit), voltage (10-bit) and temperature (0.25 °C) values.

### Verified in QEMU (the model read by the kernel over sysfs)

Booting the `kgpe-d16-bmc` machine, the mainline driver binds
(`w83795 1-002f: hwmon_device_register()`), and `/sys/.../1-002f/*_input` reads
back the modelled values exactly:

```
fan1..6 = 4963 5113 4804 3600 3750 3901 RPM   (fan7/fan8 = 0, unpopulated)
in0/in1 = 1000 mV (VCORE0/1)   in12/in13 = 3300 mV (3VDD/3VSB)   in14 = 3036 mV (VBAT)
temp1 = 42250 mC (CPU diode)   temp7 = 45000 mC   temp8 = 47000 mC (SB-TSI die)
```

This proves the model + the DTS binding + the register semantics end-to-end.

## OpenBMC integration — and the mainline-driver gap it exposed

`ipmitool sdr` reads D-Bus sensor objects that **phosphor-hwmon** publishes from
`/sys/class/hwmon/hwmonN/{name,<type>N_input}`. The stock mainline
`drivers/hwmon/w83795.c` uses the **legacy** `hwmon_device_register()` API: it
creates the sensor attributes on the *i2c client* device (`hwmonN/device/…`) and
leaves `hwmonN` **nameless and without `*_input` files**, so phosphor-hwmon reads
`hwmonN/fan1_input` → not found → every sensor shows `disabled` in `sdr`. This
gap is in Linux, independent of the QEMU model, and identical on real hardware.

**Fix (`kernel/patches/0003-hwmon-w83795-modern-hwmon-registration.patch`):** a
minimal conversion to `hwmon_device_register_with_info()` that exposes the
`*_input` channels (fan1-14, in0-20, temp1-14 incl. DTS as temp7-14) under
`hwmonN/` with a `name` file, reusing the driver's existing value computations
via a small read callback. The rich limit/alarm/pwm attributes stay on the i2c
client via the unchanged `w83795_handle_files()`. With this, phosphor-hwmon reads
the chip and `ipmitool sdr`/`sensor` and Redfish Thermal/Power show real values.

## Sensor-name caveat (image build vs. board)

The running OpenBMC image is built for the ast2400 **quanta-q71l** machine
(ARMv5TE = the AST2050 CPU), so the IPMI SDR *names* are that build's defaults
(`fan1-8`, `pvcc_cpu*`, `p3v3_scaled`, `temp*`). `w83795-hwmon.conf` maps the
W83795G channels onto those existing SDR names so real readings light them up
without an image rebuild; a KGPE-D16-proper naming (VCORE1/CPU1_DIE/…) needs a
rebuild with a kgpe-d16 sensor YAML (`HW-WIRING-power-sensors.md` §3.3).
