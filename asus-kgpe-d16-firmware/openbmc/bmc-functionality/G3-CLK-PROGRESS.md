# G3-CLK — root-causing the silicon clk findings (#94 UARTCLK gate, #93 I2C timeouts)

Branch `claude/bmc-g3-clk` off `claude/bmc-hwpass` (46db1ab). QEMU submodule
branch `claude/g3-clk-gates` off a010d696. Method: QEMU-first faithfulness —
model the real SCU clock-stop/reset behaviour so QEMU reproduces the silicon
failure, then fix the kernel properly, verify in QEMU, then (optionally) prove
on the rig.

## Root-cause analysis (datasheet-grounded)

### #94 — serial console dies at t≈4.16 s ("clk: Disabling unused clocks")

**Datasheet facts** (AST2050 A3 V1.05 §18 p209–210; extraction
`qemu-model/peripherals/scu/DATASHEET-SCU.md` §4):

- G3 `SCU0C[15]` = **Stop UARTCLK — one gate shared by BOTH UART1 and UART2**
  (reset 0 = running). The console UART at 0x1e784000 is the G3's **UART2**.
- G3 `SCU0C[17:16]` are **reserved (0)** — there is no per-UART gate and no
  UART5 on this SoC.

**Kernel facts** (v6.6.70 + our 0001 patch): the AST2050 clk driver reuses the
**AST2400 gate table** (`aspeed_gates[]` in `drivers/clk/clk-aspeed.c`), so the
kernel registers `uart1clk-gate`=bit15, `uart2clk-gate`=bit16,
`uart5clk-gate`=bit17. `aspeed-g4.dtsi` wires the console
(`uart5: serial@1e784000`) to `ASPEED_CLK_GATE_UART5CLK` (bit17) — a
**reserved no-op bit on the G3** — so the 8250 driver's clk reference holds
nothing real. The *real* console gate (bit15) is registered as the *unused*
`uart1clk-gate`, and `clk_disable_unused()` sets `SCU0C[15]=1` at late init →
UART1+UART2 clock-dead → console TX drains never complete → late console
writers (getty, PID1 status writes) block in the tty layer → PID1 stops petting
the 120 s aspeed WDT → SoC reset at the deterministic T+370 s observed on
silicon (HWPASS-PROGRESS.md §C.8). `clk_ignore_unused` masks it by never
gating.

**Latent sibling bug (same mechanism, found in this audit):** `SCU0C[8]` Stop
LCLK (LPC) is real on the G3 (same bit as G4) and **nothing in our DTS
references `ASPEED_CLK_GATE_LCLK`** — the only LPC consumer we enable is
`kcs@2c`, and `kcs_bmc_aspeed.c` takes no clock at all (g4-dtsi's lpc_ctrl/
lpc_snoop/ibt, which do reference LCLK, are all disabled). So on a boot
*without* `clk_ignore_unused`, `clk_disable_unused()` also stops the LPC
clock → host-KCS (and the VUART/SOL LPC side) dies on real silicon. The final
C.10 demo only worked because `clk_ignore_unused` masked this too.

**Why QEMU didn't catch it:** the `aspeed.scu-ast2050` model stores SCU0C
writes with **no behavioural effect** — gated UART/LPC keep working. That is
the unfaithfulness to fix (task #94's QEMU side).

### #93 — every I2C bus-1 transaction times out (-110) on silicon

Structural audit — everything below **checks out compatible**, eliminating the
easy hypotheses:

| Hypothesis | Verdict | Evidence |
|---|---|---|
| I2C clock gated by clk framework | **No** | G3 SCU0C has **no I2C gate** (I2C runs from PCLK, ungateable); final demo booted with `clk_ignore_unused` (nothing gated) and I2C was still dead |
| Wrong APB/PCLK rate → wrong SCL divisor | **No** | kernel derived PCLK≈47 MHz (`sched_clock: 32 bits at 47MHz`); external wall-clock matched kernel timing on silicon (T+370 s determinism), so the rate belief is ≈right; worst-case divisor error is a bounded % of SCL, not a timeout |
| Undefined I2CD04 AC-timing fields (G3 `Init = X`; mainline preserves tBUF/tHDSTA/tACST, writes 0 to BaseClk#2 [7:4]) | **Bounded, not fatal** | all X-able fields count 1–8 cycles of BaseClk#1/#2; with the divisors mainline programs, worst case is µs-scale — cannot produce 1 s timeouts. (Still worth fully programming like the vendor driver does — Raptor writes `0x77700300 \| …`.) |
| Wrong IRQ line | **No** | datasheet §10 Table 36 p99: I2C = VIC **12**, exactly what aspeed-g4.dtsi's i2c-ic uses. The same table is silicon-corroborated by working LPC=8 (host-KCS demo), UART2=10 (console), MAC1=2, Timer1=16 |
| VIC trigger misprogram for line 12 | **No** | irq-aspeed-g3-vic programs SENSE/EVENT bit12 = level-high (matches datasheet "12 I2C/SMBus (hi)"); same VIC config drives working level lines 2/8/10 |
| Wrong engine (bus-numbering off-by-one) | **No** | Raptor's `dev-i2c.c` (fetched from raptor-engineering/ast2050-linux-kernel): `ast_i2c_dev1_device` (engine 0x40) has `.id = 0` → Raptor's proven `i2c-1` = datasheet Device #2 @ 0x1e78a080 = our DTS `&i2c1`. Same engine |
| Engine held in SCU04[2] reset | **Unlikely** | G3 SCU04 resets 0x000FFE5C (bit2=1, I2C held) **but** aspeed-g4.dtsi i2c nodes carry `resets = <&syscon ASPEED_RESET_I2C>` (bit 2 — same bit on G3) and `i2c-aspeed.c` deasserts at probe; kernel SCU writes provably land on silicon (the SCU0C[15] gate itself is the #94 proof) |
| Pinmux | **Unlikely** | G3 I2C1–4 pads are dedicated (SCU74 only muxes I2C5/6/7, p219–220; I2CG04[1:0]=00 default = 7-set I2C). Raptor's working init does no pinmux for this engine (`ast_scu_multi_func_i2c()` is a 2300/2400-only body) |

**Signature analysis:** `-110` on *every* transaction incl. `i2cdetect` matches
i2c-aspeed's *bus-busy → `aspeed_i2c_recover_bus()` → wait_for_completion
timeout → -ETIMEDOUT* path (or a completion IRQ that never arrives). The
discriminating fact is **I2CD14[18:17] (sampled SCL/SDA line state) + [16]
(bus-busy) + [22:19] (state machine)** on the live engine — readable over P2A
(culvert, read-only) — plus I2CD04/I2CD00 as-programmed values. That is the
next-evidence step; do NOT guess further without it.

## Work plan

1. **QEMU faithfulness** (submodule branch `claude/g3-clk-gates`):
   - `aspeed.scu-ast2050`: SCU0C[15] stops UART1+UART2 (register file inert →
     LSR reads 0, no THRE, no IRQ — the silicon-observed "console dead");
     SCU0C[8] stops the LPC block (KCS regs inert); SCU04[2] holds the I2C
     block in reset (registers inert until deasserted). G3 SCU04 reset value
     0x000FFE5C.
   - Repro gate: CURRENT kernel booted WITHOUT `clk_ignore_unused` must lose
     its console at ≈4.16 s in QEMU (and KCS must die), like silicon.
2. **Kernel fix** (patch 0001 rework + small extras):
   - G3-specific gate table in clk-aspeed (shared bit-15 uartclk-gate aliased
     to UART1/UART2/UART5 dt ids; real LCLK bit8; USB2.0 bit14 inverted; no
     MAC/UART3/4/SD/eSPI/LHCLK gates — those bits are reserved on G3; MAC gate
     ids resolve to ungated pass-throughs), keep MCLK/BCLK/DCLK/REFCLK
     critical (BCLK/DCLK = the P2A/VGA recovery path, no Linux consumer).
   - Guard G4-only divider/register accesses that don't exist on the G3
     (SCU08 SD/MAC/LHCLK fields, SCU D8 bclk divider, ECLK divider —
     the last *overlaps the G3 LHCLK divider field*, a write hazard).
   - `kcs_bmc_aspeed`: optional clock (devm_clk_get_optional + enable); DTS
     `kcs@2c` gains `clocks = <&syscon ASPEED_CLK_GATE_LCLK>`.
   - Fully program I2CD04 (all AC-timing fields) like the vendor driver —
     correctness hardening for `Init = X`, independent of the #93 root cause.
3. **Verify in QEMU**: fixed kernel boots to login WITHOUT `clk_ignore_unused`;
   F3 i2c/sensor test green; C2/C4 oracles green; integration suite green.
4. **Silicon** (optional, low-risk only): P2A read-only I2C diagnostic dump;
   if justified, boot the fixed kernel without `clk_ignore_unused` per
   `hwpass-boot-and-demo.sh` (incl. the 00-bmc-eth0.network deletion step).

## #93 SILICON ROOT CAUSE (2026-07-12 evening, live-BMC devmem diagnostics)

Read-only devmem dumps on the running board (image from HWRECOVER C.10, which
boots with `clk_ignore_unused`) — every "easy" hypothesis measured FALSE:

- `SCU00=0x00000001` → SCU **unlocked** (kernel SCU writes land).
- `SCU04=0x000FF658` → bit2=0: **I2C reset properly de-asserted** by
  i2c-aspeed's `reset_control_deassert`.
- `SCU08=0x61800070` → PCLK divider [25:23]=0b011 → PCLK = 200 MHz/8 = 25 MHz.
- `I2CG04=0` (7-set I2C pinmux), `I2CD00=0x8001` (master enabled,
  multi-master disabled), `I2CD0C=0x207F` (driver's interrupt enables set).
- VIC: enable bit12 set, SENSE/EVENT bit12 = level-high. `/proc/interrupts`:
  the i2c demux IRQ has fired **0 times ever**.
- Idle `I2CD14=0x0A060000`: sampled **SCL=1 SDA=1** (bus electrically fine),
  state machine IDLE, not busy.

**The wedge, caught live:** during a probe of an unclaimed address
(`i2cdetect -y 1 0x21 0x21`, 1.2 s = one adapter timeout), sustained
`I2CD14=0x12CD0002`: state machine **[22:19]=0b1001 = MSTART**, SDA_OE=1
(START being driven, SDA low, SCL still high), bus-busy=1, Master-TX command
still latched — the FSM **never leaves the START state**; no I2CD10 status,
no IRQ, until the driver's timeout + recovery resets the engine
(`I2CD14` back to 0x0A060000). Every transaction repeats this.

The stalled phase is **tHDSTA (Start-hold) counting**, and the live
`I2CD04=0x18076005` shows the mainline-**preserved power-up garbage**:
tHDSTA[27:24]=0x8 = "1×**BaseClk#2**" units (with BaseClk#2 divisor [7:4]
left 0 by mainline). tBUF/tACST use BaseClk#1 and don't stall; the FSM wedges
exactly in the only phase clocked by BaseClk#2 on this power-up value. The
vendor driver (Raptor/Aspeed SDK `select_i2c_clock()`) always writes
`0x777xxxxx` — all three fields in BaseClk#1 units — so the vendor stack
never exercises this corner (matching "first-ever exercise fails").
Patch 0005 (program tBUF/tHDSTA/tACST=7 in BaseClk#1 units, vendor-style)
targets exactly this. A live confirmation `devmem` write of I2CD04 was
prepared but declined by policy (un-sanctioned live write); the sanctioned
proof is the Phase-2 fixed-kernel boot, whose i2c init programs the same
values.

## Log

- 2026-07-12: worktree + branches created; full datasheet/driver/Raptor audit
  above completed (no code changes yet).
- 2026-07-12: **QEMU faithfulness landed** (submodule eecfbf68, branch
  `claude/g3-clk-gates`): 2050 SCU drives `g3-uartclk-stop`/`g3-lclk-stop`/
  `g3-i2c-rst`; the 2050 SoC disables the UART1+UART2 / LPC / I2C MMIO regions
  accordingly (inert = reads 0, writes dropped, no IRQ). SCU04[2] reset
  default already holds I2C (0xFFCFFEDC bit2=1). fwtests updated: i2c now
  unlocks SCU + de-asserts the reset like real firmware (and asserts
  inert-while-held); uart/lpc assert gate/ungate. Verified: i2c/uart/lpc
  fwtests PASS, integration suite 76 passed + 10 pre-existing xfails,
  **C4 oracle PASS** (Dell vendor firmware boots to a serving appweb on the
  faithful model — the vendor stack de-asserts/keeps clocks on, as real
  firmware must).
