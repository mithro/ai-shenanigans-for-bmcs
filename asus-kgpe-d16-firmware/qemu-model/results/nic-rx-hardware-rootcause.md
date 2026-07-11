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
