#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# ///
"""F7 — verify the KGPE-D16 BMC networking ground truth: DUAL channel.

Schematic §7 (authoritative) is titled "Ethernet — dual channel: dedicated PHY +
NC-SI sideband". The board has BOTH:
  * Channel 1 — RMII1/MII -> Realtek RTL8201N dedicated management PHY = the BMC's
    own eth0 (MAC0). This is NOT NC-SI.
  * Channel 2 — RMII2 -> an NC-SI SIDEBAND to the two Intel 82574L host NICs
    (MAC1). NC-SI genuinely exists here (an earlier "no NC-SI anywhere" guard was
    WRONG -- corrected 2026-07-18 against the schematic + the working D07 NC-SI).

This is the faithful, buildless guard: it holds eth0/MAC0 to the dedicated PHY
while allowing (and scoping) the Channel-2 NC-SI sideband, so a change that
silently flips eth0 to NC-SI, or drops/mis-scopes the sideband, fails loudly:

  1. DTS `&mac0` uses `phy-mode = "rmii"` and has NO `use-ncsi` (eth0 = dedicated PHY).
  2. Raptor's real KGPE-D16 U-Boot sets the MAC1 PHY-mode scratch = 0 (its own
     networking is Dedicated PHY; U-Boot does not use the host-NIC sideband).
  3. The AST2050 datasheet notes record: G3 MAC has no NC-SI *hardware* mode, so
     NC-SI is the software protocol (kernel net/ncsi) over the RMII2 MAC.
  4. NC-SI is scoped to the RMII2/MAC1 sideband: kernel builds CONFIG_NET_NCSI and
     the DTS puts `use-ncsi` on `&mac1` (never `&mac0`).
  5. The `&mac1` NC-SI sideband is `status="disabled"` by default, so the C2/C4/NFS
     single-NIC oracle boots are unaffected (the D07 test enables it at runtime).
  6. (If --boot-log given) the eth0-only boot brings eth0 up via a dedicated PHY +
     DHCP, with ZERO NC-SI in that log (mac1 disabled -> no sideband in this boot).

Run:
  uv run asus-kgpe-d16-firmware/openbmc/bmc-functionality/f7-ncsi-evidence.py
  uv run .../f7-ncsi-evidence.py --boot-log .../evidence/qemu-ncsi/eth0-dedicated-phy-boot.log

Exit 0 = all invariants hold (eth0 dedicated PHY; NC-SI scoped to the MAC1
sideband). Nonzero = a check failed.
"""
import argparse
import os
import re
import selectors
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
KGPE = REPO / "asus-kgpe-d16-firmware"

# Result accumulator ---------------------------------------------------------
_fails = []
_passes = []


def check(name, ok, detail=""):
    (_passes if ok else _fails).append(name)
    mark = "PASS" if ok else "FAIL"
    line = f"[{mark}] {name}"
    if detail and not ok:
        line += f"\n         {detail}"
    print(line)
    return ok


def read(path):
    p = Path(path)
    if not p.exists():
        return None
    return p.read_text(errors="replace")


# 1. DTS: dedicated PHY, RMII, no NC-SI -------------------------------------
def check_dts():
    dts = KGPE / "qemu-firmware/dts/aspeed-bmc-asus-kgpe-d16.dts"
    text = read(dts)
    if text is None:
        return check("DTS present", False, f"missing {dts}")
    # Isolate the &mac0 { ... } block.
    m = re.search(r"&mac0\s*\{(.*?)\n\};", text, re.S)
    if not m:
        return check("DTS &mac0 block found", False, "no &mac0 node in DTS")
    mac0 = m.group(1)
    # Strip C comments so `use-ncsi` in prose doesn't trip us.
    mac0_code = re.sub(r"/\*.*?\*/", "", mac0, flags=re.S)
    ok_rmii = 'phy-mode = "rmii"' in mac0_code
    check("DTS &mac0 uses phy-mode=rmii (dedicated PHY)", ok_rmii,
          "expected phy-mode = \"rmii\" in the &mac0 node")
    ok_no_ncsi = "use-ncsi" not in mac0_code
    check("DTS &mac0 has NO use-ncsi property", ok_no_ncsi,
          "found use-ncsi in &mac0 — that would make it NC-SI, not dedicated-PHY")
    return ok_rmii and ok_no_ncsi


# 2. Raptor U-Boot: Dedicated PHY (scratch = 0) -----------------------------
def check_raptor():
    hdr = read(KGPE / "ast2050.h")
    ok = False
    if hdr is not None:
        m = re.search(r"CONFIG_MAC1_PHY_SETTING\s+(\d)", hdr)
        ok = bool(m) and m.group(1) == "0"
    check("Raptor ast2050.h: CONFIG_MAC1_PHY_SETTING = 0 (Dedicated PHY)", ok,
          "0 = Dedicated PHY; 1/2 would be NC-SI")
    # Cross-check the analysis doc's plain-language statement.
    ua = read(KGPE / "RAPTOR-UBOOT-ANALYSIS.md") or ""
    ok_doc = "Dedicated PHY (not NC-SI)" in ua
    check("RAPTOR-UBOOT-ANALYSIS.md states 'Dedicated PHY (not NC-SI)'", ok_doc)
    return ok and ok_doc


# 3. Datasheet: no NC-SI hardware mode in the G3 MAC ------------------------
def check_datasheet():
    md = read(KGPE / "qemu-model/peripherals/mac/DATASHEET-MAC.md") or ""
    ok = "no NCSI mode" in md or "no NC-SI hardware mode" in md
    check("Datasheet note: G3 MAC has no NC-SI hardware mode", ok,
          "expected the SCU70[8:6] MII/RMII-only / no-NCSI finding in DATASHEET-MAC.md")
    return ok


# 4. NC-SI is scoped to the RMII2/MAC1 host-NIC sideband, NOT eth0/MAC0 ------
def check_ncsi_scoped_to_mac1():
    """Schematic §7 is a DUAL-channel topology: dedicated PHY on MAC0 (eth0) AND
    an NC-SI sideband on RMII2/MAC1 to the two 82574L host NICs. So NC-SI DOES
    exist on this board (the earlier 'no NC-SI anywhere' guard was wrong); the
    real invariant is that NC-SI stays on the MAC1 sideband and never on eth0.
    The AST2050 G3 MAC has no NC-SI *hardware* mode (check 3) -- NC-SI is the
    software protocol (kernel CONFIG_NET_NCSI over RMII2), so that config being
    enabled is EXPECTED here, not a red flag."""
    # The sideband needs the software NC-SI stack built. Read the SPECIFIC board
    # config fragment directly -- do NOT rglob qemu-firmware/kernel/, which (when a
    # kernel has been built locally) contains the gitignored kernel/linux/ tree with
    # ~88k files incl. unrelated aspeed_g4/g5 defconfigs that ALSO set
    # CONFIG_NET_NCSI=y. A tree-walk would false-PASS (mask a real "NC-SI dropped
    # from kgpe-d16.config" regression) and be very slow. (code-review 2026-07-18.)
    kcfg = read(KGPE / "qemu-firmware/kernel/kgpe-d16.config") or ""
    kncsi = bool(re.search(r"CONFIG_NET_NCSI\s*=\s*y", kcfg))
    check("kernel builds CONFIG_NET_NCSI for the RMII2/MAC1 host-NIC sideband", kncsi,
          "expected CONFIG_NET_NCSI=y in qemu-firmware/kernel/kgpe-d16.config "
          "(the Channel-2 NC-SI sideband, schematic §7, needs the software NC-SI stack)")
    # The DTS must scope use-ncsi to &mac1 (never &mac0 -- check 1 guards mac0).
    dts = KGPE / "qemu-firmware/dts/aspeed-bmc-asus-kgpe-d16.dts"
    text = read(dts) or ""
    m1 = re.search(r"&mac1\s*\{(.*?)\n\};", text, re.S)
    mac1 = re.sub(r"/\*.*?\*/", "", m1.group(1), flags=re.S) if m1 else ""
    ok_mac1 = bool(m1) and "use-ncsi" in mac1
    check("DTS scopes NC-SI to &mac1 (RMII2 sideband), not eth0/&mac0", ok_mac1,
          "expected use-ncsi in the &mac1 node (Channel-2 host-NIC sideband)")
    return kncsi and ok_mac1


# 5. The NC-SI sideband is OFF by default so the C2/C4 single-NIC oracle boots -
def check_sideband_off_by_default():
    """MAC1/NC-SI must be status=\"disabled\" in the committed DTS: it has no QEMU
    backend on the plain machine, so a silently-enabled &mac1 would break the
    C2/C4/NFS single-NIC oracle boots. The D07 NC-SI test flips it okay at runtime
    (fdtput) with a second slirp NIC that answers NC-SI."""
    dts = KGPE / "qemu-firmware/dts/aspeed-bmc-asus-kgpe-d16.dts"
    text = read(dts) or ""
    m1 = re.search(r"&mac1\s*\{(.*?)\n\};", text, re.S)
    mac1 = re.sub(r"/\*.*?\*/", "", m1.group(1), flags=re.S) if m1 else ""
    ok = bool(m1) and re.search(r'status\s*=\s*"disabled"', mac1)
    check("DTS &mac1 NC-SI sideband is status=disabled by default (oracle-safe)",
          bool(ok),
          "expected status=\"disabled\" in &mac1 so C2/C4/NFS single-NIC boots are unaffected")
    return bool(ok)


# 6. Boot log: dedicated-PHY eth0 up + DHCP, zero NC-SI ----------------------
def check_boot_log(path):
    text = read(path)
    if text is None:
        return check("boot log present", False, f"missing {path}")
    checks = [
        ("boot: ftgmac100 read its own MAC from chip",
         re.search(r"ftgmac100.*Read MAC address", text)),
        ("boot: a dedicated PHY was attached over MDIO",
         re.search(r"attached PHY driver", text)),
        ("boot: eth0 link came up",
         re.search(r"ftgmac100.*eth0:\s*Link is Up", text)),
        ("boot: eth0 got a DHCP lease (shared L2 with host)",
         re.search(r"(IP-Config: Got DHCP answer|inet 10\.0\.2\.15)", text)),
    ]
    all_ok = True
    for name, hit in checks:
        all_ok &= check(name, bool(hit))
    # The decisive negative: NO NC-SI anywhere in the boot.
    ncsi_lines = [ln for ln in text.splitlines() if re.search(r"nc[_-]?si", ln, re.I)]
    ok_no_ncsi = not ncsi_lines
    all_ok &= check("boot: ZERO NC-SI in dmesg (dedicated-PHY path, no sideband)",
                    ok_no_ncsi,
                    f"unexpected NC-SI lines: {ncsi_lines}" if ncsi_lines else "")
    return all_ok


MACHINE = "kgpe-d16-bmc"
# The kernel's built-in IP autoconfig leases from slirp before userspace, so the
# dedicated-PHY eth0 bring-up + DHCP is visible in dmesg regardless of the rootfs.
BOOT_APPEND = "console=ttyS4,115200n8 earlyprintk ip=dhcp"
DHCP_MARKER = "IP-Config: Got DHCP answer"


def boot_and_capture(args, out_path):
    """Boot the faithful kgpe-d16-bmc machine with a dedicated ftgmac100 NIC over
    slirp, stream+capture serial until the DHCP lease (or timeout), save the log."""
    cmd = [args.qemu, "-M", MACHINE, "-m", str(args.mem), "-nographic",
           "-monitor", "none", "-serial", "stdio",
           "-kernel", args.kernel, "-append", args.append or BOOT_APPEND,
           "-nic", "user,model=ftgmac100,hostfwd=tcp::2222-:22"]
    if args.dtb:
        cmd += ["-dtb", args.dtb]
    if args.initrd:
        cmd += ["-initrd", args.initrd]
    print("boot:", " ".join(cmd), flush=True)
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         bufsize=0)
    sel = selectors.DefaultSelector()
    sel.register(p.stdout, selectors.EVENT_READ)
    deadline = time.time() + args.boot_timeout
    captured = bytearray()
    saw_dhcp = False
    while time.time() < deadline and not saw_dhcp:
        if p.poll() is not None:
            break
        for _ in sel.select(timeout=1.0):
            chunk = os.read(p.stdout.fileno(), 4096)
            if not chunk:
                deadline = 0
                break
            sys.stdout.write(chunk.decode("utf-8", "replace"))
            sys.stdout.flush()
            captured += chunk
            if DHCP_MARKER.encode() in captured:
                # Grab a little more so the eth0 summary lines land in the log.
                saw_dhcp = True
    # A short drain so the trailing "eth0: 10.0.2.15" lines are captured.
    drain_end = time.time() + 3
    while time.time() < drain_end and p.poll() is None:
        for _ in sel.select(timeout=0.5):
            chunk = os.read(p.stdout.fileno(), 4096)
            if not chunk:
                break
            sys.stdout.write(chunk.decode("utf-8", "replace"))
            sys.stdout.flush()
            captured += chunk
    p.terminate()
    try:
        p.wait(timeout=10)
    except subprocess.TimeoutExpired:
        p.kill()
    Path(out_path).write_bytes(bytes(captured))
    print(f"\n[boot] captured {len(captured)} bytes -> {out_path}", flush=True)
    if not saw_dhcp:
        print(f"[boot] WARNING: did not see {DHCP_MARKER!r} within "
              f"{args.boot_timeout}s", flush=True)
    return out_path


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--boot-log",
                    help="QEMU boot log to assert dedicated-PHY eth0 + no NC-SI. "
                         "With --qemu, the boot is run and its log written here.")
    # Optional: boot QEMU ourselves (self-contained CI test), then assert the log.
    ap.add_argument("--qemu", help="path to qemu-system-arm (boots the machine)")
    ap.add_argument("--kernel")
    ap.add_argument("--dtb")
    ap.add_argument("--initrd")
    ap.add_argument("--mem", default=64, type=int)
    ap.add_argument("--append", help="override kernel cmdline")
    ap.add_argument("--boot-timeout", default=300, type=int)
    args = ap.parse_args()

    if args.qemu:
        if not (args.kernel and args.boot_log):
            print("--qemu requires --kernel and --boot-log", file=sys.stderr)
            return 2
        boot_and_capture(args, args.boot_log)

    print("=== F7: KGPE-D16 networking = DEDICATED PHY (eth0/MAC0) + NC-SI "
          "sideband (RMII2/MAC1) ===")
    print(f"repo: {REPO}\n")
    print("-- Static invariants (no build required) --")
    check_dts()
    check_raptor()
    check_datasheet()
    check_ncsi_scoped_to_mac1()
    check_sideband_off_by_default()
    if args.boot_log:
        print("\n-- QEMU boot-log invariants --")
        check_boot_log(args.boot_log)

    print(f"\n=== {len(_passes)} passed, {len(_fails)} failed ===")
    if _fails:
        print("FAILED:", ", ".join(_fails))
        return 1
    print("All F7 ground-truth invariants hold: the KGPE-D16 BMC eth0 uses a "
          "dedicated RTL8201CP PHY (RMII1), and NC-SI is scoped to the RMII2/MAC1 "
          "host-NIC sideband (schematic §7 dual channel), off by default.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
