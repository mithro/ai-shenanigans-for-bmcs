# Hardware access — Raspberry Pi lab bridges

Two Raspberry Pi 4B **bridges** put the target boards on the network. Each Pi
carries the JTAG / UART / SPI-flash / Ethernet harnesses to one board and is
reachable over SSH, so the QEMU-developed firmware work can be exercised against
real silicon without being physically at the bench.

> **Verification:** every host-specific fact below was captured live on
> **2026-07-11** by SSH into both bridges (`ssh asus-bmc` / `ssh hppdu-bmc`);
> the command output is the evidence. The **KGPE-D16 target is powered and in
> active service** (remotely switchable — see *Board power* below). The **iPDU
> target still has no power connected**, so its target-side links — JTAG TAP
> IDCODE, UART boot log, Ethernet carrier — cannot be exercised yet.

## The two bridges at a glance

| Bridge host (`.iot.welland.mithis.com`) | Target board | Target SoC | Target power | Wiring / board docs |
|---|---|---|---|---|
| `rpi4-asus-aspeed2050-dev` | ASUS KGPE-D16 BMC | ASPEED **AST2050** (ARM926EJ-S) | **ON** — remotely switchable (Tasmota `au-plug-10`) | [`asus-kgpe-d16-firmware/RPI4-OPENOCD-JTAG-WIRING.md`](asus-kgpe-d16-firmware/RPI4-OPENOCD-JTAG-WIRING.md) · [`asus-kgpe-d16-firmware/HARDWARE-ACCESS.md`](asus-kgpe-d16-firmware/HARDWARE-ACCESS.md) |
| `rpi4-hppdu-dev` | HPE iPDU (AF531A) | Digi **NS9360** (ARM926EJ-S) | not connected | [`hpe-ipdu-firmware/HEADERS-J1-J6.md`](hpe-ipdu-firmware/HEADERS-J1-J6.md) |

Both target SoCs are ARM926EJ-S (EmbeddedICE-RT over raw JTAG), which is why the
same debug tooling applies to both — see the adapter comparison in
[`hpe-ipdu-firmware/HEADERS-J1-J6.md`](hpe-ipdu-firmware/HEADERS-J1-J6.md).

## Bridge platform (both Pis)

- Raspberry Pi 4B, **Debian GNU/Linux 13 (trixie)**, kernel
  `6.18.34+rpt-rpi-v8`, `aarch64`.
- **OpenOCD** `0.12.0+dev-snapshot (2026-02-16)` installed.
- Logins `tim` (uid 1000) and `claude` (uid 1001) are both in the
  hardware-access groups: `dialout` (serial), `plugdev`, `gpio`, `spi`, `i2c`,
  `netdev`, plus `sudo`.
- A single onboard NIC `eth0` (`bcmgenet`) + `wlan0` (`brcmfmac`) are the Pi's
  own management path; the USB adapters below are the *target-facing* links.

---

## `rpi4-asus-aspeed2050-dev` — ASUS KGPE-D16 / AST2050

| Attached device | USB ID | Exposes | Purpose |
|---|---|---|---|
| **ULX3S FPGA (12F, v3.0.8)** — onboard FT231X | `0403:6015` | `/dev/serial-ulx3s` (= `/dev/serial/spispy` = `ttyUSB0`) | [spispy](https://github.com/osresearch/spispy) SPI-flash **emulation** of the BMC boot flash |
| **2× RTL8153 USB Gb Ethernet** | `0bda:8153` (×2) | `eth-bmc`, `eth-host` | The two AST2050 BMC NICs (see *Target networks*) |
| **Prolific PL2303 USB-serial** | `067b:2303` | `/dev/serial-com1` (= `ttyUSB1`) | x86 **host COM1** (3F8h) — BIOS/OS serial console, 115200 8N1 |
| **Magewell XI100DUSB-HDMI** | `2935:0001` | `/dev/video0` | Capture of the host VGA/HDMI display |

- **JTAG + the BMC-console UART are wired to the Pi's own 40-pin GPIO header**
  (bit-bang JTAG + the Pi's PL011 `ttyAMA0`), per
  [`RPI4-OPENOCD-JTAG-WIRING.md`](asus-kgpe-d16-firmware/RPI4-OPENOCD-JTAG-WIRING.md).
  The ULX3S is dedicated to spispy flash emulation, **not** JTAG.
- **JTAG is hardware-verified working (2026-07-10):** TAP IDCODE `0x07926f0f`,
  RTCK echo 64/64, halt/resume run-control, AHB reads over JTAG
  (`SCU7C=0x00000202`, independently matching culvert-over-P2A), and a faithful
  DDR2 init (`ddr2-init.tcl`) — DRAM read-backs pass.
- OpenOCD configs are committed in
  [`asus-kgpe-d16-firmware/openocd/`](asus-kgpe-d16-firmware/openocd/)
  (`rpi4-jtag.cfg` + `ast2050.cfg` + `kgpe-d16-bmc.cfg`); live working copies —
  plus `ddr2-init.tcl`, `first-contact.sh`, `rtck-echo-test.py` — sit in
  `~/openocd-bmc/` on the Pi.

### Serial map

| udev name | Line | State |
|---|---|---|
| `/dev/serial-bmc-console` → `ttyAMA0` | Pi PL011 GPIO UART ↔ **BMC UART2** (`0x1e784000`) | Proven readable at **1200 baud** (vendor firmware and our kernel consoles); higher rates untested |
| `/dev/serial-com1` → `ttyUSB1` | PL2303 ↔ **x86 host COM1** (3F8h/IRQ4) | 115200 8N1 — **owned by the `kgpe-seriald` daemon; never attach a second reader** (see [`asus-kgpe-d16-firmware/HARDWARE-ACCESS.md`](asus-kgpe-d16-firmware/HARDWARE-ACCESS.md)) |
| `/dev/serial-ulx3s` (= `/dev/serial/spispy`) → `ttyUSB0` | ULX3S FT231X | spispy tooling |

### Target networks (verified live, both UP)

| Interface | MAC | Driver | IP | Role |
|---|---|---|---|---|
| `eth-bmc` | `00:e0:4c:68:00:fc` | `r8152` | `192.168.66.1/24` | BMC network — TFTP + NFS |
| `eth-host` | `00:e0:4c:68:00:23` | `r8152` | `192.168.77.1/24` | Host network — PXE |

> Note: the 2026-07-07 revision of this table had the two MACs swapped; the
> mapping above is the live 2026-07-11 state (`ip -br link` / `ip -br addr`).

Services running on the bridge:

- **TFTP for the BMC** — dnsmasq (`--port=0 --enable-tftp`) on `eth-bmc`,
  root `/srv/tftp-bmc/`, staged with the current kernels/DTBs/initrds
  (`uImage-kgpe-d16-g3vic`, `kgpe-g3vic.dtb`, `initrd-nfsbmc.cpio.gz`, …) for
  U-Boot `tftp` loads.
- **NFS for the BMC** — `/srv/nfs/bmc` and `/srv/nfs/openbmc` exported to
  `192.168.66.0/24` (`rw,no_root_squash`) for NFS-root userspace.
- **PXE for the x86 host** — a second dnsmasq (`/srv/pxe/dnsmasq.conf`) on
  `eth-host`: DHCP `192.168.77.50–150` + TFTP `pxelinux.0`, boots the host into
  SystemRescue.
- Live addresses: the x86 host answers at **`192.168.77.138`** (ping verified
  2026-07-11). The BMC takes **`192.168.66.2`** when running U-Boot or our
  kernel; it was parked idle after a JTAG session at capture time, so it was
  not answering ping.

### Board power (Tasmota `au-plug-10`)

Mains power to the whole board is a Tasmota smart plug, HTTP-controlled from
the Pi (no auth):

```sh
curl -s 'http://au-plug-10/cm?cmnd=Power'        # query -> {"POWER":"ON"}
curl -s 'http://au-plug-10/cm?cmnd=Status%208'   # power meter (W, V, A)
# 'Power%20On' / 'Power%20Off' / 'Power%20TOGGLE' switch mains —
# STATE-MUTATING: coordinate first (see below)
```

Verified 2026-07-11: `{"POWER":"ON"}`, board drawing **49 W** (232 V, 0.239 A).

### Rig coordination (IMPORTANT)

Several agent/operator sessions share this one physical rig. The shared
protocol is **`/home/claude/HARDWARE-COORDINATION.md` on the Pi**: read it and
append your intent *before* any state-mutating action (power switching, resets,
flash/AHB writes, driving the JTAG lines); read-only observation may run
concurrently.

The full host-control reference (BIOS setup over the serial console, video
capture, keyboard injection, power procedures, boot gotchas) is
[`asus-kgpe-d16-firmware/HARDWARE-ACCESS.md`](asus-kgpe-d16-firmware/HARDWARE-ACCESS.md).

---

## `rpi4-hppdu-dev` — HPE iPDU (AF531A) / NS9360

Re-verified 2026-07-11 — unchanged since the 2026-07-07 capture:

| Attached device | USB ID | Exposes | Purpose |
|---|---|---|---|
| **TIAO TUMPA** (FT2232H, dual-channel) | `0403:8a98` | ch A = MPSSE **JTAG**, ch B = UART → `/dev/ttyUSB0` | NS9360 ARM926EJ-S debug + console. OpenOCD ships `interface/ftdi/tumpa.cfg`. |
| **Apple USB Ethernet [A1277]** | `05ac:1402` | `eth-pdu` | The iPDU network link |

- `eth-pdu` (`asix` driver): **NO-CARRIER** — the target board is still
  unpowered, so no target-side link can light up.
- On this bridge `/dev/ttyUSB0` is group `plugdev` (not `dialout`); the
  `claude` and `tim` accounts are members of both.

---

## Interface naming

The target-facing USB NICs are given **persistent semantic names** by udev
(`eth-bmc` / `eth-host` / `eth-pdu`) rather than the kernel's enumeration-order
`ethN`. Names are stable across reboots and USB re-enumeration, so scripts can
address "the BMC NIC" without guessing which port came up first. `eth0` on each
Pi is always the onboard management NIC.

---

## SSH access

A **dedicated key** authenticates to both bridges as either account:

- Key: `~/.ssh/rpi-bmc-dev` (ed25519),
  fingerprint `SHA256:IYBiksgF9yO9vy9OZ0UYIi8qHIPI5PZDDYhl9l8ley4`.
- Public half (present in `~claude/.ssh/authorized_keys` and
  `~tim/.ssh/authorized_keys` on both hosts):

  ```
  ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFe9rHa2veQIe5r8iU8pHJQZSCFkuqaPXX5dzywcvxLA rpi-bmc-dev claude+tim@rpi4-bmc-bridges
  ```

- Account **`claude`** (uid 1001): normal user, home `/home/claude`, shell
  `/bin/bash`, **passwordless sudo** (`/etc/sudoers.d/claude`, mode `0440`,
  validated with `visudo -cf`). The account password is **locked** — key-only
  login. Account `tim` retains its existing RSA key in addition to this one.

### SSH config aliases

Convenience `Host` blocks (in `~/.ssh/config_extra`, which is `Include`d before
the `*.mithis.com` wildcard so its `User`/`IdentityFile` win) pin auth to the
dedicated key via `IdentitiesOnly yes`:

| Alias | Logs in as | Host |
|---|---|---|
| `ssh asus-bmc` | `claude` | `rpi4-asus-aspeed2050-dev.iot.welland.mithis.com` |
| `ssh hppdu-bmc` | `claude` | `rpi4-hppdu-dev.iot.welland.mithis.com` |
| `ssh asus-bmc-tim` | `tim` | (same asus host) |
| `ssh hppdu-bmc-tim` | `tim` | (same hppdu host) |

The `claude` aliases also set `ClearAllForwardings yes` to drop the
clipboard-over-SSH `RemoteForward` (it targets `tim`'s homedir and would warn
under a different account).

### Provisioning (reproducible)

The `claude` account was created idempotently on each bridge with (as `tim`,
who has passwordless sudo):

```sh
# 1. normal user with home + bash
sudo useradd --create-home --shell /bin/bash claude

# 2. mirror the hardware/admin groups (only those present on the host)
for g in sudo adm dialout cdrom audio video plugdev users input render \
         netdev spi i2c gpio; do
  getent group "$g" >/dev/null && sudo usermod -aG "$g" claude
done

# 3. passwordless sudo, validated
printf 'claude ALL=(ALL) NOPASSWD:ALL\n' | sudo tee /etc/sudoers.d/claude
sudo chmod 0440 /etc/sudoers.d/claude
sudo visudo -cf /etc/sudoers.d/claude

# 4. authorise the dedicated key for both claude and tim
PUB="$(cat ~/.ssh/rpi-bmc-dev.pub)"    # run from the workstation holding the key
for u in claude tim; do
  sudo install -d -m 700 -o "$u" -g "$u" /home/"$u"/.ssh
  echo "$PUB" | sudo tee -a /home/"$u"/.ssh/authorized_keys
  sudo chown "$u:$u" /home/"$u"/.ssh/authorized_keys
  sudo chmod 600 /home/"$u"/.ssh/authorized_keys
done
```

---

## Setup gaps / TODO (re-checked 2026-07-11)

- **Serial-over-network is still not set up** on either bridge — none of
  `ser2net` / `socat` / `tio` / `picocom` / `minicom` / `screen` are installed.
  Set the line speed before attaching (`stty -F <dev> <baud>`). Known line
  rates: BMC console **1200 8N1** (proven); host COM1 **115200 8N1** (managed
  by the `kgpe-seriald` daemon — do not attach to it directly); iPDU console
  expected 115200 8N1 (unverified — no power).
- **No NS9360 OpenOCD config is committed.** The AST2050 side is done
  (committed configs + hardware-verified run-control); for the NS9360 start
  from `interface/ftdi/tumpa.cfg` + a generic `arm926ejs` target.
- **iPDU board power is not connected** — the single gate on all NS9360 live
  validation (JTAG TAP, boot log, `eth-pdu` carrier).

(Resolved since the 2026-07-07 capture: KGPE-D16 board power — now remotely
switchable and ON; ASUS-side Ethernet bring-up — both target NICs UP with
static IPs and TFTP/NFS/PXE serving.)

---

## See also

- [`asus-kgpe-d16-firmware/HARDWARE-ACCESS.md`](asus-kgpe-d16-firmware/HARDWARE-ACCESS.md)
  — full KGPE-D16 rig control: BIOS over serial, video capture, keyboard
  injection, power procedures, boot gotchas.
- [`asus-kgpe-d16-firmware/RPI4-OPENOCD-JTAG-WIRING.md`](asus-kgpe-d16-firmware/RPI4-OPENOCD-JTAG-WIRING.md)
  — full RPi4↔AST2050 JTAG/UART/SPI wiring, pinouts, and OpenOCD setup.
- [`asus-kgpe-d16-firmware/openocd/`](asus-kgpe-d16-firmware/openocd/)
  — the committed OpenOCD configs (hardware-verified 2026-07-10).
- [`asus-kgpe-d16-firmware/HEADER-PINOUTS.md`](asus-kgpe-d16-firmware/HEADER-PINOUTS.md)
  · [`asus-kgpe-d16-firmware/JTAG-HEADERS.md`](asus-kgpe-d16-firmware/JTAG-HEADERS.md)
  — KGPE-D16 debug-header pinouts.
- [`hpe-ipdu-firmware/HEADERS-J1-J6.md`](hpe-ipdu-firmware/HEADERS-J1-J6.md)
  — NS9360 debug headers + JTAG-adapter comparison.
