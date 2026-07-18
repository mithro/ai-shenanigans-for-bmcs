# D07 — NC-SI on MAC2 (RMII2 → 82574L sideband)

Reopens the old "#9 true NC-SI is not wired" verdict, which was MAC1-scoped and
wrong: schematic §7 shows the AST2050's **MAC2 (0x1e680000, RMII2)** is a
multi-drop NC-SI sideband to the two Intel 82574L host NICs (LU1/LU2), and the
real strap (measured **SCU70=0x00819582**, bits[8:6]=110 = "RMII(MAC#1) and
RMII(MAC#2)") enables it.

## Phase 1 — Linux NC-SI stack validated in QEMU ✅ (`00-qemu-ncsi-discovery-PASS.txt`)

The kgpe-d16-bmc machine now wires **both** MACs (`macs_mask = MAC0 | MAC1`,
faithful to the board). The D07 test boots with two ftgmac100 NICs — MAC0 (eth0)
for SSH, MAC1 (eth1) whose slirp backend answers NC-SI control frames — and the
kernel's `net/ncsi` (CONFIG_NET_NCSI) runs discovery against it:

```
ftgmac100 1e680000.ethernet: Using NCSI interface
ftgmac100 1e680000.ethernet eth1: NCSI: No channel with link found, configuring channel 0
```
→ `eth1` carrier up, `NCSI RESULT: PASS`. This validates the full software
path: `ftgmac100` MAC1 + DTS `use-ncsi` + `CONFIG_NET_NCSI` + `net/ncsi`
discovery/config handshake. **C2 (single-NIC SSH boot) still PASSES** — MAC1 is
disabled in the default DTS, so the oracle boots are unaffected.

## Phase 2 — faithful 82574L responder (TODO)

The slirp responder is a generic single-package NC-SI endpoint; it returns
MFR-ID 0x0 (`NCSI: No GMA handler available for MFR-ID (0x0)`). A faithful model
of the KGPE-D16's sideband needs an **82574L NC-SI responder**: two packages
(LU1/LU2 with distinct package IDs), NC-SI 1.0.0a command matrix (per the 82574
datasheet Table 65/66), and the **Intel OEM commands** (mfr **0x157**) — Get
System MAC Address (0x06) and keep-PHY (0x20). The kernel is already built with
`CONFIG_NCSI_OEM_CMD_GET_MAC`/`KEEP_PHY`. This responder would live in the MAC
model (libslirp is an external subproject) — planned as a new QEMU device.

## Silicon — the NICs are NC-SI-enabled ✅ (`01-silicon-82574L-nvm-ncsi-enabled.txt`); full discovery TODO

The open question is **answered**: `ethtool -e` on both real 82574Ls
(SystemRescue host, 2026-07-18) shows **NVM word 0x0F = 0xa558 → MNGM bits
[14:13] = 01 = NC-SI enabled** on BOTH NICs, with **package IDs 0 and 1**
(word 0x2E = 0x00a0 / 0x10a0) — exactly the two-package multi-drop sideband.
So the BMC's MAC2 NC-SI WILL discover them. MAC2 is strap-enabled
(SCU70=0x00819582) and LU1/LU2 are on +3V3_AUX.

Remaining: boot the BMC with the net/ncsi kernel and mac1 enabled (a realhw
build with the mac1+NET_NCSI DTS/config, then JTAG+netboot) and confirm the
BMC discovers the two real channels. This is now de-risked — the responders
exist and are configured.
