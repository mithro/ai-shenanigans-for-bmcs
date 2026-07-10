# In-system CMOS BIOS-settings editor (staged)

Everything needed to read and change KGP(M)E-D16 BIOS settings **from Linux on the
booted host, without the BIOS menu** — staged here, to be run when the board is up.
Built from the module-1B static decode (cross-validated by AMIBCP, see
[`../amibcp/README.md`](../amibcp/README.md)) and the analysis in
[`../BIOS-CONFIG-WITHOUT-MENU.md`](../BIOS-CONFIG-WITHOUT-MENU.md).

> **Not run against hardware from here.** The board is currently powered off /
> in use by another task. Run `bios_cmos.py` as root on the host itself.

## Files
- **`cmos_map.json`** — the setting map. `simple_cmos_settings` (15) are
  statically decoded with a real **CMOS byte** (index 0x00–0x7F); the byte-index
  reading is verified (all in range; LAN1=`0x56`, LAN2=`0x64` match AMIBCP).
  `extended_settings_of_interest` (serial/power/…) are `Ext.Func` questions whose
  byte must be **learned by diff** (they don't use the simple grammar).
- **`bios_cmos.py`** — the tool (stdlib only, `uv run`). Accesses RTC CMOS via I/O
  ports **70h/71h** through `/dev/port` (full 0x00–0x7F; avoids the kernel nvram
  driver's own checksum so the *BIOS* checksum is handled explicitly).

## Confidence (read before writing)
| Layer | State |
|---|---|
| CMOS **byte** of `simple_cmos_settings` | verified (byte-index, 0x00–0x7F; LAN1/LAN2 match AMIBCP) |
| **Bit** within a *byte-owned* setting (LAN1/LAN2) | assumed low bits — confirm with one `learn` |
| **Bit** within a *shared* byte (ACPI group @0x3A, …) | unknown — **must** `learn` |
| Byte+bits of `extended_settings_of_interest` (serial) | unknown — **must** `learn` |
| Value-code == option index | assumed — confirm with `learn` |
| **BIOS checksum** range/location | UNVERIFIED — find with `checksum`/`learn` before any write |

## Workflow on the booted host
```sh
sudo -E uv run bios_cmos.py dump  baseline.cmos     # snapshot all 128 bytes
sudo -E uv run bios_cmos.py show                    # decode current mapped values
sudo -E uv run bios_cmos.py checksum                # identify the live BIOS checksum word

# learn any setting's exact byte+bits (serial + bit-packed) — one menu change each:
sudo -E uv run bios_cmos.py learn "Serial Port Mode"
#   -> snapshot A ; you set it to 115200 in Setup, save, reboot to OS ; snapshot B ; diff

# once byte+bits+checksum are known, write (dry-run first):
sudo -E uv run bios_cmos.py set "Onboard LAN1 Boot=PXE"                      # DRY-RUN
sudo -E uv run bios_cmos.py set "Onboard LAN1 Boot=PXE" --apply --checksum-verified
```
`dump`/`diff`/`show`/`learn`/`checksum` are read-only. `set` is dry-run unless
`--apply`, and `--apply` refuses to write until `--checksum-verified` (an unfixed
checksum makes the BIOS silently reload defaults on next boot).

## The changes we actually want (from the AMIBCP defaults review)
Serial redirection is already *Enabled* and LAN-Boot already *PXE* by default — so
the useful edits are the sub-values:
1. **Serial Port Mode → `115200 8,n,1`** (stock default index 01 ≈ 57600 — a 115200
   capture sees nothing) — `learn` then `set`.
2. **Redirection After BIOS POST → `Always`** (so the OS console redirects, not just POST).
3. **Serial port number → `COM1`** (confirm).
4. **Boot order → Network first** (Boot page) for PXE. *(Boot order is an ordered
   list, not a simple enum — `learn` shows which CMOS bytes hold it.)*

## Alternative: the AMIBCP ROM-edit route
Instead of live CMOS, edit these defaults in AMIBCP, `File → Save`, and reflash the
ROM (external via the socketed W25Q16 / spispy, or in-system with `amd_imc_force`).
No CMOS byte or checksum needed — see [`../amibcp/README.md`](../amibcp/README.md).
```
