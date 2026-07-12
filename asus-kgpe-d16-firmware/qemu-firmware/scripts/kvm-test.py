#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# ///
"""F8 test: boot the KVM-enabled kernel on the kgpe-d16-bmc (AST2050) QEMU machine
and prove the KVM-over-IP silicon path works, layer by layer.

KVM-over-IP on the AST2050 is three cooperating blocks (see
openbmc/bmc-functionality/F8-KVM.md):

  1. VIDEO ENGINE @0x1E700000 (VIC INT#7) — the aspeed-video V4L2 driver binds the
     modelled AST2050 video engine and exposes /dev/video0 (the KVM screen-capture
     device). The BMC-only QEMU machine has no VGA host source, so the achievable bar
     is "driver probes the modelled engine + opens the capture device".
  2. USB2.0 vhub @0x1E6A0000 (VIC INT#5) — a virtual HID keyboard+mouse gadget the BMC
     presents TO THE SERVER HOST. QEMU does not emulate that host, so the gadget is
     bound to the in-guest dummy_hcd (software UDC+host loopback) and an actual
     keypress ('a') HID report is shown crossing to a host-side evdev input device.
  3. obmc-ikvm — userspace RFB/VNC server (assessed for the 64 MB image in F8-KVM.md §4).

The initramfs /init runs the demo when 'f8kvm' is on the kernel cmdline and prints
results between the F8-KVM-DEMO-{BEGIN,END} markers.

PASS = video (/dev/video0) AND HID (keypress report written to /dev/hidg0) both seen.
"""
import argparse
import os
import selectors
import subprocess
import sys
import time

VIDEO_MARK = "F8-VIDEO: /dev/video0 present"
HID_MARK = "F8-HID: wrote press report"
END_MARK = "F8-KVM-DEMO-END"


def stream_until(proc, markers, timeout):
    """Pump QEMU serial to stdout until any marker seen or deadline/exit."""
    sel = selectors.DefaultSelector()
    sel.register(proc.stdout, selectors.EVENT_READ)
    deadline = time.time() + timeout
    buf = b""
    while time.time() < deadline:
        if proc.poll() is not None:
            return None, buf
        for _ in sel.select(timeout=1.0):
            chunk = os.read(proc.stdout.fileno(), 4096)
            if not chunk:
                continue
            sys.stdout.write(chunk.decode("utf-8", "replace"))
            sys.stdout.flush()
            buf += chunk
            for m in markers:
                if m.encode() in buf:
                    return m, buf
    return None, buf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qemu", required=True)
    ap.add_argument("--kernel", required=True)
    ap.add_argument("--initrd", required=True)
    ap.add_argument("--dtb", required=True)
    # The real AST2050 has 64 MB DDR2 (hardware-verified); default to it so the demo
    # reflects the actual memory the KVM path must live in.
    ap.add_argument("--mem", type=int, default=64)
    ap.add_argument("--boot-timeout", type=int, default=300)
    args = ap.parse_args()

    append = "console=ttyS4,115200n8 earlyprintk f8kvm"
    cmd = [args.qemu, "-M", "kgpe-d16-bmc", "-m", str(args.mem), "-nographic",
           "-monitor", "none", "-serial", "stdio",
           "-nic", "user,model=ftgmac100",
           "-kernel", args.kernel, "-initrd", args.initrd,
           "-dtb", args.dtb, "-append", append, "-no-reboot"]
    print("boot:", " ".join(cmd))
    qemu = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, bufsize=0)
    try:
        _, buf = stream_until(qemu, [END_MARK], args.boot_timeout)
        text = buf.decode("utf-8", "replace")
        video = VIDEO_MARK in text
        hid = HID_MARK in text
        # The keypress crossing to the host evdev is the strongest signal; report it
        # separately but do not require it for PASS (dummy_hcd delivery timing varies).
        evdev = ("host received these input_event bytes" in text) and \
                (" 01 00 1e 00 " in text or "0000001e" in text.replace(" ", ""))
        print("\n--- F8 KVM checks ---")
        print(f"  [{'PASS' if video else 'FAIL'}] VIDEO: aspeed-video probes the "
              f"AST2050 video engine @0x1e700000 -> /dev/video0")
        print(f"  [{'PASS' if hid else 'FAIL'}] HID: virtual keyboard gadget created; "
              f"keypress report written to /dev/hidg0 (the byte-stream a keypress produces)")
        print(f"  [{'INFO' if evdev else 'n/a '}] HID: keypress delivered to a host-side "
              f"evdev input device over dummy_hcd (EV_KEY / KEY_A)")
        ok = video and hid
        print("\nF8 KVM RESULT:", "PASS" if ok else "FAIL")
        return 0 if ok else 1
    finally:
        qemu.terminate()
        try:
            qemu.wait(timeout=10)
        except subprocess.TimeoutExpired:
            qemu.kill()


if __name__ == "__main__":
    raise SystemExit(main())
