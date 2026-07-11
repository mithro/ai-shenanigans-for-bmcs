# F5 goal 2 — host-side IPMI (KCS/BT over LPC): status + remaining work

**LAN IPMI (goal 1) is complete** (QEMU + real AST2050, see `PROGRESS.md`). This
document is the precise remaining-work map for **host-side IPMI** — a host OS
talking IPMI to the BMC over the AST2050 **LPC** KCS or BT channel — as the task
directs when full host modeling is too deep to finish alongside LAN.

## What "host-side IPMI" needs (3 layers)

```
 x86 host  --LPC I/O ports-->  AST2050 LPC (KCS/BT @0x1E789000)  <--MMIO--  BMC Linux
 (ipmitool -I open)             HICR/IDR/ODR/STR (KCS), BT regs             kcs_bmc_aspeed / bt-bmc
                                                                            -> /dev/ipmi-kcs* | /dev/ipmi-bt
                                                                            -> kcsbridge | btbridged (org.openbmc.HostIpmi)
                                                                            -> ipmid (same D-Bus handlers as netipmid)
```

The **BMC-side command handling is identical to LAN** (both front-ends hand the
IPMI message to `ipmid`'s D-Bus command registry), so once a KCS/BT device node
exists and a bridge binds it, every command proven over LAN also answers to the
host. Only the *transport* differs.

## Current state (this repo)

| Layer | State | Evidence |
|---|---|---|
| QEMU LPC (G3) model | **EXISTS + wired** | `qemu/hw/misc/aspeed_lpc_ast2050.c` — register-accurate G3 layout (HICR0-4, LADR, IDR/ODR/STR KCS, BT 0x48-0x68, HICR5-8 iLPC2AHB) at `0x1E789000`; instantiated + MMIO-mapped + IRQ-connected in the G3 SoC (`qemu/hw/arm/aspeed_ast2400.c`, `lpc-g3` / `TYPE_ASPEED_LPC_AST2050`). |
| DTS KCS/BT node | **MISSING** | Boot DTB has `lpc@1e789000` with only `lpc-ctrl` + `lpc-snoop` children — **no `kcs` / `bt` node** — so the kernel binds no `kcs_bmc_aspeed` / `bt-bmc` driver and creates **no `/dev/ipmi-kcs*` or `/dev/ipmi-bt`**. |
| BMC bridge daemon | present, unbindable | Image ships `btbridged` (`org.openbmc.HostIpmi`) — the F0 build selected **BT** (see `BUILD-NOTES.md` note 1). With no `/dev/ipmi-bt` it cannot start, so it is masked in the F5 `lan`/`realhw` profiles. |
| `ipmid` D-Bus handlers | **working** | Proven over LAN — same handlers serve KCS/BT. |
| Emulated LPC **host peer** | **absent** | The `kgpe-d16-bmc` QEMU machine models only the BMC; there is no emulated x86 host driving the LPC I/O side, so a full host->BMC round-trip cannot be shown in QEMU without adding one. |

## Remaining work — two milestones

### M1 — "KCS/BT channel alive on the BMC side" (shallow; the task's minimum)
1. Add a KCS (or BT) child node to the kernel DTS under `lpc@1e789000` and rebuild
   the DTB. For KCS channel 3 (the system-interface channel, matches
   `channel_config.json` id 15 `ipmi_kcs3`):
   ```dts
   lpc@1e789000 {
       kcs3: kcs@24 {                       /* IDR3/ODR3/STR3 at 0x24/0x34/0x44 */
           compatible = "aspeed,ast2400-kcs-bmc";
           interrupts = <8>;                /* LPC IRQ, per G3 SoC wiring */
           kcs_chan = <3>;
           status = "okay";
       };
   };
   ```
   (For BT instead — to match the shipped `btbridged` — add `ibt@... {
   compatible = "aspeed,ast2400-ibt-bmc"; }`.)
2. Boot; the `kcs_bmc_aspeed`/`bt-bmc` driver creates `/dev/ipmi-kcs3`
   (`/dev/ipmi-bt`); un-mask the bridge (`kcsbridge` / `org.openbmc.HostIpmi`).
3. **Prove alive:** `systemctl is-active` the bridge = `active` + `ls /dev/ipmi-*`
   present + the bridge's journal shows it opened the device and registered on
   D-Bus. That satisfies "prove the KCS channel is alive in QEMU" without a host
   peer. The QEMU G3 LPC model already services the register reads/writes the
   driver issues.

### M2 — full host->BMC round-trip (deep; follow-up)
Needs an **emulated LPC host** driving the KCS/BT from the host I/O-port side, so
`ipmitool -I open`/`-I bt` from a host context completes a real transaction. Two
options: (a) QEMU's built-in IPMI host models (`isa-ipmi-kcs`/`isa-ipmi-bt`)
wired to the BMC LPC — architecturally awkward across the single-SoC machine; or
(b) extend `aspeed_lpc_ast2050.c` with the KCS/BT **OBF/IBF state machine** plus a
back-channel a test can poke as the "host". This is the register state-machine
refinement the model's header already flags as future work.

## Recommendation
LAN IPMI already exposes system-id / power / sensors / SEL / FRU / users on the
real 64 MB board with **no extra hardware**, so it is the practical BMC-management
path. Host-side KCS/BT is worth **M1** (cheap, demonstrates the channel) as a
follow-up; **M2** (full host peer) is only needed to exercise a host firmware
stack against the BMC and can wait until there is a concrete consumer.
