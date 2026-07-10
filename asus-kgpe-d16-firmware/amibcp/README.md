# AMIBCP under wine — reading the KGPE-D16 setup structure (sandboxed)

We ran **AMIBCP 3.51** (the AMIBIOS8 line) on the dumped stock BIOS
([`../backup/kgpe-d16-ami-bios-3309.bin`](../backup/kgpe-d16-ami-bios-3309.bin))
to independently verify the module-1B hand-decode in
[`../BIOS-CONFIG-WITHOUT-MENU.md`](../BIOS-CONFIG-WITHOUT-MENU.md) and read the
stock defaults. AMIBCP is a proprietary Windows tool, so it runs **fully
sandboxed**. Done 2026-07-08.

## The sandbox (proper, tested)
AMIBCP is an untrusted third-party binary, so it does **not** run as your user:
- **Dedicated unprivileged user `amibcp`** (uid 30033) — and `/home/tim` is
  `drwx------`, so the sandbox user literally cannot read your home (wine even
  errors "could not open Z:\home\tim" — that's the isolation working).
- **No network**: an nftables rule drops *all* IP traffic from uid 30033
  (verified — `curl` to GitHub *and* a raw IP both blocked). AMIBCP can't
  phone home or exfiltrate.
- **Throwaway display**: renders only to VNC `:99`
  ([`scripts/vnc-display.sh`](../../scripts/vnc-display.sh)); driven headlessly
  with `xdotool`, captured with `import`.
- Binary obtained from GitHub `direstraits96/BIOS-MOD-TOOLS` (versioned/visible,
  not an aggregator): **AMIBCP 3.51** `sha256 0d630b4b…`. The 4.x/5.x line is
  Aptio-only and will not open this AMI95 ROM.

Reproduce (scripts in `tmp/`): `setup_amibcp_sandbox.py` (download + user + nft +
wineprefix), then `launch_amibcp.py` (verify no-net, launch), then the
`drive*_amibcp.py` steppers (xdotool navigation + screenshots). For extra
hardening the launch can be wrapped in `bwrap --unshare-net` (bubblewrap +
unprivileged userns are available).

```sh
# essence of the sandboxed run:
sudo useradd -m amibcp
sudo nft add table inet amibcp_sbx
sudo nft 'add chain inet amibcp_sbx out { type filter hook output priority 0; policy accept; }'
sudo nft add rule inet amibcp_sbx out meta skuid amibcp drop      # no network
scripts/vnc-display.sh start ; xhost +si:localuser:amibcp          # X :99 only
sudo -u amibcp env HOME=/home/amibcp WINEPREFIX=/home/amibcp/.wine DISPLAY=:99 \
     wine /home/amibcp/AMIBCP.exe                                  # File>Open the .bin
```

## What AMIBCP shows (and doesn't)
The **Setup Configuration** tab lists, per question: **Handle**, name, Display
Status, Access/Use, and **Failsafe/Optimal defaults**. It does **not** expose the
raw **CMOS byte offset** (no column, no per-item dialog, no View toggle) — so the
CMOS offsets still come from the hand-decode; AMIBCP is the structural
cross-check + the defaults + a ROM editor.

## Result 1 — the hand-decode is verified
Every handle AMIBCP shows equals a token from the module-1B decode:

| Setting (page) | AMIBCP handle | hand-decode token |
|---|---|---|
| Serial Port Mode (Server → Remote Access) | 03BA | 0x03BA ✓ |
| Flow Control | 0458 | 0x0458 ✓ |
| Terminal Type | 03B4 | 0x03B4 ✓ |
| Redirection After BIOS POST | 0456 | 0x0456 ✓ |
| Serial Port1 Address (Advanced → Onboard Devices) | 01C9 | 0x01C9 ✓ |
| Onboard LAN1 Boot | 046A | 0x046A ✓ |
| Onboard LAN2 Boot | 046B | 0x046B ✓ |

Evidence: [`remote-access-serial.png`](remote-access-serial.png),
[`onboard-devices-lan-boot.png`](onboard-devices-lan-boot.png),
[`rom-loaded.png`](rom-loaded.png).

## Result 2 — the stock defaults (this reframes the task)
| Setting | Handle | Optimal default | note |
|---|---|---|---|
| **Remote Access** (serial redir enable) | 03B2 | **01 = Enabled** | already on |
| Serial port number | 03B6 | 01 | COM index |
| **Serial Port Mode** (baud) | 03BA | **01** | value order 115200/57600/38400/19200 ⇒ **57600** |
| Flow Control | 0458 | 01 | |
| **Redirection After BIOS POST** | 0456 | **00** | likely stops redir after POST → no OS console |
| Terminal Type | 03B4 | 02 | |
| **Onboard LAN1/LAN2 Boot** | 046A/046B | **PXE** | netboot already selected |

So serial redirection and PXE are **already enabled by default** — the real fixes are:
1. **Serial Port Mode → 115200** (default appears to be 57600; a 115200 capture sees nothing),
2. **Redirection After BIOS POST → Always** (so the OS console is redirected, not just POST),
3. confirm **Serial port number = COM1**, and
4. for netboot, **Boot order → Network first** (Boot page) — the LAN-boot toggle is already PXE.

## Changing the settings — two routes
1. **AMIBCP ROM-edit + reflash (menu-less, permanent default).** In AMIBCP set the
   Optimal/Failsafe value (or default) for the four items above, **File → Save**,
   and flash the modified ROM: external via the socketed W25Q16 / ULX3S-spispy rig
   (safe), or in-system `flashrom -p internal … amd_imc_force` (risky). No CMOS
   byte needed — AMIBCP edits the setup defaults directly.
2. **Live CMOS write (host booted).** Use the hand-decoded CMOS offsets
   (LAN1 Boot `0x56`, LAN2 `0x64`, ACPI 0x3A; serial page offsets decoded the same
   way) to read-modify-write `/dev/nvram` + fix the checksum. Persists (fresh
   battery). Confirm each offset with a one-shot CMOS diff when the host is back up.
```
