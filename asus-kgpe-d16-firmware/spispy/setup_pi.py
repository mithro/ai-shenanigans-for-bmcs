# /// script
# requires-python = ">=3.11"
# ///
"""Provision the asus-bmc Raspberry Pi for spispy / ULX3S flash emulation.

Idempotent bootstrap that mirrors the workstation setup so a bitstream built on
either host behaves identically (same oss-cad-suite, same clone path):

  1. install the pinned oss-cad-suite (linux-arm64) under ~/oss-cad-suite
  2. clone mithro/spispy over HTTPS to ~/github/mithro/spispy   (public fork,
     so no SSH key is needed on the Pi; SSH to GitHub works too)
  3. install the udev rules so the ULX3S shows up as /dev/spispy-{jtag,ctrl}

Run ON THE PI:
    uv run setup_pi.py

Then build + load per ULX3S-SPISPY-BUILD-AND-FLASH.md. Fails loud on any error
(no silent fallbacks) — re-running after a fix is safe.
"""

import os
import platform
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

# Pinned to match the workstation install so both hosts use identical tools.
OSSCAD_DATE = "20260718"
OSSCAD_URL = (
    "https://github.com/YosysHQ/oss-cad-suite-build/releases/download/"
    f"2026-07-18/oss-cad-suite-linux-arm64-{OSSCAD_DATE}.tgz"
)
SPISPY_REPO = "https://github.com/mithro/spispy.git"
# The modern-toolchain (`default_nettype none) uart.v fix lives on this branch;
# master would fail to synthesise under yosys 0.67. Both hosts build from it.
SPISPY_BRANCH = "claude/oss-cad-suite-build"
HOME = Path.home()
CLONE_DIR = HOME / "github" / "mithro" / "spispy"
OSSCAD_DIR = HOME / "oss-cad-suite"
RULES = Path(__file__).resolve().parent / "99-spispy-ulx3s.rules"


def run(cmd, **kw):
    """Run a command, echoing it; raise (fail loud) on non-zero exit."""
    print("+", " ".join(str(c) for c in cmd))
    subprocess.run(cmd, check=True, **kw)


def install_osscad():
    if (OSSCAD_DIR / "bin" / "openFPGALoader").exists():
        print(f"oss-cad-suite already present at {OSSCAD_DIR}; skipping.")
        return
    tgz = HOME / f"oss-cad-suite-linux-arm64-{OSSCAD_DATE}.tgz"
    if not tgz.exists():
        print(f"downloading {OSSCAD_URL}")
        # stream to disk so a Pi with modest RAM can handle the ~700 MB file
        with urllib.request.urlopen(OSSCAD_URL) as r, open(tgz, "wb") as f:  # noqa: S310
            shutil.copyfileobj(r, f, length=1 << 20)
    print(f"extracting {tgz.name} -> {OSSCAD_DIR}")
    with tarfile.open(tgz) as t:
        t.extractall(HOME)  # archive roots at oss-cad-suite/
    if not (OSSCAD_DIR / "bin" / "openFPGALoader").exists():
        sys.exit(f"ERROR: extraction did not produce {OSSCAD_DIR}/bin/openFPGALoader")


def clone_spispy():
    if (CLONE_DIR / ".git").exists():
        print(f"{CLONE_DIR} already cloned; fetching latest.")
        run(["git", "-C", str(CLONE_DIR), "fetch", "--all", "--prune"])
    else:
        CLONE_DIR.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", SPISPY_REPO, str(CLONE_DIR)])
    run(["git", "-C", str(CLONE_DIR), "checkout", SPISPY_BRANCH])


def install_udev():
    if not RULES.exists():
        sys.exit(f"ERROR: udev rules not found next to this script: {RULES}")
    dest = Path("/etc/udev/rules.d") / RULES.name
    run(["sudo", "cp", str(RULES), str(dest)])
    run(["sudo", "udevadm", "control", "--reload-rules"])
    run(["sudo", "udevadm", "trigger"])
    print(f"installed {dest}")


def main():
    if platform.machine() != "aarch64":
        sys.exit(f"ERROR: expected aarch64 (Pi 4B 64-bit OS), got {platform.machine()}")
    install_osscad()
    clone_spispy()
    install_udev()
    print(
        "\nDone. Next:\n"
        f"  export PATH={OSSCAD_DIR}/bin:$PATH\n"
        f"  cd {CLONE_DIR}/verilog && make PRJTRELLIS= spispy.bit\n"
        "  openFPGALoader -b ulx3s spispy.bit\n"
        "  # then verify the CDC control port:\n"
        "  ./bin/spispy -v -d /dev/spispy-ctrl   # expect: Version: '11111111'\n"
        "\nIf /dev/spispy-ctrl is missing, confirm your user is in 'plugdev'\n"
        "(sudo usermod -aG plugdev \"$USER\"; then log out/in).\n"
    )


if __name__ == "__main__":
    main()
