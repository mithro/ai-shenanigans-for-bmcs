# ftgmac100 eth0 RX=0 on the real AST2050 — root cause + QEMU faithfulness gap

**Goal (user-directed 2026-07-11):** the OpenBMC-over-NFS boot works in QEMU but
fails on the real AST2050 because `eth0` RX is dead. Per the project's
faithfulness principle, the fix order is: (1) find why the bug does **not** happen
in QEMU, (2) make QEMU faithful enough to **reproduce** it, (3) fix the driver,
(4) verify the fix in QEMU, (5) verify it on real hardware. This doc records
steps (1) and the N1 hardware root-cause.

## Real-silicon validation that DID pass (context)

Booting our faithful G3-VIC kernel (`uImage-kgpe-d16-g3vic` + `kgpe-g3vic.dtb`)
over the P2A/U-Boot/TFTP path on the real AST2050 (`asus-bmc` rig) reproduced the
faithful SoC **register-for-register** — evidence in `nic-rx-hardware-rootcause`
sibling logs and the boot console:

| Real-silicon console line | Confirms the QEMU model |
|---|---|
| `ASPEED Unknown rev A0 (00000202)` | `AST2050_A1_SILICON_REV = 0x202` |
| `aspeed-g3-vic: SENSE=0x903897fe EVENT=0x983f97fe DUAL=0x7c00000` | faithful G3 VIC values |
| `clocksource: FTTMR010-TIMER2` + IP-Config completes | the timer fix (task #57) works on silicon |
| `Memory: 44212K/57344K` (+8 MB fb) | real 64 MB DDR |
| `RTL8201CP ... Link is Up - 100Mbps/Full` | the board's real PHY (task #61) |

P2A register reads independently matched: `SCU7C=0x00000202`, `SCU04=0x000ffe5c`.

## N1 — the RX failure is the MAC RX engine, not the driver ring

On the real AST2050 the ftgmac100 **transmits** fine but **receives nothing**:

- Live `/init` on real HW: `IK-ETH0-STATS tx=9 rx=0 txerr=0 txdrop=0 rxerr=0`,
  `ping 192.168.66.1 -> 100% packet loss`, even after `eth0` `promiscuous mode`.
- Read over P2A while Linux runs with `eth0` up:
  - `MAC_MADR=0x0000960e` (MAC programmed), `MACCR=0x0002d51f`
    (`RXDMA_EN|RXMAC_EN` set), `RXR_BADR=0x41b2c000` (Linux's own RX ring).
  - RX ring is **fully valid**: `RXDES3` buffer pointers set
    (`0x41b837a2 / 0x41b83062 / 0x41b82922`), `RBSR=0x600` (RX buffer size set).
- **Decisive test** (`tmp/mac_rx_traffic.py`): flood **800 frames** at the BMC MAC
  (static ARP on the Pi, since the BMC can't answer ARP with RX dead). Result:
  **every RX descriptor stayed `RXDES0=0x00000000`, `RXR_BADR` unchanged, `MACSR`
  unchanged.** The MAC DMA'd **zero** of 800 frames into a valid ring.

**Conclusion:** with a valid RX ring, RX enabled in `MACCR`, link up at 100 Mbps,
and TX working, the MAC's **RX engine pulls no frames off the RMII interface.**
This rules out driver descriptor/coherency bugs (the MAC never touches the ring).
The failure is the **MAC RX / RMII RX-clock path**.

Cross-check: the **U-Boot** `aspeednic` driver RXes fine on the *byte-identical*
SCU (it TFTPs the 3.4 MB kernel — that is RX). And the prior `NIC-MAC-REGISTER-
COMPARISON.md` established SCU04/08/0C/48/70/74/80/88/90 are identical between
working-U-Boot and broken-Linux. So RX-vs-no-RX is **not** an SCU/pinmux
difference — it is what U-Boot's NIC init does to the MAC/PHY RMII RX path that
the mainline Linux driver does **not** (it "assumes firmware/SCU configured RMII";
the `RCLK` ref-clock gate is only wired for AST2500/AST2600, never the G3).

## Step 1 — why the bug does NOT reproduce in QEMU

`hw/net/ftgmac100.c` `ftgmac100_can_receive()` gates RX on **only**:

```c
if ((s->maccr & (RXDMA_EN|RXMAC_EN)) != (RXDMA_EN|RXMAC_EN)) return false;
if (ftgmac100_read_bd(&bd, s->rx_descriptor)) return false;   // free descriptor
return !(bd.des0 & RXPKT_RDY);
```

It models **no RMII reference clock, no PHY mode, no RX clock-domain state**. The
driver always sets `MACCR` `RXDMA_EN|RXMAC_EN` and a valid ring, so QEMU always
delivers RX — the driver's failure to enable the RMII RX path has *zero* effect in
emulation. **That is the faithfulness gap.**

## Plan (N2–N5)

- **N2 (faithful QEMU):** model the RMII RX-clock dependency so RX is delivered
  only after the driver enables it. Reset it to "off" (matching real HW after the
  MAC SW_RST); gate `ftgmac100_can_receive` on it. An unfixed driver then gets
  `rx=0` in QEMU too. Add an fwtest/integration check. Pin the exact silicon
  enable (candidate: RMII RCLK gate / MAC RMII-RX enable) via a U-Boot-`aspeednic`
  vs Linux register diff or a P2A poke-and-observe experiment.
- **N3 (driver fix):** enable the RMII RX path for `aspeed,ast2050-mac` in
  `ftgmac100`; confirm `rx>0` in the now-faithful QEMU.
- **N4:** boot OpenBMC over NFS in QEMU → Redfish (regression-free legacy boots).
- **N5:** build the fixed kernel, TFTP-boot on real HW → `rx>0` → NFS → OpenBMC →
  curl Redfish from the Pi.

Diagnostic tooling: `tmp/mac_rx_probe.py`, `tmp/mac_rx_traffic.py`,
`tmp/rx_desc_probe.py` (P2A reads via the culvert host bridge).

## N2–N3 DONE (QEMU-first): the RMII RX-datapath gate + the driver fix

Worked on branch `claude/ftgmac100-rx-qemu` (QEMU submodule branch
`ast2050-ftgmac100-rx`).

### What the source diff actually shows (Raptor/U-Boot vs mainline)

The MAC *register* programming is **not** the differentiator. Compared line by
line (mainline `drivers/net/ethernet/faraday/ftgmac100.c` and `.h` vs U-Boot
`aspeednic.c` and Raptor `ftgmac100_26.c`/`.h`):

- Both enable RX identically: `MACCR RXMAC_EN|RXDMA_EN` (mainline
  `ftgmac100_start_hw` ftgmac100.c:319-322; U-Boot `START_MAC` aspeednic.c:216-218;
  Raptor `maccr_val` ftgmac100_26.c:2645). Both set FIFO sizes (FEAR/TPAFCR),
  RBSR, APTC RX auto-poll, DBLAC, ITC, RXR_BADR — the datasheet "Frame Receiving
  Procedure" steps 1-14 (AST2050 A3 DS V1.05 p.151-152). Neither writes RXPD.
- **MACCR bit 11**: mainline calls it `PHY_LINK_LEVEL` (ftgmac100.h:161), Raptor
  calls it `CRC_CHK` (ftgmac100_26.h:145); the AST2050 datasheet says MAC50[11]
  is **Reserved(0)** and the real PHY-link control is **bit 6** ("PHY link status
  detection"). It looked like a candidate, but a live QEMU capture shows **both**
  the mainline kernel (`MACCR=0x000a9d1f`) and the Dell vendor firmware
  (`MACCR=0x000a0d0f`/`0x000a8d0f`) set bit 11 — so it is not the differentiator
  and gating on it would break the vendor (C4).
- Neither the SDK/U-Boot drivers nor mainline write any RMII-specific PHY vendor
  register for the board PHY — RMII is strap-selected.

So there is **no single MAC register bit** that mainline sets-and-the-vendor-clears
(or vice-versa) that gates RX. This confirms N1: the failure is the **RMII RX
physical datapath**, not the driver's register config.

### The one measured, driver-visible difference: PHY reset

Instrumenting the QEMU ftgmac100 model (PHY BMCR writes) across real boots:

| firmware (kgpe-d16-bmc QEMU) | MII BMCR reset (reg0 bit15) writes | RX |
|---|---|---|
| mainline 6.6 ftgmac100 (unpatched) | **0** | dead |
| Dell C410X vendor firmware (C4) | **4** (`val=0x8000`) | works |

The vendor firmware **resets+reconfigures the RMII PHY**; the mainline driver
**never resets the PHY** for the G3 (it only warns "Unsupported PHY mode rmii"
at ftgmac100.c:1462-1466 and, per its own comment 1454-1460, "assumes the SCU
has been configured properly by pinmux or the firmware"; its only RMII-refclk
handling, `priv->rclk`, is "AST2500/AST2600 RMII ref clock gate" ftgmac100.c:92-93,
never populated for the G3). Re-establishing the RMII RX clock/datapath by
resetting the PHY is exactly the step mainline omits for the AST2050.

### N2 — faithful QEMU model (submodule `hw/net/ftgmac100.c` + `include/.../ftgmac100.h`, `hw/arm/aspeed_ast2400.c`)

Added a G3-scoped RX gate (new `aspeed-g3` bool property, set by the AST2050 SoC
in `aspeed_ast2400.c` when `silicon_rev == AST2050_A1_SILICON_REV`):

- `FTGMAC100State::rmii_rx_ready` — the RMII RX datapath state (PHY side).
- Closed on **power-on/hard reset only** (`ftgmac100_do_reset`, `!sw_reset`); a
  MACCR SW_RST does **not** close it (a MAC reset does not reset the PHY).
- **Opened** when the guest issues a PHY BMCR reset (`do_phy_write`, MII_BMCR &
  MII_BMCR_RESET).
- Enforced in **both** `ftgmac100_can_receive()` and the `ftgmac100_receive()`
  delivery path (can_receive alone is only a flow-control hint — a queued frame
  can still be delivered — so the drop must also sit on the delivery path).

Scoped to the G3, so AST2400/2500/2600 machines are unchanged.

### N3 — driver fix (`kernel/patches/0002-ftgmac100-ast2050-rmii-rx.patch` + DTS)

- Recognise `aspeed,ast2050-mac` (`is_ast2050`) in `ftgmac100_probe`; for it,
  reset the RMII PHY in `ftgmac100_mii_probe()` (`phy_write(phydev, MII_BMCR,
  BMCR_RESET)`) to (re)establish the RX datapath. phylib reconfigures speed on
  the next `phy_start()`, so this only re-arms the RMII RX side.
- DTS `aspeed-bmc-asus-kgpe-d16.dts`: mac0 compatible now
  `"aspeed,ast2050-mac", "aspeed,ast2400-mac", "faraday,ftgmac100"` and the
  `fixed-link` workaround is removed so the driver runs the real MDIO/PHY probe
  path (where the reset happens). QEMU's ftgmac100 PHY model negotiates 100Mbps
  fine without fixed-link.

### QEMU verification (kgpe-d16-bmc, gated model)

- **Reproduces:** unpatched mainline kernel + no-fixed-link DTS → `can_receive`
  returns false (gate closed, 0 PHY resets), SSH-over-hostfwd never connects →
  `C2 RESULT: FAIL`. Faithful to the real-silicon `rx=0`.
- **Fixed:** patched kernel → console prints `AST2050: resetting RMII PHY to
  enable RX datapath`, the gate opens, SSH login succeeds → `C2 RESULT: PASS`.
- **Regression:** the Dell C410X vendor firmware (C4) resets the PHY on its own,
  so the gate opens and its BMC web service stays reachable.
