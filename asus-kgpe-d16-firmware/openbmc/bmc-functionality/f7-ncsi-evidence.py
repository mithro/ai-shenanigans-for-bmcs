#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# ///
"""F7 — verify the KGPE-D16 BMC networking ground truth: dedicated PHY, NOT NC-SI.

This is the faithful, buildless guard for the F7 finding (see F7-NCSI.md). It
asserts a set of invariants against the *actual* repo artifacts so that a future
change which silently flips the KGPE-D16 to NC-SI (e.g. adding `use-ncsi;` to the
DTS, or claiming an NC-SI demo) fails loudly:

  1. DTS `&mac0` uses `phy-mode = "rmii"` and has NO `use-ncsi` / NC-SI channel node.
  2. Raptor's real KGPE-D16 U-Boot sets the MAC1 PHY-mode scratch = 0 (Dedicated PHY).
  3. The AST2050 datasheet notes record: G3 MAC has no NC-SI hardware mode/register.
  4. The D16 kernel tree does not build CONFIG_NET_NCSI.
  5. (If checked out) our QEMU ftgmac100 model has no NC-SI handling / responder.
  6. (If --boot-log given) the QEMU boot brings eth0 up via a dedicated PHY + DHCP,
     with ZERO NC-SI anywhere in the log.

Run:
  uv run asus-kgpe-d16-firmware/openbmc/bmc-functionality/f7-ncsi-evidence.py
  uv run .../f7-ncsi-evidence.py --boot-log .../evidence/qemu-ncsi/eth0-dedicated-phy-boot.log

Exit 0 = all invariants hold (dedicated PHY, not NC-SI). Nonzero = a check failed.
"""
import argparse
import re
import sys
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


# 4. Kernel does not build CONFIG_NET_NCSI ----------------------------------
def check_kernel():
    kdir = KGPE / "qemu-firmware/kernel"
    hits = []
    if kdir.exists():
        for p in kdir.rglob("*"):
            if p.is_file() and p.suffix in (".config", ".cfg", "") and p.name != "out":
                try:
                    t = p.read_text(errors="replace")
                except (IsADirectoryError, PermissionError):
                    continue
                if re.search(r"CONFIG_NET_NCSI\s*=\s*y", t):
                    hits.append(str(p.relative_to(REPO)))
    ok = not hits
    check("D16 kernel does NOT enable CONFIG_NET_NCSI", ok,
          f"found CONFIG_NET_NCSI=y in: {hits}" if hits else "")
    return ok


# 5. QEMU ftgmac100 model has no NC-SI (if submodule checked out) -----------
def check_qemu():
    f = KGPE / "qemu-firmware/qemu/qemu/hw/net/ftgmac100.c"
    text = read(f)
    if text is None:
        print("[SKIP] QEMU ftgmac100.c not checked out (submodule) — skipping model check")
        return True
    # Any real NC-SI handling would reference ncsi/NC-SI in the model.
    hits = [ln for ln in text.splitlines() if re.search(r"nc[_-]?si", ln, re.I)]
    ok = not hits
    check("QEMU ftgmac100 model exposes no NC-SI handling/responder", ok,
          f"{len(hits)} NC-SI reference(s) in ftgmac100.c" if hits else "")
    return ok


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


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--boot-log",
                    help="optional QEMU boot log to assert dedicated-PHY eth0 + no NC-SI")
    args = ap.parse_args()

    print("=== F7: KGPE-D16 BMC networking = DEDICATED PHY, not NC-SI ===")
    print(f"repo: {REPO}\n")
    print("-- Static invariants (no build required) --")
    check_dts()
    check_raptor()
    check_datasheet()
    check_kernel()
    check_qemu()
    if args.boot_log:
        print("\n-- QEMU boot-log invariants --")
        check_boot_log(args.boot_log)

    print(f"\n=== {len(_passes)} passed, {len(_fails)} failed ===")
    if _fails:
        print("FAILED:", ", ".join(_fails))
        return 1
    print("All F7 ground-truth invariants hold: the KGPE-D16 BMC uses a dedicated "
          "RTL8201CP PHY (RMII), not NC-SI.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
