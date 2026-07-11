# ftgmac100 eth0 RX=0 on the real AST2050 — SOLVED (register/bit pinned on silicon)

**Agent:** HARDWARE (`claude/ftgmac100-rx-hw`), 2026-07-11, on the `asus-bmc` rig.
This supersedes the N1 conclusion in `nic-rx-hardware-rootcause.md` ("the MAC
DMAs zero frames / RX engine is dead"). Live silicon shows the opposite: **the
MAC receives every frame, but mis-samples all of them.**

## TL;DR — the exact mechanism

- **Register / bit:** `MACCR` (MAC1 base `0x1e660000`, offset `0x50`) **bit 19
  `FAST_MODE`** (100 Mbps timing select).
- **Fault:** the mainline `ftgmac100` driver leaves `FAST_MODE` **CLEAR** (MAC in
  **10 Mbps** RMII timing) while the RTL8201CP link is **100 Mbps**. The MAC
  over-samples every incoming frame → each is counted **frame-too-long + CRC
  error** → the driver drops 100 % of RX → `rx=0`. TX is unaffected.
- **Fix (one bit):** set `MACCR` bit 19 for a 100 M link. Proven on silicon by a
  live P2A poke (below) and by the driver patch in
  `kernel/patches/0002-ftgmac100-set-mac-speed-from-cur_speed.patch`.
- **Why the driver loses it:** `ftgmac100_start_hw()` only *preserves* the speed
  bits already in `MACCR` (`maccr &= (FAST_MODE|GIGA_MODE)`); the speed is set
  only in `ftgmac100_reset_and_config_mac()`, written **in the same word as
  `SW_RST`**. On the **AST2050 (G3)** the MAC `SW_RST` **clears `MACCR`** (the
  header even notes "reset clears all registers"), so the speed bit does not
  survive the reset, and `start_hw()`'s preserve-only logic can never restore it.
  On AST2400/AST2500 the bit survives `SW_RST`, which is why mainline works there
  and the bug is **G3-specific**.

## Live silicon evidence

### 1. Full MAC register file (broken-Linux, `mac_block_dump.py`)

The board booted our faithful G3-VIC kernel over P2A/U-Boot/TFTP with an initrd
whose `/init` brings `eth0` up (promiscuous). Read over P2A while running:

```
MACCR (0x50)        = 0x0002d51f   <- FAST_MODE (bit19) CLEAR, GIGA (bit9) clear => 10M timing
                                      (RXMAC_EN|RXDMA_EN|TXMAC_EN|TXDMA_EN|FULLDUP|CRC_APD|
                                       RX_RUNT|RX_ALL|HT_MULTI|RX_BROADPKT|RM_VLAN all set)
RXR_BADR (0x24)     = 0x41b2c000   RX ring base (valid)
RXR_PTR  (0x98)     = 0x41b2c2e0   HW RX pointer HAS ADVANCED (~46 descriptors) => MAC is DMAing
RBSR (0x4c)         = 0x00000600   RX buffer size ok
APTC (0x34)         = 0x00000001   RX autopoll on
DBLAC(0x38)=0x22f72 TPAFCR(0x48)=0xf1 FEAR(0x44)=0 ITC(0x30)=0x1010  (all init'd; not the fault)
RX_pkts   (0xb0)    = 0x000000ae = 174   <- MAC RX engine RECEIVED 174 frames
RX_CRCER_FTL (0xc4) = 0x00ae009a         <- ~all 174 counted CRC-error / frame-too-long
TX_pkts   (0xa0)    = 0x11                (TX fine)
```

So the RX engine is **not** dead: `RX_pkts` climbs, `RXR_PTR` advances, but almost
every frame is an error → the driver drops them → `rx=0`. (The earlier
"RXDES0 all zero" snapshot was a measurement artifact: the driver recycles each
errored descriptor's OWN bit straight back to the MAC, so a static read of the
ring base usually catches freshly-cleared descriptors.)

### 2. Decisive poke-and-observe (`poke_fastmode.py`)

Flood 600 frames at the BMC MAC, read the MAC's own RX counters before/after,
then set `MACCR |= FAST_MODE` **live via P2A (no reset)** and flood again:

| flood | MACCR bit19 | RX_pkts Δ | CRC-err Δ | frame-too-long Δ | Pi→BMC ping |
|-------|-------------|-----------|-----------|------------------|-------------|
| #1    | 0 (10M)     | +123      | +110      | +123             | **100 % loss** |
| #2    | 1 (100M)    | +602      | **+0**    | **+0**           | **600/600, 0 % loss** |

Setting bit 19 alone — **no SW_RST, no ring change** — turned every frame from a
CRC/FTL error into a clean receive, and **the BMC became pingable** (`3/3`,
0.69 ms). This is conclusive: the RMII datapath honours `MACCR` bit 19 live, and
its clear state is the entire bug.

### 3. End-to-end proof with the patched kernel (`real-silicon-rxfix-boot.log`)

Built `uImage-kgpe-d16-rxfix` (v6.6.70 + the driver patch below), TFTP-booted it
on the real AST2050 with the **same** `kgpe-g3vic.dtb` that gave `rx=0` — so the
**driver patch is the only variable**:

```
ftgmac100 1e660000.ethernet eth0: Link is Up - 100Mbps/Full - flow control rx/tx
3 packets transmitted, 3 packets received, 0% packet loss   (BMC -> Pi)
IK-ETH0-STATS tx=10 rx=4 txerr=0 txdrop=0 rxerr=0            (rx>0, was rx=0)
IK-DROPBEAR-UP listening :22
```

From the Pi afterwards: `ping 192.168.66.2` = **3/3, 0 % loss**; P2A read
**`MACCR=0x000ad51f`** (bit 19 `FAST_MODE` **set by the driver itself**, vs the
`0x0002d51f` broken baseline) and **`RX_CRCER_FTL=0x00000000`** (no RX errors).
The patched driver sets the speed correctly with no manual poke.

## The driver fix (minimal, faithful, G3-correct)

`ftgmac100_start_hw()` — derive the speed bits from `priv->cur_speed` instead of
only preserving `MACCR`'s current value, so the speed is re-applied on every
(re)start regardless of whether the preceding `SW_RST` cleared it:

```c
-	u32 maccr = ioread32(priv->base + FTGMAC100_OFFSET_MACCR);
-
-	/* Keep the original GMAC and FAST bits */
-	maccr &= (FTGMAC100_MACCR_FAST_MODE | FTGMAC100_MACCR_GIGA_MODE);
+	u32 maccr = 0;
+
+	/* Set the speed mode from the current link speed. Do not merely
+	 * preserve MACCR's current speed bits: on the AST2050 (G3) the MAC
+	 * SW_RST in ftgmac100_reset_and_config_mac() clears MACCR (speed bit
+	 * included), unlike AST2400/2500 where it survives, so preserve-only
+	 * leaves the MAC in 10M timing on a 100M link -> every RX frame is
+	 * frame-too-long/CRC-error -> rx=0. HW-verified on the real AST2050.
+	 */
+	switch (priv->cur_speed) {
+	case SPEED_100:
+		maccr |= FTGMAC100_MACCR_FAST_MODE;
+		break;
+	case SPEED_1000:
+		maccr |= FTGMAC100_MACCR_GIGA_MODE;
+		break;
+	default:
+		break;   /* 10M or no link: both clear */
+	}
```

This is identical to what `ftgmac100_reset_and_config_mac()` already computes from
`cur_speed`; it just guarantees the value reaches `MACCR` *after* the reset. It
does not change AST2400/2500 behaviour (there `cur_speed` drives the same bits).

## Faithfulness note for the QEMU model

The QEMU `hw/net/ftgmac100.c` gates RX only on `MACCR` RXDMA/RXMAC + a free
descriptor; it models **no link-speed / RMII timing**, so an unfixed driver still
receives in emulation. To reproduce this bug faithfully the model must (a) treat
`MACCR` `SW_RST` on the G3 as clearing `MACCR` (so the speed bit is lost across
reset, matching silicon), and (b) drop / error frames delivered while the MAC
speed (`FAST_MODE`/`GIGA_MODE`) disagrees with the link speed. Either is enough
to make the unfixed driver show `rx=0` in QEMU; the driver patch then restores it.
