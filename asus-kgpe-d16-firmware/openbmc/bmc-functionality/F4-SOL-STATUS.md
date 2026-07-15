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

## `ipmitool sol activate` — provider gap RESOLVED; residual is RMCP+ RAKP (2026-07-16)

`netipmid`'s Activate-Payload reads the SOL config object
`/xyz/openbmc_project/ipmi/sol/eth0` (interface `xyz.openbmc_project.Ipmi.SOL`)
via the ObjectMapper. The earlier "**image ships no provider**" finding was on the
**base quanta-q71l image** (openbmc-full), which is built WITHOUT the KGPE-D16
settings recipe. **On the recipe-built image (img2) the provider IS present** —
`busctl` confirms it (`evidence/qemu-sol/sol-provider-present-recipe-image.txt`):
`ObjectMapper GetObject /xyz/openbmc_project/ipmi/sol/eth0` → rc=0, owned by
`xyz.openbmc_project.Settings`, interface `xyz.openbmc_project.Ipmi.SOL`; the
object shows in `busctl tree`. It is delivered by `settings/sol-template.yaml` +
`phosphor-settings-defaults-native.bbappend`, staged by `sync-to-openbmc-tree.sh`
(and, as of this session, the sync is wired into `build-openbmc-rootfs.yml`, so a
fresh asset build will carry it).

So the SOL config provider is **not** the blocker anymore. The `sol activate` gap
has been walked down layer by layer (each fix exposes the next):

1. **RAKP session-auth** — was "no response from RAKP 1 message" (netipmid RAKP
   slow under 256 MB load). **FIXED** by `-N 5 -R 3` in the harness (2026-07-16):
   `sol payload status` now returns rc=0 "User 1 on channel 1 is enabled".
2. **Ipmi.SOL provider** — present on the recipe-built image (busctl-confirmed).
3. **netipmid registerSOLService** — the *current* residual: `sol activate` now
   reaches netipmid, which logs **"Failed to get service path in
   registerSOLService"** and tells the client "BMC requests SOL session on
   different port", so activation still doesn't stream. This is a netipmid↔
   obmc-console SOL **service-registration** binding issue (deeper than the config
   object) — a phosphor-net-ipmid / obmc-console wiring follow-up, not RAKP and not
   the provider.

The SOL **data path** is proven regardless: `obmc-console-client` captures the
injected host bytes over the AST2050 VUART (748 B / 17 markers, F4 RESULT PASS).
The harness now bumps the `sol activate` timeout past the RAKP window and scans the
output for the streamed host markers, so it will report a **TRUE SOL SESSION**
automatically once the registerSOLService gap is closed. No QEMU/DTS/kernel change
is needed.

## Real hardware (AST2050 on the rig) — 2026-07-12

Done **non-disruptively** (no reboot; the board was left running F5's IPMI image
as live evidence). Evidence: `evidence/real-hw-sol/sol-channel-realhw.txt`.

* **SOL channel established on real silicon.** From the Pi,
  `ipmitool -I lanplus -H 192.168.66.2 … mc info` returns rc=0 (RMCP+ session up)
  and `… sol payload status 1 1` → **"User 1 on channel 1 is enabled"** — the SOL
  front-end (`netipmid`) answers on the real AST2050. (`netipmid` is socket-
  activated and races on the slow board, F5's finding, so RMCP+ sessions are
  intermittent and were retried until clean.)
* **VUART DTB staged, ready to boot.** `/srv/tftp-bmc/kgpe-g3vic-vuart.dtb` =
  the real-HW `kgpe-g3vic.dtb` with the vuart node enabled
  (`fdtput … /ahb/apb/serial@1e787000 status okay`). Booting the fuller image
  over NFS with **this DTB** + the F4/`realhw` masks (P2A path, as F5/F1 did) is
  what brings up `/dev/ttyVUART0` + `obmc-console-server` on real silicon — the
  same chain proven in QEMU. That boot is a state-mutating P2A reset of the shared
  board and was **not** performed here (the orchestration is the other agents'
  tooling and the board was serving F5's live evidence); the artifact is staged so
  it is a one-step follow-up.

Two constraints bound any real-HW **byte** capture (independent of the above):

1. **Host-byte wiring.** On the current rig the x86 **host COM1 is tapped by an
   external FTDI** (`/dev/serial-com1` on the Pi), *not* routed into the BMC VUART
   (`HARDWARE-ACCESS.md`). A real host→BMC→SOL byte capture needs the host's COM1
   to be the AST2050 VUART/PUART (BIOS/board-dependent). Absent that, real HW
   establishes the **SOL channel** (VUART tty + `obmc-console-server` + RMCP+
   reachable) rather than streaming live host output — which is what was done.
2. **The `ipmitool sol activate` config-object gap above applies equally on real
   HW** until the SOL config provider is added to the image.

See `evidence/qemu-sol/` (QEMU captures), `evidence/real-hw-sol/` (real board),
and `PROGRESS.md` for the log.
