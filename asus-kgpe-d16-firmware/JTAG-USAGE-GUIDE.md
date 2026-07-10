# Using JTAG on the AST2050 BMC with a Raspberry Pi 4B + OpenOCD

The operational companion to [`RPI4-OPENOCD-JTAG-WIRING.md`](RPI4-OPENOCD-JTAG-WIRING.md)
(which covers the *wiring*). This document covers **how to drive the AST2050's
ARM926EJ-S core over JTAG once the harness is connected** — bring-up, run
control, register and memory access, GDB, common workflows, and troubleshooting.

Everything here is **verified on real hardware**: an ASUS KGPE-D16, its
Aspeed AST2050 BMC wired to the `rpi4-asus-aspeed2050-dev` bridge Pi, driven by
`linuxgpiod` bit-bang under OpenOCD `0.12.0+dev-snapshot (2026-02-16)`. Captured
command output is reproduced verbatim in fenced blocks marked **“real output”**.

> **Related docs:** [`RPI4-OPENOCD-JTAG-WIRING.md`](RPI4-OPENOCD-JTAG-WIRING.md)
> (harness, pin maps, pre-power checklist) · [`HEADER-PINOUTS.md`](HEADER-PINOUTS.md)
> (per-header diagrams) · [`JTAG-HEADERS.md`](JTAG-HEADERS.md) (both KGPE-D16
> JTAG headers + the x86/HDT side) · [`DDR2-INIT-REVERSE-ENGINEERING.md`](DDR2-INIT-REVERSE-ENGINEERING.md)
> (the SDRAM training sequence referenced in §8) · configs in [`openocd/`](openocd/).

---

## 1. What this gives you (and what it doesn't)

| You get | You don't get |
|---|---|
| Full run-control of the **AST2050 BMC** ARM926EJ-S: halt, resume, reset-halt, single-step | Any control of the **x86 host** (Opteron/SR5690/SP5100) — that's AMD HDT, proprietary, not OpenOCD. See [`JTAG-HEADERS.md`](JTAG-HEADERS.md). |
| Read/write **CPU registers** and **memory-mapped SoC registers** (SCU, SDMC, WDT, …) over AHB | Reliable **DRAM** access *until DDR2 is trained* — see §8. |
| Hardware **breakpoints/watchpoints** (2 units) and a **GDB** server | Kernel-aware debugging out of the box (Raptor: “do not expect OpenOCD to debug the Linux kernel” without more work). |
| A host-independent second path into the BMC that **cross-checks P2A/culvert** (both read `SCU7C = 0x202`) | Speed — `linuxgpiod` bit-bang is slow (§10). |

The AST2050 core is an **ARM926EJ-S (ARMv5TE)**, debugged via **EmbeddedICE-RT
over raw JTAG** — not CoreSight/SWD. Raw-JTAG adapters (Pi bit-bang, FTDI,
J-Link) work; SWD-only probes (ST-Link, CMSIS-DAP, Black Magic) do **not**.

---

## 2. Prerequisites

1. **Harness wired** per [`RPI4-OPENOCD-JTAG-WIRING.md`](RPI4-OPENOCD-JTAG-WIRING.md)
   §2 — the 6 signals (TCK/TMS/TDI/TDO/nTRST/nSRST) + ≥1 GND, and optionally
   the RTCK monitor on GPIO27 (§4). Wire with **both boards off**.
2. **Board powered.** The KGPE-D16 is power-on-with-AC: energising the Tasmota
   plug boots host + BMC. See [`../`](../) hardware notes; from the bridge Pi:
   ```sh
   curl "http://au-plug-10.iot.welland.mithis.com/cm?cmnd=Power%20On"
   ```
3. **OpenOCD ≥ 0.12** on the Pi (`sudo apt install openocd`, or build). The
   bridge Pi already has it.
4. **GPIO permissions.** The `claude`/`tim` users on the bridge Pi are in the
   `gpio` group, so **no `sudo` is needed** — `linuxgpiod` opens
   `/dev/gpiochip0` directly. (Verified: OpenOCD claims the lines fine as an
   unprivileged user.)
5. **Configs present.** On the bridge Pi they live in `~/openocd-bmc/`
   (mirrors [`openocd/`](openocd/) in this repo) alongside the two helper
   scripts `first-contact.sh` and `rtck-echo-test.py`.

---

## 3. The config files and how to invoke them

Three layered configs in [`openocd/`](openocd/), split adapter / SoC / board:

| File | Role |
|---|---|
| `rpi4-jtag.cfg` | **Adapter.** `linuxgpiod` driver + the GPIO→signal map + `transport select jtag`. |
| `ast2050.cfg` | **SoC.** TAP declaration (`-irlen 4`, IDCODE `0x07926f0f`), reset topology, ARM926 target `ast2050.cpu`. |
| `kgpe-d16-bmc.cfg` | **Board.** `source`s `ast2050.cfg`, adds `init_board` (reset config + 100 kHz). |

Because `kgpe-d16-bmc.cfg` **sources `ast2050.cfg` itself**, there are exactly
two correct invocations:

```sh
cd ~/openocd-bmc          # (or asus-kgpe-d16-firmware/openocd in this repo)

# (A) Full board stack — the normal one:
openocd -f rpi4-jtag.cfg -f kgpe-d16-bmc.cfg

# (B) SoC-only, for first-contact IDCODE discovery:
openocd -f rpi4-jtag.cfg -f ast2050.cfg -c "init; scan_chain; shutdown"
```

> **Do NOT** pass `-f ast2050.cfg -f kgpe-d16-bmc.cfg` together — the target
> gets created twice and OpenOCD aborts:
> ```
> Error: Command/target: ast2050.cpu Exists
> ```

Add `-c "<command>"` args to script a batch run, or connect interactively (§6).

---

## 4. Step 0 — RTCK liveness check (optional, recommended)

Before scanning, prove the chip is **powered and core-clocked** with the RTCK
echo test. ARM926EJ-S `RTCK` is `TCK` re-synchronised through the core-clock
domain, so an echo means the TAP clock path is alive — and it cleanly
distinguishes “board dead / clock stopped” from “scan wiring fault.” Requires
the optional RTCK→GPIO27 wire.

```sh
python3 ~/openocd-bmc/rtck-echo-test.py     # or: uv run rtck-echo-test.py
```

**Real output (harness wired, board on):**
```
RTCK echo: high phase 64/64, low phase 64/64
PASS: RTCK follows TCK — AST2050 is powered, core-clocked, and the TAP clock path is alive.
```

A stuck-low result (`high 0/64, low 64/64`) = board off, RTCK unrouted, or the
wire is missing — also the normal result with nothing connected.

> **Exclusive GPIO:** the kernel gives one owner per line. **Do not run the RTCK
> test while OpenOCD is attached** (both want TCK) — it will fail with `EBUSY`.
> Run the test, let it exit, *then* start OpenOCD.

---

## 5. First contact — IDCODE scan

```sh
~/openocd-bmc/first-contact.sh
# = openocd -f rpi4-jtag.cfg -f ast2050.cfg -c "init; scan_chain; shutdown"
```

**Real output (PASS):**
```
Info : Linux GPIOD JTAG/SWD bitbang driver
Info : Note: The adapter "linuxgpiod" doesn't support configurable speed
Info : JTAG tap: ast2050.cpu tap/device found: 0x07926f0f (mfg: 0x787 (Shenzhen South Electron Co Ltd), part: 0x7926, ver: 0x0)
Info : Embedded ICE version 6
Info : ast2050.cpu: hardware has 2 breakpoint/watchpoint units
Info : [ast2050.cpu] Examination succeed
```

The magic number is **IDCODE `0x07926f0f`** — the ARM926EJ-S generic TAP,
Raptor-confirmed on this exact AST2050. (`mfg 0x787` decodes as an ARM/JEDEC
continuation quirk, not a literal vendor; the part `0x7926` is what matters.)

**Failure signature (nothing wired / board unpowered):**
```
Error: JTAG scan chain interrogation failed: all ones
Error: ast2050.cpu: IR capture error; saw 0x0f not 0x01
```
“All ones” = TDO floating high → check GND first, then TDO/TMS/TCK, then power.

---

## 6. Interactive sessions — telnet and GDB

Start the board stack and leave it running:

```sh
openocd -f rpi4-jtag.cfg -f kgpe-d16-bmc.cfg
```

It opens two servers (as announced in every real run):

| Port | Protocol | Use |
|---|---|---|
| **4444** | OpenOCD telnet command line | `telnet localhost 4444` → type `halt`, `reg`, `mdw`, … |
| **3333** | GDB remote | `target remote localhost:3333` from `arm-none-eabi-gdb` (§11) |

From another shell on the Pi:
```sh
telnet localhost 4444
```
Everything in §7–§9 can be typed here directly. Type `shutdown` (or Ctrl-C the
OpenOCD process) to end.

For **one-shot scripted** runs, pass `-c` commands instead and finish with
`shutdown`, e.g.:
```sh
openocd -f rpi4-jtag.cfg -f kgpe-d16-bmc.cfg \
        -c init -c halt -c "mdw 0x1e6e207c" -c resume -c shutdown
```

> **Scripts vs. `-c`:** commands like `reg` and `mdw` **auto-print** their result
> at the telnet prompt and when given via `-c`, but inside a **sourced `.tcl`
> file** they return a value instead of printing — there, wrap them:
> `echo [dict get [get_reg pc] pc]` or capture `read_memory`.

---

## 7. Core run-control

| Command | Effect |
|---|---|
| `halt` | Stop the core, enter debug state. |
| `resume` | Continue from the current PC. |
| `resume <addr>` | Set PC then continue. |
| `step` | Execute one instruction. |
| `reset halt` | Assert reset, then halt (see caveat below). |
| `reset run` | Assert reset and let it run. |

**`halt` — real output** (the AST2050 with dead stock firmware is off in the
weeds, hence “unknown state” and Undefined/garbage PC — see §8):
```
Warn : target was in unknown state when halt was requested
target halted in ARM state due to debug-request, current mode: Undefined instruction
cpsr: 0x800000db pc: 0x064046c0
MMU: disabled, D-Cache: disabled, I-Cache: disabled
```

**`step` — real output** (PC advances one ARM instruction, +4 each):
```
target halted ... pc: 0x064046c4
target halted ... pc: 0x064046c8
target halted ... pc: 0x064046cc
```

**`reset halt` — real output** (note the combined-reset caveat):
```
Warn : srst pulls trst - can not reset into halted mode. Issuing halt after reset.
target halted in ARM state due to debug-request, current mode: Supervisor
cpsr: 0x000000d3 pc: 0x0005d50c
```

> **Combined-reset caveat — and why independent pins don't help.**
> `ast2050.cfg` uses `reset_config trst_and_srst combined` (Raptor's topology):
> OpenOCD cannot hold the core halted *through* reset, so it resets then halts
> as soon as it can — catching the core a little past the reset vector (here
> `0x0005d50c`, Supervisor mode). The Pi drives **nTRST and nSRST on separate
> GPIOs** (GPIO17 / GPIO18), so it's natural to ask whether telling OpenOCD they
> are `separate` — holding nTRST deasserted while pulsing nSRST — buys a clean
> reset-vector halt. **Tested on the real board: it does not.** Both
> `reset_config separate` and `reset_config separate srst_nogate` make
> `reset halt` **time out** (`Error: timed out while waiting for target
> halted`). The coupling is **inside the AST2050 silicon** — asserting nSRST
> also resets the EmbeddedICE debug logic, clearing any armed halt/vector-catch
> — not in the wiring, so independent GPIO control can't defeat it. `combined`
> is correct; "reset, then immediate halt" is the best available, and for early
> bring-up halting a few thousand instructions in is fine. (For DDR2 init and
> most register work you don't need reset at all — a plain `halt` is enough.)

---

## 8. Memory access — and the DRAM training caveat

Read/write AHB with `mdw`/`mdh`/`mdb` (word/half/byte) and `mww`/`mwh`/`mwb`:

```
mdw <addr> [count]      ;# display words
mww <addr> <value>      ;# write a word
```

### Memory-mapped registers: always work (no training)

SoC registers live in the always-on AHB space and read/write immediately.
Reading the SCU identity block — **real output**:
```
0x1e6e207c: 00000202      ;# SCU7C silicon revision
0x1e6e2004: 000ffe5c      ;# SCU04
0x1e6e2014: 00003eff      ;# SCU14 (hardware strap/config)
```
`SCU7C = 0x00000202` read here over JTAG **independently matches** the value
read over host-side **P2A/culvert** — the two access paths cross-validate.

### ⚠️ DRAM does NOT work until the DDR2 controller is trained

DRAM is **not usable straight after power-on on this board**, because the stock
BMC firmware is dead and never completes SDRAM (DDR2) training. Until the SDMC
controller is initialised — the `platform.S` / MRS/EMRS sequence documented in
[`DDR2-INIT-REVERSE-ENGINEERING.md`](DDR2-INIT-REVERSE-ENGINEERING.md) — the
native DRAM window (`0x40000000`, 64 MB) does not back reads or writes.

**Evidence — a save/write/verify/restore at `0x42000000` (real output):**
```
0x42000000: orig=0x40101000  wrote=0xa5a5a5a5  readback=0x40101000  restored=0x40101000
```
The write of `0xa5a5a5a5` **did not stick** — and *every* DRAM address returns
the same constant `0x40101000`, the tell-tale of an untrained/non-responding
DDR2 array (floating/aliased bus). Consistently, the halted PC wanders through
un-backed space executing floating-bus garbage (`pc: 0x15555420`,
`0x064046c0`, … — `0x5555…`/`0xaaaa…` patterns run as instructions).

**Proof that JTAG *writes* themselves work** — a **CPU register** write is
decoupled from any memory decode (real output):
```
r1 after write #1 = 0xdeadbeef
r1 after write #2 = 0xcafebabe
```
So the write path is fine; it's the *DRAM* that isn't ready.

**To use DRAM over JTAG, run the DDR2 init script** — it does exactly this:

```sh
openocd -f rpi4-jtag.cfg -f kgpe-d16-bmc.cfg -f ddr2-init.tcl
```

[`openocd/ddr2-init.tcl`](openocd/ddr2-init.tcl) is a faithful,
register-for-register port of Raptor's [`platform.S`](platform.S) DDR2 bring-up
(the same sequence as the P2A `ddr2-init-p2a.py`, but issued by the ARM926
core's own AHB — *more* faithful, since the CPU does the writes as real firmware
would). It halts the core, programs the SCU M-PLL and the SDMC `MCRxx` timing /
DLL / MRS-EMRS registers (computing `MCR04` from the live `SCU70` strap),
relocks, and verifies. See [`DDR2-INIT-REVERSE-ENGINEERING.md`](DDR2-INIT-REVERSE-ENGINEERING.md)
for the per-register provenance.

**Real output (DRAM goes from dead to working):**
```
straps: SCU70=0x00819582 SCU40=0x00000000
MCR04 = 0x00000585 (from SCU70 strap)
=== DRAM write/read-back verify (0x40000000 native window) ===
  0x40000000 <- 0xdeadbeef  read=0xdeadbeef  OK
  0x40000004 <- 0x12345678  read=0x12345678  OK
  0x40100000 <- 0xa5a5a5a5  read=0xa5a5a5a5  OK
  0x43f00000 <- 0x5a5a5a5a  read=0x5a5a5a5a  OK
>>> DDR2 TRAINED: all read-backs match. DRAM is usable.
```

Training **persists** across OpenOCD sessions (the SDMC stays configured and
refreshing as long as the board is powered) — verified by a later session with
**no** re-init writing fresh patterns that stick, while `0x40000000` still held
`deadbeef` from the init run. After training you can `load_image`/`mww` a
payload into DRAM and `resume <addr>` (§12).

> **Crash-safety rule (inherited from the P2A work):** never write `0x0` or the
> SMC flash window `0x14000000` while the DRAM→`0x0` remap is **not** set — it
> stalls the AST2050 AHB and can hang the host's PCIe. When in doubt, work in
> the **native** DRAM window (`0x40000000`) and SoC register space, not the
> low remapped aliases.

---

## 9. Register access

```
reg                      ;# list/dump all core registers
reg pc                   ;# read one register (auto-prints at telnet/-c)
reg pc 0x40000000        ;# write one register
reg cpsr                 ;# current program status (mode/flags)
```

`reg <name> <value>` write/read-back is the safest JTAG-write smoke test (see
§8 — `r1` round-trips `0xdeadbeef`/`0xcafebabe`). `cpsr` mode nibble decodes:
`0x13`=Supervisor, `0x1b`=Undefined, `0x10`=User, `0x1f`=System; the `0x80`
bit in `cpsr` is the IRQ-disable (I) flag.

> Inside a **sourced `.tcl`** file `reg` returns rather than prints — use
> `get_reg`: `echo [dict get [get_reg pc] pc]`.

---

## 10. Adapter speed

`rpi4-jtag.cfg` sets `adapter speed 100` (kHz), but with `linuxgpiod` OpenOCD
prints:
```
Info : Note: The adapter "linuxgpiod" doesn't support configurable speed
```
The libgpiod char-dev path is **syscall-bound and inherently slow** (tens–low
hundreds of kHz) — which is *safe* for flying-lead bring-up, and the setting is
simply ignored. If you need real speed control, switch to the commented
`bcm2835gpio` fallback in `rpi4-jtag.cfg` (direct-mmap; honours `adapter
speed`; BCM2711 peripheral base `0xFE000000`) — but expect to tune it and keep
leads short. For flashing/large transfers, the syscall bit-bang will feel slow;
that's expected.

---

## 11. GDB

With the board stack running (§6), from the Pi:

```sh
arm-none-eabi-gdb            # or gdb-multiarch
(gdb) set architecture armv5te
(gdb) target remote localhost:3333
(gdb) monitor halt          # run any OpenOCD command via "monitor ..."
(gdb) info registers
(gdb) x/8xw 0x1e6e2004      # examine SoC registers
(gdb) monitor reset halt
```

`monitor <cmd>` tunnels OpenOCD commands (§7–§9) through GDB. Symbol-level
debugging needs an ELF with symbols (`file u-boot`, etc.); raw poking works
without one. Kernel-aware debugging is out of scope (Raptor's caveat).

---

## 12. Common workflows

**Attach to a running BMC and look around**
```sh
openocd -f rpi4-jtag.cfg -f kgpe-d16-bmc.cfg -c init -c halt \
        -c "reg pc" -c "reg cpsr" -c "mdw 0x1e6e207c" -c resume -c shutdown
```

**Halt shortly after reset (early bring-up)**
```sh
openocd -f rpi4-jtag.cfg -f kgpe-d16-bmc.cfg -c init -c "reset halt" \
        -c "reg pc" -c shutdown
```

**Bring DRAM up, then load & run code** (see §8)
1. `openocd -f rpi4-jtag.cfg -f kgpe-d16-bmc.cfg -f ddr2-init.tcl` → DRAM trained.
2. In an interactive session: `load_image u-boot.bin 0x40000000` (or `mww`-poke).
3. `resume 0x40000000` (or `reg pc 0x40000000` then `resume`).

**Cross-check a P2A/culvert reading**
Read the same SoC register both ways; they should agree. `SCU7C` reads `0x202`
over JTAG *and* over P2A — a good sanity anchor when debugging either path.

---

## 13. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `JTAG scan chain interrogation failed: all ones` + `IR capture error; saw 0x0f` | TDO floating — nothing connected, board unpowered, or GND/TDO/TMS wiring. Wire GND first; re-buzz signals; confirm VTref ≈3.3 V; run the RTCK test (§4). |
| `Command/target: ast2050.cpu Exists` | You passed both `ast2050.cfg` **and** `kgpe-d16-bmc.cfg`. Use one invocation from §3. |
| `illegal option for adapter gpio trst: -push-pull` | Old config on a newer OpenOCD. Drive modes belong in `reset_config`, not per-signal — fixed in the current [`openocd/`](openocd/) configs. |
| RTCK test fails with a busy/claim error | OpenOCD is attached and owns the GPIO lines. Stop OpenOCD, then run the RTCK test (§4). |
| DRAM reads a constant / writes don't stick | DDR2 not trained — expected after power-on with dead firmware. Train the SDMC first (§8). |
| `srst pulls trst - can not reset into halted mode` | Expected with the combined-reset topology (§7). Harmless; the core halts just after reset. |
| Scans intermittently / only at low speed | Flying leads too long or too fast. Keep <10 cm; `linuxgpiod` is already slow, so suspect wiring/grounding. |
| `target was in unknown state when halt was requested` | The core was executing garbage (dead firmware / untrained DRAM). Harmless — you still get control. |

---

## 14. Safety rules (recap)

- **VTref (AST_JTAG1 pin 1) is meter-only** — confirm ≈3.3 V, never drive it.
- **RTCK (pin 11) is a target *output*** — the Pi side is **input-only**; never
  drive it.
- **Both sides are 3.3 V; the Pi is NOT 5 V tolerant.** No 5 V pin near a GPIO.
- **Wire with both boards off**; ground connected first, removed last.
- **Never write `0x0` or `0x14000000` pre-remap** (§8 crash rule).
- **Don't run the RTCK test and OpenOCD at once** (exclusive GPIO, §4).

---

## 15. Verified-facts quick reference

| Fact | Value | Source |
|---|---|---|
| TAP IDCODE | `0x07926f0f` (ARM926EJ-S) | §5 real output; Raptor |
| EmbeddedICE version | 6 | §5 real output |
| HW breakpoint/watchpoint units | 2 | §5 real output |
| Adapter driver | `linuxgpiod`, `/dev/gpiochip0`, no configurable speed | §3, §10 |
| Privilege | none (`gpio` group; no `sudo`) | §2 |
| SCU silicon rev (`0x1e6e207c`) | `0x00000202` (JTAG == P2A) | §8 real output |
| SCU04 / SCU14 | `0x000ffe5c` / `0x00003eff` | §8 real output |
| DRAM native window | `0x40000000`, 64 MB (train with `ddr2-init.tcl`) | §8; `ast2050.h` |
| Reset-halt topology | `combined` only (SRST resets EmbeddedICE in silicon; `separate`/`srst_nogate` time out) | §7 tested |
| GDB / telnet ports | 3333 / 4444 | §6 real output |
| OpenOCD | `0.12.0+dev-snapshot (2026-02-16)` on the bridge Pi | all runs |

---

## Sources

- Raptor Engineering — KGPE-D16 BMC Port Status (AST_JTAG1 = 20-pin ARM header,
  Olimex ARM-USB-TINY + OpenOCD, IDCODE, U-Boot bring-up):
  <https://www.raptorengineering.com/coreboot/kgpe-d16-bmc-port-status.php>
- OpenOCD User's Guide — ARM926EJ-S target, `adapter gpio`, `reset_config`,
  `reg`/`mdw`/`mww`, GDB/telnet servers: <https://openocd.org/doc/html/>
- This repo — [`RPI4-OPENOCD-JTAG-WIRING.md`](RPI4-OPENOCD-JTAG-WIRING.md),
  [`DDR2-INIT-REVERSE-ENGINEERING.md`](DDR2-INIT-REVERSE-ENGINEERING.md),
  [`platform.S`](platform.S), [`ast2050.h`](ast2050.h), and the
  [`openocd/`](openocd/) configs + helper scripts.
- Live capture: bridge Pi `rpi4-asus-aspeed2050-dev`, 2026-07-10 (all “real
  output” blocks).
