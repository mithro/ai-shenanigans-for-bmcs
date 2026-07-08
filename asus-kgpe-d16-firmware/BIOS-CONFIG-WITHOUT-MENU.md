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
- Settings live in **battery-backed CMOS RTC NVRAM**. With the current **dead
  CMOS battery** they don't survive a power-off (this is also why every cold
  boot halts at the AMI *F1=Setup / F2=defaults* prompt). Replacing the battery
  makes CMOS writes persistent.
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
3. With a **good battery** the written CMOS persists across power-off; with the
   dead battery it only survives a *warm* reboot (RTC stays powered).

## Static parse of the setup table (module 1B) — results
Going deeper than the string list: the **setup question table** is in the
decompressed runtime module `amibody_1b.rom` (the "SLAB"), laid out per setup
page. Each question record is:
```
<prompt-token:2> <help-token:2> <0x0291> <parent-token:2> <STORAGE-word:2> <0x0380> <value-token>... 0x01
```
Worked example — the two Onboard-LAN-Boot questions, structurally identical
except for their storage handle:
```
Onboard LAN1 Boot:  6a04  2596  0291  046c  16d6  0380  00ba 046d 046e  01   (Disabled/PXE/iSCSI)
Onboard LAN2 Boot:  6b04  2598  0291  046c  16e4  0380  00ba 046d 046e  01
                    prompt help  --   --    STORE  --    values           end
```
The value lists (Disabled / PXE / iSCSI) are confirmed inline; the records differ
only in prompt token, help token, and the **STORAGE word** (`0x16d6` vs `0x16e4`).
(Other pages — Remote Access/serial, power — use the same record grammar with
minor per-page variation; the serial options sit on the Remote Access page around
module-1B offset 0x11fxx.)

### Course-correction from the parse
`0x16d6` is **far beyond the 128-byte RTC CMOS** (indices 0x00–0x7F). So these
settings are stored in AMIBIOS8's large **"setup variable" NVRAM** (flash-backed),
**not** the RTC CMOS that the F1/F2 checksum guards. Consequences:
- They very likely **persist across power-off even with the dead battery** (flash,
  not battery-backed) — the dead battery may only be resetting the *core* RTC-CMOS
  settings (date, and whatever trips the checksum).
- A plain `/dev/nvram` (RTC) write will **not** reach them. The menu-less write
  target is the **flash NVRAM store** (or coreboot), and any empirical diff must
  watch the flash region, not just `/dev/nvram`.

## Confirming the exact storage location per option
Two complementary methods:
1. **Empirical diff on the right medium** — baseline, change ONE option in Setup,
   re-read, diff. Do it against **both** `/dev/nvram` (RTC) **and** a flashrom
   re-read of the NVRAM region, so we see which medium each setting lands in:
   ```
   dump A  →  change ONE option in Setup  →  dump B  →  diff(A,B) = that option's bytes
   ```
   Best done once the battery is in (a single menu pass sticks), driven over the
   Magewell. Once **serial redirection** is confirmed on, all future BIOS access is
   over `/dev/serial-com1` — no menu, no Magewell.
2. **Finish the static decode** — map the STORAGE word (e.g. `0x16d6`) to a
   physical NVRAM offset by locating the setup-variable base in module 1B / the
   flash NVRAM block. This yields offsets with no menu at all, cross-checked by (1).

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
