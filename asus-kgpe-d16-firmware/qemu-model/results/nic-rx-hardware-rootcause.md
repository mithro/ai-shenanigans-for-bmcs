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

- **Pin the exact silicon RX-enable (prereq for a faithful N2).** Ruled OUT so far:
  - *SoC RMII RCLK output* — `clk-aspeed.c:517` puts the "RMII1 50 MHz (RCLK)
    output enable" at **SCU48 bit 29**; the prior dump shows **SCU48=0x0 in BOTH**
    working-U-Boot and broken-Linux. So the SoC does not drive the refclk (bit29=0)
    yet U-Boot RXes — the RCLK-not-enabled theory is **wrong for this board** (the
    refclk is external/PHY-sourced). *(Checked the real bit instead of assuming.)*
  - *SCU/pinmux/clock* — byte-identical U-Boot vs Linux (`NIC-MAC-REGISTER-COMPARISON.md`).
  - *Driver RX ring / coherency* — ring is valid, MAC never touches it.

  Remaining suspects: (a) a **MAC-internal RMII-RX state cleared by the driver's
  `ftgmac100_reset_mac` `SW_RST`** and not restored (the "Unsupported PHY mode rmii"
  path does no RMII re-init); (b) the **RTL8201CP PHY config** (RMII mode / RXC) that
  U-Boot's `aspeednic` sets over MDIO and Linux's phylib doesn't. Next experiments:
  diff the RTL8201CP MDIO registers U-Boot-working vs Linux-broken (via MAC
  PHYCR/PHYDATA over P2A); and a `SW_RST`-skip driver build to test suspect (a).
- **N2 (faithful QEMU):** once the real enable is pinned, gate
  `ftgmac100_can_receive` on it (reset "off" to match real HW post-`SW_RST`); an
  unfixed driver then gets `rx=0` in QEMU too. Add an fwtest/integration check.
- **N3 (driver fix):** enable the RMII RX path for `aspeed,ast2050-mac` in
  `ftgmac100`; confirm `rx>0` in the now-faithful QEMU.
- **N4:** boot OpenBMC over NFS in QEMU → Redfish (regression-free legacy boots).
- **N5:** build the fixed kernel, TFTP-boot on real HW → `rx>0` → NFS → OpenBMC →
  curl Redfish from the Pi.

Diagnostic tooling: `tmp/mac_rx_probe.py`, `tmp/mac_rx_traffic.py`,
`tmp/rx_desc_probe.py` (P2A reads via the culvert host bridge).

## N2–N3 DONE (QEMU-first) — the real cause is MACCR FAST_MODE (HW-verified)

Worked on branch `claude/ftgmac100-rx-qemu` (QEMU submodule branch
`ast2050-ftgmac100-rx`). The hardware agent (branch `claude/ftgmac100-rx-hw`)
proved the mechanism on the real AST2050 by poke-and-observe with the driver
unchanged: writing **`MACCR |= 0x80000` (bit19 FAST_MODE)** live, with no reset
and no PHY/RMII change, gave **600/600 frames received, 0 errors, BMC pingable**.
So FAST_MODE alone is necessary and sufficient; it is **not** an RMII-datapath
problem (the RX_pkts counter climbs and RXR_PTR advances — the MAC is not
RX-dead, it CRC-/frame-length-errors every over-sampled frame).

### Mechanism (why G3-specific)

- The AST2050 (G3) link is 100 Mbps RMII, so the MAC must run 100M timing —
  `MACCR[19] FAST_MODE` set (`MACCR[9] GIGA_MODE` clear). In 10M timing on a
  100M link every frame is over-sampled → CRC / frame-too-long → dropped → rx=0.
- On the G3 a **MAC SW_RST clears MACCR** (the speed bit included), unlike the
  AST2400/2500 where it survives. The datasheet even notes SPEED_100/GMAC_MODE
  "cannot be software reset" on later parts — the G3 does not honour that.
- Mainline `ftgmac100_start_hw()` only **preserves** the speed bits
  (`maccr &= (FAST_MODE | GIGA_MODE)`, ftgmac100.c:316). Speed is set only in
  `ftgmac100_reset_and_config_mac()` in the same register write as the SW_RST
  (ftgmac100.c:141-168), so on the G3 it is lost across the reset and
  preserve-only can never restore it. Result: `FAST_MODE=0` → rx=0. (This matches
  the N1 real-silicon capture `MACCR=0x0002d51f`, bit19=0, vs working U-Boot
  `0x0008050f`, bit19=1.)

### N2 — faithful QEMU model (submodule `hw/net/ftgmac100.c`, `.h`, `hw/arm/aspeed_ast2400.c`)

Scoped to the G3 via a new `aspeed-g3` bool property (set by the AST2050 SoC in
`aspeed_ast2400.c` when `silicon_rev == AST2050_A1_SILICON_REV`):

- `ftgmac100_do_reset()`: on the G3 a MAC SW_RST **fully clears MACCR** (speed
  bit lost), instead of the AST2400/2500 behaviour of preserving FAST/GIGA.
- `ftgmac100_can_receive()` **and** `ftgmac100_receive()`: on the G3, drop RX
  unless the MAC speed mode matches the 100M RMII link (FAST_MODE set, GIGA
  clear). can_receive() alone is only a flow-control hint, so the drop must also
  sit on the delivery path.

AST2400/2500/2600 are untouched (their SW_RST preserves the speed bit).

### N3 — driver fix (`kernel/patches/0002-ftgmac100-set-mac-speed-from-cur_speed-g3.patch`)

The HW-proven fix, shared verbatim with the hardware branch:
`ftgmac100_start_hw()` **re-derives** FAST_MODE/GIGA_MODE from `priv->cur_speed`
instead of preserving them, so the speed bit is restored after the G3 SW_RST.
The DTS uses the real RTL8201CP PHY (`phy-mode="rmii"`, no `fixed-link`); the fix
does not depend on the DTS (FAST_MODE alone), verified below with the real-PHY DTB.

### QEMU verification (kgpe-d16-bmc, real-PHY DTB)

- **Reproduces:** unpatched mainline kernel → the G3 SW_RST clears the speed bit,
  preserve-only `start_hw()` leaves `FAST_MODE=0`, the speed-mismatch drop fires
  → SSH-over-hostfwd never connects → rx=0 (faithful to real silicon).
- **Fixed:** cur_speed-patched kernel → `FAST_MODE=1` matches the 100M link → SSH
  login succeeds → `C2 RESULT: PASS`.
- **Regression:** the Dell C410X vendor firmware (C4) writes MACCR with FAST_MODE
  set (`0x000a0d0f`/`0x000a8d0f`), so the speed gate passes and its BMC web
  service stays reachable; OpenBMC-over-NFS (same cur_speed kernel) answers
  Redfish.

Convergence: the QEMU model reproduces the FAST_MODE bug and the *same*
`cur_speed` fix works in QEMU and on the real AST2050.
