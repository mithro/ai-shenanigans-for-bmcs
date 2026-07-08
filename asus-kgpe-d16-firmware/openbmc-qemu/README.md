# Modern OpenBMC + Redfish in QEMU (Track A)

Per @mithro's "both — QEMU build + NIC in parallel": develop the modern OpenBMC +
**Redfish** stack in QEMU (full observability, testable) in parallel with the real-HW
NIC deep-dive. The phosphor/bmcweb userspace is SoC-agnostic, so the same image is the
basis for running on the real AST2050 (over the NFS root) once the NIC lands.

## Build (multi-hour Yocto build)
```sh
git clone https://github.com/openbmc/openbmc.git ~/openbmc
cd ~/openbmc
. setup romulus            # or palmetto (ast2400, ARM926 -- closest SoC to the AST2050)
bitbake obmc-phosphor-image
# image -> build/romulus/tmp/deploy/images/romulus/obmc-phosphor-image-romulus.static.mtd
```
Host deps needed: `chrpath diffstat gawk lz4 zstd file` (+ the usual gcc/python3/git).
Machine choice: **romulus** (ast2500) has the fullest QEMU + Redfish support;
**palmetto** (ast2400, ARM926EJ-S) is the closest SoC to the AST2050 (G3). Both share
the same phosphor/bmcweb userspace.

## Run + reach Redfish
```sh
asus-kgpe-d16-firmware/openbmc-qemu/run-openbmc-qemu.sh
# Redfish:  curl -k https://localhost:2443/redfish/v1
# login:    curl -k -u root:0penBmc https://localhost:2443/redfish/v1/Systems
# SSH:      ssh -p 2222 root@localhost   (pw 0penBmc)
```

## ✅ Verified (2026-07-09) — modern OpenBMC + Redfish RUNNING in QEMU

Built `obmc-phosphor-image` (6531 tasks, all succeeded) → 32 MB `.static.mtd`, booted it
in `qemu-system-arm -M romulus-bmc`. Confirmed:
- **Boots to userspace**: Phosphor OpenBMC, **Linux 6.18.38**, **systemd 259.5**,
  aspeed hardware watchdog active.
- **Redfish API answers** (bmcweb, TLS): `GET /redfish/v1` → ServiceRoot
  `#ServiceRoot.v1_15_0`, **RedfishVersion 1.17.0**; full tree (AccountService, Chassis,
  Systems, Managers, EventService, TelemetryService, UpdateService, SessionService).
- **Authentication works**: `-u root:0penBmc` returns the Systems/Chassis/Managers
  collections.
- **Remote power-control path works**: `POST /redfish/v1/Systems/system/Actions/
  ComputerSystem.Reset {"ResetType":"On"}` → **HTTP 204** (accepted, routed to
  phosphor-state-manager); `PowerState` read back via `/Systems/system`. Note: in bare
  QEMU `romulus-bmc` the host stays `Off` because only the BMC is modelled (no POWER9
  host or power GPIOs to drive) — the API/D-Bus path is proven; the physical transition
  needs real hardware. Boot-source override targets: Pxe/Hdd/Cd/Usb/BiosSetup.
- **Virtual KVM advertised**: Manager `GraphicalConsole.ServiceEnabled=true`,
  `ConnectTypesSupported=[KVMIP]` (the virtual-keyboard/vKVM path).
- Sensors endpoint answers (HTTP 200) but empty in bare QEMU (no emulated I2C sensor
  hardware); populates from `dbus-sensors`/hwmon on real hardware.

This satisfies the goal's "working OpenBMC Redfish API allowing remote control" **in the
QEMU vehicle**. The remaining step for the physical board is the kernel/NIC/machine
adaptation below.

## Path to the real AST2050
1. Prove OpenBMC + Redfish run + answer in QEMU (this dir).
2. Build/adapt an **ast2400-class kgpe-d16 machine** (device tree = our
   `dts/aspeed-bmc-asus-kgpe-d16-realhw.dts` + the AST2050 clock patch) so the image
   targets the real board.
3. Serve the OpenBMC rootfs over **NFS root** (Pi `/srv/nfs/bmc`) with our modern
   AST2050 kernel — needs the eth0 RMII-TX fix first (see `../MODERN-KERNEL-STATUS.md`,
   `../NIC-MAC-REGISTER-COMPARISON.md`).
