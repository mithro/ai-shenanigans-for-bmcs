# Real-hardware USB verification (#2 virtual media + #3b keyboard)

**Status:** the QEMU side is DONE and verified (`F6-USB-HOST.md`,
`evidence/f6-usb-host/03-two-vm-enumeration-PASS.txt` — a second host imports the
BMC gadget and reads `/dev/sda` + a `KEY_A` evdev event). This document is the
**ready-to-run** procedure for the **real AST2050 (KGPE-D16)** half.

> **Why it is not run from the build sandbox:** the AST2050 rig lives on the
> `192.168.66.0/24` BMC net behind the Raspberry-Pi bridge `asus-bmc`, which is the
> *only* host with a route to the board (`192.168.66.2`). That network is **not
> reachable from the CI/build sandbox** (ping 192.168.66.2 → 100 % loss; the bridge
> hostname does not resolve), so the steps below must be run from the Pi / a host on
> the rig net — exactly like `f3-realhw-sensors.py --pi asus-bmc` and the other
> real-HW scripts here. Nothing below is state-mutating beyond loading modules +
> attaching a USB/IP device (fully reversible: `usbip detach` + `modprobe -r`).

The AST2050 has exactly one USB block — the USB2.0 device/vhub @`0x1E6A0000` (no host
controller; `F6-USB.md`). So there are two silicon tests, in increasing fidelity:

---

## Test A — USB/IP over the rig network (function/enumeration half; no USB cabling)

Proves the **same gadget/descriptor/enumeration stack** that passed in QEMU works on
real silicon, using the network instead of a USB cable. Binds the gadget to the
`usbip-vudc` UDC (as in QEMU) and imports it on the Pi. **This is the tractable
first test.**

### Prereqs
- The board booted on the **patch-0007 kernel** built from this branch
  (`USBIP_VUDC=y` via `kernel/kgpe-d16-usbip.config`; the static-ARM usbip userspace
  is in the initramfs). Boot it the usual way (TFTP/`-kernel` or NFS-root; see
  `BUILD-NOTES.md` / the culvert P2A+TFTP path). Add `usbiphost usbipkbd` to the
  kernel cmdline so the export gate + keypress loop run (or run the gate's commands
  by hand from a shell).
- The Pi `asus-bmc` (usbip client): `sudo apt-get install -y usbip
  linux-modules-extra-$(uname -r)` (or the distro's usbip), then
  `sudo modprobe vhci-hcd`.

### Steps (on the Pi, which routes to 192.168.66.2)
```sh
# 1. Confirm the board exports the gadget:
usbip list -r 192.168.66.2
#    expect:  usbip-vudc.0: ... (1d6b:0104)

# 2. Attach it (imports into vhci-hcd; the "record connection" error is non-fatal):
sudo usbip attach -r 192.168.66.2 -b usbip-vudc.0

# 3. #2 virtual media — a new USB disk enumerates; read the magic at offset 512:
lsusb | grep -i 1d6b
NEW=$(ls -t /dev/sd? | head -1)
sudo dd if="$NEW" bs=1 skip=512 count=24
#    expect:  KGPE-D16-USBIP-VMEDIA-OK

# 4. #3b keyboard — the board's usbipkbd loop drives KEY_A; capture it:
KBDEV=$(grep -il vKVM /sys/class/input/event*/device/name | head -1 \
        | sed 's,/device/name,,;s,/sys/class/input,/dev/input,')
sudo timeout 6 dd if="$KBDEV" bs=24 count=64 2>/dev/null | hexdump -C | grep '01 00 1e 00 01 00 00 00'
#    a match = EV_KEY KEY_A press delivered to the (real) host

# 5. Clean up:
sudo usbip detach -p 00
```
PASS = steps 1–4 all succeed. This is the UDC-agnostic function half — **the same
proof QEMU gave, now on the real board's OpenBMC/kernel over the real network.**

---

## Test B — physical USB to a real host (full silicon datapath; highest fidelity)

Exercises the **real AST2050 vhub silicon** (register/IRQ/EP-DMA/PHY), not usbip.
Bind the gadget to the real vhub UDC and let a physically-connected host enumerate.

### Steps
1. Boot the patch-0007 kernel (the G3 vhub fix — `VHUB-G3-PORT-PLAN.md` — must be in;
   the mainline driver hangs the SoC on the G3, see `usb-vhub-silicon-boundary.txt`).
2. Build the same configfs gadget (HID keyboard + mass_storage), but bind it to a
   **real** vhub port UDC instead of usbip-vudc:
   `echo 1e6a0000.usb-vhub:p1 > .../usb_gadget/g/UDC`.
3. Physically connect the AST2050 board's **USB device port** to a host PC.
4. On the host: confirm a USB keyboard + mass-storage device enumerate
   (`dmesg | grep -i 'new .*USB device'`, `lsusb`), read the mass-storage magic, and
   observe the keystroke.

### Known blockers (why B is not yet green)
- The patch-0007 vhub **silicon retest is rig-blocked** — P2A/TFTP access degrades
  after ~15 boot cycles, so a clean fresh boot of the fixed kernel has not been
  re-run (`SILICON-STATUS.md` #2). Test B needs that fresh boot first.
- It also needs the board's USB device port **physically cabled** to a host and that
  host booted — a bench-setup step, not something the network bridges provide.

---

## Recommendation

Run **Test A** first — it reuses the QEMU-proven stack, needs only the network + the
patch-0007 kernel on the board, and is fully reversible. It gives real-silicon
evidence for the #2/#3b **function** path immediately. **Test B** is the ultimate
proof of the G3 vhub datapath and should follow once the vhub fresh-boot retest is
unblocked and the USB port is cabled to a host. Capture transcripts into
`evidence/real-hw-usb/` (mirroring the other `evidence/real-hw-*` dirs).
