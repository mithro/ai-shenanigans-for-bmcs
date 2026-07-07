# Hardware access — Raspberry Pi lab bridges

Two Raspberry Pi 4B **bridges** put the target boards on the network. Each Pi
carries the JTAG / UART / SPI-flash / Ethernet harnesses to one board and is
reachable over SSH, so the QEMU-developed firmware work can be exercised against
real silicon without being physically at the bench.

> **Verification:** every host-specific fact below was captured live on
> **2026-07-07** by SSH into both bridges (`ssh asus-bmc` / `ssh hppdu-bmc`);
> the command output is the evidence. **Target-board power is not yet
> connected**, so the harnesses can be wired and the adapters enumerated, but
> target-side links — JTAG TAP IDCODE, UART boot log, Ethernet carrier — cannot
> be exercised until power is applied.

## The two bridges at a glance

| Bridge host (`.iot.welland.mithis.com`) | Target board | Target SoC | Wiring / board docs |
|---|---|---|---|
| `rpi4-asus-aspeed2050-dev` | ASUS KGPE-D16 BMC | ASPEED **AST2050** (ARM926EJ-S) | [`asus-kgpe-d16-firmware/RPI4-OPENOCD-JTAG-WIRING.md`](asus-kgpe-d16-firmware/RPI4-OPENOCD-JTAG-WIRING.md) |
| `rpi4-hppdu-dev` | HPE iPDU (AF531A) | Digi **NS9360** (ARM926EJ-S) | [`hpe-ipdu-firmware/HEADERS-J1-J6.md`](hpe-ipdu-firmware/HEADERS-J1-J6.md) |

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
| **ULX3S FPGA (12F, v3.0.8)** — onboard FT231X | `0403:6015` | `/dev/ttyUSB0` | UART bridge **and** [spispy](https://github.com/osresearch/spispy) SPI-flash **emulation** of the BMC boot flash |
| **2× RTL8153 USB Gb Ethernet** | `0bda:8153` (×2) | `eth-bmc`, `eth-host` | The two AST2050 BMC NICs |

- **JTAG + UART are also wired to the Pi's own 40-pin GPIO header** (bit-bang
  JTAG + UART0), per [`RPI4-OPENOCD-JTAG-WIRING.md`](asus-kgpe-d16-firmware/RPI4-OPENOCD-JTAG-WIRING.md).
  The ULX3S is dedicated to spispy flash emulation, **not** JTAG.
- OpenOCD configs for this target live in
  [`asus-kgpe-d16-firmware/openocd/`](asus-kgpe-d16-firmware/openocd/)
  (`rpi4-jtag.cfg` + `ast2050.cfg` + `kgpe-d16-bmc.cfg`).

Target-facing NICs (verified `state=down` — no carrier until the board is powered):

| Interface | MAC | Driver |
|---|---|---|
| `eth-bmc` | `00:e0:4c:68:00:23` | `r8152` |
| `eth-host` | `00:e0:4c:68:00:fc` | `r8152` |

---

## `rpi4-hppdu-dev` — HPE iPDU (AF531A) / NS9360

| Attached device | USB ID | Exposes | Purpose |
|---|---|---|---|
| **TIAO TUMPA** (FT2232H, dual-channel) | `0403:8a98` | ch A = MPSSE **JTAG**, ch B = UART → `/dev/ttyUSB0` | NS9360 ARM926EJ-S debug + console. OpenOCD ships `interface/ftdi/tumpa.cfg`. |
| **Apple USB Ethernet [A1277]** | `05ac:1402` | `eth-pdu` | The iPDU network link |

Target-facing NIC (verified `state=down`):

| Interface | MAC | Driver |
|---|---|---|
| `eth-pdu` | `5c:f7:e6:8b:41:9b` | `asix` |

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

## Setup gaps / TODO

- **Serial-over-network is not yet set up.** None of `ser2net` / `socat` / `tio`
  / `picocom` / `minicom` / `screen` are installed. `/dev/ttyUSB0` defaults to
  9600 baud; **both targets are 115200 8N1** — set the line speed before
  attaching (`stty -F /dev/ttyUSB0 115200`), or install `ser2net`/`tio` for a
  networked console.
- **No NS9360 OpenOCD config is committed.** The AST2050 side has
  `asus-kgpe-d16-firmware/openocd/`; the NS9360 is the same ARM926EJ-S debug
  architecture, so a generic `arm926ejs` target config applies (start from
  `interface/ftdi/tumpa.cfg`).
- **Ethernet bring-up + IPs** for the target NICs is pending board power.
- **Board power is not connected** — the single biggest gate on live validation.

---

## See also

- [`asus-kgpe-d16-firmware/RPI4-OPENOCD-JTAG-WIRING.md`](asus-kgpe-d16-firmware/RPI4-OPENOCD-JTAG-WIRING.md)
  — full RPi4↔AST2050 JTAG/UART/SPI wiring, pinouts, and OpenOCD setup.
- [`asus-kgpe-d16-firmware/HEADER-PINOUTS.md`](asus-kgpe-d16-firmware/HEADER-PINOUTS.md)
  · [`asus-kgpe-d16-firmware/JTAG-HEADERS.md`](asus-kgpe-d16-firmware/JTAG-HEADERS.md)
  — KGPE-D16 debug-header pinouts.
- [`hpe-ipdu-firmware/HEADERS-J1-J6.md`](hpe-ipdu-firmware/HEADERS-J1-J6.md)
  — NS9360 debug headers + JTAG-adapter comparison.
