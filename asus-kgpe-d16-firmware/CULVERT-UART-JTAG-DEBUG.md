# Culvert — Aspeed BMC AHB debug over UART, plus software JTAG

Extracted analysis of [`amboar/culvert`](https://github.com/amboar/culvert), a
test/debug tool for the "AHB bridges" that ASPEED BMC SoCs expose to the host.
The reason it matters for **this** project: culvert gives two ways to reach the
inside of an ASPEED BMC over a **serial cable** — a debug-UART shell with
arbitrary read/write of the BMC's physical address space, and a
**software/virtual JTAG** that drives the SoC's *internal* JTAG master and
re-exposes it to OpenOCD/GDB. Neither needs the physical `AST_JTAG1` header
soldered (contrast [`JTAG-HEADERS.md`](JTAG-HEADERS.md) and
[`RPI4-OPENOCD-JTAG-WIRING.md`](RPI4-OPENOCD-JTAG-WIRING.md), which cover the
hardware-JTAG route).

> **Provenance.** Everything below is read out of the culvert source at upstream
> commit `3fd2e9409e88e17f7c646e701491e547359faa8f` (2026-04-25). Citations are
> `path:line` into that tree. License is Apache-2.0 (same as this repo).

> **Status of facts:** ✅ = verified in culvert source (cited) · 🔶 = strong
> inference, stated as such · ⚠️ = must be confirmed on *our* AST2050 hardware
> before trusting it. The AST2050 (G3) applicability caveats in §6 are the ones
> that matter most for this repo — read them before wiring anything up.

---

## 0. What culvert is, in one paragraph

ASPEED BMCs boot (on AST2400/AST2500) into a hardware configuration that lets an
external agent — the host CPU over PCIe or LPC, or anyone on the debug UART —
reach into the BMC's ARM AHB (the SoC's main system bus) and do arbitrary
reads/writes. This exists so BMC/host firmware can be brought up and so the BMC
can act as a dumb IO-expander before it has its own firmware. Culvert is a
Swiss-army tool that speaks *all* of these "bridge" interfaces uniformly, then
layers useful operations on top (probe the machine's security posture, dump/
reflash the BMC's SPI flash, read/write RAM, open a console, drive JTAG). Its
own README warns loudly that poking these interfaces can crash or brick the
target — that warning applies doubly to an unsupported SoC like ours (§6).

---

## 1. The AHB bridge interfaces (culvert's threat-model table)

From `README.md`. These are the doors into the BMC's address space; culvert can
use any of them as its transport (`via <driver>`):

| Interface | What it is | Notes |
|---|---|---|
| **Debug UART** | Hardware UART "debug shell" with arbitrary AHB access | On **UART1 or UART5** (SoC strap selects which). **This is the serial path** — §2. ✅ |
| PCIe VGA P2A | PCIe MMIO → AHB via a 64 KiB sliding window | Write-filters in the SCU can protect AHB regions; off by default |
| iLPC2AHB | A SuperIO logical device giving arbitrary AHB access over LPC | One AHB-wide write filter in the LPC controller; off by default |
| LPC2AHB | BMC-controlled mapping of LPC firmware cycles onto AHB | |
| X-DMA | Arbitrary M-bus (DRAM) access | |
| PCIe BMC device | Fixed PCIe MMIO windows, restricted 4 KiB AHB access | |

Culvert today implements P2A, iLPC2AHB, LPC2AHB and **Debug UART** as transports
(`README.md`, "Tool Features"), plus a Linux `/dev/mem` backend for running
*on* the BMC itself.

The driver name for the serial path is **`debug-uart`**
(`src/bridge/debug.c:` `debug_driver.name = "debug-uart"`). ✅

---

## 2. The Debug UART interface — the serial path (the headline feature)

### 2.1 What it gives you

A tiny command shell, baked into ASPEED silicon, that reads and writes the BMC's
AHB directly. You reach it with nothing but a **3.3 V TTL serial adapter** on the
right UART pins — no host CPU, no PCIe, no LPC. Culvert wraps the shell so the
same `read`/`write`/`probe`/`sfc`/`jtag` verbs work over it.

Which physical UART carries it is a strap:
- **AST2500:** `SCU070[29]` (`SCU_STRAP_DBG_SEL`) → set = **UART5**, clear =
  **UART1** (`src/soc/debugctl.c:` `ast2500_debugctl_report`). ✅
- **AST2600:** decided by which UART controller block is the debug bridge
  (`0x1e783000` → UART1, `0x1e784000` → UART5) (`src/soc/debugctl.c:`
  `ast2600_debugctl_report`). ✅
- Also gated by `SCU02C[10]` (`SCU_MISC_UART_DBG`) (`src/soc/debugctl.c:`
  `SCU_MISC_UART_DBG`). ✅

`culvert probe` reports this for you, e.g. `Debug UART port: UART5` in the README
sample output. ✅

### 2.2 How culvert enters the shell (`debug_enter`, `src/bridge/debug.c`)

The full handshake, exactly as culvert performs it:

1. **(optional force-quit)** if `--force-quit`, set 115200 baud and blast
   `ESC q CR LF` twice (`"\x1Bq\r\n\x1Bq\r\n"`) to cancel any half-typed command
   and leave a previous debug session. ✅
2. **Drop to 1200 baud.** `console_set_baud(ctx->console, 1200)`. ✅
3. **Send the password** (see §2.3), then **expect the `"$ "` prompt**. ✅
4. **Raise to 115200 baud** and `sleep(1)`. From here the shell runs at 115200
   8N1. ✅

Exit (`debug_exit`): send `q`, wait, then restore 115200 baud. ✅

Host-side line settings: culvert's TTY backend only knows two speeds — **B1200**
and **B115200** (`src/tty.c:` `tty_baud_map`) — matching the two used above. ✅
The prompt/line terminator culvert sends is a bare **`\r`** (carriage return)
(`src/bridge/debug.c:` `prompt_init(&ctx->prompt, fd, "\r", false)`). ✅

### 2.3 The password (public)

ASPEED self-published the debug-UART password, so culvert embeds it rather than
asking you for it (`src/bridge/debug.c`). It is:

```
5z&0VK{@`HW}H~V310=l=JB+M]IV-f;Sz98XfCA&Rp)i|Jo=2?IBN$QaQ2"Kb|Ov
```

Source cited in culvert's own comment: *ASPEED SDK User Guide v09.01, page 381,
"5. start use debug command"* —
`https://github.com/AspeedTech-BMC/openbmc/releases/download/v09.01/SDK_User_Guide_v09.01.pdf`. ✅

### 2.4 The debug-shell command set (reverse-engineered from culvert's usage)

Culvert never documents the shell grammar prose-style; it's inferable from the
command strings it builds. All addresses/values are **hex, no `0x`**. Prompt is
`"$ "`. (`src/bridge/debug.c`.) ✅

| Shell cmd | Form culvert emits | Meaning | Built in |
|---|---|---|---|
| `r` | `r <addr>` | Read one 32-bit word; reply is the value | `debug_readl` → `debug_read_fixed(…, 'r', …)` |
| `w` | `w <addr> <val>` | Write one 32-bit word | `debug_writel` |
| `i` | `i <addr>` | Read one **byte** (used for sub-word / unaligned reads) | `debug_read` when `len < 4` |
| `o` | `o <addr> <byte>` | Write one **byte** | `debug_write` when `len <= 4` |
| `d` | `d <addr> <len>` | **Dump** a block; ASCII hex, ≤ 128 KiB per call | `debug_read`, `DEBUG_D_MAX_LEN = 128*1024` |
| `u` | `u <addr> <len>` | **Upload** (write) a block, then raw bytes; ≤ 128 B per chunk | `debug_write`, `DEBUG_CMD_U_MAX = 128` |
| `q` | `q` | Quit the debug shell | `debug_exit` |
| `ESC` | `0x1B` | Cancel the current command line | force-quit path |

**`d` output format.** Lines look like:

```
20002ba0:31e01002 20433002 30813003 e1a06002
```

i.e. `address:word word word word`, four 32-bit words per line, each printed
MSB-first (`0x31e01002` is the word's value). Culvert parses each token with
`%02hhx%02hhx%02hhx%02hhx` into reversed byte positions, storing the word
little-endian in the output buffer (`src/bridge/debug.c:` `debug_parse_d`). ✅

**Known quirk (worth knowing if you script the shell):** writing `0` to the G5
watchdog reload register (`0x1e785004`, or its `+0x20` alias `0x1e785024`)
does **not** echo a `$ ` prompt, so culvert special-cases it and skips the
prompt wait (`src/bridge/debug.c:` `debug_writel`, `AST_G5_WDT | WDT_RELOAD`). ✅

### 2.5 Driving it from the command line

Direct 4-byte poke/peek (`src/cmd/debug.c`):

```sh
# read a word
culvert debug read  0x1e6e207c via debug-uart /dev/ttyUSB0
# write a word
culvert debug write 0x1e6e207c 0x0        via debug-uart /dev/ttyUSB0
# blindly leave a stuck debug session first:
culvert debug --force-quit read 0x1e6e207c via debug-uart /dev/ttyUSB0
```

Probe the machine's exposure over the serial path (README sample):

```sh
culvert probe via debug-uart /dev/ttyUSB0
# [*] Opening /dev/ttyUSB0
# [*] Entering debug mode
# … reports xdma / p2a / debug / ilpc posture, then:
# [*] Exiting debug mode
```

Any culvert verb that takes `via <driver>` accepts `via debug-uart <tty>`, so
`sfc` (flash dump/reflash), `read`/`write` (RAM/flash), `reset`, `trace`, etc.
all work over serial — subject to the AST2050 caveat in §6.

### 2.6 Remote serial over a Digi PortServer TS-16 (relevant to us)

Culvert can reach a debug UART that is wired to a **Digi PortServer TS-16**
terminal server instead of a local `/dev/ttyUSB*`
(`src/ts16.c`, `src/bridge/debug.c:` `debug_init_v` matches the interface string
`"digi,portserver-ts-16"`). It:

- telnets to the concentrator on **port 23**, logs in (`login:` / `password:`),
- puts the target port into **binary mode** (`set port range=N bin=on`) and
  `kill tty=N` to reset it,
- opens the **raw data socket at TCP `2000 + 100 + port`**
  (`src/ts16.c:` `ts16_console_init`), and
- sets baud via `set line range=N baud=<n>` (`ts16_set_baud`). ✅

Invocation form (from the comment in `src/cmd/debug.c`):

```sh
culvert debug read 0x1e6e207c \
    via debug-uart digi,portserver-ts-16 <IP> <SERIAL_PORT> <USER> <PASSWORD>
```

This project already works with Digi hardware elsewhere (the HP iPDU is a Digi
NS9360), and remote serial concentrators are how bench BMCs are commonly wired,
so this backend is directly reusable if a TS-16 is on hand.

---

## 3. Software / virtual JTAG — debugging U-Boot & the kernel over UART

This is the part that answers "talk to the ASPEED over UART for bootloader/JTAG
debugging." Reference: `docs/OpenOCD.md`, `src/cmd/jtag.c`, `src/soc/jtag.c`.

### 3.1 The idea

ASPEED BMCs contain a **JTAG master** peripheral (normally used to program
external CPLDs). Culvert reconfigures it two ways:
1. Put the JTAG master into **software (bit-bang) mode**, so TCK/TMS/TDI/TDO are
   driven by writing SoC registers.
2. **Route** its output internally to the BMC's own ARM core (or PCIe PHY), or
   out to the external pins.

It then runs a small TCP server speaking OpenOCD's **`remote_bitbang`** protocol
and translates each bit-bang command into a JTAG-master register write. Net
effect: **OpenOCD → culvert → internal JTAG master → ARM core**, with culvert's
own transport (e.g. the debug UART) carrying the register accesses. You can halt
and debug the ARM core **even when it isn't executing** and **without any
external JTAG pins** — ideal for commercial boards where `AST_JTAG1` isn't
broken out. ✅

> ⚠️ `docs/OpenOCD.md` warns: halting the BMC core of the machine you're running
> on can hang host+BMC together and may need an external power cycle. On a
> bench AST2050 driven from a separate host this is fine; don't do it to a live
> production BMC.

### 3.2 Routing targets (`-t/--target-type`)

`culvert jtag` maps target names to SCU `MISC_CTRL[15:14]` routing bits
(`src/soc/jtag.h`, `src/cmd/jtag.c`): ✅

| `--target-type` | Routes JTAG to | SCU bits (`SCU_MISC_CTRL[15:14]`) |
|---|---|---|
| `arm` (default) | Internal ARM core of the BMC | `SCU_JTAG_MASTER_TO_ARM` = `BIT(15)｜BIT(14)` |
| `pcie` | Internal PCIe PHY | `SCU_JTAG_MASTER_TO_PCIE` = `BIT(15)` |
| `external` | External JTAG pins (CPLDs, an Arm64 host CPU, …) | `SCU_JTAG_NORMAL` = `0` |

`MISC_CTRL` is at SCU offset `0x2c` on AST2400/2500 and `0xc0` on AST2600; the
JTAG master is taken out of reset via the SCU reset-control register first
(`src/soc/jtag.c:` `ast2400_jtag_route` / `ast2600_jtag_route`,
`*_jtag_release`). ✅

### 3.3 JTAG-master engine registers culvert drives (`src/soc/jtag.c`)

For reference when reconstructing this for an unsupported SoC (base is the JTAG
node `@1e6e4000`): ✅

| Reg (offset) | Name | Culvert usage |
|---|---|---|
| `0x08` | `AST_JTAG_EC` (engine control) | `ENG_EN｜ENG_OUT_EN`, then pulse `FORCE_TMS` to reset the controller (bits `31/30/29`) |
| `0x10` | `AST_JTAG_SW_MODE` | `SW_MODE_EN`(19) enables bit-bang; `TCK`(18)/`TMS`(17)/`TDIO`(16) are the driven/observed lines |

Bit-bang set: write `SW_MODE_EN | tck<<18 | tms<<17 | tdi<<16`. Bit-bang get:
read back bit 16 for TDO (`jtag_bitbang_set` / `jtag_bitbang_get`). ✅

### 3.4 The `remote_bitbang` command loop (`src/cmd/jtag.c`)

Culvert listens on **127.0.0.1:33333** (default; `-p` to change) and implements
OpenOCD's bit-bang byte protocol: `'0'..'7'` = drive (tck,tms,tdi) from the low
3 bits, `'R'` = sample TDO and reply ASCII `'0'`/`'1'`, `'B'/'b'` = LED on/off
(ignored), `'r/s/t/u'` = reset (currently unsupported, logged), `'Q'` = quit.
Server binds loopback only. ✅

### 3.5 End-to-end recipe (from `docs/OpenOCD.md`, AST2500 example)

**OpenOCD config** (`~/ast2500.cfg` — culvert ships the same file at
`openocd/scripts/ast2500.cfg`): ✅

```tcl
adapter driver remote_bitbang
remote_bitbang port 33333
remote_bitbang host localhost

transport select jtag
reset_config none

set _CHIPNAME ast2500
jtag newtap auto0 tap -irlen 5 -expected-id 0x07b76f0f
set _TARGETNAME $_CHIPNAME.cpu
target create $_TARGETNAME arm11 -chain-position auto0.tap
```

**Run it:**

```sh
# 1. culvert exposes the internal ARM TAP as a bit-bang server, over the debug UART
culvert jtag via debug-uart /dev/ttyUSB0
#   [*] Ready to accept OpenOCD remote_bitbang connections on 127.0.0.1:33333

# 2. OpenOCD attaches
openocd -f ~/ast2500.cfg
#   Info : found ARM1176 … Examination succeed … gdb server on 3333

# 3. GDB attaches to OpenOCD
gdb-multiarch
(gdb) set remotetimeout 50000        # needed when going via UART (it's slow)
(gdb) set architecture armv6
(gdb) target extended-remote localhost:3333
```

Then load the ELF of U-Boot / the kernel and debug. `docs/OpenOCD.md` is blunt:
*"Using GDB over a Debug UART connection is painfully slow, but it'll work in a
pinch."* External devices: `culvert jtag --target external via debug-uart
/dev/ttyUSB0`. ✅

**AST2600** ships two extra configs — `openocd/scripts/ast2600-a7.cfg` (dual
Cortex-A7, DAP id `0x6ba00477`, dbgbase `0x94030000`/`0x94032000`) and
`ast2600-cm3.cfg` (the CM3 coprocessor, which must first be enabled with
`culvert coprocessor run …`). Not relevant to our AST2050 but shows the pattern.
✅

---

## 4. Other culvert capabilities (brief)

From `culvert --help` (`README.md`) and `src/cmd/*`:

- **`console`** — bring up a getty on the BMC's console *from the host* over LPC,
  by clock-gating and re-muxing UARTs. It routes host `UART3`↔`UART5`, drives a
  software 16550 through the SuperIO/LPC (`src/uart/suart.c`), logs in, launches
  `agetty -8 -L ttyS1 1200 xterm`, then re-muxes `UART3`↔`UART2`
  (`src/cmd/console.c`). Only `uart3` (host) / `uart2` (BMC) are supported. The
  UART routing is done via LPC `HICR9`/`HICRA` mux registers
  (`src/soc/uart/mux.c`). ✅
- **`sfc`** — read/write/erase the SPI flash controller's regions; **`read`/
  `write`/`replace`** — dump/patch RAM or flash. The BMC CPU is clock-gated
  around flash writes and the SoC reset afterwards (`README.md`). ✅
- **`probe`** — enumerate every reachable bridge and optionally set exit status
  on a `--require integrity|confidentiality` policy (security test suites). ✅
- **`otp`** (AST2600-only), **`trace`** (watch a register), **`reset`**,
  **`coprocessor`** (AST2600 CM3), **`devmem`/`ilpc`/`p2a`/`debug`** low-level
  transports. ✅

### 4.1 UART clock / baud math (for reconstructing UART behaviour)

The software-16550 divisor culvert uses is `divisor = (24000000 / 13) / (16 *
baud)` (`src/uart/suart.c:` `baud_to_divisor`) — i.e. ASPEED's UART reference
clock is **24 MHz ÷ 13 ≈ 1.846 MHz**. Handy when checking that an AST2050 UART
is clocked/strapped the way you expect. ✅

---

## 5. Building culvert

From `README.md` (Meson; cross-compiles for x86-64, ppc64/le, armv6, aarch64): ✅

```sh
# Debian deps
apt install build-essential flex swig bison meson device-tree-compiler libyaml-dev qemu-user

# native
meson setup build && meson compile -C build

# cross for 32-bit ARM (e.g. to run ON a BMC / on an armv6 bridge)
meson setup build-arm --cross-file meson/arm-linux-gnueabi-gcc.ini && meson compile -C build-arm
```

For the OpenOCD side you need OpenOCD built **with `remote_bitbang`**
(`./bootstrap && ./configure --enable-remote-bitbang && make`), plus
`gdb-multiarch` (`docs/OpenOCD.md`). ✅

---

## 6. Applicability to **our** hardware (AST2050 / G3) — read this first

Two questions decide this: (a) does the AST2050 *hardware* expose culvert's AHB
backdoors, and (b) does culvert's *software* recognise the part. Cross-checked
against the **AST2050/AST1100 A3 Datasheet, V1.02 (2008)**
(`../dell-c410x-firmware/datasheets/AST2050_AST1100_Datasheet.pdf`) and culvert
source. Full porting roadmap:
[`../docs/plans/2026-07-07-culvert-ast2050-g3-support.md`](../docs/plans/2026-07-07-culvert-ast2050-g3-support.md).

### 6.1 Hardware: the AST2050 *does* have AHB backdoor bridges ✅

Contrary to a first guess from culvert's device trees, the AST2050 datasheet
documents the same backdoor family culvert uses — only the *UART* console is
missing:

- **P2A (P-Bus→AHB), §36:** verbatim "a back door for host CPU to access all the
  internal IP modules in ARM SOC sub-system," stated use "H/W or S/W debugging
  through host CPU." 64 KiB window (`P2A04[31:16]` base, `P2A00[0]` enable key,
  regs at MMIOBASE+`F000h`/`F004h`), via the Aspeed VGA PCI function `1A03:2000`
  (`SCU30`). = culvert **`p2a`**. ✅
- **LPC-to-AHB:** `HICR5[8] ENL2H` + `HICR7 ADRBASE` / `HICR8 ADRMASK`. =
  culvert **`ilpc`/`lpc2ahb`**. ✅
- **External JTAG** for ARM code debug (§2.1, "ICE"-controllable CPU reset). ✅
- **No UART debug console:** `SCU70` has no debug-UART-select strap (the
  AST2500's `SCU70[29]` has no G3 equivalent; no UART5) and `SCU2C[10]` (the
  AST2500 debug-UART enable) is **"Reserved."** So culvert's **`debug-uart`**
  transport — and software-JTAG-over-serial — is a genuine dead end on the
  AST2050. Reach the AHB via `p2a`, `ilpc`, or `devmem` instead. ✅

### 6.2 Software: culvert does not yet recognise the AST2050 ✅

- Its revision table lists only AST2400/2500/2600 (`src/rev.c:18-23`) and
  `rev_generation` only maps generations `0x02/0x04/0x05` → `g4/g5/g6`
  (`src/rev.c:171-177`). The AST2050 generation nibble (`SCU 0x7C[31:24]`) is
  **`0x00`**, so `soc_probe()` fails with "Revision 0x… is unsupported" — and
  culvert's G6 heuristic may even mis-detect the `0x00`-gen part. ✅
- No G3 device tree (`src/devicetree/` has only g4/g5/g6). ✅
- Everything that calls `soc_probe()` (`probe`, `p2a`, `ilpc`, `sfc`, `jtag`)
  therefore needs a **G3 port** first: a `rev.c` entry + `g3.dts` + driver match
  data, then G3 register offsets for the `p2a`/`ilpc` drivers. See the plan.

### 6.3 Board split ⚠️

- **KGPE-D16:** an AMD Opteron host is wired to the BMC over PCI **and** LPC, so
  `p2a` and `ilpc` work **from the host** (host powered), and `devmem` from the
  BMC once our firmware boots.
- **Dell C410X:** **no host CPU** — nothing drives the PCI/LPC backdoors, so
  culvert there runs **on the BMC via `devmem`**, or you use physical JTAG.

### Suggested next steps (open items)

- [ ] Prototype the culvert **G3 port** (rev id + `g3.dts` + `p2a`/`ilpc` G3
      offsets) on `mithro/culvert` branch `ast2050-support`; test
      `culvert probe via devmem` on the BMC. See the plan doc.
- [ ] (KGPE-D16, from host) confirm the Aspeed VGA function `1A03:2000`
      enumerates, then exercise `culvert … via p2a`.
- [ ] Confirm the internal JTAG-master base + `MISC_CTRL[15:14]` routing exist on
      G3 (external JTAG itself is datasheet-confirmed) before relying on
      `culvert jtag`.

---

## 7. Source index (culvert @ `3fd2e94`)

| Topic | File |
|---|---|
| Interfaces / threat model / `--help` / examples | `README.md` |
| Debug-UART enter/exit handshake, shell command grammar, `d`/`u` framing | `src/bridge/debug.c`, `src/bridge/debug.h` |
| Debug-UART port/strap reporting (`SCU070[29]`, `SCU02C[10]`) | `src/soc/debugctl.c` |
| Host TTY baud (B1200/B115200) | `src/tty.c` |
| Remote serial via Digi PortServer TS-16 | `src/ts16.c`, `src/ts16.h` |
| Software 16550 over SuperIO/LPC (baud math) | `src/uart/suart.c`, `src/uart/suart.h` |
| Software/virtual JTAG: OpenOCD `remote_bitbang` server & command loop | `src/cmd/jtag.c` |
| JTAG master engine registers + SCU routing/reset | `src/soc/jtag.c`, `src/soc/jtag.h` |
| OpenOCD how-to (ARM/GDB flow, warnings) | `docs/OpenOCD.md` |
| Ready-made OpenOCD configs (ast2500 / ast2600-a7 / ast2600-cm3) | `openocd/scripts/*.cfg` |
| UART mux (LPC `HICR9`/`HICRA`) for `console` | `src/soc/uart/mux.c` |
| Silicon revision table (**no AST2050**) | `src/rev.c` |
| Device trees (g4/g5/g6 only — **no g3**) | `src/devicetree/g4.dts`, `g5.dts`, `g6.dts` |

**See also (this repo):** [`JTAG-HEADERS.md`](JTAG-HEADERS.md) ·
[`RPI4-OPENOCD-JTAG-WIRING.md`](RPI4-OPENOCD-JTAG-WIRING.md) ·
[`RAPTOR-UBOOT-ANALYSIS.md`](RAPTOR-UBOOT-ANALYSIS.md) ·
[`ast2050.h`](ast2050.h) ·
[`../dell-c410x-firmware/REUSING-KGPE-D16-WORK.md`](../dell-c410x-firmware/REUSING-KGPE-D16-WORK.md).
