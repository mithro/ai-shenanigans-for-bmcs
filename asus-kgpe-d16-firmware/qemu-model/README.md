# AST2050 (G3) faithful QEMU model — program plan & tracker

**Goal (2026-07-10):** Get the complete **OpenBMC** system booting **via TFTP +
NFS root** inside a QEMU that **correctly emulates the real ASUS KGPE-D16 AST2050
hardware** — comprehensively tested so we have high confidence the emulation
behaves *identically* to silicon. Every peripheral the ASUS motherboard exposes
must be modelled faithfully so that **all** OpenBMC functionality (power, sensors,
SOL, vKVM/keyboard, COM/VGA capture, Redfish, culvert) can be verified in
emulation. There must be a comprehensive test suite for **every** device.

> **Faithfulness rule:** the device must behave as it does on the **AST2050 (G3)** —
> *not* how a newer AST2400/2500/2600 behaves. Where upstream QEMU models the newer
> part, we diverge to match the G3.

This directory (`asus-kgpe-d16-firmware/qemu-model/`) is the home of that program.
The actual device C code lives in the QEMU fork submodule
(`asus-kgpe-d16-firmware/qemu-firmware/qemu/qemu`, `mithro/qemu` branch
`d16-ast2050-machine`). Here we keep the **plan, the per-peripheral docs, the
bare-metal firmware test suite, the golden reference captures, and the integration
tests** that pin the model to reality.

---

## 1. Honest status: what already exists vs. what this program adds

Prior work (do not re-derive — see `../qemu-firmware/STATUS.md`, `../qemu-firmware/PLAN.md`,
`../qemu-firmware/AST2050-PERIPHERAL-MODELING.md`, and PR #16 / PR #22):

| Already done | Where | Caveat this program must fix |
|---|---|---|
| `kgpe-d16-bmc` QEMU machine boots from-source U-Boot+kernel+initramfs to SSH | PR #16 | **Built on AST2400/G4 device models** ("runs the G3 kernel unchanged") — *not* faithful to the AST2050 |
| Raptor 2.6.28.9 stack boots | PR #16 | same G4-based machine |
| Dell C410X vendor firmware boots to `appweb` web service | PR #16 | required RE stopgap kernel patches because AST2050 blocks (I2C MAC-info EEPROM, legacy SPI EEPROM, VIC 0x14/0x38, USB UDC, Video engine) are **unmodelled** |
| Modern OpenBMC + Redfish built from source and verified | PR #22 | runs on **`romulus`/AST2500**, a different machine; not TFTP/NFS; host power can't truly transition |

**What is genuinely new here (the pivot):**
1. A **G3-faithful** `ast2050` SoC + machine (correct SCU rev-id/straps/clocks,
   compact VIC, DDR2 SDRAM controller, G3 memory map) — so an *unmodified* vendor
   kernel and a mainline kernel both see the real hardware.
2. **Per-peripheral** validation: for **every** device a (1) firmware test suite,
   (2) driver-grade doc, (3) faithful QEMU model, (4) integration test — see §4.
3. OpenBMC booting **via TFTP + NFS root** on the faithful machine, with the full
   host-control surface verifiable in emulation.

## 2. Why "G3-faithful" is real work — concrete divergences

QEMU upstream models AST2400/2500/2600 but **not** the AST2050 (G3). The AST2050
shares the ARM926EJ-S core with the AST2400 (QEMU's `palmetto-bmc`) but differs in
ways that a "close enough" G4 model gets wrong. Evidence gathered on real silicon
(culvert P2A session) and from the Raptor sources:

- **Interrupt controller (VIC) @ `0x1E6C0000`.** AST2050 uses a **single compact
  bank** (`0x00` IRQ_STATUS … `0x14` IRQ_CLEAR/disable, `0x24` SENSE, `0x28`
  BOTH_EDGE, `0x2C` EVENT, `0x38` EDGE_CLEAR, `0x20` PROTECT — see `hwreg.h`,
  datasheet §16). QEMU's `hw/intc/aspeed_vic.c` models the AST2400 **two-bank
  interleaved** map (second bank at `+0x80`) with write-only-clear semantics — so
  reads of `0x14`/`0x38` hit "Bad register" and return 0. Confirmed on HW: the real
  VIC is at `0x1E6C0000` (not the G4 `0x1E6C0080` interleave). *This needs a
  dedicated G3 VIC model.*
- **SCU @ `0x1E6E2000`.** Silicon **revision-ID** (`0x7C`), **hardware strap**
  (`0x70`), and **H-PLL/M-PLL** parameter encodings differ from the AST2400; the
  clock rates the kernel computes (timer tick, UART divisor, MAC clock) depend on
  these. A G4 SCU produces G4 clocks.
- **SDRAM controller @ `0x1E6E0000`.** AST2050 is **DDR2** (Raptor `platform.S`:
  MCR10=`0x22201725`, MCR20=`0x00c82222`, key `0xFC600309`); AST2400 is DDR3. U-Boot
  DRAM init pokes controller registers whose meaning is DDR2-specific.
- **Flash/SMC controller.** `hwreg.h` `AST_SMC_BASE = 0x16000000` with the boot
  flash memory-mapped (≈`0x14000000`) — the legacy SMC, not the AST2400 FMC at
  `0x1E620000`. (We boot from memory, but the controller is still probed.)
- **Absent-on-G3 blocks.** Newer parts add PECI, extra I2C/PWM engines, RCLK-based
  MAC delay, eSPI, etc. The model must *not* expose these on the AST2050.

The datasheet cross-check of the full map is in `AST2050-MEMORY-MAP.md`.

## 3. Peripheral inventory (master matrix)

Base addresses below are from Raptor `hwreg.h` + the AST2050-PERIPHERAL-MODELING
findings, **pending** datasheet confirmation in `AST2050-MEMORY-MAP.md`. The four
deliverable columns (**T**=firmware test, **D**=doc, **M**=QEMU model, **I**=
integration test) track completion: ☐ todo · ◐ partial · ☑ done.

| # | Peripheral | Base | OpenBMC/board use | T | D | M | I | Phase |
|--:|---|---|---|:-:|:-:|:-:|:-:|:-:|
| 1 | SCU (system control: clocks, straps, rev-id, reset, pinmux) | 0x1E6E2000 | clocks/identity gate everything | ☐ | ☐ | ◐ | ☐ | 1 |
| 2 | SDRAM controller (DDR2) | 0x1E6E0000 | U-Boot DRAM init | ☐ | ☐ | ◐ | ☐ | 1 |
| 3 | VIC (interrupt controller, compact G3) | 0x1E6C0000 | all IRQs | ☐ | ☐ | ◐ | ☐ | 1 |
| 4 | Timer (FTTMR010, 3×) | 0x1E782000 | clocksource/clockevent | ☐ | ☐ | ◐ | ☐ | 1 |
| 5 | UART1 / UART2 (16550) | 0x1E783000 / 0x1E784000 | console, SOL | ☐ | ☐ | ◐ | ☐ | 1 |
| 6 | WDT | 0x1E785000 | watchdog, reset | ☐ | ☐ | ◐ | ☐ | 1 |
| 7 | AHB controller + remap | 0x1E600000 | boot remap (0x0↔DRAM) | ☐ | ☐ | ◐ | ☐ | 1 |
| 8 | ftgmac100 MAC1 (RMII + RTL8201CP PHY) | 0x1E660000 | **netboot/NFS**, network | ☐ | ☐ | ◐ | ☐ | 2 |
| 9 | MDIO / PHY | in MAC | link, autoneg | ☐ | ☐ | ◐ | ☐ | 2 |
| 10 | SMC / SPI flash controller | 0x16000000 (regs) | flash probe (we boot from RAM) | ☐ | ☐ | ☐ | ☐ | 2 |
| 11 | I2C controller (multiple engines) | TBD (≈0x1E78A000) | sensors, EEPROM, PSU | ☐ | ☐ | ☐ | ☐ | 3 |
| 12 | GPIO | 0x1E780000 | power ctl, presence, LEDs | ☐ | ☐ | ◐ | ☐ | 3 |
| 13 | PWM / tach | TBD (≈0x1E786000) | fan control/monitor | ☐ | ☐ | ☐ | ☐ | 3 |
| 14 | ADC | TBD (≈0x1E6E9000) | voltage/temp sensors | ☐ | ☐ | ☐ | ☐ | 3 |
| 15 | RTC | TBD (≈0x1E781000) | time | ☐ | ☐ | ☐ | ☐ | 3 |
| 16 | LPC (KCS/BT IPMI, SuperIO, iLPC2AHB) | TBD (≈0x1E789000) | host IPMI, culvert ilpc | ☐ | ☐ | ☐ | 3 |
| 17 | Video engine (KVM capture) | 0x1E700000 | vKVM, VGA capture | ☐ | ☐ | ☐ | ☐ | 4 |
| 18 | USB2.0 UDC / virtual hub | 0x1E6A0000 | virtual media, vkeyboard | ☐ | ☐ | ☐ | ☐ | 4 |
| 19 | P2A / PCIe-to-AHB bridge | via SCU/PCI | culvert p2a | ☐ | ☐ | ☐ | ☐ | 5 |
| 20 | Hash/crypto, mailbox, scratch, misc | TBD | as probed | ☐ | ☐ | ☐ | ☐ | 5 |

The matrix is authoritative once `AST2050-MEMORY-MAP.md` confirms/corrects the TBD
rows and the "present on G3?" question for each.

## 4. The four deliverables per peripheral (definition of done)

For peripheral `<p>` under `peripherals/<p>/`:

1. **Firmware test — `fwtest.c`** (+ registered in the shared harness). A small,
   self-contained bare-metal routine that pokes `<p>` and prints a **deterministic,
   greppable** report over UART (reset values, RMW behaviour, IRQ assertion, etc.).
   It runs **unmodified on QEMU and on real hardware** (via the RPi rig), so the two
   can be diffed byte-for-byte. Built by `fwtest/build.py`.
2. **Doc — `DOC.md`.** Datasheet-cited register map + reset values + behaviour +
   how U-Boot / Zephyr / Linux drivers use it + the **AST2050-specific quirks**.
   Enough to write a driver from scratch. Every claim carries evidence (datasheet
   §/page, `hwreg.h`, decompiled snippet, or a captured value).
3. **QEMU model — commits in the `mithro/qemu` fork** (`hw/…`). Observable behaviour
   matches the datasheet **and** the firmware test's golden output. Faithful to G3,
   not G4.
4. **Integration test — `integration/test_<p>.py`.** Built on `firmware-testbench`.
   Asserts the firmware test's QEMU output **equals the golden reference** (and,
   once HW access is granted, equals the live silicon capture). This is the proof
   that "U-Boot & Linux behave identically on QEMU and real hardware."

## 5. Validation without touching real hardware (do all of this first)

Per the standing directive, **all work that can be done without real hardware is
completed before requesting hardware access.** Golden references come from:

- **Recorded real-silicon captures** already in the repo/memory (culvert P2A
  register reads, U-Boot boot logs, `SCU7C`, DDR2 params, VIC config words).
- **Datasheet reset values** (documented power-on register state).
- **Raptor known-good init** sequences (`platform.S`, `RAPTOR-UBOOT-ANALYSIS.md`).

The QEMU model must reproduce these. Where no golden capture exists yet, the
integration test is marked `xfail(reason="awaiting HW capture")` — tracked, not
hidden. A later **gated** step (only with explicit permission) re-runs the same
firmware tests on silicon and replaces xfail/golden with live captures. That step
is enumerated in `HW-VALIDATION-CHECKLIST.md` (written before HW is requested) so
one hardware session validates everything at once.

## 6. Phasing (incremental; each lands before the next)

- **Phase 0 — setup & harness** *(in progress)*: worktree, this plan, the bare-metal
  firmware-test harness (crt0 + UART + report protocol), golden-data schema.
- **Phase 1 — SoC identity & boot foundation**: SCU, SDRAM, VIC, Timer, UART, WDT,
  AHB/remap. Exit: mainline U-Boot + kernel boot on the *faithful* machine with G3
  clocks/identity, no "Bad register" VIC noise.
- **Phase 2 — netboot/NFS transport**: ftgmac100 (RMII + RTL8201CP), MDIO/PHY, SMC.
  Exit: kernel TFTP-loads + mounts an NFS root under the faithful machine.
- **Phase 3 — OpenBMC peripheral surface**: I2C, GPIO, PWM/tach, ADC, RTC, LPC/KCS/BT.
  Exit: OpenBMC's hwmon/IPMI/GPIO stacks bind and read plausible values.
- **Phase 4 — host control & media**: Video engine (KVM/VGA capture), USB UDC
  (virtual media/keyboard), SOL routing. Exit: vKVM + SOL + virtual media exercised.
- **Phase 5 — culvert surfaces**: P2A / iLPC2AHB / debug bridges. Exit: culvert's
  features work against the model.
- **Phase 6 — integration**: modern OpenBMC image boots via **TFTP + NFS root** on
  the faithful machine; Redfish + full host control verified; the whole per-device
  integration suite green in CI.

## 7. Layout

```
qemu-model/
  README.md                 this plan + the master matrix
  PROGRESS.md               running log, committed after every change
  AST2050-MEMORY-MAP.md     datasheet-cited authoritative memory map
  HW-VALIDATION-CHECKLIST.md the one gated hardware session (written before HW is touched)
  fwtest/                   shared bare-metal test harness (crt0, linker, UART, report)
    build.py
  peripherals/<p>/
    DOC.md                  driver-grade doc (deliverable 2)
    fwtest.c                firmware test (deliverable 1)
    golden/                 recorded reference captures (real HW + datasheet resets)
  integration/
    test_<p>.py             integration tests on firmware-testbench (deliverable 4)
```

The QEMU device C code (deliverable 3) is committed in the `mithro/qemu` submodule.
