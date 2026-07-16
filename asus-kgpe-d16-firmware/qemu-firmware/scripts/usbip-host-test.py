#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# ///
"""Two-VM USB/IP full-enumeration test (features #2 + #3b).

Boots the faithful kgpe-d16-bmc (ARM) exporting its USB gadget over USB/IP, and a
qemu-system-x86_64 "virtual host" (the running host kernel + kernel-matched modules)
that imports it via vhci-hcd and enumerates it. Asserts, from the x86 serial:
  - X86-USBIP-ATTACHED : the host attached the remote gadget
  - X86-MASS-OK        : #2 — read the known magic off the mass-storage LUN
  - X86-KEY-OK         : #3b — a KEY_A press was delivered to the host's evdev

Network: the BMC forwards usbipd :3240 to the runner (hostfwd 127.0.0.1:3240); the
x86 guest reaches it via the SLIRP host alias 10.0.2.2:3240.

Build inputs first:
  sh   scripts/build-kernel.sh
  uv run initramfs/build.py
  uv run scripts/build-x86-vhost.py
See openbmc/bmc-functionality/F6-USB-HOST.md.
"""
import argparse
import os
import platform
import selectors
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class Vm:
    def __init__(self, name, cmd, logpath):
        self.name = name
        self.cmd = cmd
        self.buf = b""
        self.logf = open(logpath, "wb")
        self.proc = None
        self._stop = False

    def start(self):
        print(f"[{self.name}] boot:", " ".join(str(c) for c in self.cmd), flush=True)
        self.proc = subprocess.Popen(self.cmd, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, bufsize=0)
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self):
        sel = selectors.DefaultSelector()
        sel.register(self.proc.stdout, selectors.EVENT_READ)
        while not self._stop and self.proc.poll() is None:
            for _ in sel.select(timeout=0.5):
                chunk = os.read(self.proc.stdout.fileno(), 4096)
                if chunk:
                    self.buf += chunk
                    self.logf.write(chunk); self.logf.flush()

    def text(self):
        return self.buf.decode("utf-8", "replace")

    def wait_for(self, marker, timeout):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if marker in self.text():
                return True
            if self.proc.poll() is not None and marker not in self.text():
                return False
            time.sleep(0.5)
        return marker in self.text()

    def kill(self):
        self._stop = True
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.logf.close()


def main():
    krel = platform.release()
    ap = argparse.ArgumentParser()
    ap.add_argument("--qemu-arm", default=str(ROOT / "qemu/qemu/build/qemu-system-arm"))
    ap.add_argument("--qemu-x86", default="qemu-system-x86_64")
    ap.add_argument("--kernel", default=str(ROOT / "kernel/out/zImage-kgpe-d16"))
    ap.add_argument("--dtb", default=str(ROOT / "kernel/out/aspeed-bmc-asus-kgpe-d16.dtb"))
    ap.add_argument("--initrd", default=str(ROOT / "initramfs/out/initramfs.cpio.gz"))
    ap.add_argument("--vmlinuz", default=f"/boot/vmlinuz-{krel}")
    ap.add_argument("--vhost-initrd", default=str(ROOT / "kernel/out/vhost-x86-initramfs.cpio.gz"))
    ap.add_argument("--mem-bmc", type=int, default=64)
    ap.add_argument("--mem-x86", type=int, default=512)
    ap.add_argument("--logdir", default=str(ROOT / "initramfs/out"))
    args = ap.parse_args()

    logdir = Path(args.logdir); logdir.mkdir(parents=True, exist_ok=True)

    bmc = Vm("bmc", [
        args.qemu_arm, "-M", "kgpe-d16-bmc", "-m", str(args.mem_bmc), "-nographic",
        "-monitor", "none", "-serial", "stdio",
        "-nic", "user,model=ftgmac100,hostfwd=tcp:127.0.0.1:3240-:3240",
        "-kernel", args.kernel, "-initrd", args.initrd, "-dtb", args.dtb,
        "-append", "console=ttyS4,115200n8 usbiphost usbipkbd", "-no-reboot",
    ], logdir / "usbip-bmc.log")

    x86 = Vm("x86", [
        args.qemu_x86, "-m", str(args.mem_x86), "-nographic", "-no-reboot",
        "-kernel", args.vmlinuz, "-initrd", args.vhost_initrd,
        "-nic", "user,model=e1000",
        "-append", "console=ttyS0 panic=1 rdinit=/init",
    ], logdir / "usbip-x86.log")

    ok = False
    try:
        bmc.start()
        print("[bmc] waiting for usbipd to listen...", flush=True)
        if not bmc.wait_for("USBIP-DAEMON-LISTENING", timeout=240):
            print("FAIL: BMC usbipd did not come up\n--- bmc tail ---")
            print("\n".join(bmc.text().splitlines()[-25:]))
            return 1
        print("[bmc] usbipd listening; booting x86 virtual host...", flush=True)
        x86.start()
        x86.wait_for("=== X86-VHOST-END ===", timeout=240)
        t = x86.text()
        attached = "X86-USBIP-ATTACHED" in t
        mass = "X86-MASS-OK" in t
        key = "X86-KEY-OK" in t
        print("\n--- x86 virtual-host tail ---")
        print("\n".join(t.splitlines()[-30:]))
        print("\n--- USB/IP two-VM enumeration checks ---")
        print(f"  [{'PASS' if attached else 'FAIL'}] host attached the remote gadget (X86-USBIP-ATTACHED)")
        print(f"  [{'PASS' if mass else 'FAIL'}] #2 mass-storage magic read by the host (X86-MASS-OK)")
        print(f"  [{'PASS' if key else 'FAIL'}] #3b KEY_A delivered to the host evdev (X86-KEY-OK)")
        ok = attached and mass and key
        print("\nUSBIP-HOST RESULT:", "PASS" if ok else "FAIL")
    finally:
        x86.kill()
        bmc.kill()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
