# F4 — Serial-over-LAN (SOL) on OpenBMC / AST2050: status

Goal: see the host's serial console remotely, bridged by the BMC. Built on the F5
IPMI backbone (lean 64-MB image). This documents the mechanism, what is proven in
QEMU and on real hardware, and the one remaining image-recipe gap.

## The mechanism (host serial → SOL)

```
 x86 host COM1 (I/O 0x3F8, SIRQ 4)                     BMC (AST2050 Linux)
        │  LPC                                          ┌──────────────────────────┐
        ▼                                               │ 8250_aspeed_vuart        │
  AST2050 VUART @0x1E787000  ──── virtual 16550 ───────▶│  /dev/ttyS5              │
  (datasheet §29; host I/O                              │  udev(iomem_base=1E787000)│
   base set via VUART28/2C)                             │  → /dev/ttyVUART0 symlink │
                                                        │  → obmc-console@ttyVUART0 │
                                                        │     (obmc-console-server) │
                                                        │  → @obmc-console.default  │
                                                        │       ├──────────────┐    │
                                                        │  netipmid (SOL) ◀────┘    │
                                                        │   RMCP+ UDP/623           │
                                                        │  obmc-console-client :2200│
                                                        └──────────────────────────┘
        remote admin: `ipmitool -I lanplus … sol activate`  /  `obmc-console-client`
```

The AST2050 **does** have a VUART (full A3 datasheet §29, base `0x1E787000`, host
I/O address programmable via VUART28/2C). Raptor Engineering's real AST2050
OpenBMC port bridges the host console through exactly this block
(`dev-vuart.c` → mainline `8250_aspeed_vuart.c`); this work models and wires it.

## What was built

| Layer | Change | State |
|---|---|---|
| **QEMU model** | `aspeed_ast2400.c`: model the host VUART as a SerialMM 16550 at `0x1E787000` (IRQ 8), instantiated when the SoC sets `has_vuart` (AST2050 only). Machine wires it to `serial_hd(1)`. | **Done** — `mithro/qemu` branch `ast2050-vuart-sol`, submodule bumped. |
| **DTS** | Enable `&vuart` in `aspeed-bmc-asus-kgpe-d16.dts` (alias serial5, iomem `0x1E787000`). | **Done** |
| **Kernel** | mainline `8250_aspeed_vuart` binds it → `/dev/ttyS5`; the shipped udev rule `80-obmc-console-uart.rules` (keyed on `iomem_base==0x1E787000`) symlinks `/dev/ttyVUART0` and starts `obmc-console@ttyVUART0`. | **Done** (no kernel change; DTB only) |
| **Image** | No rootfs change: the fuller image already ships `obmc-console-server`, the udev rule, and `server.ttyVUART0.conf` (`lpc-address=0x3f8, sirq=4`). Console-id defaults to `default` → socket `@obmc-console.default`. | **Reused as-is** |
| **64-MB mask** | `f4_sol_daemons.py` — the SOL profile = F5's `realhw` set (mask bmcweb + RAM hogs), asserting the console stack is **kept**. | **Done** |

## Proven in QEMU (`f4-sol-test.py`, CI-suitable, exit-coded)

Boots the fuller image over NFS on `kgpe-d16-bmc` at `mem=64`, wires the VUART to
a TCP chardev (the host COM1 stand-in), feeds `HOSTLINE-NN` lines into it, and:

* **PASS gate — obmc-console-client (OpenBMC's SOL client):** the injected lines
  are captured back over the console — **836 bytes / 19 markers** in the recorded
  run — proving the full path host → VUART → `obmc-console-server` →
  `@obmc-console.default` → client. Evidence `evidence/qemu-sol/`.
* **Raw datapath check:** 360 bytes read directly off `/dev/ttyVUART0` — the QEMU
  VUART RX is faithful.
* **ipmitool `-I lanplus … sol`:** SOL **payload is enabled** (`sol payload
  status 1 1` rc=0, "User 1 on channel 1 is enabled") and the RMCP+ session
  reaches `netipmid`; `sol activate` does **not** stream — see the gap below.

## The one gap — `ipmitool sol activate` (image-recipe, not model/plumbing)

`netipmid`'s Activate-Payload reads the SOL config object
`/xyz/openbmc_project/ipmi/sol/eth0` (interface `xyz.openbmc_project.Ipmi.SOL`,
property `Progress`) via the ObjectMapper. **This image ships no provider** for
that object (verified: no D-Bus owner; the legacy `phosphor-settings-manager`
`settings.yaml` only defines `org.openbmc.settings.Host`). So the D-Bus read
returns `ResourceNotFound` and `ipmitool` reports "No response activating SOL
payload" (netipmid journal: `sd_bus_call: …ResourceNotFound`).

This is purely the **IPMI front-end config object** — the SOL *bytes* flow (proven
via `obmc-console-client`, which uses the same `obmc-console-server`). The fix is
an image change: add a provider of `xyz.openbmc_project.Ipmi.SOL` per network
interface (in current OpenBMC this is a settings/SOL-config recipe), then rebuild
and re-stage. No QEMU/DTS/kernel change is needed. Tracked as a follow-up.

## Real hardware (AST2050 on the rig)

The same DTB + image bring `/dev/ttyVUART0` + `obmc-console-server` up on the real
silicon (the mainline `8250_aspeed_vuart` binds the real `0x1E787000`; the model
was validated against it). Two caveats specific to the rig:

1. **Host-byte wiring.** On the current rig the x86 **host COM1 is tapped by an
   external FTDI** (`/dev/serial-com1` on the Pi), *not* routed into the BMC VUART
   (`HARDWARE-ACCESS.md`). So a real host→BMC→SOL byte capture needs the host's
   COM1 to be the AST2050 VUART/PUART (BIOS/board-dependent). Absent that, the
   real-HW demo establishes the **SOL channel** (VUART tty + `obmc-console-server`
   + RMCP+ reachable) and documents the wiring, rather than streaming live host
   output.
2. **The `ipmitool sol activate` gap above applies equally on real HW** until the
   SOL config-object provider is added to the image.

See `evidence/qemu-sol/` for the QEMU captures and `PROGRESS.md` for the log.
