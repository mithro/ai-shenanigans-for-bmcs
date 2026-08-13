#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# ///
"""Phase-6 (6a) test: boot the faithful kgpe-d16-bmc machine with its root
filesystem served over NFS — the transport OpenBMC uses on the fpgas.online
rigs — and prove the guest mounts root over the network and runs userspace
from it.

Boot chain
----------
  qemu-system-arm -M kgpe-d16-bmc
    -kernel zImage-kgpe-d16 -dtb aspeed-bmc-asus-kgpe-d16.dtb
    -nic user,model=ftgmac100                 (QEMU slirp: guest 10.0.2.15,
                                               gateway/host 10.0.2.2)
    -append 'root=/dev/nfs rw ip=dhcp
             nfsroot=10.0.2.2:<export>,vers=3,tcp,nolock init=/init ...'

The kernel's built-in IP autoconfig (ip=dhcp) leases 10.0.2.15 from slirp, then
CONFIG_ROOT_NFS mounts <export> from the host NFS server (reached at 10.0.2.2
through slirp -> host loopback) *before* userspace. `/init` therefore executes
from the NFS root; its BMC-READY marker is proof the netboot+NFS path worked on
the faithful machine with the FTGMAC100 model.

PASS requires BOTH:
  * the kernel VFS message "Mounted root (nfs filesystem" (root came over NFS), and
  * "BMC-READY" (the NFS-hosted /init ran to completion).

Optionally (--key) also SSHes in over the slirp hostfwd to confirm the userspace
is fully live over NFS, mirroring the C2 SSH check.
"""
import argparse
import os
import selectors
import subprocess
import sys
import time

NFS_MOUNT_MARKER = "Mounted root (nfs filesystem"
READY_MARKER = "BMC-READY"


def wait_for_all(proc, markers, timeout):
    """Stream QEMU serial to our stdout until every marker is seen (or timeout /
    QEMU exit). Returns (all_seen: bool, seen: set, buf: bytes)."""
    sel = selectors.DefaultSelector()
    sel.register(proc.stdout, selectors.EVENT_READ)
    deadline = time.time() + timeout
    buf = b""
    seen = set()
    while time.time() < deadline:
        if proc.poll() is not None:
            return markers.issubset(seen), seen, buf
        for _ in sel.select(timeout=1.0):
            chunk = os.read(proc.stdout.fileno(), 4096)
            if not chunk:
                continue
            sys.stdout.write(chunk.decode("utf-8", "replace"))
            sys.stdout.flush()
            buf += chunk
            for m in markers:
                if m.encode() in buf:
                    seen.add(m)
            if markers.issubset(seen):
                return True, seen, buf
    return markers.issubset(seen), seen, buf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qemu", required=True)
    ap.add_argument("--kernel", required=True)
    ap.add_argument("--dtb", required=True)
    ap.add_argument("--nfsroot", required=True,
                    help="server:/export path, e.g. 10.0.2.2:/export/kgpe-d16-rootfs")
    ap.add_argument("--key", help="optional SSH private key; if given, also SSH "
                    "in over the slirp hostfwd to confirm userspace over NFS")
    ap.add_argument("--port", type=int, default=2222)
    ap.add_argument("--mem", type=int, default=128)
    ap.add_argument("--boot-timeout", type=int, default=300)
    args = ap.parse_args()

    # vers=3 keeps it simple (no v4 pseudo-fs/idmap); tcp is robust over slirp;
    # nolock avoids needing statd/NLM at boot. init=/init runs our BusyBox init
    # (the rootfs also ships busybox's /sbin/init, which we do NOT want here).
    append = (
        "console=ttyS4,115200n8 earlyprintk "
        "root=/dev/nfs rw ip=dhcp "
        f"nfsroot={args.nfsroot},vers=3,tcp,nolock "
        "init=/init"
    )
    cmd = [args.qemu, "-M", "kgpe-d16-bmc", "-m", str(args.mem), "-nographic",
           "-monitor", "none", "-serial", "stdio",
           "-nic", f"user,model=ftgmac100,hostfwd=tcp::{args.port}-:22",
           "-kernel", args.kernel, "-dtb", args.dtb, "-append", append]
    print("boot:", " ".join(cmd))
    qemu = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, bufsize=0)
    try:
        markers = {NFS_MOUNT_MARKER, READY_MARKER}
        ok, seen, _ = wait_for_all(qemu, markers, args.boot_timeout)
        print("\n--- NFS-root boot markers ---")
        print(f"  NFS root mounted : {'YES' if NFS_MOUNT_MARKER in seen else 'NO'}"
              f"  ({NFS_MOUNT_MARKER!r})")
        print(f"  userspace ready  : {'YES' if READY_MARKER in seen else 'NO'}"
              f"  ({READY_MARKER!r})")
        if not ok:
            print(f"\nFAIL: did not reach an NFS-root shell within "
                  f"{args.boot_timeout}s")
            if NFS_MOUNT_MARKER not in seen:
                print("  hint: NFS mount never happened — check the host NFS "
                      "export (insecure,no_root_squash) and slirp reachability "
                      "of 10.0.2.2, or the kernel's NFS/IP_PNP config.")
            elif READY_MARKER not in seen:
                print("  hint: root mounted over NFS but /init did not finish — "
                      "check init=/init and the exported tree.")
            return 1

        print("\nPASS: root mounted over NFS and userspace booted from it.")

        if args.key:
            ssh = ["ssh", "-i", args.key, "-p", str(args.port),
                   "-o", "StrictHostKeyChecking=no",
                   "-o", "UserKnownHostsFile=/dev/null",
                   "-o", "HostKeyAlgorithms=ssh-ed25519",
                   "-o", "IdentitiesOnly=yes", "-o", "ConnectTimeout=30",
                   "root@127.0.0.1",
                   "echo NFS_SSH_OK; mount | grep ' / '; hostname; uname -sm"]
            print("\n--- optional: SSH in over NFS-booted userspace ---")
            for attempt in range(1, 7):
                time.sleep(8)
                print(f"--- ssh attempt {attempt} ---")
                r = subprocess.run(ssh, capture_output=True, text=True,
                                   timeout=90)
                if r.stdout:
                    print(r.stdout)
                if r.stderr.strip():
                    print(r.stderr.strip())
                if r.returncode == 0 and "NFS_SSH_OK" in r.stdout:
                    print("SSH-over-NFS: OK")
                    break
            else:
                print("SSH-over-NFS: could not connect (non-fatal; NFS-root "
                      "boot already PASSed).")
        return 0
    finally:
        qemu.terminate()
        try:
            qemu.wait(timeout=10)
        except subprocess.TimeoutExpired:
            qemu.kill()


if __name__ == "__main__":
    raise SystemExit(main())
