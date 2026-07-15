#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = ["paramiko"]
# ///
"""F4 — Serial-over-LAN on the AST2050 host VUART, in faithful QEMU.

Boots the fuller OpenBMC image (F0) over NFS on the ``kgpe-d16-bmc`` machine at
the real AST2050 DRAM size (``--mem 64``), masking bmcweb + the RAM hogs (F5's
``realhw`` set, which **keeps** the console stack — see ``f4_sol_daemons.py``).

The machine models the AST2050 host **VUART** at 0x1E787000 (the virtual 16550 an
x86 host reaches over LPC I/O 0x3F8) and wires it to ``serial_hd(1)``.  We attach
that to a TCP chardev and **write host-console lines into it** — standing in for
the host's COM1 output.  On the BMC, the kernel's ``8250_aspeed_vuart`` binds it
as ``/dev/ttyVUART0`` and the shipped udev rule starts ``obmc-console-server``,
which publishes the console on ``@obmc-console.default``.

We then **capture the host bytes over SOL** two ways:

  1. ``obmc-console-client`` (OpenBMC's console/SOL client) over an SSH PTY — the
     PASS gate: it must echo back the injected ``HOSTLINE-NN`` markers, proving
     the full path host -> VUART -> obmc-console-server -> console socket -> client.
  2. ``ipmitool -I lanplus ... sol`` (RMCP+): we report SOL **payload status**
     (enabled) and attempt ``sol activate``.  Activation currently returns
     "No response" because this image ships no ``xyz.openbmc_project.Ipmi.SOL``
     config-object provider (Activate Payload -> ResourceNotFound in netipmid) —
     a documented image-recipe gap, NOT a VUART/model or console-plumbing gap
     (obmc-console-client proves the same bytes flow).  Reported, not failed.

Exit 0 = PASS (console-client captured the host bytes), 1 = FAIL.  CI must provide
the QEMU binary (with the VUART model), the g3vic kernel + VUART-enabled DTB, an
NFS export of the fuller rootfs reachable from slirp at 10.0.2.2, and ``ipmitool``.
"""
import argparse
import logging
import os
import socket
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from f4_sol_daemons import mask_cmdline, KEEP_FOR_SOL  # noqa: E402

# paramiko's transport thread logs a stack trace for every SSH connect that
# races the guest still booting; those are expected retries — keep them quiet.
logging.getLogger("paramiko").setLevel(logging.CRITICAL)

MARKER = "HOSTLINE"


def tail_log(path, markers, deadline, echo=True):
    """Tail the QEMU serial log until any marker appears or the deadline."""
    seen, pos = b"", 0
    while time.time() < deadline:
        if os.path.exists(path):
            with open(path, "rb") as f:
                f.seek(pos)
                chunk = f.read()
                pos = f.tell()
            if chunk:
                if echo:
                    sys.stdout.write(chunk.decode("utf-8", "replace"))
                    sys.stdout.flush()
                seen += chunk
                for m in markers:
                    if m.encode() in seen:
                        return m
        time.sleep(1.0)
    return None


class HostFeeder(threading.Thread):
    """Hold the VUART chardev open and emit host-console lines (the 'host')."""

    def __init__(self, port):
        super().__init__(daemon=True)
        self.port = port
        self._stop = threading.Event()
        self.sent = 0
        self.err = None

    def run(self):
        try:
            s = socket.create_connection(("127.0.0.1", self.port), timeout=15)
        except OSError as e:
            self.err = e
            return
        n = 0
        while not self._stop.is_set():
            n += 1
            try:
                s.sendall(
                    f"{MARKER}-{n:02d} the-quick-brown-fox-jumps-over\r\n".encode())
            except OSError as e:
                self.err = e
                break
            self.sent = n
            time.sleep(0.4)
        s.close()

    def stop(self):
        self._stop.set()


def ssh_connect(port, user, password):
    import paramiko
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect("127.0.0.1", port=port, username=user, password=password,
              timeout=20, allow_agent=False, look_for_keys=False)
    return c


def wait_console_up(ssh_port, user, password, deadline):
    """Poll (SSH) until obmc-console@ttyVUART0 is active + /dev/ttyVUART0 exists."""
    last = ""
    while time.time() < deadline:
        try:
            c = ssh_connect(ssh_port, user, password)
        except Exception as e:  # noqa: BLE001 - transient during boot
            msg = f"ssh not ready: {type(e).__name__}"
            if msg != last:
                print("  ...", msg)
                last = msg
            time.sleep(6)
            continue
        _, out, _ = c.exec_command(
            "systemctl is-active obmc-console@ttyVUART0.service; "
            "ls -l /dev/ttyVUART0; "
            "dmesg | grep -i 'ASPEED VUART'")
        text = out.read().decode("utf-8", "replace")
        c.close()
        if "active" in text and "ttyVUART0" in text:
            print("[console] obmc-console@ttyVUART0 is active:")
            print("  " + "\n  ".join(text.strip().splitlines()))
            return text
        print("  ... console not ready yet")
        time.sleep(6)
    return None


def capture_via_console_client(ssh_port, user, password, feeder, seconds=8):
    """Capture host bytes via obmc-console-client over an SSH PTY."""
    c = ssh_connect(ssh_port, user, password)
    chan = c.get_transport().open_session()
    chan.get_pty()
    chan.exec_command("obmc-console-client -i default")
    captured = b""
    deadline = time.time() + seconds
    while time.time() < deadline:
        if chan.recv_ready():
            captured += chan.recv(4096)
        else:
            time.sleep(0.2)
        if feeder.err:
            break
    chan.close()
    c.close()
    return captured.decode("utf-8", "replace")


def ipmi(port, args, user, password, timeout=35):
    # -N 5 -R 3: the AST2050 netipmid RMCP+ RAKP handshake is slow under the
    # 256 MB QEMU load; ipmitool's default 1 s/4-retry gives up before RAKP 1
    # responds ("no response from RAKP 1 message"), intermittently failing the
    # session. A 5 s per-message timeout with 3 retries makes RMCP+ auth reliable
    # (same workaround as f5-ipmi-test.py). SOL payload activation is interactive
    # and still bounded by the subprocess `timeout`.
    cmd = ["ipmitool", "-I", "lanplus", "-H", "127.0.0.1", "-p", str(port),
           "-U", user, "-P", password, "-C", "17", "-N", "5", "-R", "3"] + args
    try:
        p = subprocess.run(cmd, stdin=subprocess.DEVNULL,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           timeout=timeout)
        return p.returncode, p.stdout.decode("utf-8", "replace")
    except subprocess.TimeoutExpired as e:
        return 124, (e.stdout or b"").decode("utf-8", "replace")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qemu", required=True)
    ap.add_argument("--kernel", required=True)
    ap.add_argument("--dtb", required=True)
    ap.add_argument("--nfsroot", required=True,
                    help="server:/export, e.g. 10.0.2.2:/export/openbmc-full")
    ap.add_argument("--vuart-port", type=int, default=17787,
                    help="host TCP port for the VUART chardev (serial_hd(1))")
    ap.add_argument("--ssh-port", type=int, default=12222)
    ap.add_argument("--ipmi-port", type=int, default=16623)
    ap.add_argument("--mem", type=int, default=64)
    ap.add_argument("--user", default="root")
    ap.add_argument("--password", default="0penBmc")
    ap.add_argument("--profile", default="realhw")
    ap.add_argument("--boot-timeout", type=int, default=1200)
    ap.add_argument("--evidence-dir", default="evidence/qemu-sol")
    ap.add_argument("--serial-log", default=None)
    args = ap.parse_args()

    os.makedirs(args.evidence_dir, exist_ok=True)
    logpath = args.serial_log or os.path.join(
        os.getcwd(), "tmp", f"f4-boot-{os.getpid()}.log")
    os.makedirs(os.path.dirname(logpath), exist_ok=True)
    if os.path.exists(logpath):
        os.remove(logpath)

    append = (
        "console=ttyS4,115200n8 "
        f"mem={args.mem}M root=/dev/nfs rw ip=dhcp "
        f"nfsroot={args.nfsroot},vers=3,tcp,nolock "
        + mask_cmdline(args.profile)
    )
    print(f"[mask] profile={args.profile}; console stack KEPT: "
          f"{', '.join(KEEP_FOR_SOL)}")
    # serial_hd(0)=console log; serial_hd(1)=VUART chardev (host COM1 stand-in)
    hostuart = (f"socket,id=hostuart,host=127.0.0.1,port={args.vuart_port},"
                "server=on,wait=off")
    nic = (f"user,model=ftgmac100,hostfwd=tcp::{args.ssh_port}-:22,"
           f"hostfwd=udp::{args.ipmi_port}-:623")
    cmd = [args.qemu, "-M", "kgpe-d16-bmc", "-m", str(args.mem), "-nographic",
           "-monitor", "none",
           "-serial", f"file:{logpath}",
           "-chardev", hostuart, "-serial", "chardev:hostuart",
           "-nic", nic,
           "-kernel", args.kernel, "-dtb", args.dtb, "-append", append]
    print("boot:", " ".join(cmd))
    qemu = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, bufsize=0)
    deadline = time.time() + args.boot_timeout
    result = 1
    feeder = HostFeeder(args.vuart_port)
    try:
        hit = tail_log(logpath, ["Mounted root (nfs filesystem",
                                 "VFS: Mounted root"], deadline)
        if hit:
            print(f"\n[nfs] root mounted over NFS ({hit!r})")
        tail_log(logpath, ["login:", "Startup finished",
                           "Reached target"], min(time.time() + 120, deadline))

        if not wait_console_up(args.ssh_port, args.user, args.password, deadline):
            print("\nF4 RESULT: FAIL — obmc-console@ttyVUART0 never came up")
            return 1

        # Start feeding host bytes into the VUART, then capture over SOL.
        feeder.start()
        time.sleep(2)
        if feeder.err:
            print(f"\nF4 RESULT: FAIL — could not open VUART chardev: {feeder.err}")
            return 1

        print("\n[capture-A] obmc-console-client (OpenBMC SOL client) over SSH ...")
        cap = capture_via_console_client(args.ssh_port, args.user,
                                         args.password, feeder, seconds=8)
        markers = [ln for ln in cap.splitlines() if MARKER in ln]
        with open(os.path.join(args.evidence_dir,
                               "sol-console-client-capture.txt"), "w") as f:
            f.write("# obmc-console-client -i default (host bytes over SOL)\n")
            f.write(f"# host lines fed into the VUART: {feeder.sent}\n")
            f.write(f"# markers captured over the console: {len(markers)}\n\n")
            f.write(cap)
        print(f"[capture-A] captured {len(cap)} bytes, {len(markers)} "
              f"'{MARKER}' markers")
        for ln in markers[:5]:
            print("   >>", ln.strip())

        # ipmitool SOL probe (payload status + activate) — reported, not gating.
        # Restart netipmid with the network up first: its socket-activated
        # standalone instance can start before DHCP settles and never bind
        # UDP/623 (F5's finding), which otherwise races the RMCP+ handshake.
        print("\n[capture-B] ipmitool -I lanplus SOL (RMCP+) ...")
        cj = ssh_connect(args.ssh_port, args.user, args.password)
        cj.exec_command("systemctl restart phosphor-ipmi-net@eth0.service")[1].read()
        cj.close()
        for _ in range(8):
            rc_w, _w = ipmi(args.ipmi_port, ["mc", "info"], args.user,
                            args.password, timeout=12)
            if rc_w == 0:
                print("  netipmid RMCP+ warm (mc info rc=0)")
                break
            time.sleep(3)
        rc_ps, ps = ipmi(args.ipmi_port, ["sol", "payload", "status", "1", "1"],
                         args.user, args.password)
        rc_act, act = ipmi(args.ipmi_port, ["sol", "activate"],
                           args.user, args.password, timeout=10)
        # Grab netipmid's own log line for the activation — the genuine gap.
        cj = ssh_connect(args.ssh_port, args.user, args.password)
        _, jo, _ = cj.exec_command(
            "journalctl -u phosphor-ipmi-net@eth0.service --no-pager | "
            "grep -iE 'ResourceNotFound|sol|console' | tail -5")
        jtail = jo.read().decode("utf-8", "replace")
        cj.close()
        with open(os.path.join(args.evidence_dir, "sol-ipmitool-probe.txt"),
                  "w") as f:
            f.write("$ ipmitool -I lanplus ... mc info      -> warm-up rc="
                    f"{rc_w}\n\n")
            f.write("$ ipmitool -I lanplus ... sol payload status 1 1\n")
            f.write(f"# rc={rc_ps}\n{ps}\n")
            f.write("$ ipmitool -I lanplus ... sol activate\n")
            f.write(f"# rc={rc_act}\n{act}\n")
            f.write("# netipmid journal during activation:\n")
            f.write(jtail + "\n")
            f.write("\n# NOTE: SOL payload is *enabled* (status above), but this "
                    "image ships no\n# xyz.openbmc_project.Ipmi.SOL config-object "
                    "provider, so netipmid's Activate\n# Payload does a D-Bus read "
                    "of /xyz/openbmc_project/ipmi/sol/eth0 that returns\n# "
                    "ResourceNotFound -> 'No response activating SOL payload'. The "
                    "SOL *bytes*\n# flow regardless (proven by capture-A via "
                    "obmc-console-client); only the IPMI\n# front-end config object "
                    "is absent (an image-recipe follow-up).\n")
        print(f"[capture-B] sol payload status rc={rc_ps}: {ps.strip()[:80]}")
        print(f"[capture-B] sol activate rc={rc_act}: {act.strip()[:80]}")
        if jtail.strip():
            print(f"[capture-B] netipmid: {jtail.strip().splitlines()[-1][:90]}")

        ok = len(markers) >= 3 and feeder.sent >= 3
        print("\n=== F4 Serial-over-LAN ===")
        print(f"  VUART host bytes fed        : {feeder.sent}")
        print(f"  captured over obmc-console  : {len(markers)} markers")
        print(f"  ipmitool sol payload status : rc={rc_ps} "
              f"({'enabled' if 'enabled' in ps else 'see evidence'})")
        print(f"  ipmitool sol activate       : rc={rc_act} (known image gap)")
        result = 0 if ok else 1
        print("\nF4 RESULT:", "PASS — host serial captured over SOL "
              "(obmc-console on the AST2050 VUART) in 64 MB" if result == 0
              else "FAIL — host bytes not captured over the console")
        return result
    finally:
        feeder.stop()
        qemu.terminate()
        try:
            qemu.wait(timeout=10)
        except subprocess.TimeoutExpired:
            qemu.kill()


if __name__ == "__main__":
    raise SystemExit(main())
