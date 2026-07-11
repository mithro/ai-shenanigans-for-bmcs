# F3 QEMU sensor evidence — W83795G on the kgpe-d16-bmc machine

Boot: `qemu-system-arm -M kgpe-d16-bmc -m 256` (kernel #9 with the modernised
w83795 driver), OpenBMC fuller image over NFS (`/export/openbmc-f3sensors`, the
W83795 hwmon config installed at `ahb/apb/bus@1e78a000/i2c-bus@80/hwmon@2f.conf`).

- `hwmon-sysfs.txt` — the mainline w83795 driver reads the QEMU model's registers:
  fan1..6 = 4963/5113/4804/3600/3750/3901 RPM (fan7/8=0), in0/in1=1000 mV (VCORE),
  in12/13=3300 mV (3V3/3VSB), in14=3036 mV (VBAT), temp1=42250 mC (CPU diode),
  temp7/8=45000/47000 mC (SB-TSI DTS). This is the QEMU W83795G model, proven.
- `dbus-sensors.txt` — phosphor-hwmon publishes the readings on D-Bus
  (/xyz/openbmc_project/sensors/{fan_tach,temperature,voltage}/...).
- `ipmi-sdr-list.txt`, `ipmi-sensor.txt`, `ipmi-sdr-{fan,temp,voltage}.txt` —
  `ipmitool -I lanplus ... sdr/sensor` over LAN: 23 sensors read **ok** with real
  values (fan1=4900 RPM ... p3v3_scaled=3.26 V, p5v_scaled=4.99 V,
  p12v_scaled=11.97 V, pvcc_cpu0=0.96 V, p3v_vbat=3.01 V, temp1=41.90 C,
  temp2_inlet=44.97 C).
- `ipmi-sdr-baseline.txt` — the SAME SDRs BEFORE the driver fix / before the
  hwmon config: every sensor "disabled" (phosphor-hwmon couldn't read the legacy
  w83795 hwmon layout). The delta is the F3 work.
- `redfish-chassis.txt` — Redfish `/redfish/v1/Chassis` is an EMPTY collection:
  bmcweb surfaces sensors only when they are associated with a Chassis inventory
  item, and the quanta-q71l-based image ships no Chassis inventory for this board
  (an entity-manager gap, separate from the sensor read path). IPMI SDR — which
  reads the D-Bus sensors directly — is the working, real-HW-fit sensor channel.
