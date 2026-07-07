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

## The one remaining piece — the exact CMOS byte+bit per option
The AMIBIOS8 setup module binds each option's string-token to a CMOS byte+bit,
but parsing that table statically is AMIBCP-level work. The reliable, definitive
method is a **one-shot empirical CMOS diff**, per option:
```
read /dev/nvram (baseline)  →  change ONE option in Setup  →  read /dev/nvram  →  diff = that option's byte+bit
```
Do this once the battery is in (so a single menu pass sticks), driven over the
Magewell; thereafter every change is a menu-less `/dev/nvram` write + checksum
fixup. And once **serial redirection** is confirmed on, all future BIOS access is
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
