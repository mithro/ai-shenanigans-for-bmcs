# Changing KGPE-D16 BIOS settings without the menu

Goal: enable **serial console redirection** and **network/PXE boot** on the ASUS
KGP(M)E-D16 host without navigating the interactive BIOS menu (we can see the
screen over the Magewell HDMI capture but can't type to the host). Analysis is
from the stock BIOS image dumped in-system with flashrom
([`backup/kgpe-d16-ami-bios-3309.bin`](backup/kgpe-d16-ami-bios-3309.bin),
2 MB Winbond W25Q16, `sha256 671e62ca…`). Verified 2026-07-08.

## What the firmware is (and what that rules out)
- Legacy **AMIBIOS8** — `bios_extract` reports *AMI95 Version 0800 (06/16/16)*;
  setup engine `av02.61 (C)1985-2010 American Megatrends`. **Not Aptio/UEFI**
  (no `/sys/firmware/efi`), so **AMISCE / SCELNX_64 does not apply** (that's an
  Aptio EFI-variable tool).
- Settings live in **battery-backed CMOS RTC NVRAM**. The CMOS coin cell was
  **replaced 2026-07-08**, so CMOS writes now **persist across power-off**, and the
  cold-boot *F1=Setup / F2=defaults* halt + wrong-boot-clock (which had been
  breaking TLS for `pacman`/`git`) should be gone. (Before the swap, the dead
  battery reset CMOS on every power-off.)
- Flash is a **socketed** 2 MB W25Q16; flashrom reads it in-system, but WRITE is
  disabled by the SP5100 **IMC** guard (needs `amd_imc_force`; external flashing
  is the safe route).

## The options to set — confirmed in the BIOS code
Decompressed the AMIBIOS8 modules with coreboot `bios_extract`: the human labels
are in `amilang_US.rom` (Multilanguage), the setup question logic in
`amibody_04.rom` ("Setup Client"). In AMIBIOS8 a question's option values sit
contiguously after its label, so these lists are the ROM's own option sets.

### Serial console redirection  (menu path: Advanced → Remote Access)
| Option (ROM string) | Set to | Values present in ROM |
|---|---|---|
| Console Redirection / Remote Access | **Enabled** | Enabled / Disabled |
| Serial port number | **COM1** | COM1, COM2 |
| Serial Port Mode | **115200 8,n,1** | 115200 / 57600 / 38400 / 19200 8,n,1 |
| Terminal Type | **VT100** | VT100 (… ANSI/VT-UTF8) |
| Flow Control | **Disabled** | Enabled / Disabled |
| SuperIO `Serial Port1 Address` (Advanced → SuperIO) | **Enabled** | (address/Disabled) |

### Network / PXE boot  (menu path: Boot / Advanced)
| Option (ROM string) | Set to | Values present in ROM |
|---|---|---|
| Onboard LAN1 Boot (and/or LAN2 / "Onboard LAN Boot") | **PXE** | PXE / iSCSI / (Disabled) |
| Boot Device Priority → 1st device | **Network Card** | Removable / HDD / CD-ROM / Network Card … |

### Bonus — auto power-on
| Restore on AC Power Loss | **Power On** | Power On / Power Off / Last State |

Set this and the board powers on with AC instead of needing the Tasmota plug
(`au-plug-10`) toggled.

## CMOS byte-programming mechanism
1. CMOS RTC NVRAM = `/dev/nvram` (char 10,144) and I/O ports 0x70/0x71; the
   general-purpose bytes are offset ≥ 0x0E. Writable as root (dump captured in
   `hardware-inventory/`).
2. After writing option bytes you **must recompute the AMIBIOS CMOS checksum**
   (16-bit sum over the CMOS data range, stored in two CMOS bytes) — otherwise the
   BIOS reports *CMOS checksum bad*, loads defaults, and discards the change on
   the next boot.
3. With the coin cell **replaced (2026-07-08)** the written CMOS now **persists
   across power-off** (previously, the dead battery meant a change only survived a
   *warm* reboot).

## Static parse of the setup table (module 1B) — results
The **setup question table** is in the decompressed runtime module
`amibody_1b.rom` (the "SLAB"), laid out per setup page. A question record is:
```
<prompt-token:2> <help-token:2> 91 02 <parent-token:2> <cmos-byte> <mask-byte> 80 <count:1> <value-token>×count 0x01
```
Worked example — the two Onboard-LAN-Boot questions, identical except for their
CMOS index:
```
Onboard LAN1 Boot:  6a04 2596 91 02 046c | D6 16 | 80 03 | 00ba 046d 046e | 01
Onboard LAN2 Boot:  6b04 2598 91 02 046c | E4 16 | 80 03 | 00ba 046d 046e | 01
                    prompt help          | cmos·mask| fl·cnt| Disabled/PXE/iSCSI
```
- **`cmos-byte`**: bit 7 = shown/hidden flag; bits 0–6 = the **RTC CMOS index**
  (0x00–0x7F).
- **`mask-byte`**: bitfield position/width within that CMOS byte.
- **`80 <count>`**: flag + **number of option values**; exactly `count` value-tokens
  follow (LAN Boot = 3 values → `03`, and `00ba 046d 046e` = Disabled/PXE/iSCSI ✓).

### Decoded RTC CMOS locations (index = byte & 0x7F)
| Setting | CMOS index | mask | # values |
|---|---|---|---|
| ACPI 2.0 Support | 0x3A | 0x15 | 3 |
| Onboard LAN1 Boot | **0x56** | 0x16 | 3 |
| Onboard LAN2 Boot | **0x64** | 0x16 | 3 |

**Corrected reading** (was previously mis-read as a flash-NVRAM word offset): the
byte after the CMOS index is the *mask* (varies per setting), not a word's high
half — so these settings live in the **128-byte RTC CMOS** (`/dev/nvram`, ports
70/71h), matching the documented AMIBIOS8 format (RTC index with **bit 7 = shown**,
per the [Win-Raid legacy-AMIBIOS8 guide](https://winraid.level1techs.com/t/guide-legacy-amibios8-make-all-compiled-settings-available/37221))
and the dead-battery F1/F2 symptom. RTC CMOS is the write target; the fresh
battery (2026-07-08) makes it persist.

Only the LAN/ACPI records use this exact 3-value variant; the **serial options are
a sibling variant on the Remote Access page** — the complete, exact map for every
setting is best pulled from **AMIBCP** (see below).

## Cross-validated with AMIBCP (+ the stock defaults)
AMIBCP 3.51 was run on the dump **sandboxed** (dedicated user + no network + VNC
:99) — see [`amibcp/README.md`](amibcp/README.md). It does **not** expose the raw
CMOS offset (so the hand-decode above stays the offset source), but its **Handle**
column equals our tokens 1:1 (03BA/0458/03B4/0456/046A/046B/01C9 all confirmed),
independently verifying the module-1B decode.

It also revealed the **stock defaults reframe the task**: `Remote Access` (serial
redir) is **Enabled** by default and `Onboard LAN1/LAN2 Boot` default to **PXE** —
so nothing is "off". The real changes are the sub-values:
1. **Serial Port Mode → 115200** (Optimal default index 01 = 57600 by the ROM's
   value order — a 115200 capture would see nothing),
2. **Redirection After BIOS POST → Always** (default 00 likely stops redir after POST),
3. confirm **Serial port number = COM1**, and
4. **Boot order → Network first** for PXE (Boot page) — LAN-boot itself is already PXE.

Confirm any exact CMOS byte with a one-shot empirical diff:
```
dump /dev/nvram  →  change ONE option in Setup (Magewell)  →  dump  →  diff = that option's byte+bit
```
Once serial redirection at the right baud is confirmed, all future BIOS access is
over `/dev/serial-com1` — no menu, no Magewell.

## Tooling used (installed locally)
- `bios_extract` (coreboot) — decompresses the AMIBIOS8 LZH modules (the
  `amideco` engine). Built in `tmp/bios-tools/`.
- `binwalk 2.1.0` — general firmware carving.
- flashrom (on the rescue host) — in-system SPI read of the W25Q16.

## Strategic alternative — coreboot / libreboot
Menu-less by design (build-time Kconfig + `nvramtool`), **serial console + iPXE/
SeaBIOS netboot native**, and **dead-battery-proof**. Flash the socketed W25Q16
externally via the ULX3S-spispy / Pi-SPI rig. The dumped AMI image is the backup
and the source of the AGESA / CPU-microcode / VBIOS blobs. The KGPE-D16 is a
flagship libreboot board (Raptor Engineering's port) — this is the project's
endgame.
