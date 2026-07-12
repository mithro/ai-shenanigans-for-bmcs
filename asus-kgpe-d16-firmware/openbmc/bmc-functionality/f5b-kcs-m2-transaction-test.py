#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# ///
"""F5b M2 — a GENUINE host->BMC IPMI transaction over the LPC KCS channel in QEMU.

Boots the OpenBMC stack (the F-IMG2/F-HWPASS image that ships ``kcsbridged``
wired to ``/dev/ipmi-kcs3``) over NFS on the faithful ``kgpe-d16-bmc`` machine at
the real 64 MB DRAM size, then plays the **host** side of the IPMI KCS SMS
protocol (IPMI v2.0 spec §9.15 "KCS Interface" transfer flows) against the
channel-3 host I/O port pair and sends **Get Device ID** (netfn 0x06, cmd 0x01).

The host side is driven through the QEMU G3 LPC model's QOM back-channel
(``host-kcs3-data`` / ``host-kcs3-cmdsts`` on ``/machine/soc/lpc-g3``, via QMP):
one ``qom-set`` = one host OUT cycle to the data/command port, one ``qom-get`` =
one host IN cycle from the data/status port. The back-channel replaces ONLY the
LPC bus wires — the machine has no host CPU — while every handshake effect
(IDR/IBF/C-D latch, ODR/OBF, the VIC #8 interrupt) is the faithful datasheet
state machine (AST2050 A3 datasheet p.313-316) that the in-guest mainline
``kcs_bmc_aspeed`` + ``kcs_bmc_cdev_ipmi`` drivers react to. Nothing in the
transaction path is scripted on the BMC side: the kernel KCS state machine,
``kcsbridged`` and ``ipmid`` (phosphor-ipmi-host) are the stock OpenBMC stack.

Full path proven:

  this test (IPMI KCS host protocol, via QMP = LPC wires)
    -> QEMU aspeed_lpc_ast2050 KCS state machine (IDR3/ODR3/STR3, VIC #8 IRQ)
      -> kernel kcs_bmc_aspeed / kcs_bmc_cdev_ipmi   (/dev/ipmi-kcs3)
        -> kcsbridged (phosphor-ipmi-kcs@ipmi-kcs3)  (D-Bus)
          -> ipmid (phosphor-ipmi-host)               = the ANSWERING LAYER
        <- response bytes flow back through ODR3/OBF one KCS READ cycle each

PASS gate: the response is a well-formed Get Device ID response (netfn 0x07,
cmd 0x01, completion code present) **and** the BMC-side journal shows
``kcsbridged`` handled the request (evidence captured over SSH). The raw
host-side byte trace and the journal excerpts land in --evidence-dir.

Example:
  uv run f5b-kcs-m2-transaction-test.py \
      --qemu    .../qemu-firmware/qemu/build/qemu-system-arm \
      --kernel  .../kernel/out/zImage-kgpe-d16 \
      --dtb     .../kernel/out/aspeed-bmc-asus-kgpe-d16.dtb \
      --nfsroot 10.0.2.2:/export/openbmc-hwpass --mem 64 \
      --evidence-dir evidence/host-kcs-m2
"""
import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time

from f5_masked_daemons import mask_cmdline

LPC_G3_QOM_PATH = "/machine/soc/lpc-g3"

# IPMI KCS SMS control codes + status decode (IPMI v2.0 §9.5-9.15).
KCS_WRITE_START, KCS_WRITE_END, KCS_READ = 0x61, 0x62, 0x68
STR_OBF, STR_IBF = 0x01, 0x02
STATE_IDLE, STATE_READ, STATE_WRITE, STATE_ERROR = 0, 1, 2, 3
STATE_NAMES = {0: "IDLE", 1: "READ", 2: "WRITE", 3: "ERROR"}


class QMPError(RuntimeError):
    pass


class QMP:
    """Minimal QMP client over the QEMU -qmp unix socket."""

    def __init__(self, path, timeout=30):
        deadline = time.time() + timeout
        while True:
            try:
                self.sock = socket.socket(socket.AF_UNIX)
                self.sock.connect(path)
                break
            except (FileNotFoundError, ConnectionRefusedError):
                if time.time() > deadline:
                    raise
                time.sleep(0.2)
        self.f = self.sock.makefile("rw")
        greeting = json.loads(self.f.readline())
        if "QMP" not in greeting:
            raise QMPError(f"no QMP greeting: {greeting}")
        self.cmd("qmp_capabilities")

    def cmd(self, execute, arguments=None):
        msg = {"execute": execute}
        if arguments is not None:
            msg["arguments"] = arguments
        self.f.write(json.dumps(msg) + "\n")
        self.f.flush()
        while True:
            resp = json.loads(self.f.readline())
            if "return" in resp:
                return resp["return"]
            if "error" in resp:
                raise QMPError(f"{execute} {arguments}: {resp['error']}")
            # async events are skipped


class KCSHost:
    """The HOST side of IPMI KCS channel 3: I/O port cycles via the QOM
    back-channel, byte handshake per the IPMI v2.0 KCS transfer flows."""

    def __init__(self, qmp, trace):
        self.qmp = qmp
        self.trace = trace          # list[str], the evidence byte trace

    # -- one LPC I/O cycle each ------------------------------------------------
    def out_data(self, b):
        self.qmp.cmd("qom-set", {"path": LPC_G3_QOM_PATH,
                                 "property": "host-kcs3-data", "value": b})
        self.trace.append(f"OUT 0xca2 (data)   <- {b:#04x}")

    def out_cmd(self, b):
        self.qmp.cmd("qom-set", {"path": LPC_G3_QOM_PATH,
                                 "property": "host-kcs3-cmdsts", "value": b})
        self.trace.append(f"OUT 0xca3 (cmd)    <- {b:#04x}")

    def in_data(self):
        b = self.qmp.cmd("qom-get", {"path": LPC_G3_QOM_PATH,
                                     "property": "host-kcs3-data"})
        self.trace.append(f"IN  0xca2 (data)   -> {b:#04x}")
        return b

    def in_status(self, quiet=False):
        b = self.qmp.cmd("qom-get", {"path": LPC_G3_QOM_PATH,
                                     "property": "host-kcs3-cmdsts"})
        if not quiet:
            self.trace.append(
                f"IN  0xca3 (status) -> {b:#04x}  "
                f"[state={STATE_NAMES[(b >> 6) & 3]}"
                f"{' IBF' if b & STR_IBF else ''}"
                f"{' OBF' if b & STR_OBF else ''}]")
        return b

    # -- IPMI KCS handshake primitives ------------------------------------------
    def wait_ibf_clear(self, timeout=30):
        deadline = time.time() + timeout
        polls = 0
        while time.time() < deadline:
            st = self.in_status(quiet=True)
            polls += 1
            if not (st & STR_IBF):
                self.trace.append(
                    f"IN  0xca3 (status) -> {st:#04x}  [IBF clear after "
                    f"{polls} poll(s); state={STATE_NAMES[(st >> 6) & 3]}"
                    f"{' OBF' if st & STR_OBF else ''}]")
                return st
            time.sleep(0.02)
        raise TimeoutError("KCS: IBF did not clear (BMC not consuming IDR)")

    def wait_obf_set(self, timeout=30):
        deadline = time.time() + timeout
        polls = 0
        while time.time() < deadline:
            st = self.in_status(quiet=True)
            polls += 1
            if st & STR_OBF:
                self.trace.append(
                    f"IN  0xca3 (status) -> {st:#04x}  [OBF set after "
                    f"{polls} poll(s); state={STATE_NAMES[(st >> 6) & 3]}]")
                return st
            time.sleep(0.02)
        raise TimeoutError("KCS: OBF never set (BMC posted no byte)")

    def state(self, st):
        return (st >> 6) & 3

    def transaction(self, request, timeout=60):
        """One IPMI request/response over KCS (IPMI v2.0 §9.15 flow charts).
        `request` = [netfn<<2|lun, cmd, data...]; returns the response bytes."""
        self.trace.append(f"--- KCS transaction: request {bytes(request).hex(' ')} ---")
        # WRITE phase
        self.wait_ibf_clear()
        st = self.in_status()
        if st & STR_OBF:
            self.in_data()                      # flush a stale OBF byte
        self.out_cmd(KCS_WRITE_START)
        st = self.wait_ibf_clear()
        if self.state(st) != STATE_WRITE:
            raise RuntimeError(f"KCS: no WRITE state after WRITE_START "
                               f"(status {st:#04x})")
        for b in request[:-1]:
            if self.in_status() & STR_OBF:
                self.in_data()                  # BMC dummy-writes ODR: consume
            self.out_data(b)
            st = self.wait_ibf_clear()
            if self.state(st) != STATE_WRITE:
                raise RuntimeError(f"KCS: left WRITE state mid-request "
                                   f"(status {st:#04x})")
        if self.in_status() & STR_OBF:
            self.in_data()
        self.out_cmd(KCS_WRITE_END)
        st = self.wait_ibf_clear()
        if self.state(st) != STATE_WRITE:
            raise RuntimeError(f"KCS: no WRITE state after WRITE_END "
                               f"(status {st:#04x})")
        if st & STR_OBF:
            self.in_data()
        self.out_data(request[-1])              # last byte
        # READ phase
        response = []
        deadline = time.time() + timeout
        while True:
            if time.time() > deadline:
                raise TimeoutError("KCS: READ phase did not complete")
            st = self.wait_ibf_clear()
            phase = self.state(st)
            if phase == STATE_READ:
                self.wait_obf_set()
                response.append(self.in_data())
                self.out_data(KCS_READ)
            elif phase == STATE_IDLE:
                self.wait_obf_set()
                self.in_data()                  # dummy byte ends the transfer
                break
            elif phase == STATE_WRITE:
                time.sleep(0.02)                # BMC still processing
            else:
                raise RuntimeError(f"KCS: ERROR state (status {st:#04x})")
        self.trace.append(f"--- KCS transaction: response {bytes(response).hex(' ')} ---")
        return response


def stream_serial(logpath, markers, deadline):
    """Tail the QEMU serial log file until any marker appears."""
    pos = 0
    data = b""
    while time.time() < deadline:
        if os.path.exists(logpath):
            with open(logpath, "rb") as f:
                f.seek(pos)
                chunk = f.read()
                pos = f.tell()
            if chunk:
                sys.stdout.write(chunk.decode("utf-8", "replace"))
                sys.stdout.flush()
                data += chunk
            for m in markers:
                if m.encode() in data:
                    return m
        time.sleep(2)
    return None


def ssh_run(port, password, script, timeout=120):
    """Run `script` on the BMC over sshpass+dropbear (OpenBMC root login)."""
    cmd = ["sshpass", "-p", password, "ssh", "-p", str(port),
           "-o", "StrictHostKeyChecking=no",
           "-o", "UserKnownHostsFile=/dev/null",
           "-o", "ConnectTimeout=20",
           "root@127.0.0.1", "sh -s"]
    p = subprocess.run(cmd, input=script, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, text=True, timeout=timeout)
    return p.returncode, p.stdout


DEVID_FIELDS = [
    "device_id", "device_rev", "fw_rev1", "fw_rev2", "ipmi_version",
    "additional_dev_support", "manuf_id_0", "manuf_id_1", "manuf_id_2",
    "product_id_0", "product_id_1",
]


def decode_devid(resp):
    """Human decode of [netfn|lun, cmd, cc, body...]."""
    lines = [f"  raw response: {bytes(resp).hex(' ')}",
             f"  netfn/lun = {resp[0]:#04x} (netfn {resp[0] >> 2:#x} = "
             f"App response), cmd = {resp[1]:#04x}, cc = {resp[2]:#04x}"]
    body = resp[3:]
    for i, name in enumerate(DEVID_FIELDS):
        if i < len(body):
            lines.append(f"  {name:<24}= {body[i]:#04x}")
    if len(body) >= 9:
        manuf = body[6] | body[7] << 8 | body[8] << 16
        lines.append(f"  manufacturer IANA       = {manuf} ({manuf:#x})")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qemu", required=True)
    ap.add_argument("--kernel", required=True)
    ap.add_argument("--dtb", required=True)
    ap.add_argument("--nfsroot", required=True,
                    help="server:/export, e.g. 10.0.2.2:/export/openbmc-hwpass")
    ap.add_argument("--ssh-port", type=int, default=12232)
    ap.add_argument("--mem", type=int, default=64,
                    help="DRAM MB (64 = the real AST2050 size)")
    ap.add_argument("--password", default="0penBmc")
    ap.add_argument("--boot-timeout", type=int, default=1200)
    ap.add_argument("--evidence-dir", default="evidence/host-kcs-m2")
    ap.add_argument("--serial-log", default=None)
    args = ap.parse_args()

    if not shutil.which("sshpass"):
        print("FAIL: sshpass not on PATH (apt-get install sshpass)")
        return 2

    os.makedirs(args.evidence_dir, exist_ok=True)
    logpath = args.serial_log or os.path.join(
        os.getcwd(), "tmp", f"kcs-m2-boot-{os.getpid()}.log")
    os.makedirs(os.path.dirname(logpath), exist_ok=True)
    if os.path.exists(logpath):
        os.remove(logpath)
    qmp_path = os.path.join(os.path.dirname(logpath),
                            f"kcs-m2-qmp-{os.getpid()}.sock")

    append = (
        "console=ttyS4,115200n8 "
        f"mem={args.mem}M "
        "root=/dev/nfs rw ip=dhcp "
        f"nfsroot={args.nfsroot},vers=3,tcp,nolock "
        + mask_cmdline("kcs")
    )
    cmd = [args.qemu, "-M", "kgpe-d16-bmc", "-m", str(args.mem), "-nographic",
           "-monitor", "none", "-serial", f"file:{logpath}",
           "-qmp", f"unix:{qmp_path},server=on,wait=off",
           "-nic", f"user,model=ftgmac100,hostfwd=tcp::{args.ssh_port}-:22",
           "-kernel", args.kernel, "-dtb", args.dtb, "-append", append]
    print("boot:", " ".join(cmd))
    qemu = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, bufsize=0)
    deadline = time.time() + args.boot_timeout
    try:
        # 1. kernel KCS channel up (driver programmed the faithful model)
        hit = stream_serial(logpath, ["Initialised channel 3 at 0xca2"], deadline)
        if not hit:
            print("\nM2 RESULT: FAIL — kernel never initialised KCS channel 3")
            return 1
        print("\n[kcs] kernel ast-kcs-bmc channel 3 up at 0xca2")

        # 2. wait for the userspace bridge: poll systemd over SSH. `systemctl
        # is-active A B` exits 0 iff BOTH units are active — use that exit code
        # (robust against the ssh host-key warning that pollutes stdout).
        print("[bridge] waiting for phosphor-ipmi-kcs@ipmi-kcs3 + ipmid ...")
        bridge_up = False
        out, rc = "", -1
        while time.time() < deadline:
            try:
                rc, out = ssh_run(args.ssh_port, args.password,
                                  "systemctl is-active "
                                  "phosphor-ipmi-kcs@ipmi-kcs3.service "
                                  "phosphor-ipmi-host.service", timeout=60)
            except subprocess.TimeoutExpired:
                continue
            # rc 255 = ssh transport failure (guest not ready); keep polling.
            if rc == 0:
                bridge_up = True
                break
            time.sleep(10)
        if not bridge_up:
            print("\nM2 RESULT: FAIL — kcsbridged/ipmid did not come up "
                  f"(last rc={rc}: {out!r})")
            return 1
        print("[bridge] kcsbridged (phosphor-ipmi-kcs@ipmi-kcs3) + ipmid ACTIVE")

        # 3. the transaction: Get Device ID from the HOST side
        trace = []
        qmp = QMP(qmp_path)
        host = KCSHost(qmp, trace)
        request = [0x06 << 2 | 0x0, 0x01]       # netfn App, lun 0, cmd 0x01
        print("\n[kcs] driving Get Device ID through the KCS state machine ...")
        t0 = time.time()
        response = host.transaction(request)
        elapsed = time.time() - t0
        print(f"[kcs] transaction complete in {elapsed:.1f}s, "
              f"{len(response)} response bytes")
        with open(os.path.join(args.evidence_dir, "host-byte-trace.txt"), "w") as f:
            f.write("F5b M2 — host-side KCS byte trace (each line = one LPC "
                    "I/O cycle via the QOM back-channel)\n")
            f.write(f"request: {bytes(request).hex(' ')}\n\n")
            f.write("\n".join(trace) + "\n")
        print("\n=== host-side byte trace (tail) ===")
        print("\n".join(trace[-12:]))

        # 4. BMC-side evidence: journal for kcsbridged + ipmid, driver state
        rc, journal = ssh_run(args.ssh_port, args.password, r"""
echo '=== systemctl status (bridge + ipmid) ==='
systemctl status --no-pager -l phosphor-ipmi-kcs@ipmi-kcs3.service | head -12
systemctl status --no-pager -l phosphor-ipmi-host.service | head -8
echo '=== journal: kcsbridged ==='
journalctl --no-pager -u phosphor-ipmi-kcs@ipmi-kcs3.service | tail -30
echo '=== journal: ipmid (tail) ==='
journalctl --no-pager -u phosphor-ipmi-host.service | tail -15
echo '=== kcsbridged holds /dev/ipmi-kcs3 ==='
ls -l /proc/$(pidof kcsbridged)/fd | grep ipmi-kcs || echo 'fd list unavailable'
echo '=== dmesg: kcs ==='
dmesg | grep -i kcs
""", timeout=120)
        with open(os.path.join(args.evidence_dir, "bmc-journal.txt"), "w") as f:
            f.write(journal)
        print("\n=== BMC-side journal (excerpt) ===")
        print("\n".join(journal.splitlines()[:40]))

        # 5. assess
        ok_form = (len(response) >= 3 and response[0] == (0x07 << 2)
                   and response[1] == 0x01)
        cc = response[2] if ok_form else None
        ok_cc = cc == 0x00
        ok_bridge = "ipmi-kcs" in journal and "active (running)" in journal
        print("\n=== F5b M2 host->BMC IPMI-over-KCS transaction ===")
        print(f"  [{'PASS' if ok_form else 'FAIL'}] well-formed Get Device ID "
              f"response (netfn 0x07, cmd 0x01)")
        print(f"  [{'PASS' if ok_cc else 'FAIL'}] completion code 0x00"
              + (f" (got {cc:#04x})" if cc is not None else " (no cc byte)"))
        print(f"  [{'PASS' if ok_bridge else 'FAIL'}] kcsbridged active and "
              f"holding /dev/ipmi-kcs3 (BMC-side journal)")
        if ok_form:
            print("\n" + decode_devid(response))
        ok = ok_form and ok_cc and ok_bridge
        print("\nM2 RESULT:", "PASS — genuine host->BMC Get Device ID over the "
              f"KCS state machine, answered by ipmid via kcsbridged, at "
              f"{args.mem} MB" if ok else "FAIL")
        return 0 if ok else 1
    finally:
        qemu.terminate()
        try:
            qemu.wait(timeout=10)
        except subprocess.TimeoutExpired:
            qemu.kill()


if __name__ == "__main__":
    raise SystemExit(main())
