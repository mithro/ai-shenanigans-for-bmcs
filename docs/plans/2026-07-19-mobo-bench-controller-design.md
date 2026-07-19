# Design: `mobo-bench` — a ULX3S LiteX bench controller for the KGPE-D16

Status: draft for review · Date: 2026-07-19 · Owner: mithro

> Repository name **proposed** as `mobo-bench` (under the `mithro` GitHub user);
> confirm before the repo is created in P0. Alternatives considered:
> `bench-controller`, `ulx3s-bench`.

## 1. Purpose

A single FPGA "bench controller" on the ULX3S (Lattice ECP5) that terminates
**every** debug/control connector of an ASUS KGPE-D16 motherboard through one
**fixed cable harness**, and exposes them all — concurrently — to a Raspberry
Pi 5 over USB (with ESP32 Wi-Fi as a later alternate transport). The goal is
complete remote control, debugging, and development of **both** coreboot (host
x86) and BMC (ASPEED AST2050) firmware, with **no re-cabling** to switch
functions.

This is the successor to `osresearch/spispy` (single SPI-flash emulator): same
board, far broader scope, rebuilt as a LiteX SoC.

### Success criteria (MVP milestone)

From the Pi 5, through one harness, with **stock host tools**:
- boot the AST2050 BMC from an **emulated** SPI flash image,
- watch/interact with the **BMC console** as a normal `/dev/ttyACM*`,
- run **OpenOCD** against the BMC ARM TAP (IDCODE `0x07926f0f`),
- all three at once, plus the host BIOS flash emulated read-only.

## 2. Key decisions (from brainstorming)

| Decision | Choice | Rationale |
|---|---|---|
| SoC framework | **LiteX** (Migen), small VexRiscv-class CPU | resource-efficient, gives bridge/CSR/RemoteClient for free |
| Target board | **45F first, then optimize to fit 12F/25F** | dev headroom on 45F; two boards (45F + 12F), each on its own RPi 5 |
| USB | **soft USB hub (Greg Davill hub emulation)** presenting multiple **standard** USB devices; full-speed (US2 has no ULPI) | stock host tools work unmodified; one FPGA USB port → many logical devices |
| Control plane | LiteX **wishbone bridge** device → `litex_server` + `RemoteClient` | free CSR/memory access for debug |
| SPI-flash emulation | **custom core** (LiteSPI is master-only); LiteDRAM-backed; port/adapt `ArthurHeymans/NORbert` (full command set) with `osresearch/spispy` as the ULX3S-proven baseline | no off-the-shelf device emulator exists |
| SPI timing | may use **fast-read (0x0B) dummy cycles** / extra dummy cycles for latency slack | relaxes spispy's hard ~50 ns first-bit constraint; must stay compliant with AST2050/BIOS needs |
| SPI R/W | **BIOS = read-only; BMC = read+write** (start read-only). Both flashes ideally concurrent; **initially one-at-a-time is acceptable** | matches use: capture BMC writes; BIOS images loaded host-side |
| Serial | **≥1 TTL UART** (BMC console) + **≥2 full RS-232 UARTs** (host COM1/COM2 via on-harness MAX3232) | inventory: BMC console is 3V3 TTL; host COM is RS-232 |
| JTAG | generic JTAG masters for **BMC ARM TAP and AMD HDT**; probe protocol = **XVC** | XVC is OpenOCD's easy-to-implement + batched/high-throughput option; reuses `mithro/rp1-jtag` XVC tooling |
| GPIO | jumpers (VGA_SW1, IPMI_SEL1, RECOVERY1, CLRTC1…), front-panel buttons/LEDs, BMC straps | read/write via CSRs |
| Activity LEDs | 8 ULX3S LEDs stretch-pulse on SPI/UART/JTAG access | at-a-glance activity |
| Verification | **RPi 5 `rp1-pio` / `rp1-jtag`** as a hardware-in-the-loop (HIL) test harness | validate each core (SPI master reads, JTAG scans, UART loopback) before/again-with the real board |
| Delivery | phased sub-projects, each its own spec→plan→build→review; new `mithro` repo added here as a **git submodule** | manage scope; some phases run in parallel |

### Out of scope / accepted constraints
- **AMD HDT run-control protocol is proprietary.** We provide a generic JTAG
  master to the HDT header (fine-pitch 1.27 mm adapter on the harness) so IDCODE
  scans / experimentation are possible; useful AMD debug is not guaranteed.
- Soft USB is **full-speed (~160 KB/s)**. Fine for control + UART + JTAG; a
  16–64 MB flash image is minutes to stream — image loads use a faster path
  (see §5, "flash image loading").

## 3. Architecture

```
KGPE-D16 connectors        harness           ULX3S · LiteX SoC            soft USB hub → RPi 5 host
------------------------   ---------------   -------------------------    --------------------------------
BMC_FW1  (BMC SPI R/W) ─┐  direct 3V3        spiflash_emu ×2 + LiteDRAM   wishbone bridge → litex_server
FU1      (BIOS SPI RO) ─┤                    uart_bridge ×N               CDC-ACM ×N      → one tty/port
AST_UART1 (TTL console)─┤  MAX3232 ×2+       jtag_master ×N (XVC)         XVC-over-USB(+socat) → openocd
COM1/COM2 (RS-232)     ─┤  (TTL↔RS-232)      gpio banks                   serprog ×N      → flashrom
AST_JTAG1 (BMC TAP)    ─┤  1.27mm adapter    activity LEDs                (ESP32 Wi-Fi: later alt xport)
AMD HDT   (host CPU)   ─┤  (HDT)
PANEL1/jumpers/straps  ─┘  direct 3V3
```

**USB device model (the crux).** One FPGA USB-FS port → soft hub → several
independent standard-class devices so no custom host protocol is needed where a
standard one exists:
- **wishbone bridge** — LiteX UARTBone/etherbone endpoint → `litex_server` + `RemoteClient` (CSR/memory debug).
- **CDC-ACM ×N** — one `/dev/ttyACM*` per UART port (`screen`/`minicom`).
- **XVC JTAG ×N** — one per TAP (BMC, HDT). `xvc.c` is TCP-socket, so a ~10-line
  `socat TCP-LISTEN:2542 → /dev/ttyACM*` shim on the Pi bridges USB↔TCP (or run
  XVC over Ethernet/ESP32 with no shim). Batched (whole-scan) → high throughput.
- **serprog ×N** — flashrom's serial programmer protocol → load/verify the
  emulated flash images with stock `flashrom`.

### 3.1 Connector inventory (P0 input)

In-scope KGPE-D16 connectors, from the schematic-derived docs under
`asus-kgpe-d16-firmware/schematic-wiring/` (authoritative) and the older
photo/manual docs (noted). All BMC-domain lines are 3V3 LVCMOS and directly
drivable; host COM is RS-232 (needs on-harness MAX3232); AMD HDT is fine-pitch
+ proprietary.

| Connector | Function / chip | Pins | Level | Source doc |
|---|---|---|---|---|
| `BMC_FW1` | BMC boot SPI **R/W** (AST2050) + 3 straps | 2×7 DIP (13) | 3V3 | `BMC-CONNECTORS.md`, `AST2050-BMC-WIRING.md §4`, `ULX3S-SPISPY-BMC-FLASH-WIRING.md §3` (spispy-compatible) |
| `FU1` | host BIOS SPI **RO** (SP5100) | DIP-8 | 3V3 std-by | `SP5100-SOUTHBRIDGE-WIRING.md §8` |
| `AST_UART1` | BMC console UART (TTL) | 1×4 | 3V3 TTL 115200 | `BMC-CONNECTORS.md`, `RPI4-OPENOCD-JTAG-WIRING.md §3` |
| `COM1`/`COM2` | host serial (Super-I/O → AZ75232) | DB9 / 10-1 | **RS-232** | `W83667HG-SUPERIO-WIRING.md §4` |
| `AST_JTAG1` | BMC ARM926 TAP (IDCODE `0x07926f0f`) | 2×10 · 2.54mm | 3V3 | `JTAG-HEADERS.md` (Header 1) |
| `AMD HDT` | host CPU HDT (**proprietary**) | 2×10 · **1.27mm** | VDDIO | `JTAG-HEADERS.md` (Header 2) — needs adapter |
| `PANEL1` | front panel: pwr/reset/NMI btn, LEDs, speaker | 2×10 | 3V3/5V | `BMC-CONNECTORS.md` |
| `AUX_PANEL1` | aux panel: locator LED/btn, LAN-link LEDs | 2×10 | 3V3 | `BMC-CONNECTORS.md` |
| jumpers | `VGA_SW1`, `IPMI_SEL1`, `RECOVERY1` (1×3), `CLRTC1` | 3-pin | 3V3 | `BMC-CONNECTORS.md`, `ASUS-KGPE-D16.md` |
| straps | `IKVMEN#`, `BMC_PRESENT#`, `SOLEN#` (on `BMC_FW1`) | — | 3V3 | `BMC-CONNECTORS.md` |

P0 pulls exact pin-by-pin nets from those docs and the KGPE-D16 schematic; the
`BMC_FW1` mapping stays compatible with the existing spispy wiring where
possible. Signal budget ≈ 35–40 ≤ 56 ULX3S GPIO.

## 4. Components (units, interfaces, dependencies)

Each is a self-contained core with a CSR/stream interface to the SoC bus.

1. **`spiflash_emu`** — SPI-flash **device** emulator. In: SPI bus from the
   target's controller (CS#, SCK, MOSI, MISO). Backing store: a LiteDRAM native
   port (image in SDRAM) with an SCK-domain prefetch FIFO; refresh suppressed
   while CS# low. Decodes read (0x03), fast-read (0x0B, dummy cycles = latency
   slack), SFDP, RDID; BMC instance adds program/erase (write) FSM. Depends on:
   LiteDRAM, clocking. Params: capacity, R/W, command set.
2. **`uart_bridge`** — a UART core per port, streamed to a CDC-ACM USB function.
   TTL variant direct; RS-232 variant via harness MAX3232. Depends on: USB CDC.
3. **`jtag_master`** — shift-register TCK/TMS/TDI/TDO(+TRST/SRST) master with an
   **XVC server** front-end (settck/shift/getinfo), one per TAP. Depends on: USB
   (CDC or bulk) + Pi-side socat.
4. **`gpio` banks** — CSR-mapped in/out/oe for jumpers, front-panel
   buttons (open-drain drivers), LEDs (inputs), BMC straps.
5. **`activity_leds`** — pulse-stretch monitors tapped off SPI CS/SCK, UART
   tx/rx, JTAG TCK → 8 board LEDs.
6. **`usb_hub` + functions** — Greg Davill soft hub enumerating the above as
   standard devices; wishbone bridge for control.
7. **control plane** — LiteX bridge + `csr.csv`; Pi-side `RemoteClient`.

## 5. Verification strategy

**Hardware-in-the-loop (HIL) on the RPi 5, before the real board.** The Pi 5's
RP1 PIO (`mithro/rp1-jtag`, `mithro/rpi5-rp1-pio-bench`) plays the role of the
target so each core is provable on the bench:
- **SPI:** RP1-PIO SPI *master* issues 0x03/0x0B reads of a known image loaded
  into the emulator; compare to the golden file. Then boot the real BMC/BIOS.
- **JTAG:** `openocd` via the XVC path scans IDCODE; cross-check with the Pi's
  native `rp1-jtag` OpenOCD adapter.
- **UART:** loopback/echo through each CDC-ACM tty; then the real BMC console.
- **CSR/memory:** `RemoteClient` read/write sanity + a blinky.
Per-phase CI where feasible (`litex_sim`/verilator for logic; HIL on a Pi 5).

**Flash image loading** (USB-FS is slow): load the SDRAM image via the Pi over
the wishbone bridge / a dedicated fast path (FTDI high-baud or, later, Ethernet),
not by streaming through the FS-USB serprog device for large images.

## 6. Decomposition (phases)

Each phase = its own spec → plan → build → review. Columns = dependency waves.

- **Wave 0 (foundation):**
  - **P0 — Wiring & repo.** Full harness diagram (connectors ↔ ULX3S GPIO ↔
    MAX3232 ↔ HDT adapter), pin map, new `mithro` repo + submodule here.
  - **P1 — SoC + USB hub + bridge.** Minimal LiteX SoC on 45F, soft USB hub,
    wishbone bridge; `RemoteClient` + blinky from the Pi 5.
- **Wave 1 (parallel, after P1):**
  - **P2 — SPI-flash emulator** (read-only, 1 instance; serprog device).
  - **P3 — UART bridges** (≥1 TTL + ≥2 RS-232; CDC-ACM per port).
  - **P4 — JTAG master(s) + XVC** (BMC TAP, then HDT).
  - **P5 — GPIO/panel/LEDs** (jumpers, buttons, straps, activity LEDs).
- **Wave 2 (integrate):**
  - **P6 — Dual concurrent flash + BMC write** emulation.
  - **P7 — Shrink/optimize to 12F/25F.**
  - **P8 — ESP32 Wi-Fi transport** (optional).

## 7. First sub-project: P0 + P1 (detail)

**P0 — Wiring & repo skeleton**
- Produce the harness **wiring diagram + pin map**: every in-scope connector
  (§ inventory) → a ULX3S J1/J2 GPIO, noting MAX3232 for RS-232 and the 1.27 mm
  HDT adapter. Budget check: ~35–40 signals ≤ 56 GPIO — fits. Keep the spispy
  BMC_FW1 mapping compatible where possible.
- **Gating decision (before repo creation, can't be cleanly changed after):**
  confirm the **repo name** and the **submodule path** (`asus-kgpe-d16-firmware/
  mobo-bench` vs a top-level `mobo-bench`).
- Create the `mithro/<name>` repo (LiteX layout: `<name>/soc.py`, `cores/`,
  `firmware/`, `sim/`, `test/` HIL, `wiring/`, `docs/`), Apache-2.0, and add it
  as a **git submodule** under this repo. Push via HTTPS or SSH (both work).

**P1 — LiteX SoC + soft USB hub + wishbone bridge**
- Minimal LiteX SoC for `radiona_ulx3s` (ECP5 **45F**), small CPU, 48 MHz USB
  PLL. LiteDRAM is brought up as **foundational-only** here (its first real
  consumer is P2's `spiflash_emu`) — it is *not* part of the P1 exit criteria.
- Integrate the **soft USB hub** and a first standard device: the **wishbone
  bridge**; verify `litex_server`/`RemoteClient` CSR read/write + blinky from
  the Pi 5. Add one CDC-ACM as a smoke test.
- Deliverable: a Pi-5-controllable SoC skeleton the Wave-1 cores plug into.

## 8. Repo & submodule
- New repo under `mithro`; add here as a submodule (path e.g.
  `asus-kgpe-d16-firmware/mobo-bench` or top-level `mobo-bench` — decide in P0).
- This design doc is authored here; it (and per-phase specs) move into the new
  repo's `docs/` once it exists.

## 9. Risks / open questions
- **Resource fit on 12F/25F** (P7): USB hub + 2× flash + N UART + N JTAG + CPU.
  Mitigation: 45F-first, measure nextpnr, drop CPU/instances as needed.
- **Soft-hub maturity** (Greg Davill hub emulation): validate enumeration of
  the full device set early in P1; fallback = fewer functions / composite CDC.
- **SPI write emulation** correctness (P6) — hardest FSM; NORbert as reference.
- **AMD HDT** usefulness unknown (accepted); provide the master, don't promise
  run-control.
- **XVC-over-USB** needs a Pi-side socat shim; acceptable, documented.
- **Host RS-232** requires a MAX3232 on the harness (BOM item).
