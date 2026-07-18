# W83601G register map — from the official Nuvoton datasheet V1.31 (Mar 2009)

Source (verified, public): `https://www.nuvoton.com/export/resource-files/W83601G_Datasheet_V131.pdf`
(mirror `https://www.insidegadgets.com/wp-content/uploads/2013/10/W83601G.pdf`).
Part matches the KGPE-D16 exactly: *"general purpose input/output ICs with SMBus
(I²C) … provides 15 GPI/O pins … SMBus (I²C) address setting pins"*, 20-pin SSOP,
Port 1 = GP10–GP17, Port 2 = GP20–GP26.

Access model: 8-bit internal index (CR00–CR21), SMBus write-byte
(`addr, index, data`) / read-byte (`addr, index` → restart → `addr|R`, data).

## Register table (§7.1)

| Idx | Name | R/W | Reset | Notes |
|-----|------|-----|-------|-------|
| 00h | Port 1 Input Data | R | — | incoming pin levels, inverted by CR02 |
| 01h | **Port 1 Output Data** | R/W | **0x00** | GP17..GP10 — LED-drive register |
| 02h | Port 1 Polarity Inversion | R/W | **0xF0** | 1 = invert that pin |
| 03h | **Port 1 I/O Config** | R/W | **0xFF** | 1 = input, 0 = output (reset: all inputs) |
| 04h | Port 1 Output Style | R/W | 0x00 | 0 = level, 1 = pulse |
| 05h | Port 1 Input Latched | R | — | latched at POR/RST# |
| 06–07h | Reserved | — | — | silicon reads 0xFF |
| 08h | Port 2 Input Data | R | — | |
| 09h | **Port 2 Output Data** | R/W | **0x00** | GP26..GP20 (bit7 rsvd) — LED-drive |
| 0Ah | Port 2 Polarity Inversion | R/W | **0x70** | |
| 0Bh | **Port 2 I/O Config** | R/W | **0x7F** | reset: all inputs |
| 0Ch | Port 2 Output Style | R/W | 0x00 | |
| 0Dh | Port 2 Input Latched | R | — | **bits[2:0] = SMBus addr A2..A0** |
| 0E–0Fh | Reserved | — | — | |
| 10h | Port 1 Interrupt Status | R | 0x00 | |
| 11h | Port 2 Interrupt Status | R | 0x00 | |
| 12h | Port 1 Interrupt Enable | R/W | 0x00 | |
| 13h | Port 2 Interrupt Enable | R/W | 0x00 | |
| 14h | Mode Configuration | R/W | 0x00 | |
| 15h | Power-LED Configuration | R/W | 0x00 | bit7=1 → HW blink driver |
| 16–1Fh | Reserved | — | — | |
| 20h | Chip ID High | R | **0x60** | |
| 21h | Chip ID Low | R | **0x12** | table says 0x12; §7.2 text says 0x13 (datasheet self-inconsistent) |

## Address / straps

Address byte = `0 0 1 1 A2 A1 A0 R/W`, i.e. **7-bit = 0b0011_A2A1A0 → 0x18…0x1F**.
A0=pin3, A1=pin4, A2=pin5, latched at POR/RST#, internal pull-downs (unconnected → 0);
read back in CR0D[2:0].

## LED-drive sequence (BMC)

1. Clear the target bit in **CR03** (Port 1) / **CR0B** (Port 2) → output mode.
2. Write the bit in **CR01** (GP10–GP17) / **CR09** (GP20–GP26).
   Account for the CR02/CR0A polarity-inversion resets (0xF0 / 0x70) on the
   upper bits when reasoning about on/off level.

No dedicated in-tree Linux driver (kernel `gpio-winbond.c` is the *SuperIO/LPC*
GPIO block, a different chip) — the BMC drives it as a raw SMBus device.

## Silicon cross-check (2026-07-18, this board)

`i2cget -y 4 0x18 0x01 → 0x00` == datasheet CR01 reset 0x00 ✓ (confirms the part).
`i2cget -y 4 0x18 0x07 → 0xff` == reserved-index open-bus read ✓.
`i2cget -y 4 0x18 0x00 → 0x0f`, `0x19 0x00 → 0xb5` = Port-1 input levels (board /
strap dependent; seeded per-instance in the QEMU model).
