#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""F2 — host power control demonstrated in faithful QEMU.

Boots the fuller OpenBMC image (F0, ``obmc-phosphor-image-ast2050-full``) over
NFS on the faithful ``kgpe-d16-bmc`` machine at the real AST2050 DRAM size
(``--mem 64``), masking the non-power daemons (``f2_masked_daemons.py``) so the
host + chassis **state managers** and ``bmcweb`` fit in 64 MB.  Then it proves
the modeled host-power loop two ways:

  1. **GPIO loop through the real driver.**  Over the serial console it runs
     ``kgpe-power.sh`` (Raptor's ``asus_power.sh`` request-line sequences over
     sysfs GPIO) for on / off / reset.  Each write reaches the AST2050 GPIO
     model, whose KGPE-D16 power-sequencer (``aspeed_gpio_kgpe_d16_pwrseq``)
     latches host power and drives the GPIOH2 power-state input.  H2 is read back
     **independently over QMP** (``qom-get /machine/soc/gpio gpioH2``), so the
     confirmation does not go through the guest at all:

         init/off -> H2 = False (off) ; on/reset -> H2 = True (on)

  2. **Redfish reachability + power actions.**  It GETs the Redfish
     ``ComputerSystem`` and POSTs ``ComputerSystem.Reset`` (ForceOff / On /
     ForceRestart, ``root:0penBmc``), capturing that bmcweb accepts each action.
     (Wiring these actions to the GPIO automatically is op-pwrctl /
     org.openbmc.control.Power — see PROGRESS.md; this test proves the model +
     the acceptance path; the QMP GPIO readback is the authoritative power-state
     evidence.)

Exit 0 = PASS.  Evidence JSON written under ``--evidence-dir``.

Example:
  uv run f2-power-control-test.py \
      --qemu   .../qemu-firmware/qemu/build/qemu-system-arm \
      --kernel .../uImage-kgpe-d16 --dtb .../aspeed-bmc-asus-kgpe-d16.dtb \
      --nfsroot 10.0.2.2:/export/openbmc-full --mem 64 \
      --evidence-dir evidence/qemu
"""
import argparse
import base64
import json
import os
import selectors
import socket
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from f2_masked_daemons import mask_cmdline, MASK_UNITS  # noqa: E402


# ---------------------------------------------------------------- QMP client --
class Qmp:
    """Minimal QMP client to read the modeled GPIOH2 power-state pin."""

    def __init__(self, path):
        self.path = path
        self.sock = None

    def connect(self, deadline):
        while time.time() < deadline:
            if os.path.exists(self.path):
                try:
                    s = socket.socket(socket.AF_UNIX)
                    s.connect(self.path)
                    self.sock = s
                    self.f = s.makefile("rw")
                    self.f.readline()  # greeting
                    self._cmd({"execute": "qmp_capabilities"})
                    return True
                except OSError:
                    pass
            time.sleep(0.5)
        return False

    def _cmd(self, d):
        self.f.write(json.dumps(d) + "\n")
        self.f.flush()
        return json.loads(self.f.readline())

    def power_state(self, gpio_path="/machine/soc/gpio", pin="gpioH2"):
        r = self._cmd({"execute": "qom-get",
                       "arguments": {"path": gpio_path, "property": pin}})
        return r.get("return")


# ------------------------------------------------------------ serial console --
class Console:
    """Drive the QEMU serial console: echo output to stdout, expect + send."""

    def __init__(self, proc):
        self.proc = proc
        self.buf = b""
        self.sel = selectors.DefaultSelector()
        self.sel.register(proc.stdout, selectors.EVENT_READ)

    def _pump(self, timeout):
        for _ in self.sel.select(timeout=timeout):
            chunk = os.read(self.proc.stdout.fileno(), 4096)
            if chunk:
                sys.stdout.write(chunk.decode("utf-8", "replace"))
                sys.stdout.flush()
                self.buf += chunk

    def expect(self, markers, deadline):
        if isinstance(markers, str):
            markers = [markers]
        while time.time() < deadline:
            if self.proc.poll() is not None:
                return None
            self._pump(1.0)
            for m in markers:
                idx = self.buf.rfind(m.encode())
                if idx != -1:
                    self.buf = self.buf[idx + len(m):]
                    return m
        return None

    def send(self, line):
        self.proc.stdin.write((line + "\n").encode())
        self.proc.stdin.flush()

    def run(self, cmd, tag, deadline):
        """Run a guest command bracketed by sentinels; return captured text."""
        self.send(f"echo __B_{tag}__; {cmd}; echo __E_{tag}__$?")
        if self.expect(f"__B_{tag}__", deadline) is None:
            return None
        start = len(self.buf)  # unused; we scan for end sentinel next
        _ = start
        pre = self.buf
        if self.expect(f"__E_{tag}__", deadline) is None:
            return None
        # everything between the begin echo result and end sentinel
        text = pre.decode("utf-8", "replace")
        return text


# ---------------------------------------------------------------- Redfish -----
def _ctx():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def rf(port, path, user, pw, method="GET", body=None, timeout=20, retries=4):
    url = f"https://127.0.0.1:{port}{path}"
    data = json.dumps(body).encode() if body is not None else None
    for attempt in range(retries):
        req = urllib.request.Request(url, data=data, method=method)
        if user:
            tok = base64.b64encode(f"{user}:{pw}".encode()).decode()
            req.add_header("Authorization", f"Basic {tok}")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=_ctx()) as r:
                b = r.read().decode("utf-8", "replace")
                try:
                    return r.status, json.loads(b)
                except json.JSONDecodeError:
                    return r.status, b
        except urllib.error.HTTPError as e:
            b = e.read().decode("utf-8", "replace")
            try:
                return e.code, json.loads(b)
            except json.JSONDecodeError:
                return e.code, b
        except Exception as e:  # noqa: BLE001
            last = str(e)
            time.sleep(2.0 * (attempt + 1))
    return None, last


def wait_redfish(port, deadline):
    while time.time() < deadline:
        st, doc = rf(port, "/redfish/v1", None, None, timeout=10, retries=1)
        if st == 200 and isinstance(doc, dict) and "RedfishVersion" in doc:
            return doc["RedfishVersion"]
        time.sleep(5)
    return None


# ------------------------------------------------------------------- main ------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qemu", required=True)
    ap.add_argument("--kernel", required=True)
    ap.add_argument("--dtb", required=True)
    ap.add_argument("--nfsroot", required=True)
    ap.add_argument("--https-port", type=int, default=2443)
    ap.add_argument("--ssh-port", type=int, default=2222)
    ap.add_argument("--mem", type=int, default=64)
    ap.add_argument("--user", default="root")
    ap.add_argument("--password", default="0penBmc")
    ap.add_argument("--power-script", default="/usr/local/bin/kgpe-power.sh",
                    help="path of kgpe-power.sh inside the guest (staged via NFS)")
    ap.add_argument("--driver", choices=["redfish", "sysfs"], default="redfish",
                    help="redfish = drive Redfish ComputerSystem.Reset and let "
                         "op-pwrctl toggle the GPIO (fully-automated loop); "
                         "sysfs = drive kgpe-power.sh directly (no op-pwrctl)")
    ap.add_argument("--boot-timeout", type=int, default=1500)
    ap.add_argument("--evidence-dir", default="evidence/qemu")
    ap.add_argument("--qmp-sock", default=None,
                    help="QMP unix socket path (must be <108 bytes; default: "
                         "$XDG_RUNTIME_DIR/f2q-<pid>.sock)")
    args = ap.parse_args()

    os.makedirs(args.evidence_dir, exist_ok=True)
    # A QMP unix socket path must be < 108 bytes; the evidence dir is too deep,
    # so default to the per-user runtime dir (the proper place for a runtime
    # control socket, and short).
    qmp_sock = args.qmp_sock or os.path.join(
        os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"),
        f"f2q-{os.getpid()}.sock")
    if len(qmp_sock) >= 108:
        print(f"FAIL: QMP socket path too long ({len(qmp_sock)} bytes): {qmp_sock}")
        return 1
    if os.path.exists(qmp_sock):
        os.remove(qmp_sock)

    append = (
        "console=ttyS4,115200n8 "
        f"mem={args.mem}M root=/dev/nfs rw ip=dhcp "
        f"nfsroot={args.nfsroot},vers=3,tcp,nolock "
        + mask_cmdline()
    )
    hostfwd = (f"user,model=ftgmac100,"
               f"hostfwd=tcp::{args.https_port}-:443,"
               f"hostfwd=tcp::{args.ssh_port}-:22")
    cmd = [args.qemu, "-M", "kgpe-d16-bmc", "-m", str(args.mem), "-nographic",
           "-monitor", "none", "-serial", "stdio", "-nic", hostfwd,
           "-qmp", f"unix:{qmp_sock},server,nowait",
           "-kernel", args.kernel, "-dtb", args.dtb, "-append", append]
    print(f"[mask] {len(MASK_UNITS)} daemons masked for the 64 MB budget")
    print("boot:", " ".join(cmd))
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, bufsize=0)
    con = Console(proc)
    qmp = Qmp(qmp_sock)
    results = {"qmp_power_state": {}, "guest_power_state": {}, "redfish": {}}
    ok = True
    deadline = time.time() + args.boot_timeout
    try:
        if not qmp.connect(deadline):
            print("FAIL: QMP did not connect")
            return 1
        print("[qmp] connected; initial modeled power-state:",
              qmp.power_state())

        con.expect(["Mounted root", "VFS: Mounted root"], deadline)
        print("\n[nfs] root mounted")
        # login prompt
        if con.expect(["kgpe-d16 login:", "login:"], deadline) is None:
            print("FAIL: no login prompt")
            return 1
        con.send(args.user)
        con.expect(["Password:"], deadline)
        con.send(args.password)
        if con.expect(["# ", "root@", "~#"], time.time() + 120) is None:
            print("FAIL: shell prompt not reached")
            return 1
        print("\n[login] root shell reached")

        reset_url = ("/redfish/v1/Systems/system/Actions/"
                     "ComputerSystem.Reset")

        def poll_power(want_on, budget=120):
            """Poll QMP gpioH2 + Redfish PowerState until they reach want_on."""
            want_rf = "On" if want_on else "Off"
            end = time.time() + budget
            modeled = qmp.power_state()
            pstate = None
            while time.time() < end:
                modeled = qmp.power_state()
                _, sd = rf(args.https_port, "/redfish/v1/Systems/system",
                           args.user, args.password, timeout=10, retries=1)
                pstate = sd.get("PowerState") if isinstance(sd, dict) else None
                if modeled == want_on and pstate == want_rf:
                    break
                con.expect(["__never__"], min(time.time() + 4, end))
            return modeled, pstate

        if args.driver == "sysfs":
            # Direct sysfs drive (image without op-pwrctl): kgpe-power.sh moves
            # the request lines; H2 is confirmed over QMP.
            steps = [("init", False), ("on", True), ("off", False),
                     ("on", True), ("reset", True)]
            for step, want_on in steps:
                out = con.run(f"sh {args.power_script} {step}", f"pwr_{step}",
                              time.time() + 90)
                time.sleep(1.0)
                modeled = qmp.power_state()
                guest = None
                if out:
                    for ln in out.splitlines():
                        if "POWER_STATE(GPIOH2)=" in ln:
                            guest = ln.split("=")[-1].strip()
                results["qmp_power_state"][step] = modeled
                results["guest_power_state"][step] = guest
                if modeled != want_on:
                    ok = False
                print(f"[power:{step}] QMP gpioH2={modeled} guest={guest} "
                      f"want={'on' if want_on else 'off'} "
                      f"[{'PASS' if modeled == want_on else 'FAIL'}]")

        # --- Fully-automated Redfish -> state-manager -> op-pwrctl -> GPIO loop --
        print("\n[redfish] waiting for bmcweb + op-pwrctl ...")
        ver = wait_redfish(args.https_port, min(time.time() + 400, deadline))
        results["redfish"]["service_root_version"] = ver
        if not ver:
            print("FAIL: bmcweb/Redfish did not come up in 64 MB")
            results["redfish"]["note"] = "bmcweb not up in budget"
            ok = False
        else:
            print(f"[redfish] ServiceRoot up: RedfishVersion={ver}")
            # settle op-pwrctl's first pgood poll
            con.expect(["__never__"], min(time.time() + 8, deadline))
            m0, p0 = qmp.power_state(), None
            _, sd = rf(args.https_port, "/redfish/v1/Systems/system",
                       args.user, args.password)
            p0 = sd.get("PowerState") if isinstance(sd, dict) else None
            print(f"[redfish] initial: QMP gpioH2={m0} PowerState={p0}")
            results["redfish"]["initial"] = {"gpioH2": m0, "PowerState": p0}
            if args.driver == "redfish":
                loop = [("On", True), ("ForceOff", False), ("On", True),
                        ("ForceRestart", True)]
                for rtype, want_on in loop:
                    st, _ = rf(args.https_port, reset_url, args.user,
                               args.password, method="POST",
                               body={"ResetType": rtype})
                    accepted = st in (200, 202, 204)
                    modeled, pstate = poll_power(want_on)
                    want_rf = "On" if want_on else "Off"
                    step_ok = accepted and modeled == want_on and pstate == want_rf
                    if not step_ok:
                        ok = False
                    results["redfish"].setdefault("reset_loop", {})[rtype] = {
                        "http": st, "gpioH2": modeled, "PowerState": pstate,
                        "expected": want_rf}
                    print(f"[redfish] Reset {rtype} -> HTTP {st} ; "
                          f"QMP gpioH2={modeled} PowerState={pstate} "
                          f"want={want_rf} [{'PASS' if step_ok else 'FAIL'}]")
            # capture the final ComputerSystem doc
            _, sysdoc = rf(args.https_port, "/redfish/v1/Systems/system",
                           args.user, args.password)
            if isinstance(sysdoc, dict):
                results["redfish"]["final_PowerState"] = sysdoc.get("PowerState")
                with open(os.path.join(args.evidence_dir,
                                       "systems-system.json"), "w") as f:
                    json.dump(sysdoc, f, indent=2, sort_keys=True)

        with open(os.path.join(args.evidence_dir, "f2-power-results.json"),
                  "w") as f:
            json.dump(results, f, indent=2, sort_keys=True)

        print("\n=== F2 power-control summary ===")
        print(json.dumps(results, indent=2, sort_keys=True))
        print("\nF2 RESULT:", "PASS — modeled host power on/off/reset via the "
              "OpenBMC GPIO path, confirmed on GPIOH2 over QMP"
              if ok else "FAIL")
        return 0 if ok else 1
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=10)
        except Exception:  # noqa: BLE001
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
