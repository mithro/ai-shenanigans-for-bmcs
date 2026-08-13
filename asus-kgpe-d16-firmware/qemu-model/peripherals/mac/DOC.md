# MAC (ftgmac100) — AST2050 driver + faithfulness doc

**Base 0x1E660000 (MAC1) / 0x1E680000 (MAC2).** Faraday FTGMAC100, 10/100 only on
the G3. The KGPE-D16 BMC uses **MAC1 in RMII mode** (SCU70[8:6]=`100`) with an
external **Realtek RTL8201CP** 10/100 PHY. Netboot-critical (TFTP + NFS root). Full
register/descriptor detail: **[`DATASHEET-MAC.md`](DATASHEET-MAC.md)**.

## 1. Key registers

| Off | Register | Notes |
|---|---|---|
| 0x00 | ISR / 0x04 IER | interrupts (VIC source 2) |
| 0x08/0x0C | MAC address (MADR/LADR) | |
| 0x20 | NPTXR_BADR | TX ring base (full [31:4]) |
| 0x24 | RXR_BADR | RX ring base (full [31:4]) |
| 0x50 | **MACCR** | enables + mode (below) |
| 0x60/0x64 | PHYCR / PHYDATA | MDIO access |

**MACCR (0x50)** — `[0]`TXDMA_EN `[1]`RXDMA_EN `[2]`TXMAC_EN `[3]`RXMAC_EN
`[4]`REMOVE_VLAN `[8]`FULLDUP `[9]`GMAC_MODE `[10]`CRC_APD `[12]`RX_RUNT
`[14]`RX_ALLADDR `[15]`RX_HT_EN `[16]`RX_MULTIPKT `[17]`RX_BROADPKT `[19]`SPEED_100
`[31]`SW_RST. The culvert Linux capture `0x0002D51F` = all TX/RX DMA+MAC enabled,
full-duplex, CRC append, RX wide open — but **SPEED_100=0 (10 Mbps)**, i.e. the real
"RX-broken" state was a speed/PHY mismatch, not filtering.

## 2. Driver notes

- **RMII mode** is a hardware strap (SCU70[8:6]), not a MACCR bit.
- **MDIO** via PHYCR (0x60): set `MDC_CYCTHR[5:0]=0x34`, `PHYAD[20:16]`, `REGAD[25:21]`,
  `MIIRD bit26` (or `MIIWR bit27`); poll the bit to auto-clear; read PHYDATA[31:16].
  The driver auto-scans MDIO addresses 0–31 to find the RTL8201CP.
- **Descriptors**: 16-byte, des0 = OWN(bit31) + EDORR/EDOTR(bit30), des3 = buffer base.

## 3. QEMU faithfulness

`peripherals/mac/fwtest.c` vs the current model:
- ✓ **MACCR is RW** and holds the real captured `0x0002D51F`.
- ✓ **Ring base regs store the full [31:4] address** (`RXR_BADR=0x41B10000` reads back
  exactly — the datasheet-vs-DRAM [27:4] discrepancy is not present in QEMU).
- ✓ **MDIO works** (PHYCR/PHYDATA read a PHY).
- ✓ **PHY model is now RTL8201CP for the D16** (task #61). On the `aspeed-g3` MAC the
  MDIO returns PHY id **PHYID1=`0x0000` / PHYID2=`0x8201`** (`0x0000_8201` = Realtek
  **RTL8201CP**, a 10/100 transceiver — RTL8201CP datasheet MII reg 2/3; mainline
  `drivers/net/phy/realtek.c` `PHY_ID_MATCH_EXACT(0x00008201)`), its BMSR clears the
  extended-status/gigabit bit (0x786D-class, no reg-15), BMCR resets to `0x3100`
  (autoneg + 100M + full-duplex), and the 1000BASE-T control/status registers read 0.
  The AST2400+/Dell-C410X (C4) path keeps the RTL8211E gigabit identity
  (`0x001C_C915`) — the change is gated on `silicon_rev == AST2050` so C4 is
  unaffected (the reg-17 PHY-Specific-Status carrier is left intact).
  `hw/net/ftgmac100.c::do_phy_read()`/`phy_reset()`.
- The G3 ftgmac100 must **not** expose gigabit/RGMII, NC-SI hardware mode, or an
  RCLK/RGMII delay register (all AST2400+). Presenting the 10/100 RTL8201CP (no
  gigabit BMSR/CTRL1000 bits) is the PHY-visible half of that G3 faithfulness.

**Full TX/RX (DMA over descriptor rings)** is exercised by the boot tests — eth0 comes
up 100M/full in the C2 boot, so the datapath is functional; only the PHY *identity* is
unfaithful for the D16.

## 4. Faithful-model plan (oracle-gated) — DONE (task #61)

- ☑ **Present the RTL8201CP** (10/100) as the D16's PHY. Implemented in
  `hw/net/ftgmac100.c` gated on the `aspeed-g3` device flag (set by the SoC when
  `silicon_rev == AST2050`): PHY id 0x0000/0x8201, BMSR without EXTSTAT, BMCR reset
  0x3100, gigabit CTRL1000/STAT1000 = 0. The **C410X (C4)** path keeps RTL8211E — the
  investigation found C4's vendor ftgmac driver depends on the **reg-17 PHY-Specific
  Status carrier**, not the PHY *identity*, so that register is left untouched and C4
  stays green with no extra RE patches (per-board PHY, fewer patches — the ideal).
- ☑ Confirmed no gigabit/RGMII/NCSI/RCLK surfaces on the G3 MAC (§5; the RTL8201CP is
  the PHY-visible edge). `test_mac.py::test_phy_bmsr_no_gigabit` guards the BMSR.

## 5. Deliverable status

| # | Deliverable | State |
|---|---|---|
| 1 | firmware test (`fwtest.c`) | ☑ MACCR RW, ring-base [31:4], MDIO/PHY-id |
| 2 | doc (this + `DATASHEET-MAC.md`) | ☑ |
| 3 | QEMU model | ☑ register + DMA faithful; **PHY = RTL8201CP (10/100) on the G3** (§4) |
| 4 | integration test (`../../integration/test_mac.py`) | ☑ register checks; **PHY-id asserts RTL8201CP + no-gigabit BMSR (xfail→pass)** |
