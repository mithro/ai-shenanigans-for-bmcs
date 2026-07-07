# Culvert AST2050 (G3) port — hardware-verified results

Status of the culvert AST2050 port ([`mithro/culvert`](https://github.com/mithro/culvert)
branch `ast2050-support`, vendored at [`culvert/`](culvert)), **verified against
the real ASUS KGPE-D16 AST2050** on **2026-07-08**.

## Test rig / method

- Culvert runs on the KGPE-D16 **x86 host** (PXE-booted SystemRescue), reaching
  the dead-firmware BMC's AHB over the ASPEED **P2A (PCIe→AHB) bridge** — the only
  working in-band transport on this board (iLPC backdoor disabled; devmem needs to
  run on the BMC). Host reached via the `rpi4-asus-aspeed2050-dev` bridge.
- Shared rig: coordinated with the concurrent hardware/BIOS-RE instance via
  `/home/claude/HARDWARE-COORDINATION.md` on the Pi. All work here is read-only
  except culvert's own self-reversing SCU00 unlock/relock (`0x1688a8a8`→`0x…`).
- The captured silicon identity (matches `CULVERT-BMC-ACCESS.md`):
  `SCU04 (0x1e6e2004) = 0x000ffe5c`, **`SCU7C (0x1e6e207c) = 0x00000202`**,
  `SCU14 (0x1e6e2014) = 0x00003fff`.

## ✅ Verified working on the real AST2050

| Capability | Evidence |
|---|---|
| **SoC recognition** | `Found revision 0x202` → `ast_g3` (upstream misdetected G6 → `SCU14=0x3fff` → "unsupported"). Fixed by a G3-vs-G6 discriminator on `SCU04[31:24]` (`0x00`≠AST2600's `0x05`). |
| **Device-tree selection** | `Selected devicetree for SoC 'aspeed,ast2050'` |
| **All SoC drivers bind + init** | `scu, sdmc, clk, strap, sioctl, pciectl, ilpcctl, jtag, vuart` all bound and initialised over P2A |
| **`probe`** | `culvert probe` (no `via`) → **exit 0**, after a bridge-selection fix (upstream auto-picked the dead iLPC bridge and exited −19) |
| **`read --type=ram`** | 64 B read from DRAM `0x40000000` over P2A (`exit 0`) |
| **P2A transport** | raw `p2a vga read` of any AHB address returns real data |

Commits (on `ast2050-support`): `bca3ae5` (rev/soc G3 recognition + `g3.dts`),
`2bdb695` (`host_get_ahb` prefers a bridge that can actually reach the SoC).

## ⚠️ Needs board-specific driver work (found via hardware testing)

| Gap | Detail |
|---|---|
| **Flash dump (`sfc`)** | The AST2050 uses the older **SMC @ `0x16000000`** with the flash mapped at `0x14000000` (`ast2050.h` `PHYS_FLASH_1`). Culvert's `sfc` driver only matches `aspeed,ast2500-fmc`/`-spi` (G5+) — it fails "Failed to acquire SPI controller". The mmap window `0x14000000` reads `0x0` (the SMC isn't decoding the flash — no firmware ran to configure it). **Requires a new AST2050 SMC driver** (configure `AST_SMC_BASE`, read the flash), not just a DT node. |
| **Bridge posture accuracy** | `probe` reports `p2a: Disabled` (while we're using it!) and `ilpc: Permissive` (while it reads `0xffffffff`). The `pciectl`/`ilpcctl` drivers read **AST2400 register offsets** via the g4-compatible bindings; the AST2050 enable/lock registers differ. Posture is cosmetic for read use but wrong for `probe --require`. |
| **`jtag` / `console`** | Not yet tested on hardware. `jtag` needs the JTAG master + `SCU MISC_CTRL[15:14]` routing validated on G3; `console` needs the UART mux. |

Not applicable on G3 (by design): `debug-uart` (AST2500-only), `otp`/`coprocessor`
(AST2600-only). See [`CULVERT-UART-JTAG-DEBUG.md`](CULVERT-UART-JTAG-DEBUG.md) §3.3.

## AST2050 SMC flash — reverse-engineering notes (driver spec)

Hardware RE toward the `sfc` driver (`SMC @ 0x16000000`, datasheet §11), all read
over P2A on 2026-07-08:

- **Boot flash is SPI on CE2.** `SMC00 = 0x00000240` decodes as: segment size
  **32 MB** (`[1:0]=00`), CE0=NOR, CE1=NAND, **CE2=SPI NOR** (`[9:8]=10`).
  `ast2050.h` confirms "Boot SPI: CS2". With 32 MB segments the CE2 window is
  `0x10000000 + 2×32MB = 0x14000000` (= Raptor's `PHYS_FLASH_1`); CE2 is also
  aliased into CPU boot space at `0x00000000`.
- `SMC04/08/0C` (CE0/1/2 control) all read `0` → command mode `[1:0]=00`
  "Normal Read (03h)" with default timing.
- **Direct reads return 0** at both `0x00000000` and `0x14000000`, while P2A
  concurrently reads real data elsewhere (`SCU7C=0x00000202`, `SCU04=0x000ffe5c`,
  `DRAM 0x40000000=0x00101000`). So the flash content is *not* available via a
  passive memory-mapped read in this state (BMC CPU held in reset, SMC not
  actively clocking the SPI in normal-read mode).
- **Implication for the driver:** dumping the flash needs the SMC **command/user
  mode** — manually assert CE2, clock out `03h + 3-byte addr`, read data — via the
  SMC control register, rather than relying on the mapped normal-read window (as
  culvert's AST2500 FMC driver does in user mode, but with the AST2050 SMC
  register interface).

- **User-mode read prototyped over P2A — and it does not yield flash data on this
  rig.** Confirmed P2A can *write* the SMC (`SMC0C 0x1600000c` ← `0x00000003`
  reads back), entered User Mode (`[1:0]=11`, CE# asserted), clocked `03h`+addr,
  and read the CE2 window — all reads returned `0`. The SMC clock is **not** the
  cause: `SCU0C` (Clock Stop Control) has no SMC/flash bit — the SMC runs on HCLK
  (always on). So the block is that the SMC **flash data window (`0x14000000`) is
  not served over P2A** (P2A reaches config registers and DRAM, but not the SMC's
  memory-mapped flash decode / SPI data path), and/or the boot flash is
  **spispy-emulated by the ULX3S** on this bench.
- **Conclusion:** a flash *dump on this rig* is not a culvert-driver gap — it is a
  transport/bench limitation. Use the **spispy / ULX3S SPI path** (reads the flash
  chip directly, bypassing the AST2050 SMC), which instance-A already has wired.
  A culvert SMC `sfc` driver would still be worth adding for boards with a **live**
  BMC (SMC already serving the flash window), but cannot be verified on this
  dead-BMC bench via P2A. `SMC0C` was restored to `0` after the prototype.

## Reproduce

On the PXE host (`root@192.168.77.138`, from the Pi):
```sh
git clone -b ast2050-support https://github.com/mithro/culvert && cd culvert
CC=gcc meson setup build && ninja -C build
./build/src/culvert probe                       # recognises AST2050, exit 0
./build/src/culvert -v probe via p2a vga        # full SoC probe, all drivers bind
./build/src/culvert read --type=ram 0x40000000 64 via p2a vga | xxd
```

## Next (per the plan, [`../docs/plans/2026-07-07-culvert-ast2050-g3-support.md`](../docs/plans/2026-07-07-culvert-ast2050-g3-support.md))

1. **AST2050 SMC flash driver** → real `sfc`/firmware dump (the key open-firmware capability).
2. **G3 `pciectl`/`ilpcctl`** register offsets → correct `probe` posture.
3. Validate **`jtag`** (software bitbang) and **`console`** on hardware.
4. Refine `g3.dts` (DDR2 SDMC decode; dedicated `aspeed,ast2050-*` bindings + driver matches).
