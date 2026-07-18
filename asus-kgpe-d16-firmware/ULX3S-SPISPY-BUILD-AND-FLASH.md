# Building and flashing the ULX3S spispy gateware

How to build the [spispy](https://github.com/osresearch/spispy) SPI-flash
emulator gateware, load it onto the ULX3S (ECP5-12F), and verify the control
link — the toolchain half of emulating the ASUS KGPE-D16 BMC boot flash.

For **where the wires go** (ULX3S GPIO ↔ the `BMC_FW1` socket) see the companion
[`ULX3S-SPISPY-BMC-FLASH-WIRING.md`](ULX3S-SPISPY-BMC-FLASH-WIRING.md). This
document is only about software: toolchain, source, build, load, dev nodes.

## The two-host model

| Host | Role | ULX3S attached? |
|------|------|-----------------|
| Workstation (x86-64) | Build the bitstream; primary dev | No |
| `asus-bmc` Raspberry Pi 4B (aarch64) | Build **and** load onto the ULX3S; drives the rig | **Yes** (USB) |

The ULX3S lives on the Pi. A bitstream built on either host must load and
enumerate its USB-CDC control port identically, so both hosts run the **same
pinned oss-cad-suite** and clone the **same fork to the same path**
(`~/github/mithro/spispy`).

> **Network note:** outbound SSH (port 22) is firewalled on this network, so
> GitHub is cloned/pushed over **HTTPS**, and the Pi is reached through the
> WireGuard tunnel (`10.1.90.0/24`), not public SSH.

## Source: the mithro/spispy fork

Upstream `osresearch/spispy` is forked to
[`mithro/spispy`](https://github.com/mithro/spispy). Clone the fork (HTTPS) to
the canonical path on **both** hosts:

```sh
git clone https://github.com/mithro/spispy.git ~/github/mithro/spispy
```

Modifications are developed in dedicated branches/worktrees off that fork. The
modern-toolchain build fix lives on branch `claude/oss-cad-suite-build`:

- **`uart: declare tx signals at module scope for \`default_nettype none`** —
  `spispy.v` sets `` `default_nettype none `` and `` `include ``s `uart.v`, whose
  transmit datapath signals (`serial_txd_data/strobe/ready`) were declared
  inside a `generate` branch but referenced by the module-scope `uart_tx`
  instance. Old yosys silently created undriven implicit nets; yosys 0.67
  (oss-cad-suite) correctly errors. The fix hoists them to module scope. No
  functional change for the spispy build (which uses `FIFO=512`).

## Toolchain: oss-cad-suite

[oss-cad-suite](https://github.com/YosysHQ/oss-cad-suite-build) bundles
everything the build needs — `yosys`, `nextpnr-ecp5`, `ecppack`, `ecppll`,
`openFPGALoader`, `fujprog`. Pinned release **`2026-07-18`** on both hosts.

**Workstation (x86-64):**
```sh
curl -fL -o ~/oss-cad-suite-linux-x64-20260718.tgz \
  https://github.com/YosysHQ/oss-cad-suite-build/releases/download/2026-07-18/oss-cad-suite-linux-x64-20260718.tgz
tar -C ~ -xzf ~/oss-cad-suite-linux-x64-20260718.tgz
export PATH=~/oss-cad-suite/bin:$PATH
```

**Pi (aarch64):** the `linux-arm64` asset. Easiest is the bootstrap script,
which also clones the fork and installs the udev rules:
```sh
uv run ~/github/mithro/ai-shenanigans-for-bmcs/asus-kgpe-d16-firmware/spispy/setup_pi.py
```

Verify the tools resolve:
```sh
yosys --version && nextpnr-ecp5 --version && openFPGALoader --Version
```

## Build the bitstream

```sh
export PATH=~/oss-cad-suite/bin:$PATH
cd ~/github/mithro/spispy/verilog
make PRJTRELLIS= spispy.bit
```

`PRJTRELLIS=` makes the Makefile call `ecppll` from `PATH` (oss-cad-suite)
instead of a hard-coded prjtrellis checkout. The pipeline is:

```
ecppll ─► pll_132.v ─┐
                     ├─► yosys synth_ecp5 ─► spispy.json
spispy.v + usb/*.v ──┘
spispy.json ─► nextpnr-ecp5 --25k --lpf ulx3s_v20.lpf ─► spispy.config
spispy.config ─► ecppack --idcode 0x21111043 ─► spispy.bit
```

`--idcode 0x21111043` is the ECP5 **12F** id (the ULX3S v3.0.8 here). For a 25F
board use `0x41111043`.

**Verified on the workstation (2026-07-18):** clean build, `nextpnr` and
`ecppack` both exit 0, producing `spispy.bit` (228,411 bytes). The `make`
one-liner and the manual step-by-step give a byte-identical result.

## Load onto the ULX3S (on the Pi)

The ULX3S is programmed over its FT231X via `openFPGALoader`. Default is a
volatile **SRAM** load (gone on power-cycle) — ideal for iterating:

```sh
export PATH=~/oss-cad-suite/bin:$PATH
openFPGALoader -b ulx3s spispy.bit            # SRAM (volatile)
# openFPGALoader -b ulx3s -f spispy.bit       # persist to the ULX3S config flash
```

Success prints the detected `0x21111043` IDCODE and a `Done` when the bitstream
loads. `fujprog spispy.bit` is the alternative loader if needed.

### Cross-host flashing

Build on the workstation, copy the artifact to the Pi, load there:
```sh
scp ~/github/mithro/spispy/verilog/spispy.bit asus-bmc:/tmp/spispy.bit
ssh asus-bmc 'export PATH=~/oss-cad-suite/bin:$PATH; openFPGALoader -b ulx3s /tmp/spispy.bit'
```

## Dev-node naming (udev, on the Pi)

Two USB functions appear when the ULX3S is plugged in. The rules file
[`spispy/99-spispy-ulx3s.rules`](spispy/99-spispy-ulx3s.rules) gives them stable
names:

| Function | VID:PID | Stable node | Used by |
|----------|---------|-------------|---------|
| FT231X JTAG/UART bridge | `0403:6015` | `/dev/spispy-jtag` | `openFPGALoader`, `fujprog` |
| spispy soft-USB CDC-ACM control | `1d50:6130` | `/dev/spispy-ctrl` | `bin/spispy`, `bin/write-ram` |

The CDC VID/PID (`1d50:6130`, the Openmoko shared PID space) is set in
`verilog/usb/usb_serial_ctrl_ep.v`. The rules also set `ID_MM_DEVICE_IGNORE=1`
so ModemManager doesn't probe and corrupt the control stream.

Install (done automatically by `setup_pi.py`):
```sh
sudo cp spispy/99-spispy-ulx3s.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger
# the login user must be in 'plugdev' (Pi OS default); else usermod -aG plugdev
```

## Verify the USB-CDC control link

`bin/spispy` opens the CDC port and does a version handshake: it writes `!V` and
expects the device to reply `11111111` (see `bin/spispy` around the `# send a
version command` block). That round-trip is the liveness check that the
gateware's soft-USB stack came up:

```sh
cd ~/github/mithro/spispy
./bin/spispy -v -d /dev/spispy-ctrl        # expect:  Version: '11111111'
```

Do this for a bitstream built on **each** host to confirm cross-host parity.
Then load the SFDP table and a ROM image into the emulated flash DRAM:

```sh
./bin/write-ram 0x1000000 sfdp.bin  > /dev/spispy-ctrl   # SFDP at top of DRAM
./bin/write-ram 0x0        bmc.bin  > /dev/spispy-ctrl   # ROM image at 0x0
```

`bin/spispy` needs Perl's `Device::SerialPort`
(`sudo apt install libdevice-serialport-perl`).

## Status

| Step | State |
|------|-------|
| Fork `mithro/spispy` + `uart.v` build fix (branch `claude/oss-cad-suite-build`) | **Done** |
| oss-cad-suite `2026-07-18` on workstation | **Done** |
| Gateware builds on workstation → `spispy.bit` (228,411 B, idcode `0x21111043`) | **Done, verified** |
| Pi provisioning (`setup_pi.py`), udev rules, load onto ULX3S, USB-CDC handshake | **Pending — the `asus-bmc` Pi was offline (powered down) during setup** |

When the Pi is back online: run `setup_pi.py`, build (or `scp` the workstation
bitstream), `openFPGALoader -b ulx3s spispy.bit`, then `./bin/spispy -v -d
/dev/spispy-ctrl` to confirm the `11111111` handshake on both hosts' builds.
