#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# ///
"""F6 test: boot the USB-enabled kernel on the kgpe-d16-bmc (AST2050) QEMU machine
and prove the USB stack works.

The AST2050's only USB block is the USB2.0 device / virtual-hub controller at
0x1E6A0000 (VIC INT#5) — there is NO USB host controller (datasheet §9/§10/§15). So
this asserts the two faithful things:

  1. the OpenBMC kernel PROBES the real AST2050 USB2.0 device/vhub controller:
     'aspeed_vhub 1e6a0000.usb-vhub: Initialized virtual hub in USB2 mode';
  2. the USB *gadget* stack ENUMERATES a virtual mass-storage device in-guest over
     dummy_hcd (the vhub presents to the *server host*, which QEMU does not emulate;
     dummy_hcd is a software UDC+host loopback) — F8-KVM groundwork.

The initramfs /init runs the gadget dance when 'f6usb' is on the kernel cmdline and
prints the results to the serial console between the F6-USB-DEMO-{BEGIN,END} markers.

PASS = both markers seen. See openbmc/bmc-functionality/F6-USB.md.
"""
import argparse
import os
import selectors
import subprocess
import sys
import time

VHUB_MARK = "1e6a0000.usb-vhub: Initialized virtual hub"
ENUM_MARK = "Product: AST2050 vKVM virtual-media"
END_MARK = "F6-USB-DEMO-END"


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
    ap.add_argument("--mem", type=int, default=128)
    ap.add_argument("--boot-timeout", type=int, default=240)
    args = ap.parse_args()

    append = "console=ttyS4,115200n8 earlyprintk f6usb"
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
        vhub = VHUB_MARK in text
        enum = ENUM_MARK in text
        print("\n--- F6 USB checks ---")
        print(f"  [{'PASS' if vhub else 'FAIL'}] kernel probes the AST2050 USB2.0 "
              f"device/vhub @0x1e6a0000 (aspeed_vhub 'Initialized virtual hub')")
        print(f"  [{'PASS' if enum else 'FAIL'}] USB gadget stack enumerates a "
              f"virtual mass-storage device in-guest (dummy_hcd; F8-KVM groundwork)")
        ok = vhub and enum
        print("\nF6 USB RESULT:", "PASS" if ok else "FAIL")
        return 0 if ok else 1
    finally:
        qemu.terminate()
        try:
            qemu.wait(timeout=10)
        except subprocess.TimeoutExpired:
            qemu.kill()


if __name__ == "__main__":
    raise SystemExit(main())
