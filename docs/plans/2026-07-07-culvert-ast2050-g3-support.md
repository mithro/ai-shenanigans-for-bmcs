# Extending culvert to support the ASPEED AST2050 (G3) — Plan

**Date:** 2026-07-07
**Superproject branch:** `claude/culvert-analysis`
**Fork / submodule:** [`mithro/culvert`](https://github.com/mithro/culvert) @ branch
`ast2050-support`, vendored at `asus-kgpe-d16-firmware/culvert`
(upstream base `3fd2e94`).
**Target hardware:** ASUS KGPE-D16 & Dell C410X BMCs — ASPEED **AST2050**
(a.k.a. **AST1100**), ARM926EJ-S, "G3" generation.
**Companion analysis:** [`../../asus-kgpe-d16-firmware/CULVERT-UART-JTAG-DEBUG.md`](../../asus-kgpe-d16-firmware/CULVERT-UART-JTAG-DEBUG.md)

> **Evidence markers:** ✅ verified (cited) · 🔶 strong inference (stated as such)
> · ⚠️ must be confirmed on real AST2050 silicon before trusting.

---

## 1. Goal

Make [culvert](https://github.com/amboar/culvert) usable against the AST2050 so
we can use it during open-firmware bring-up on the KGPE-D16 and C410X:
introspect the SoC (clocks, straps, SPI flash controller), dump/reflash BMC
flash, read/write RAM, and — where the hardware allows — drive the internal
JTAG master as an OpenOCD `remote_bitbang` server.

**Scope note (see §3):** the AST2050 *does* expose host→AHB backdoor bridges that
culvert already supports — **P2A** and **LPC-to-AHB** are both documented in the
AST2050/AST1100 datasheet. What it lacks is the *UART* debug console specifically
(a later AST2400+ feature). So this plan targets culvert's `p2a`, `ilpc` and
`devmem` transports on the AST2050, not `debug-uart`.

---

## 2. Background — why culvert doesn't work on the AST2050 today

Culvert only models three SoC generations (verified in the vendored tree):

- **Silicon-revision table** lists only AST2400 / AST2500 / AST2600
  (`src/rev.c:18-23`). It derives "generation" from `SCU 0x7C` bits `[31:24]`
  and only maps `0x02→g4`, `0x04→g5`, `0x05→g6` (`src/rev.c:171-177`). ✅
- **Device trees** exist only for `g4.dts` (AST2400), `g5.dts` (AST2500),
  `g6.dts` (AST2600) (`src/devicetree/`). ✅
- On an unrecognised revision, `soc_probe()` fails with *"Revision 0x… is
  unsupported"*, which blocks every verb that needs the SoC model
  (`jtag`, `probe`, `sfc`, `reset`, …). ✅

The AST2050's revision ID does not fit culvert's assumptions. Per this repo's
own reverse engineering of Raptor's DDR2 init, `SCU 0x7C`
(`SCU_REV_ID_REG` = `0x1E6E207C`, `asus-kgpe-d16-firmware/hwreg.h:94`) decodes as
(`asus-kgpe-d16-firmware/DDR2-INIT-REVERSE-ENGINEERING.md:365-367`): ✅

| Bits | Meaning | AST2050 value |
|---|---|---|
| `[31:24]` | Chip generation | **`0x00`** (= AST2050/AST2100/AST2150; `0x01` = AST2300) |
| `[23:16]` | Silicon revision within generation | `0x00`=A0, `0x01`=A1, … |
| `[7:0]` | Legacy revision ID | AST2050-generation legacy id |

So the AST2050 generation nibble is **`0x00`** — a value culvert neither lists
in its table nor maps in `rev_generation()`. Two concrete hazards follow:

1. `rev_generation()` has no `case 0x00`, so the AST2050 is "unsupported". ✅
2. **The AST2050 may be *mis*-detected as an AST2600.** Culvert's G6 heuristic is
   `is_g6 = !((probe[0] >> 28) & 0xf) && !((probe[1] >> 24) & 0xff)` where
   `probe[1]` is `SCU 0x7C` (`src/rev.c`). For the AST2050,
   `(SCU7C >> 24) & 0xff == 0x00`, making the second term true; if
   `SCU 0x04 [31:28]` also happens to be `0`, culvert would wrongly conclude G6.
   ⚠️ This must be handled, not just papered over with a new table row.

`ast2050.h:2` ("COPIED FROM AST1100 CONFIGURATION FILE") and
`RAPTOR-PORTING-GUIDE.md:32` confirm **AST2050 ≡ AST1100**; Raptor's kernel
`socinfo` driver already carries the concrete AST2050/AST1100 silicon IDs
(`RAPTOR-PORTING-GUIDE.md:287`) — that is our source of truth for the exact
constants to add to `rev.c` (§5, Phase 1).

---

## 3. What the AST2050 datasheet actually says about AHB back-doors ✅

Checked against the in-repo **AST2050/AST1100 A3 Datasheet, V1.02, 19 Sep 2008**
(`dell-c410x-firmware/datasheets/AST2050_AST1100_Datasheet.pdf`). The AST2050 has
**two of culvert's AHB backdoor transports, fully documented** — plus external
JTAG. Only the *UART* debug console is missing.

### 3.1 Present: P2A — culvert's `p2a` transport ✅

Datasheet §36 "P-Bus to AHB Bridge (P2A)" (p.393) describes it verbatim as
"a one-way bus bridge providing a **back door for host CPU to access all the
internal IP modules in ARM SOC sub-system**." Its two stated usages:
"1. Updating flash memory through host CPU" and
"**2. H/W or S/W debugging through host CPU**." Mechanism:

- `P2A00` (MMIOBASE+`F000h`) bit 0 — protection key: `1` = enable P2A bridge.
- `P2A04` (MMIOBASE+`F004h`) `[31:16]` — 64 KiB re-mapping window base:
  `AHB address = P2A04[31:16] + Pbus[15:0]`, over the PCI MMIO window
  `MMIOBASE+0x10000 … +0x1FFFF`. Byte/word/dword access.
- Reached through the Aspeed VGA PCI function, ID **`1A03:2000`** (`SCU30` init) —
  the same device culvert's P2A driver looks for.

This is culvert's "PCIe VGA P2A … arbitrary AHB access via a 64kiB sliding
window." The register offsets differ from G4/G5, so culvert's `p2a` driver needs
G3-specific offsets (§5 Phase 2), but the mechanism is the same.

### 3.2 Present: LPC-to-AHB — culvert's `ilpc`/`lpc2ahb` transport ✅

The LPC controller's Host Interface Control Registers implement it:
`HICR5[8] ENL2H` = "Enable LPC to AHB bridge", `HICR5[31:24] HWMBASE` +
`HICR6[27:24] HWNCARE` = decode range, `HICR7[31:16] ADRBASE` +
`HICR8[31:16] ADRMASK` = AHB remap base/mask. This is exactly culvert's
iLPC2AHB/LPC2AHB path.

### 3.3 Absent: the UART debug console — and it's *not* an undocumented feature ✅

The one thing genuinely missing is culvert's `debug-uart` transport. Tested the
"maybe it's just undocumented on the AST2050" hypothesis by comparing directly
against the **AST2500/AST2520 A2 Datasheet, V1.6 (12 May 2017)** (vgamuseum
`ast2520a2gp_datasheet.pdf`). The hypothesis fails — Aspeed documents the debug
UART thoroughly *and* documents it as AST2500-exclusive:

- **AST2500 §1.4 feature-comparison table** ("AST2500/AST2400/AST2300") lists:
  **Hardware UART debug — AST2500 = Yes, AST2400 = No, AST2300 = No.** So the
  feature is absent even from the *newer* AST2400 and AST2300; the older AST2050
  (G3) is not a candidate. The AST2500 datasheet also calls it "a **new** debug
  interface through UART" for AST25x0. ✅
- **AST2500 §11 "UART Debug Interface"** fully specifies it: default UART5
  (`SCU70[29]=0` → UART1), disable via `SCU2C[10]=1`, entry = 1200 baud + paste
  password → `$ ` → 115200, command set `i/o/r/w/d/t/u/q` + `Esc`. `SCU70[29]`
  describes it as "working as a hardware u-boot interface … **similar to the
  PCIe-to-AHB bridge**" — i.e. the UART peer of the P2A bridge (§3.1). ✅
- **AST2050 datasheet has none of this**: no §11 / UART-debug section; `SCU70[29]`
  is undefined (within the `[31:24]` "software defined trapping" storage); the
  AST2500 debug-UART disable bit `SCU2C[10]` is **"Reserved"** on the AST2050;
  and the AST2050 has no UART5. ✅

Conclusion: the UART debug console was **introduced with the AST2500**, is not
present on the AST2400/AST2300, and is neither documented nor strapped on the
AST2050. `culvert … via debug-uart` (and software-JTAG-over-serial) is a dead
end on the AST2050 — reach the AHB via P2A / iLPC2AHB / devmem instead (§4).
*(Cross-benefit: the §11 command grammar matches culvert's `bridge/debug.c`
exactly, validating that reverse engineering.)*

### 3.4 External JTAG for the ARM core — present ✅

Datasheet §2.1: the AST2050 "provides a JTAG-compliant interface for code
debugging … The JTAG interface also supports CPU reset pin that can be directly
controlled by In-Circuit-Emulator (ICE)." This is the `AST_JTAG1` header route
already documented in
[`RPI4-OPENOCD-JTAG-WIRING.md`](../../asus-kgpe-d16-firmware/RPI4-OPENOCD-JTAG-WIRING.md).
Whether culvert's *internal* JTAG-master software-bitbang (the `jtag` command)
also works on G3 is a separate register question (§5 Phase 3).

---

## 4. Which transports the AST2050 offers (datasheet-confirmed)

| culvert transport | On AST2050? | Notes |
|---|---|---|
| **`p2a`** (PCIe VGA → AHB, 64 KiB window, from host) | ✅ datasheet §36 | `1A03:2000` VGA function, `P2A00`/`P2A04` at MMIOBASE+F000h/F004h. Needs G3 register offsets in culvert's `p2a` driver. **KGPE-D16 only** (needs a host CPU on PCI). |
| **`ilpc` / lpc2ahb** (SuperIO/LPC → AHB, from host) | ✅ datasheet (HICR5–8) | `ENL2H`, `ADRBASE`/`ADRMASK`. **KGPE-D16 only** (needs a host CPU on LPC). |
| **`devmem`** (`/dev/mem`, running on the BMC) | ✅ once our Linux boots | Full AHB access from a shell on the BMC. The only culvert path on the **C410X** (no host CPU). Sidesteps PCI/LPC entirely. |
| **Physical JTAG** (not culvert; OpenOCD on `AST_JTAG1`) | ✅ datasheet §2.1 | ARM code debug with host powered off. See [`RPI4-OPENOCD-JTAG-WIRING.md`](../../asus-kgpe-d16-firmware/RPI4-OPENOCD-JTAG-WIRING.md). |
| **`debug-uart`** (UART password shell) | ❌ absent on G3 | §3.3 — no SCU70/SCU2C debug-UART strap. |

**Board split that drives the design:**
- **KGPE-D16** has an AMD Opteron host wired to the BMC over both **PCI and LPC**,
  so `p2a` and `ilpc` are usable **from the host** (host powered on), and `devmem`
  from the BMC once our firmware boots.
- **Dell C410X** has **no host CPU** (BMC-managed chassis), so nothing drives the
  PCI/LPC backdoors — culvert there must run **on the BMC via `devmem`**, or use
  the physical debug interfaces.

**Design implication:** make culvert *recognise* the AST2050 (§5 Phase 1), then
port the `devmem`, `p2a` and `ilpc` drivers to G3 (§5 Phase 2). `devmem` is the
lowest-risk first target (needs only recognition + an armv5 build); `p2a`/`ilpc`
add host-side, host-powered access on the KGPE-D16.

---

## 5. Work breakdown

### Phase 0 — Hardware truth-gathering (do first; cheap; unblocks the rest)

Use the `rpi4-asus-aspeed2050-dev` bridge (serial to the AST2050 already wired).

- [ ] ⚠️ **Read the live silicon revision.** Over the serial console / U-Boot
      `md 0x1e6e207c 1`, capture `SCU 0x7C`. Record generation nibble (expect
      `0x00`) and the full 32-bit value → becomes the `rev.c` constant.
- [ ] (optional) Confirm the §3.3 datasheet finding empirically: at 1200 baud,
      send the culvert password (`src/bridge/debug.c`) to each UART; expect **no**
      `$ ` response. Low priority — the datasheet already says there is no debug
      UART.
- [ ] ⚠️ **Resolve the header↔UART mapping** (see §6.2): continuity-probe the
      `AST_UART1` header pins to the AST2050, and observe which UART emits the
      boot log.
- [ ] **Read `SCU 0x70`** (`0x1E6E2070`) live and diff against the datasheet strap
      map (§3.3, §6.3) — sanity check for the board's actual strap wiring.
- [ ] (KGPE-D16, from the host) Confirm the BMC's Aspeed VGA PCI function
      `1A03:2000` enumerates, so the `p2a` path (§3.1) has a device to bind to.

### Phase 1 — Make culvert recognise the AST2050 (the mechanical core)

On `mithro/culvert` branch `ast2050-support`:

- [ ] Add a `ast_g3` generation to `enum ast_generation` and
      `bmc_silicon_gens[ast_g3] = 0x00` (`src/rev.h`, `src/rev.c`).
- [ ] Add `case 0x00: return ast_g3;` to `rev_generation()` and the AST2050/
      AST1100(/AST2100/AST2150) rows to `ast_silicon_revs[]`, using the concrete
      IDs from Raptor's `socinfo` driver (`RAPTOR-PORTING-GUIDE.md:287`) and the
      Phase-0 live read.
- [ ] **Fix the G6 mis-detection hazard** (§2 item 2): make `is_g6` also require a
      positive G6 signal (e.g. gen nibble `0x05`) rather than only the
      "top byte is zero" negative test, so a `0x00`-gen G3 can't be swallowed.
- [ ] Add `src/devicetree/g3.dts` + `g3.h`, cloned from `g4.dts`, describing at
      minimum SCU `@0x1e6e2000`, the SPI flash controller, RAM/SDMC, and the JTAG
      master (**pending Phase 3 base-address confirmation**). **Omit** the
      debug-bridge-controller node — the AST2050 has no debug UART (§3.3) — and
      instead ensure the P2A/LPC-to-AHB nodes reflect the §3.1/§3.2 registers.
      Register it in `src/devicetree/meson.build`.
- [ ] Add `"aspeed,ast2050-*"` compatibles to the SoC drivers. Where the AST2050
      is register-compatible with the AST2400, reuse the existing `ast2400_*_ops`
      (culvert already shares `ast2400_jtag_ops` between 2400 and 2500 —
      `src/soc/jtag.c` `jtag_match`), so this is mostly match-table additions.
- [ ] Build for the BMC: `meson setup build-arm --cross-file
      meson/arm-linux-gnueabi-gcc.ini` and confirm it runs on the ARM926 target.
- [ ] Smoke test: `culvert probe via devmem` on the BMC reports the AST2050 and a
      sane SoC map.

### Phase 2 — Port the transports to G3

- [ ] **`devmem`** (lowest risk, both boards): once our Linux boots on the BMC,
      run `culvert -v probe via devmem`, then `sfc` (dump BMC flash) and
      `read`/`write` (RAM), cross-checking against the register maps in
      `asus-kgpe-d16-firmware/`.
- [ ] **`p2a`** (KGPE-D16, from the host): teach culvert's `p2a`/`pciectl`
      drivers the G3 register layout from §3.1 — VGA function `1A03:2000`, key
      `P2A00[0]` at MMIOBASE+`F000h`, window base `P2A04[31:16]` at `F004h`,
      64 KiB window at MMIOBASE+`0x10000`. Note G3 has a single enable key, not
      the SCU write-filter set of G5/G6.
- [ ] **`ilpc`** (KGPE-D16, from the host): map culvert's iLPC2AHB onto the G3
      HICR5–8 registers from §3.2 (`ENL2H`, `ADRBASE`, `ADRMASK`).
- [ ] Document the working transports in `CULVERT-UART-JTAG-DEBUG.md` §6.

### Phase 3 — Software JTAG on G3 (only if the master exists there)

- [ ] Confirm the AST2050 JTAG-master base (culvert assumes `@0x1e6e4000` for
      g4/g5 — `src/soc/jtag.c`) and that `SCU MISC_CTRL[15:14]` routing
      (master→ARM) exists on G3. Cross-check `ast2050.h` / the datasheet.
- [ ] If present, wire a `g3` JTAG match (likely reusing `ast2400_jtag_ops`) and
      test `culvert jtag via devmem` → OpenOCD `remote_bitbang` → GDB, using the
      existing `openocd/scripts/ast2500.cfg` pattern adapted to the ARM926
      TAP/IDCODE.
- [ ] If a debug UART turned out to exist (Phase 0 surprise), also test
      `culvert jtag via debug-uart`.

### Phase 4 — Upstreaming

- [ ] Rebase `ast2050-support` on upstream `amboar/culvert` (the `upstream`
      remote is configured locally in the submodule).
- [ ] Open a PR to `amboar/culvert` adding G3/AST2050 support; culvert's author
      (Andrew Jeffery) is receptive to new-SoC contributions.
- [ ] Bump the superproject submodule pointer as milestones land.

---

## 6. Answering the direct question — KGPE-D16 UART wiring & debug-UART strap

*(This section stands alone; it's the "check which UART is on the header and how
the debug UART is strapped" deliverable.)*

### 6.1 Which UART carries the console — settled ✅

The firmware console is on **UART2 @ `0x1E784000`** (Linux `ttyS1`):
- U-Boot `CONFIG_CONS_INDEX 2` → COM2 = `0x1e784000`
  (`RAPTOR-UBOOT-ANALYSIS.md:345-350`, `ast2050.h`). ✅
- Kernel `console=ttyS1,115200n8` (`ast2050.h:61`,
  `RAPTOR-UBOOT-ANALYSIS.md:341`). ✅
- Raptor notes "Active: UART 2 (COM2) at 0x1e784000"
  (`RAPTOR_ENGINEERING_AST2050_ANALYSIS.md:870`). ✅

UART base map (`RAPTOR-UBOOT-ANALYSIS.md:321-322`): UART1 = `0x1E783000`
(Linux `ttyS0`), UART2 = `0x1E784000` (Linux `ttyS1`, the console). ✅

### 6.2 Which UART is on the physical header — UNRESOLVED, repo docs conflict ⚠️

The exposed 4-pin 3.3 V header is silkscreened **`AST_UART1`**, sitting just
above the AST2050, ordered `+3.3V / TX / RX / GND`, 115200 8N1
(`HEADER-PINOUTS.md:97-102`, Raptor photo). But the mapping to a SoC UART is
**internally inconsistent in our own docs**:

- `RPI4-OPENOCD-JTAG-WIRING.md:219` states the header *is* the AST2050's
  **UART1 @ `0x1e783000`** — but this is explicitly an inference "per Raptor's
  U-Boot `ast2050.h`" (i.e. from the silkscreen name), not a probed fact.
- The same doc's §3 and `HEADER-PINOUTS.md` simultaneously call `AST_UART1`
  "the **BMC console**" that "gives you the U-Boot prompt" — but the console is
  UART2 (§6.1), not UART1.

These cannot both be literally true. Either (a) the header is UART1 and is
**not** where the boot console prints, or (b) the header actually lands on UART2
(the console) and the "UART1" label is just the board's name for its first BMC
UART header. **This is exactly what Phase 0 must settle by probing** — continuity
from each header pin to the AST2050, plus watching which UART emits the boot log.
🔶 Best guess: since Raptor demonstrably reads the boot console on this header,
it is most plausibly wired to **UART2**, and the "= UART1 @ 0x1e783000" note is
an unverified silkscreen inference — but do not trust that without a meter.

### 6.3 How the debug UART is strapped — it isn't; the AST2050 has none ✅

Settled by the datasheet (§3.3), not inference:

- On the **AST2500**, the debug UART port is selected by `SCU70[29]`
  (`SCU_STRAP_DBG_SEL`: set = UART5, clear = UART1) and enabled via `SCU2C[10]`
  (`SCU_MISC_UART_DBG`) (`src/soc/debugctl.c`; OpenBMC/Aspeed refs). ✅
- On the **AST2050**, the full `SCU70` bit map (`0x1E6E2070`) contains **no
  debug-UART-select bit** and `SCU2C[10]` is **"Reserved"** — so there is
  **no debug UART to strap.** The AST2500 bit positions do **not** carry that
  meaning on G3. ✅
- What the AST2050 *does* have for host-driven AHB access — the "debug bridges"
  in the sense of §36's "H/W or S/W debugging through host CPU" — are gated by:
  **P2A** `P2A00[0]` (enable key), **LPC-to-AHB** `HICR5[8] ENL2H`, and the PCI
  path `SCU2C[8]` ("Disable PCI slave to AHB bus bridge", `0` = enabled). These,
  not a UART strap, are the knobs that expose the AST2050 AHB.

---

## 7. Risks & open questions

- ✅ **AST2050 has no debug UART** (datasheet-confirmed, §3.3) — not a risk, a
  scoping fact: don't build on `debug-uart` for G3.
- ✅ **P2A + LPC-to-AHB present** (datasheet §36 / HICR5–8) — the porting risk is
  only the *register-offset differences* vs G4/G5, not existence.
- ⚠️ **G6 mis-detection** of a `0x00`-generation part (§2). Must be fixed before
  trusting any `probe` result.
- ⚠️ **Exact AST2050 silicon-rev constant** — take from Raptor `socinfo` + the
  Phase-0 live read, not from guesswork.
- ⚠️ **JTAG master presence/base on G3** — culvert's `@0x1e6e4000` and the
  `MISC_CTRL[15:14]` routing are G4/G5 facts; confirm for G3 (external JTAG
  itself is datasheet-confirmed, §3.4).
- ⚠️ **C410X has no host CPU** — `p2a`/`ilpc` need a host driving PCI/LPC, so on
  the C410X culvert is `devmem`-only. Plan host-side testing on the KGPE-D16.
- **Register compatibility** of AST2050↔AST2400 is this repo's working
  assumption (the C410X DT is built on `aspeed-g4.dtsi`, `CLAUDE.md`); it is
  plausible 🔶 but each reused driver must be spot-checked.

---

## 8. References

- **AST2050/AST1100 A3 Datasheet, V1.02 (19 Sep 2008)** —
  `dell-c410x-firmware/datasheets/AST2050_AST1100_Datasheet.pdf`. §2.1 (CPU/JTAG),
  §36 P-Bus-to-AHB (P2A), LPC HICR5–8 (LPC-to-AHB), `SCU70`/`SCU2C`/`SCU30`.
  The primary source of truth for every AST2050 hardware claim here.
- Vendored culvert source: `asus-kgpe-d16-firmware/culvert/` (`src/rev.c`,
  `src/soc/jtag.c`, `src/bridge/debug.c`, `src/soc/debugctl.c`,
  `src/devicetree/g4.dts`).
- [`CULVERT-UART-JTAG-DEBUG.md`](../../asus-kgpe-d16-firmware/CULVERT-UART-JTAG-DEBUG.md)
  — culvert interface/protocol analysis (this plan's companion).
- `asus-kgpe-d16-firmware/`: `DDR2-INIT-REVERSE-ENGINEERING.md` (rev-ID decode),
  `RAPTOR-UBOOT-ANALYSIS.md` (UART map, console, straps), `ast2050.h`,
  `hwreg.h`, `RAPTOR-PORTING-GUIDE.md` (AST2050≡AST1100, socinfo IDs),
  `HEADER-PINOUTS.md` / `RPI4-OPENOCD-JTAG-WIRING.md` (header wiring).
- External: [amboar/culvert](https://github.com/amboar/culvert) ·
  [shenki: AST2600 UART debug boot](https://shenki.github.io/AST2600-recovery-uart/) ·
  [openbmc: debug uart uart5↔uart1](https://lists.ozlabs.org/pipermail/openbmc/2020-July/022378.html).
