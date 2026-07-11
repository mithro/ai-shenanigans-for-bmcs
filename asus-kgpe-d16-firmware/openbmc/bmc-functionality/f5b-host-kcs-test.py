#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# ///
"""F5b — host-side IPMI over LPC KCS: prove the BMC-side channel is alive in QEMU.

Boots the D16 (AST2050) kernel + BusyBox initramfs on the faithful
``kgpe-d16-bmc`` QEMU machine at the real 64 MB DRAM size, SSHes in over the
QEMU user-net hostfwd (key auth, same throwaway key as the C2 ssh-test), and
gathers the host-KCS evidence:

  * ``/dev/ipmi-kcs3``      — created by the kernel once the DTS ``&lpc/kcs@2c``
                              node binds ``kcs_bmc_aspeed`` + the cdev-ipmi
                              client (CONFIG_IPMI_KCS_BMC_CDEV_IPMI).
  * driver bound            — the ``ast-kcs-bmc`` platform driver holds the
                              ``…:kcs@2c`` device (``/sys/bus/platform/drivers``).
  * device-tree node        — ``kcs@2c`` present under ``lpc@1e789000`` with
                              compatible ``aspeed,ast2400-kcs-bmc-v2``.
  * BMC-side register poke   — read the LPC registers the driver programmed in the
                              **faithful QEMU G3 LPC model** (``aspeed_lpc_ast2050.c``)
                              via ``devmem``:
                                HICR0 (0x1e789000) bit7 LPC3E  = channel 3 enabled
                                HICR4 (0x1e789010) bit2 KCSENBL= KCS mode on ch3
                                LADR3H/L (0x14/0x18)           = host I/O port 0xca2
                              then WRITE ODR3 (0x1e789038)=0x5a and read it back —
                              a from-BMC-side KCS output-register transaction the
                              model services (Slave-RW), and read STR3 (0x44) which
                              the model keeps read-only.

This is the honest **M1** bar: the KCS channel is alive and the faithful LPC
model answers the driver + a BMC-side poke, WITHOUT faking a host-side (LPC
I/O-port) peer — the ``kgpe-d16-bmc`` machine has no host CPU, and the register-
file LPC model implements no OBF/IBF handshake, so a full host->BMC round-trip
needs a host peer (real silicon, or a model extension). See F5B-HOST-KCS-STATUS.md.

PASS gate: ``/dev/ipmi-kcs3`` exists AND the ast-kcs-bmc driver is bound AND
HICR0.LPC3E is set (the driver drove the model) AND the ODR3 poke reads back.

Example:
  uv run f5b-host-kcs-test.py \
      --qemu   .../qemu-firmware/qemu/build/qemu-system-arm \
      --kernel .../kernel/out/zImage-kgpe-d16 \
      --initrd .../initramfs/out/initramfs.cpio.gz \
      --dtb    .../kernel/out/aspeed-bmc-asus-kgpe-d16.dtb \
      --key    .../initramfs/out/id_kgpe_d16_test \
      --evidence-dir evidence/host-kcs
"""
import argparse
import os
import selectors
import subprocess
import sys
import time


# The BMC-side evidence script, run over SSH as `sh -s` (fed on stdin, so no
# shell-quoting games). BusyBox provides sh/ls/find/cat/od/dmesg/devmem.
GUEST_SCRIPT = r"""
echo '===F5B_BEGIN==='
echo '@@ uname'; uname -a
echo '@@ cmdline'; cat /proc/cmdline
echo '@@ dev_ipmi'; ls -l /dev/ipmi* 2>&1 || echo 'NONE'
echo '@@ dt_node'
DT=$(find /sys/firmware/devicetree/base -name 'kcs@2c' -type d | head -1)
echo "path=$DT"
if [ -n "$DT" ]; then
  printf 'compatible='; cat "$DT/compatible"; echo
  printf 'status='; cat "$DT/status"; echo
  printf 'reg='; od -An -tx1 "$DT/reg"
fi
echo '@@ driver_bound'; ls -l /sys/bus/platform/drivers/ast-kcs-bmc/ 2>&1 || echo 'NO ast-kcs-bmc driver dir'
echo '@@ dmesg'; dmesg | grep -iE 'kcs|ipmi|lpc' 2>&1 || echo 'no matching dmesg'
echo '@@ reg_HICR0_0x1e789000'; devmem 0x1e789000 32
echo '@@ reg_HICR2_0x1e789008'; devmem 0x1e789008 32
echo '@@ reg_HICR4_0x1e789010'; devmem 0x1e789010 32
echo '@@ reg_LADR3H_0x1e789014'; devmem 0x1e789014 32
echo '@@ reg_LADR3L_0x1e789018'; devmem 0x1e789018 32
echo '@@ reg_STR3_0x1e789044_ro'; devmem 0x1e789044 32
# The AST2050 LPC register file is 32-bit APB (DTS reg-io-width=4; the QEMU model
# enforces 4-byte access), so poke ODR3 with a 32-bit write, as the kernel's
# regmap does.
echo '@@ poke_ODR3_write_0x5a'; devmem 0x1e789038 32 0x5a
echo '@@ reg_ODR3_0x1e789038_readback'; devmem 0x1e789038 32
echo '===F5B_END==='
"""


def wait_for(proc, marker, timeout):
    """Pump QEMU serial to stdout until `marker` is seen or timeout/exit."""
    sel = selectors.DefaultSelector()
    sel.register(proc.stdout, selectors.EVENT_READ)
    deadline = time.time() + timeout
    buf = b""
    while time.time() < deadline:
        if proc.poll() is not None:
            return False, buf
        for _ in sel.select(timeout=1.0):
            chunk = os.read(proc.stdout.fileno(), 4096)
            if chunk:
                sys.stdout.write(chunk.decode("utf-8", "replace"))
                sys.stdout.flush()
                buf += chunk
                if marker.encode() in buf:
                    return True, buf
    return False, buf


def ssh_run(port, key, script, timeout=120):
    """Run `script` in the guest via `ssh … sh -s`; return (rc, output)."""
    ssh = ["ssh", "-i", key, "-p", str(port),
           "-o", "StrictHostKeyChecking=no",
           "-o", "UserKnownHostsFile=/dev/null",
           "-o", "HostKeyAlgorithms=ssh-ed25519",
           "-o", "IdentitiesOnly=yes",
           "-o", "ConnectTimeout=30",
           "root@127.0.0.1", "sh -s"]
    p = subprocess.run(ssh, input=script, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, text=True, timeout=timeout)
    return p.returncode, p.stdout


def hexval(line):
    """Parse a trailing 0x… hex value from a devmem output line."""
    tok = line.strip().split()[-1] if line.strip() else ""
    try:
        return int(tok, 16)
    except ValueError:
        return None


def assess(out):
    """Return (ok, summary_lines) from the captured guest evidence."""
    lines = out.splitlines()
    sec = {}
    cur = None
    for ln in lines:
        if ln.startswith("@@ "):
            cur = ln[3:].strip()
            sec[cur] = []
        elif cur is not None:
            sec[cur].append(ln)

    def body(name):
        return "\n".join(sec.get(name, []))

    dev_ok = "/dev/ipmi-kcs3" in body("dev_ipmi")
    drv_body = body("driver_bound")
    # ast-kcs-bmc holds the device: a symlink named "<addr>.kcs -> …/1e789000.lpc/…"
    drv_ok = ".kcs ->" in drv_body
    # HICR0 bit7 (LPC3E) set == the driver enabled KCS channel 3 in the model.
    hicr0 = None
    for ln in sec.get("reg_HICR0_0x1e789000", []):
        hicr0 = hexval(ln) if hexval(ln) is not None else hicr0
    hicr0_ok = hicr0 is not None and (hicr0 & 0x80) != 0
    # ODR3 read-back == 0x5a (low byte) after the BMC-side write.
    odr = None
    for ln in sec.get("reg_ODR3_0x1e789038_readback", []):
        odr = hexval(ln) if hexval(ln) is not None else odr
    odr_ok = odr is not None and (odr & 0xff) == 0x5a

    s = [
        f"  [{'PASS' if dev_ok else 'FAIL'}] /dev/ipmi-kcs3 present",
        f"  [{'PASS' if drv_ok else 'FAIL'}] ast-kcs-bmc driver bound to kcs@2c",
        f"  [{'PASS' if hicr0_ok else 'FAIL'}] HICR0.LPC3E set (ch3 enabled in the "
        f"faithful LPC model): HICR0={hicr0:#010x}" if hicr0 is not None
        else "  [FAIL] HICR0 unreadable",
        f"  [{'PASS' if odr_ok else 'FAIL'}] BMC-side ODR3 poke read back 0x5a: "
        f"ODR3={odr:#010x}" if odr is not None else "  [FAIL] ODR3 unreadable",
    ]
    return (dev_ok and drv_ok and hicr0_ok and odr_ok), s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qemu", required=True)
    ap.add_argument("--kernel", required=True)
    ap.add_argument("--initrd", required=True)
    ap.add_argument("--dtb", required=True)
    ap.add_argument("--key", required=True, help="SSH private key for root")
    ap.add_argument("--port", type=int, default=2223)
    ap.add_argument("--mem", type=int, default=64,
                    help="DRAM MB (64 = the real AST2050 size)")
    ap.add_argument("--boot-timeout", type=int, default=300)
    ap.add_argument("--evidence-dir", default="evidence/host-kcs")
    args = ap.parse_args()

    os.makedirs(args.evidence_dir, exist_ok=True)
    append = "console=ttyS4,115200n8 earlyprintk"
    cmd = [args.qemu, "-M", "kgpe-d16-bmc", "-m", str(args.mem), "-nographic",
           "-monitor", "none", "-serial", "stdio",
           "-nic", f"user,model=ftgmac100,hostfwd=tcp::{args.port}-:22",
           "-kernel", args.kernel, "-initrd", args.initrd,
           "-dtb", args.dtb, "-append", append]
    print("boot:", " ".join(cmd))
    qemu = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, bufsize=0)
    try:
        up, _ = wait_for(qemu, "dropbear: listening", args.boot_timeout)
        if not up:
            print(f"\nF5b RESULT: FAIL — dropbear did not come up in "
                  f"{args.boot_timeout}s")
            return 1
        out = ""
        rc = 1
        # ARM926 is slow right after boot; retry the SSH a few times.
        for attempt in range(1, 7):
            time.sleep(8)
            print(f"--- ssh/KCS evidence attempt {attempt} ---")
            try:
                rc, out = ssh_run(args.port, args.key, GUEST_SCRIPT, timeout=120)
            except subprocess.TimeoutExpired:
                print("  (ssh timed out; retrying)")
                continue
            if "===F5B_END===" in out:
                break
        print(out)
        with open(os.path.join(args.evidence_dir, "host-kcs.txt"), "w") as f:
            f.write(out)
        if "===F5B_END===" not in out:
            print("\nF5b RESULT: FAIL — could not collect KCS evidence over SSH")
            return 1
        ok, summary = assess(out)
        print("\n=== F5b host-side IPMI KCS (BMC-side readiness) ===")
        print("\n".join(summary))
        print("\nF5b RESULT:", "PASS — /dev/ipmi-kcs3 alive + ast-kcs-bmc bound + "
              "faithful LPC model serviced the driver and a BMC-side KCS poke, "
              f"at {args.mem} MB" if ok else "FAIL")
        return 0 if ok else 1
    finally:
        qemu.terminate()
        try:
            qemu.wait(timeout=10)
        except subprocess.TimeoutExpired:
            qemu.kill()


if __name__ == "__main__":
    raise SystemExit(main())
