# ASUS KGPE-D16 — schematic-derived chip wiring

Pin-level wiring documentation for the ASUS **KGPE-D16** (rev 1.04B), reverse-
engineered from its OpenBoardView `.FZ` schematic export. The focus is the three
chips that matter for the open-BMC / open-firmware work in this repo — the
**ASPEED AST2050 BMC**, the **AMD SP5100 southbridge**, and the **Nuvoton
W83667HG-A Super-I/O** — documenting every pin of each, by function, with
diagrams, and every net traced through the muxes/expanders/buffers to its far
end.

This complements the firmware/device-tree analysis in the rest of
[`../`](..): the netlist is the physical ground-truth that the firmware's
I²C/GPIO/LPC assumptions must match.

> Every support-chip identity here is **read from the schematic's part-description
> field** (the KGPE-D16 `.FZ` carries full descriptions), so part numbers are
> quoted from the board, not inferred.

## Documents

| Document | Chip | Pins |
|---|---|---|
| **[AST2050-BMC-WIRING.md](AST2050-BMC-WIRING.md)** | ASPEED AST2050A3-GP BMC (`QU1`) | 355 |
| **[SP5100-SOUTHBRIDGE-WIRING.md](SP5100-SOUTHBRIDGE-WIRING.md)** | AMD SP5100 southbridge (`SU1`) | 528 |
| **[W83667HG-SUPERIO-WIRING.md](W83667HG-SUPERIO-WIRING.md)** | Nuvoton W83667HG-A Super-I/O (`OU1`) | 128 |
| **[BMC-CONNECTORS.md](BMC-CONNECTORS.md)** | Connectors/headers/jumpers wired to the BMC — physical pinout diagrams + tables | — |
| [pinmaps/QU1_pins.md](pinmaps/QU1_pins.md) · [SU1_pins.md](pinmaps/SU1_pins.md) · [OU1_pins.md](pinmaps/OU1_pins.md) | machine-generated exhaustive per-pin tables (each section lists the components those pins connect to) | — |

## Confirmed chip inventory (from the schematic)

| Ref | Part | Role |
|---|---|---|
| `QU1` | ASPEED AST2050A3-GP (TFBGA-355) | BMC / iKVM SoC |
| `SU1` | AMD SP5100 (`218-0660026`, FCBGA-528) | Southbridge / FCH |
| `NU1` | AMD SR5690 (`215-0716038`, FCBGA-692) | Northbridge |
| `OU1` | Nuvoton W83667HG-A (QFP-128) | Super-I/O |
| `QU2` | Hynix HY5PS121621CFP-25 | BMC DDR2 DRAM (64 MB) |
| `QU4` | Winbond W83795G (LQFP-64) | Hardware monitor |
| `U5` | Realtek RTL8201N-GR (QFN64) | BMC management LAN PHY |
| `LU1`/`LU2` | Intel WG82574L (QFN64) | Host gigabit NICs |
| `U27`/`U28` | Winbond W83601G (SSOP20) ×2 | DIMM error-LED I²C GPIO expanders |
| `U25` | Holtek HT24LC08 | Board FRU EEPROM |
| `QU9` | TI SN74CBTLV3125 | I²C FET bus switch |
| `QU5` | 74HC4052 | Dual 4-ch I²C mux (DIMM SPD fan-out) |
| `QU8` | Pericom PI5C3257 | 2:1 UART mux (SOL) |
| `U23` | 74LVC125 | BMC-vs-SB I²C source-select |
| `CU1` | IDT ICS932S890 | Clock generator |
| `U12`/`U13` | BCD AZ75232 | RS-232 transceivers |
| `PU22`/`PU28` | UPI UP7706U8 | BMC +1V2/+1V8 aux LDOs |

## Key findings (BMC)

- **Always-on.** Every BMC rail is standby (`_AUX`): `+5VSB → +1V8_AUX (PU28) →
  +1V2_AUX (PU22)`, plus `+3V3_AUX`. The BMC runs whenever the PSU has AC.
- **Three personalities.** Baseboard controller (LPC/PCI/GPIO), remote-KVM engine
  (own DDR2 frame buffer `QU2`, VGA out, USB-device port, PCI VGA capture), and
  dual Ethernet — a dedicated RTL8201N management PHY over MII **and** an NC-SI
  sideband sharing the two Intel 82574L host NICs.
- **Socketed firmware** (`BMC_FW1`, and the host BIOS `FU1`) — both flashes are
  field-replaceable.
- **8 I²C/SMBus buses** fanning through a FET switch (`QU9`), a 4-channel mux
  (`QU5`) and a source-select buffer (`U23`) to the W83795G hardware monitor, two
  W83601G DIMM-error-LED expanders, a HT24LC08 FRU EEPROM, the PSU, and all 16
  DIMM SPD/thermal sensors. [BMC §10](AST2050-BMC-WIRING.md#10-i²c--smbus-topology-traced-through-every-mux--expander)
  gives per-device addresses, protocols and the exact mux-selection steps.

## Regenerating the data

The raw ASUS `.FZ` schematic and the bulk netlist dumps derived from it are
**not** committed (see `.gitignore`) — regenerate locally.

### 0. Provide the FZ decryption key (one-time setup)

The `.FZ` files are RC6-encrypted. The 44-word key is **not stored in this
repository**. Put it in a local `.env` (gitignored):

```sh
cp .env.example .env
# edit .env and set OBV_FZKEY to the 44 hex words
```

**Where to get the key.** It is the standard, publicly-circulated OpenBoardView
FZ key — not per-board and not secret to this project; it validates against the
parity signature built into OpenBoardView (`FZFile::getKeyParity()`). Get it from
your own `~/.config/OpenBoardView/obv.conf` (the `FZKey = ...` line) after
entering it once, or from a community `obv.conf` (web-search `OpenBoardView FZKey
obv.conf`). All 44 words are required. `.env.example` documents this too.

### Then regenerate

```sh
# schematic: ASUS_KGPE-D16_Rev_1.04_-_Schematics.zip -> a .FZ (any SKU; the
# doc used "KGPE-D16 r1.04B(59SB0010-MB0D06S).FZ")

# 1. Extract the .FZ into board.json
uv run tools/extract_fz.py "/path/to/KGPE-D16 r1.04B(...).FZ" --json data/board.json

# 2. Generate the per-pin map for any reference designator
uv run tools/pinmap.py data/board.json QU1 > pinmaps/QU1_pins.md   # BMC
uv run tools/pinmap.py data/board.json SU1 > pinmaps/SU1_pins.md   # southbridge
uv run tools/pinmap.py data/board.json OU1 > pinmaps/OU1_pins.md   # Super-I/O
```

Scripts are stdlib-only PEP 723 and run directly with `uv run`.

## Tools

| Tool | Purpose |
|---|---|
| `tools/extract_fz.py` | RC6-decrypt + zlib-inflate + parse a `.FZ` into parts/pins/nets JSON. Reads the key from `$OBV_FZKEY` / `.env`. |
| `tools/pinmap.py` | Per-pin functional map for any refdes; groups pins by function, lists the connected components per section, resolves nets through series resistors and isolated resistor networks, and summarises shared buses. |
| `tools/classify.py` | AST2050-specific ball classification (used while developing the BMC doc). |

## Provenance & scope

Transformative interoperability analysis (pin functions and net connectivity),
consistent with the rest of this reverse-engineering repo. The raw ASUS schematic
database is not redistributed here.
