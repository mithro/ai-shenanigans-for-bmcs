# F6-USB-HOST — full USB enumeration against a virtual host (features #2 + #3b)

**Goal:** prove the BMC's virtual USB devices (HID keyboard = #3b "send keyboard
events to the host"; mass-storage = #2 "connect virtual USB devices to the host")
are enumerated **end-to-end by an independent USB host**, entirely in emulation —
the piece the existing F6/F8 demos structurally cannot show.

## Why the existing demos aren't enough

The AST2050 has exactly one USB block — a USB2.0 **device/virtual-hub** controller
@`0x1E6A0000` (no host controller; see `F6-USB.md`). It presents virtual devices
**to the managed x86 server host**. QEMU's `kgpe-d16-bmc` machine emulates only the
BMC SoC, **not** the x86 host it plugs into, so F6/F8 bind the gadget to `dummy_hcd`
— a software UDC+host loopback **inside the BMC guest** — and the gadget never
reaches an independent host. That proves the gadget stack *runs*; it does not prove
a *foreign* USB stack enumerates it.

## Approach: USB/IP (`usbip-vudc`) → a second qemu-system-x86_64 "virtual host"

The BMC binds its configfs gadget to the kernel **`usbip-vudc`** virtual UDC;
`usbipd -D --device` serialises the gadget's URBs over TCP:3240; a **separate
qemu-system-x86_64 guest** running stock Linux imports it (`usbip attach`,
`vhci-hcd`) and enumerates it as a real USB device.

```
 BMC GUEST (qemu-system-arm -M kgpe-d16-bmc, faithful AST2050)
   configfs gadget:  f_hid (boot keyboard) + f_mass_storage (magic@512)
        │  echo usbip-vudc.0 > .../UDC
        ▼
   usbip-vudc.0  (CONFIG_USBIP_VUDC)          ← kgpe-d16-usbip.config
        │  URBs
        ▼
   usbipd -D --device   (static ARM, listens :3240)   ← usbiphost init gate
        │
        │  QEMU user-net hostfwd tcp::3240-:3240  (runner 127.0.0.1:3240)
        ▼
 VIRTUAL HOST GUEST (qemu-system-x86_64, stock Linux)
   usbip attach -r <runner> -b usbip-vudc.0
        ▼  vhci-hcd  → host USB core: GET_DESCRIPTOR / SET_CONFIGURATION / …
        ├─ usb-storage → /dev/sdX → read offset 512 == "KGPE-D16-USBIP-VMEDIA-OK"  (#2)
        └─ usbhid      → /dev/input/eventX → EV_KEY KEY_A on a hidg0 write         (#3b)
```

### The load-bearing caveat (do not paper over)

A Linux gadget binds **exactly one UDC at a time**. So the gadget is bound to
`usbip-vudc.0`, **not** the faithful `aspeed.udc-ast2050` vhub model. This test
therefore validates the **gadget / descriptor / function / enumeration** half; it
does **not** exercise the AST2050 vhub register/IRQ/EP-DMA/PHY datapath. It is
**complementary to** (not a replacement for) the patch-0007 faithful-vhub probe
test (`VHUB-G3-PORT-PLAN.md`):

| Test | UDC | Proves |
|------|-----|--------|
| F6 / patch-0007 (`test_usb.py`) | `aspeed.udc-ast2050` (silicon-faithful) | the G3 vhub probes + survives (register/IRQ semantics) |
| **F6-USB-HOST** (this) | `usbip-vudc.0` (UDC-agnostic) | an independent host fully enumerates the gadget (function/descriptors) |

Together (function-correct **+** G3-vhub-probe-survives) plus a silicon session are
what fully close #2/#3b. On real hardware the **same** configfs gadget binds to the
**real** `1e6a0000.usb-vhub` and the **real** x86 host enumerates it over physical
USB; usbip is the CI-hermetic stand-in for "a real host is on the other end."

## Build pieces

| Piece | File | State |
|-------|------|-------|
| Static ARM usbip userspace (crux de-risk) | `qemu-firmware/initramfs/build-usbip.py` | ✅ built + verified (static ARM ELF) |
| Initramfs ships usbipd/usbip | `qemu-firmware/initramfs/build.py` | ✅ verified in packed cpio |
| BMC kernel `USBIP_VUDC` | `qemu-firmware/kernel/kgpe-d16-usbip.config` + `build-kernel.sh` | ✅ merge verified (`USBIP_VUDC=y`) |
| BMC-side export gate | `qemu-firmware/initramfs/init` (`usbiphost`) | ✅ **runtime PASS** on kgpe-d16-bmc QEMU (Stage 0) |
| x86 client build blocks | static x86 usbip + static x86 busybox | ✅ built (de-risk `evidence/f6-usb-host/02-…`) |
| Two-VM runner | `qemu-firmware/scripts/usbip-host-test.py` | ⏳ pending (assemble x86 initramfs + orchestrate) |
| x86 virtual-host image | reuse host kernel + kernel-matched `.ko.xz` modules | ⏳ pending (bundle module dep-tree + init) |
| CI job | `.github/workflows/d16-kvm.yml` (or sibling) | ⏳ pending |

The x86 host side needs **no x86 kernel build**: `qemu-system-x86_64` boots the host
`vmlinuz` and the guest loads the host's kernel-matched `vhci-hcd`/`usb-storage`/
`usbhid`/`usbip-core` modules. The static x86 usbip client + static x86 busybox both
build (same libudev-zero recipe as ARM). Remaining: bundle the module dep-tree
(`usbcore`/`hid` are modules here) into an x86 initramfs, an x86 `/init` that
`usbip attach`es (`-r 10.0.2.2` via the SLIRP host alias) and asserts the magic read
(#2) + evdev keypress (#3b), and the runner + CI job.

### The static-libudev crux — SOLVED

usbip's `configure.ac` hard-requires libudev and `usbipd` links the whole
`libusbip` (which pulls libudev across `usbip_common`/`host_common`/`vhci_driver`).
A static, no-dynamic-loader ARM initramfs can't use glibc/eudev libudev cleanly.
**libudev-zero** (dependency-free static libudev, ISC) + `--without-tcp-wrappers` +
libtool `-all-static` produces fully-static ARM `usbipd`/`usbip` (usbip 2.0,
kernel-6.6.70-matched). Reproduce: `uv run initramfs/build-usbip.py`. Evidence:
`evidence/f6-usb-host/00-static-arm-usbip-crossbuild.txt`. The glibc
`getaddrinfo`-in-static warning is benign — usbip attaches by numeric IP.

## Network topology (runner)

Both guests use QEMU user-net. The BMC forwards its usbipd port to the runner
(`-nic user,model=ftgmac100,hostfwd=tcp:127.0.0.1:3240-:3240`); the x86 guest
reaches it through its own SLIRP gateway alias for the host (`10.0.2.2:3240`), so
`usbip attach -r 10.0.2.2 -b usbip-vudc.0`. (Stage 1 may instead use the CI runner
kernel as the host; Stage 2 uses a dedicated hermetic x86 guest — see below.)

## Staging

- **Stage 0 (BMC-side, boot-verifiable without the x86 guest): ✅ DONE — runtime
  PASS** on the faithful kgpe-d16-bmc QEMU (2026-07-16). Booting with `usbiphost`
  yields `USBIP-BIND-OK` (gadget bound to `usbip-vudc.0`) and
  `USBIP-DAEMON-LISTENING (:3240)`; the static-ARM usbipd runs and listens. Evidence
  `evidence/f6-usb-host/01-stage0-bmc-export-PASS.txt`. (Open item for Stage 1: the
  mass_storage LUN logged `(no medium)` at bind — confirm the host sees the backing
  image, tweak the gate if the file isn't attaching.)
- **Stage 1 (enumerate against the runner kernel):** `modprobe vhci-hcd
  usb-storage usbhid` on the runner, `usbip attach`, read `/dev/sdX` offset 512 ==
  magic, read the keypress on `/dev/input/eventX`. Fastest end-to-end; depends on
  the runner shipping `vhci-hcd`/`usb-storage` (`linux-modules-extra`).
- **Stage 2 (dedicated hermetic x86 virtual-host VM):** build a small
  `qemu-system-x86_64` guest from this repo's own kernel tree (same 6.6.70 →
  matched usbip protocol) + BusyBox initramfs with usbip + vhci-hcd; link to the
  BMC and drive the attach. The reproducible CI deliverable.

## What it proves — and the honest limits

**Proves** (against an independent Linux USB stack, over a transport, not a
self-loopback): full enumeration sequence; `f_mass_storage` → `/dev/sdX` with a
byte-exact magic read (#2); HID report-descriptor parse + a `/dev/hidg0` write
delivered as `KEY_A` on the host's evdev (#3b).

**Does NOT prove:** the AST2050 vhub register/IRQ/EP-DMA/PHY datapath (bypassed —
see caveat); nor is the virtual host the actual KGPE-D16 x86 host. usbip is a
URB-level transport; nothing below it is exercised.

## Status

Foundation **built and verified** (static ARM usbip userspace; initramfs
integration; `USBIP_VUDC` kernel config; the `usbiphost` init gate). The two-VM
runner, the x86 virtual-host image, and the CI job are the remaining pieces; the
Stage-0 BMC-side gate is runtime-verifiable as soon as a `USBIP_VUDC` kernel is
built. This moves #2/#3b from "QEMU-blocked" to "harness foundation done, crux
de-risked, enumeration proof pending the x86 host image + CI wiring."
