# mobo-bench P0 + P1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the `mobo-bench` project — a new `mithro` repo (added here as a submodule) containing the KGPE-D16 harness wiring map and a minimal LiteX SoC on the ULX3S 45F that a Raspberry Pi 5 can control over a wishbone bridge, plus a soft USB hub presenting a first standard USB device.

**Architecture:** P0 is foundation (repo + submodule + a validated connector→GPIO pin map and wiring diagram). P1 is a LiteX SoC for `radiona_ulx3s` (ECP5 45F) with a small VexRiscv CPU, a UARTBone wishbone bridge (verified from the Pi 5 via `litex_server`/`RemoteClient`), an LED CSR (blinky), and a soft USB hub (Greg Davill hub emulation / valentyusb) exposing the wishbone bridge + one CDC-ACM as standard USB devices. LiteDRAM is brought up but foundational-only.

**Tech Stack:** LiteX (Migen), litex-boards, oss-cad-suite (yosys/nextpnr-ecp5/ecppack — already installed at `~/oss-cad-suite`), openFPGALoader, VexRiscv, valentyusb/LUNA soft-USB, Python via `uv`, Raspberry Pi 5 (`openFPGALoader`, `litex_server`, `flashrom`/`openocd` later). Spec: `docs/plans/2026-07-19-mobo-bench-controller-design.md`.

---

## Conventions & prerequisites (read first)

- **Worktrees, not `main`.** All ai-shenanigans changes land on a branch in a
  `.worktrees/<name>` worktree; integrate via `--no-ff` merge/PR. The
  `mobo-bench` repo uses its own `claude/*` branches.
- **Python via `uv`** with PEP-723 inline metadata; never bare `python`/`pip`.
- **Small, frequent commits.** End commit messages with
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- **Never redirect stderr to `/dev/null`.** Fail loud.
- **Toolchain:** `~/oss-cad-suite/bin` on `PATH` provides yosys, nextpnr-ecp5,
  ecppack, openFPGALoader. LiteX is installed per Task 1.1.
- **Hardware:** the 45F ULX3S + its Raspberry Pi 5 are provided **after** P0's
  wiring diagram exists. P1 gateware/build/sim tasks proceed without hardware;
  P1 **hardware** steps (load + Pi-5 control) run once the 45F+Pi5 arrive. Where
  a step needs hardware, it is marked **[HW]** and may be deferred/simulated.
- **HIL host:** the Pi 5 is reached over SSH (alias to be set once provided,
  mirroring the existing `asus-bmc` pattern). GitHub SSH and HTTPS both work.

---

## File Structure (decomposition)

**New repo `mobo-bench/`** (LiteX-conventional):
- `mobo_bench/soc.py` — the SoC (platform target wrapper, CPU, bridges, hub).
- `mobo_bench/platform.py` — ULX3S platform + the KGPE-D16 harness pin extension.
- `mobo_bench/cores/` — custom cores (empty in P1; filled P2–P5).
- `firmware/` — CPU firmware (P1: default LiteX BIOS only).
- `sim/` — `litex_sim`/verilator configs.
- `test/` — Pi-5 hardware-in-the-loop scripts (`hil_remoteclient.py`, …).
- `wiring/make_pinmap.py` — generates + validates the connector→GPIO map.
- `wiring/pinmap.csv`, `wiring/harness.svg` — generated wiring artifacts.
- `docs/` — design + per-phase docs (the spec moves here).
- `LICENSE` (Apache-2.0), `README.md`, `.gitignore`, `pyproject`-free (uv/PEP723).

**In `ai-shenanigans` (this repo, branch `claude/mobo-bench-spec`):**
- `.gitmodules` + submodule at the agreed path.
- the design spec + this plan under `docs/plans/`.

---

## Phase P0 — Wiring & repo skeleton

### Task 0.1: Confirm gating decisions

**Files:** none (records a decision in the plan/commit message).

- [ ] **Step 1: Record repo name + submodule path.** Defaults (used unless the
  user overrides): repo **`mobo-bench`**; submodule path **top-level
  `mobo-bench/`** in ai-shenanigans (it is a general tool, not KGPE-D16-only).
- [ ] **Step 2: Confirm the license** is Apache-2.0 (repo default) and the
  GitHub owner is `mithro`.

### Task 0.2: Scaffold the `mobo-bench` repo locally

**Files:**
- Create: `~/github/mithro/mobo-bench/{README.md,LICENSE,.gitignore}`
- Create: `~/github/mithro/mobo-bench/mobo_bench/__init__.py`
- Create dirs: `mobo_bench/cores/`, `firmware/`, `sim/`, `test/`, `wiring/`, `docs/`

- [ ] **Step 1:** `git init ~/github/mithro/mobo-bench` and create the directory
  tree above (empty `.gitkeep` where needed).
- [ ] **Step 2:** Write `LICENSE` (Apache-2.0 full text) and a `README.md`
  describing the project (copy the goal/architecture from the spec header) with
  a build/verify quickstart placeholder.
- [ ] **Step 3:** Write `.gitignore` for LiteX/Python builds:
  `build/ __pycache__/ *.pyc *.bit *.svf *.json *.config .venv/ csr.csv
  analyzer.csv soc.svd`.
- [ ] **Step 4: Verify** the tree: `find ~/github/mithro/mobo-bench -maxdepth 2
  -not -path '*/.git/*'` shows the layout.
- [ ] **Step 5: Commit** (in the mobo-bench repo, branch `main`):
  `git add -A && git commit -m "Initial mobo-bench repo skeleton (LiteX layout, Apache-2.0)"`.

### Task 0.3: Create the GitHub repo and push

**Files:** none (remote).

- [ ] **Step 1:** `gh repo create mithro/mobo-bench --public --source=~/github/mithro/mobo-bench --remote=origin --description "ULX3S LiteX bench controller for the ASUS KGPE-D16"` (or create empty + `git remote add`).
- [ ] **Step 2:** `git -C ~/github/mithro/mobo-bench push -u origin main`.
- [ ] **Step 3: Verify:** `gh repo view mithro/mobo-bench --json name,visibility,url`.

### Task 0.4: Add `mobo-bench` as a submodule

**Files:**
- Modify: `.gitmodules` (created), submodule dir `mobo-bench/`
- Work in: a fresh worktree `.worktrees/mobo-bench-submodule` off `origin/main`
  (keep this plan's `claude/mobo-bench-spec` branch for docs).

- [ ] **Step 1:** In the ai-shenanigans worktree:
  `git submodule add https://github.com/mithro/mobo-bench.git mobo-bench`.
- [ ] **Step 2: Verify:** `git submodule status` lists `mobo-bench`; `.gitmodules`
  has the entry.
- [ ] **Step 3: Commit:** `git add .gitmodules mobo-bench && git commit -m
  "Add mobo-bench as a submodule"`.

### Task 0.5: Connector→GPIO pin map (script + validation)

**Files:**
- Create: `~/github/mithro/mobo-bench/wiring/make_pinmap.py` (uv/PEP-723)
- Create (generated): `wiring/pinmap.csv`
- Reference: spec §3.1 inventory + `asus-kgpe-d16-firmware/schematic-wiring/*`,
  `JTAG-HEADERS.md`, `ULX3S-SPISPY-BMC-FLASH-WIRING.md`, `spispy/verilog/ulx3s_v20.lpf`.

- [ ] **Step 1: Write the failing check.** `make_pinmap.py` declares, as data,
  every in-scope signal (from §3.1) grouped by connector, and the ULX3S GPIO
  resource list (`gp[0..27]`, `gn[0..27]` minus ESP32-shared `gp/gn[11..13]`).
  It assigns each signal a free GPIO and then **asserts**: (a) no GPIO used
  twice, (b) total ≤ available, (c) every §3.1 signal is assigned, (d) RS-232
  signals are flagged `via=MAX3232`, HDT flagged `via=1.27mm-adapter`. Write the
  assertions first with an intentionally incomplete map so it fails.
- [ ] **Step 2: Run to confirm it fails:** `uv run wiring/make_pinmap.py`
  Expected: `AssertionError` (unassigned signals / budget).
- [ ] **Step 3: Complete the map** so every signal has a GPIO and the assertions
  pass; keep the `BMC_FW1` SPI pins on the same GPIO as spispy where feasible
  (GP7=CS, GP8=SCK, GP9=MOSI, GP10=MISO) for cable compatibility.
- [ ] **Step 4: Run to confirm it passes and emits CSV:**
  `uv run wiring/make_pinmap.py` → writes `wiring/pinmap.csv`, prints a summary
  table + `used N / 50 GPIO`.
- [ ] **Step 5: Commit** the script + CSV.

### Task 0.6: Harness wiring diagram (SVG)

**Files:**
- Modify: `wiring/make_pinmap.py` (add `--svg` to render `wiring/harness.svg`)
- Create (generated): `wiring/harness.svg`

- [ ] **Step 1:** Extend the script to render a theme-aware SVG: three columns
  (KGPE-D16 connector pins | harness element: direct / MAX3232 / HDT-adapter |
  ULX3S J1/J2 GPIO), colour-coded by domain (SPI/UART/JTAG/GPIO), with the
  `pinmap.csv` as the single source of truth.
- [ ] **Step 2: Render:** `uv run wiring/make_pinmap.py --svg`.
- [ ] **Step 3: Verify** the SVG opens and every `pinmap.csv` row appears
  (a count check in the script: `#rects == #signals`).
- [ ] **Step 4:** Write `wiring/README.md` explaining the harness, the MAX3232
  requirement for COM1/COM2, and the 1.27 mm HDT adapter.
- [ ] **Step 5: Commit** the SVG + wiring README. **P0 exit:** repo + submodule
  exist; `pinmap.csv` + `harness.svg` validated; boards can now be wired.

---

## Phase P1 — LiteX SoC + wishbone bridge + soft USB hub

> Do P1 work inside the `mobo-bench` repo on branch `claude/p1-soc-skeleton`.

### Task 1.1: Install LiteX; build a baseline ULX3S 45F bitstream

**Files:**
- Create: `mobo_bench/platform.py`, `mobo_bench/soc.py`
- Create: `docs/toolchain.md` (install notes)

- [ ] **Step 1:** Install LiteX into a project venv via the official installer:
  ```sh
  mkdir -p ~/litex && cd ~/litex
  uv run --with requests - <<'PY'
  import urllib.request; urllib.request.urlretrieve(
    "https://raw.githubusercontent.com/enjoy-digital/litex/master/litex_setup.py",
    "litex_setup.py")
  PY
  python3 litex_setup.py --init --install --user   # or --config=full
  ```
  Record exact commands that worked in `docs/toolchain.md`.
- [ ] **Step 2: Sanity-build the stock target** (no custom code yet), ECP5 45F,
  toolchain = trellis (oss-cad-suite):
  ```sh
  export PATH=~/oss-cad-suite/bin:$PATH
  python3 -m litex_boards.targets.radiona_ulx3s --device LFE5U-45F \
      --build --no-compile-software
  ```
  Expected: nextpnr finishes `0 errors`, `build/.../gateware/*.bit` produced.
- [ ] **Step 3:** Capture the nextpnr **resource report** (LUT/BRAM %) into
  `docs/toolchain.md` — this is the baseline for the P7 shrink.
- [ ] **Step 4: Commit** `platform.py`/`soc.py` stubs + `docs/toolchain.md`
  (the stubs re-export the litex-boards target for now).

### Task 1.2 [HW]: Load the baseline on the 45F from the Pi 5

**Files:** `test/load.sh`

- [ ] **Step 1:** On the Pi 5 (or workstation if the ULX3S is local), load SRAM:
  `openFPGALoader -b ulx3s build/.../gateware/radiona_ulx3s.bit`.
  Expected: `Done`, IDCODE `0x41111043` (45F).
- [ ] **Step 2: Verify** the LiteX BIOS banner on the console UART
  (`litex_term /dev/ttyUSB0` on the FTDI port) shows `LiteX SoC on ULX3S`.
- [ ] **Step 3:** Save `test/load.sh` wrapper. Commit.
  *(If hardware not yet available: mark deferred; proceed with 1.3–1.6 on the
  build/sim path and run 1.2/verify steps when the board arrives.)*

### Task 1.3: UARTBone wishbone bridge + Pi-5 RemoteClient

**Files:** Modify `mobo_bench/soc.py`; Create `test/hil_remoteclient.py`

- [ ] **Step 1:** In `soc.py`, subclass the ULX3S `BaseSoC` and add a bridge —
  keep the console on the FTDI UART and add UARTBone on a second link:
  build with `--uart-name=crossover+uartbone` (crossover console + UARTBone),
  and `--csr-csv=csr.csv`.
- [ ] **Step 2: Build:** `python3 -m mobo_bench.soc --device LFE5U-45F --build --csr-csv=csr.csv`. Expected: `csr.csv` generated, bitstream built.
- [ ] **Step 3 [HW]: Verify from the Pi 5:** run `litex_server --uart --uart-port=/dev/ttyUSB0` and:
  ```python
  # test/hil_remoteclient.py
  from litex import RemoteClient
  bus = RemoteClient(csr_csv="csr.csv"); bus.open()
  print(hex(bus.read(bus.mems.csr.base)))   # ident/scratch
  bus.close()
  ```
  Expected: reads the CSR ident string / scratch register (default `0x12345678`).
- [ ] **Step 4: Commit** `soc.py` + `test/hil_remoteclient.py` + `csr.csv`.

### Task 1.4: LED CSR (blinky controllable from the Pi 5)

**Files:** Modify `mobo_bench/soc.py`; Create `test/hil_blinky.py`

- [ ] **Step 1:** Add a `CSRStorage` driving the 8 ULX3S LEDs (a `leds` CSR),
  plus a hardware heartbeat on one LED so a bare board shows life.
- [ ] **Step 2: Build** (as 1.3 Step 2).
- [ ] **Step 3 [HW]: Verify:** `test/hil_blinky.py` uses `RemoteClient` to
  `bus.regs.leds.write(0b10101010)` and the physical LEDs change; heartbeat LED
  keeps blinking. Expected: observable LED change.
- [ ] **Step 4: Commit.**

### Task 1.5: SPIKE — soft USB hub integration (research + minimal enumerate)

**Files:** `docs/usb-hub-spike.md`; Modify `mobo_bench/soc.py`

> The exact ULX3S LiteX soft-hub path (Greg Davill hub emulation vs valentyusb
> `cdc_eptri` vs LiteX 2026.04 LUNA `usb_acm`) is not yet API-pinned — resolve
> by spike before committing to it. Success = the Pi 5 enumerates the FPGA as a
> USB hub (or composite) with at least one working device.

- [ ] **Step 1:** Evaluate the three backends against LiteX HEAD: (a) LiteX
  `--uart-name=usb_acm` (LUNA CDC backend, official), (b) valentyusb
  `cdc_eptri` (Greg Davill branch), (c) a soft **hub** presenting ≥2 devices.
  Record findings + the chosen path in `docs/usb-hub-spike.md`, with the exact
  integration code.
- [ ] **Step 2:** Add the 48 MHz USB PLL + the chosen USB device to `soc.py`;
  build. Expected: nextpnr `0 errors`; note the LUT delta vs the 1.1 baseline.
- [ ] **Step 3 [HW]: Verify enumeration** on the Pi 5: `lsusb -t` shows the
  device (and hub, if the hub path was chosen). Expected: a new USB device
  appears when the bitstream loads.
- [ ] **Step 4: Commit** the spike doc + gateware.

### Task 1.6: Wishbone bridge over USB + one CDC-ACM smoke test

**Files:** Modify `mobo_bench/soc.py`; Create `test/hil_usb.py`

- [ ] **Step 1:** Route the wishbone bridge and one CDC-ACM UART through the
  USB device/hub from Task 1.5 (so control + a serial port are on USB, not just
  the FTDI link). If the hub path is immature, fall back to a single composite
  CDC device and note it.
- [ ] **Step 2: Build.**
- [ ] **Step 3 [HW]: Verify:** (a) `litex_server --uart --uart-port=/dev/ttyACM0`
  + `hil_remoteclient.py` reads CSRs over **USB**; (b) the CDC-ACM tty echoes.
  Expected: RemoteClient works over USB; tty round-trips.
- [ ] **Step 4: Commit.**

### Task 1.7: Document P1 bring-up; tag the skeleton

**Files:** `docs/p1-bringup.md`, `README.md` (quickstart)

- [ ] **Step 1:** Write `docs/p1-bringup.md`: exact build/load/verify commands,
  the resource report, the USB device list, and the RemoteClient examples.
- [ ] **Step 2:** Fill the `README.md` quickstart from the bring-up doc.
- [ ] **Step 3: Commit**; open a PR on `mithro/mobo-bench`; bump the submodule
  pointer in ai-shenanigans (branch + PR). **P1 exit:** a Pi-5-controllable SoC
  skeleton on the 45F — RemoteClient over USB + blinky + one CDC-ACM — that the
  Wave-1 cores (P2–P5) plug into.

---

## Exit criteria (P0 + P1)

- `mithro/mobo-bench` exists, is a submodule here, Apache-2.0.
- `wiring/pinmap.csv` + `harness.svg` validate all §3.1 signals ≤ ULX3S GPIO,
  spispy-compatible where possible → boards can be wired.
- LiteX SoC builds for the 45F (resource report captured).
- From the Pi 5, over USB: `RemoteClient` reads/writes CSRs, blinky works, one
  CDC-ACM tty round-trips. (HW steps run once the wired 45F+Pi5 are provided;
  until then, build/sim + enumeration are the gate.)

## Risks / deferrals
- **USB hub maturity** (Task 1.5) is the main unknown — the spike resolves it;
  fallback is a single composite CDC device (still unblocks P2–P5).
- **Hardware availability** — 45F+Pi5 arrive after P0; HW-marked steps defer
  but don't block gateware progress.
- **LiteX API drift** — pin exact commands during Task 1.1 and record them.
