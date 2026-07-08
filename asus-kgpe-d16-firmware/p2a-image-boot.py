#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Load an arbitrary ARM binary into AST2050 DRAM over culvert P2A and boot the ARM
from it -- no spispy, no JTAG. This is the general form of the proven stub boot
(arm-stub/boot-p2a.py) used for U-Boot.

Pipeline (all via culvert/P2A):
  1. (caller runs ddr2-init-p2a.py first -- DDR2 must be up, 4-bank)
  2. transfer the image to the host, siphon it into DRAM at --load (default
     0x40000000, which the remap points at 0x0 = the ARM reset vector)
  3. VERIFY + PATCH: bulk read-back, single-word-rewrite any mismatches (the DDR2
     burst write has ~0.04% beat-duplication errors; single-word writes are clean),
     loop until the image reads back byte-perfect
  4. set the DRAM->0x0 remap
  5. reset-boot trick: disable ARM (SCU70[1:0]=11, survives HRST_N) -> watchdog
     HRST_N (PC->0x0, ARM held) -> re-set remap -> enable ARM (SCU70[1:0]=10)
  6. watch the BMC UART (/dev/serial-bmc-console) for output

  uv run p2a-image-boot.py --image path/to/u-boot.bin --watch 30
"""
import argparse, base64, os, subprocess, sys, time

PI, HOST = "asus-bmc", "root@192.168.77.138"
C = "/root/culvert-g3/build/src/culvert"
P = f"{C} p2a vga"
BMC_TTY = "/dev/serial-bmc-console"
AHBK, AHBKV, REMAP = 0x1e600000, 0xaeed1a03, 0x1e60008c
SCU00, SCU00_KEY, SCU70 = 0x1e6e2000, 0x1688a8a8, 0x1e6e2070
WDT_RELOAD, WDT_RESTART, WDT_CTRL = 0x1e785004, 0x1e785008, 0x1e78500c
SCU7C, SCU3C = 0x1e6e207c, 0x1e6e203c


def host(script, timeout=240, want_bytes=False):
    pi_cmd = (f"sshpass -p systemrescue ssh -o StrictHostKeyChecking=no "
              f"-o ConnectTimeout=20 {HOST} bash -s")
    return subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15",
                           PI, pi_cmd], capture_output=True,
                          text=not want_bytes, input=script, timeout=timeout)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--load", type=lambda s: int(s, 0), default=0x40000000)
    ap.add_argument("--watch", type=int, default=30)
    ap.add_argument("--baud", type=int, default=1200,
                    help="UART capture baud (stub=1200; real U-Boot usually 115200)")
    ap.add_argument("--max-patch-iters", type=int, default=6)
    args = ap.parse_args()

    img = open(args.image, "rb").read()
    if len(img) % 4:
        img += b"\x00" * (4 - len(img) % 4)
    nbytes = len(img)
    print(f"[*] image {args.image}: {nbytes} bytes -> DRAM {args.load:#x} (=0x0 via remap)")

    # 1. transfer image to host (base64 through the nested ssh -- binary-safe)
    b64 = base64.b64encode(img).decode()
    r = host(f"base64 -d > /root/payload.bin <<'B64EOF'\n{b64}\nB64EOF\n"
             f"ls -l /root/payload.bin\n")
    sys.stdout.write(r.stdout)
    if "payload.bin" not in r.stdout:
        print("[!] transfer failed"); print(r.stderr[-400:]); return 1

    # 2. siphon the image into DRAM ONCE (fast; ~0.04% burst errors get patched below)
    r = host(f"set -u\n{C} write --type ram {args.load:#x} {nbytes} via p2a vga < /root/payload.bin\necho siphoned\n")
    sys.stdout.write(f"[siphon] {r.stdout.strip()}\n")

    # 3. VERIFY + PATCH loop (read-back + single-word rewrites; NO re-siphon)
    verify = f"""set -u
{C} read --type ram {args.load:#x} {nbytes} via p2a vga > /root/rb.bin
python3 - <<'PY'
import struct
want=open('/root/payload.bin','rb').read(); got=open('/root/rb.bin','rb').read()
base={args.load}; bad=[]
for i in range(0,len(want),4):
    if want[i:i+4]!=got[i:i+4]: bad.append((base+i, struct.unpack('<I',want[i:i+4])[0]))
open('/root/patch.txt','w').write("\\n".join(f"{{a:#x}} {{v:#x}}" for a,v in bad))
print("MISMATCHES", len(bad))
PY
"""
    for it in range(args.max_patch_iters):
        r = host(verify)
        line = [l for l in r.stdout.split("\n") if l.startswith("MISMATCHES")]
        n = int(line[0].split()[1]) if line else -1
        sys.stdout.write(f"[verify iter {it}] mismatches={n}\n")
        if n == 0:
            print("[*] image verified byte-perfect in DRAM"); break
        host(f"set -u\nwhile read a v; do {P} write \"$a\" \"$v\"; done < /root/patch.txt\necho patched\n",
             timeout=300)
    else:
        print("[!] still mismatching after patch iters -- proceeding anyway")

    # start UART capture
    subprocess.run(["ssh", "-o", "BatchMode=yes", PI,
                    f"sudo stty -F {BMC_TTY} {args.baud} raw -echo -crtscts cs8 -parenb -cstopb"],
                   capture_output=True, text=True)
    cap = subprocess.Popen(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", PI,
                            f"sudo timeout {args.watch} cat {BMC_TTY}"],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    time.sleep(2)

    # 4+5. set remap, then reset-boot trick
    boot = f"""set -u
echo '--- set remap ---'
{P} write {AHBK:#x} {AHBKV:#x}; {P} write {REMAP:#x} 0x1; {P} read 0x0
echo '--- disable ARM (SCU70[1:0]=11) ---'
{P} write {SCU00:#x} {SCU00_KEY:#x}
S=$({P} read {SCU70:#x} | grep -oE "0x[0-9a-fA-F]+" | tail -1)
{P} write {SCU70:#x} $(printf "0x%08x" $(( S | 0x1 ))); {P} write {SCU00:#x} 0x0
echo '--- watchdog HRST_N (2s) ---'
{P} write {WDT_CTRL:#x} 0x0; {P} write {WDT_RELOAD:#x} 0x1e8480
{P} write {WDT_RESTART:#x} 0x4755; {P} write {WDT_CTRL:#x} 0x13
sleep 6
echo '--- post-reset: re-set remap, re-verify image survived ---'
{P} read {SCU7C:#x}; {P} read {SCU3C:#x}
{P} write {AHBK:#x} {AHBKV:#x}; {P} write {REMAP:#x} 0x1; {P} read 0x0
echo '--- enable ARM (SCU70[1:0]=10) -> boot 0x0=DRAM ---'
{P} write {SCU00:#x} {SCU00_KEY:#x}
S2=$({P} read {SCU70:#x} | grep -oE "0x[0-9a-fA-F]+" | tail -1)
{P} write {SCU70:#x} $(printf "0x%08x" $(( S2 & ~0x1 ))); {P} write {SCU00:#x} 0x0
echo '--- ARM enabled; watching UART ---'
rm -f /root/payload.bin /root/rb.bin /root/patch.txt
"""
    r = host(boot, timeout=120)
    sys.stdout.write(r.stdout)
    if r.stderr.strip():
        sys.stdout.write("[stderr] " + r.stderr[-300:])

    print(f"\n[*] watching {BMC_TTY} for {args.watch}s ...")
    try:
        out, _ = cap.communicate(timeout=args.watch + 10)
    except subprocess.TimeoutExpired:
        cap.kill(); out, _ = cap.communicate()
    print("=== BMC UART ===")
    print(out.strip() or "(nothing seen)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
