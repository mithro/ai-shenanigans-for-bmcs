# AST2050 / AST1100 (A3) — 10/100 Ethernet MAC (Faraday FTGMAC100)

Datasheet extraction for a QEMU **faithful** emulation of the AST2050 (G3) MAC as
used by the ASUS KGPE-D16 BMC: **MAC1 @ 0x1E66_0000** in **RMII** mode driving an
external **Realtek RTL8201CP** 10/100 PHY. Netboot-critical (TFTP + NFS).

All page numbers below are **physical PDF pages** of
`datasheets/aspeed/AST2050_AST1100_A3_Datasheet_V1.05.pdf` (they coincide with the
printed page numbers here). The MAC is **Chapter 14, "10/100 Ethernet MAC
Controller"**, physical/printed pages **124-158**. The datasheet title block reads
"AST1100 Software Programming Guide" (`pdfinfo`), dated 2010-05-25.

> **Superset caveat (p.124, verbatim):** *"This is a superset of registers
> definition. For AST2050/AST1100 chip, only 10M/100M interface is supported."*
> The register map documents GMII / 1000 Mbps / `GMAC_MODE` fields, but on the
> AST2050 **gigabit is not implemented**. See §5 for what a faithful G3 model must
> NOT expose.

Overview (p.124): two identical MAC modules, independently enable-able, each with
its own register base. Digital interface can be RMII, MII, or GMII; due to pin
count only one GMII may be active. IEEE802.3 compliant, AHB bus master+slave,
linked-list DMA with direct M-Bus access, IEEE 802.1Q VLAN insert/delete, high-
priority TX queue, independent TX/RX FIFO, half/full duplex, flow control (p.125).

- Base address Ethernet **MAC #1 = 0x1E66_0000** (p.124; matches `hwreg.h`
  `AST_MAC1_BASE 0x1E660000`, line 27).
- Base address Ethernet **MAC #2 = 0x1E68_0000** (p.124; `hwreg.h` `AST_MAC2_BASE`).
- Address-space table (p. earlier, "1E66:0000-1E67:FFFF … Fast Ethernet MAC
  Controller #1 (MAC1)" / "1E68:0000-1E69:FFFF … MAC2") — 128 KiB decode each.
- Physical address = base + offset.

---

## 1. FTGMAC100 register map

Full register list (p.124). Offset = byte offset from the MAC base. Reset values
("Init") are taken from each register's header line on the cited page; where the
header shows `Init = 0` the reset is all-zero.

| Off | Name | Meaning | R/W | Reset (Init) | Page |
|-----|------|---------|-----|--------------|------|
| 0x00 | ISR | Interrupt Status Register | RW (W1C) | 0 | 125 |
| 0x04 | IER / IME | Interrupt Enable Register | RW | 0 | 126 |
| 0x08 | MAC_MADR | MAC Most-Significant Addr (upper 2 bytes) | RW | 0 | 126 |
| 0x0C | MAC_LADR | MAC Least-Significant Addr (lower 4 bytes) | RW | 0 | 126 |
| 0x10 | MAHT0 | Multicast Hash Table 0 (hash 31:0) | RW | 0 | 126 |
| 0x14 | MAHT1 | Multicast Hash Table 1 (hash 63:32) | RW | 0 | 127 |
| 0x18 | NPTXPD | Normal-Priority TX Poll Demand | W | 0 | 127 |
| 0x1C | RXPD | Receive Poll Demand | W | 0 | 127 |
| 0x20 | **NPTXR_BADR** | Normal-Priority TX Ring Base Addr | RW | 0 | 127 |
| 0x24 | **RXR_BADR** | Receive Ring Base Addr | RW | 0 | 127 |
| 0x28 | HPTXPD | High-Priority TX Poll Demand | W | 0 | 128 |
| 0x2C | HPTXR_BADR | High-Priority TX Ring Base Addr | W | 0 | 128 |
| 0x30 | **ITC** | Interrupt Timer Control | RW | 0 (rec. 0x0000_1010) | 128-130 |
| 0x34 | **APTC** | Automatic Polling Timer Control | RW | 0 (rec. 0x0000_0001) | 131-132 |
| 0x38 | **DBLAC** | DMA Burst Length & Arbitration Ctrl | RW | 0x0002_2F00 (rec. 0x0002_2F72) | 132-134 |
| 0x3C | DMAFIFOS | DMA/FIFO State (debug, R) | R | 0x0C00_0000 | 134-135 |
| 0x44 | FEAR | Feature Register (FIFO real size, R) | R | 0 | 135 |
| 0x48 | TPAFCR | TX Priority Arb. & FIFO Control | RW | 0x0000_00F1 | 135-137 |
| 0x4C | **RBSR** | Receive Buffer Size Register | RW | 0x0000_0640 | 137 |
| 0x50 | **MACCR** | MAC Control Register | RW | 0 | 137-138 |
| 0x54 | MACSR | MAC Status Register | RW (W1C) | 0 | 138-139 |
| 0x58 | TM | Test Mode Register | RW | 0 | 139 |
| 0x60 | **PHYCR** | PHY Control (MDIO) | RW | 0x0000_0034 | 139-140 |
| 0x64 | **PHYDATA** | PHY Data (MDIO) | RW | 0 | 140 |
| 0x68 | **FCR** | Flow Control Register | RW | 0x0000_0400 | 140-141 |
| 0x6C | BPR | Back Pressure Register | RW | 0x0000_0200 | 141 |
| 0x70 | PWRTC | Power Control Register | RW | 0 | 141 |
| 0x90 | NPTXR_PTR | Normal-Prio TX Ring Ptr (debug, R) | R | — | 142 |
| 0x94 | HPTXR_PTR | High-Prio TX Ring Ptr (debug, R) | R | — | 142 |
| 0x98 | RXR_PTR | RX Ring Ptr (debug, R) | R | — | 142 |
| 0xA0-0xC8 | *_CNT | Statistics counters (TPKT/RPKT/collisions/RUNT/…) | R | — | 142-144 |

**Every register offset seen in the culvert capture is confirmed by the
datasheet:** MADR 0x08, LADR 0x0C, NPTXR_BADR 0x20, RXR_BADR 0x24, ITC 0x30,
APTC 0x34, DBLAC 0x38, RBSR 0x4C, MACCR 0x50, PHYCR 0x60, FCR 0x68 — all match
p.124-141. ✔

### 1.1 ISR (0x00) / IER (0x04) — p.125-126

Both share the same bit numbering; ISR bits are **write-1-to-clear**, IER holds the
per-bit enables (`ISR[n]` ↔ `IER[n]`).

| Bit | ISR name (p.125) | Meaning |
|-----|------------------|---------|
| 10 | HPTXBUF_UNAVA | High-priority TX buffer unavailable |
| 9 | PHYSTS_CHG | PHY link status change |
| 8 | AHB_ERR | AHB bus error |
| 7 | TPKT_LOST | TX packet lost (late/excessive collision or under-run) |
| 6 | NPTXBUF_UNAVA | Normal-priority TX buffer unavailable |
| 5 | TPKT2F | TXDMA moved data into TX FIFO |
| 4 | TPKT2E | Packet transmitted to Ethernet OK |
| 3 | RPKT_LOST | RX packet lost (RX FIFO full) |
| 2 | RXBUF_UNAVA | Receiving buffer unavailable |
| 1 | RPKT2F | Packet received into RX FIFO OK |
| 0 | RPKT2B | RXDMA delivered packet to RX buffer OK |

Bits 31:11 Reserved(0). IER (0x04) fields are `<name>_EN`, "Interrupt enable of
ISR[n]" (p.126).

### 1.2 MAC address — MADR 0x08 / LADR 0x0C (p.126)

- `MADR[15:0]` = most-significant **2 bytes** of the MAC address (bits 31:16 Rsvd).
- `LADR[31:0]` = least-significant **4 bytes** of the MAC address.
- Full 6-byte MAC = `{MADR[15:0], LADR[31:0]}`.

### 1.3 Descriptor-ring base registers — NPTXR_BADR 0x20 / RXR_BADR 0x24 (p.127)

- `NPTXR_BADR[27:4]` = normal-priority TX ring base **[27:4]**, **16-byte aligned**;
  bits 31:28 Rsvd, bits 3:0 Rsvd.
- `RXR_BADR[27:4]` = RX ring base **[27:4]**, **16-byte aligned**; bits 31:28 and
  3:0 Rsvd.
- `HPTXR_BADR[27:4]` (0x2C, p.128) = high-priority TX ring base, 16-byte aligned.

> ⚠ **Faithful-model note (culvert fallback).** The datasheet documents these base
> fields as **[27:4]** (28-bit, max 0x0FFF_FFF0). The culvert capture shows
> `RXR_BADR = 0x41B1_0000`, which has **bit 30 set** (DRAM base 0x4000_0000). Linux
> therefore programs bits **above [27]**. AST DRAM lives at 0x4000_0000+, so a
> faithful FTGMAC100 model must store the full high address (mainline QEMU
> `hw/net/ftgmac100.c` keeps ~`[31:4]`), **not** mask to the datasheet's 28 bits, or
> DMA will target the wrong physical address. Values still 16-byte aligned (low 4
> bits = 0), consistent with the datasheet alignment rule.

### 1.4 Poll-demand registers — NPTXPD 0x18 / RXPD 0x1C (p.127) / HPTXPD 0x28 (p.128)

Write-any-value (read-as-0). Writing NPTXPD makes the engine read the TX
descriptor and check `TXDMA_OWN (TXDES#0[31])`; if OWN=1 it moves the buffer into
the TX FIFO. Writing RXPD makes the engine read the RX descriptor and check
`RXPKT_RDY (RXDES#0[31])`; if RDY=0 it moves the RX-FIFO packet to memory.

### 1.5 ITC (0x30) — Interrupt Timer Control (p.128-130)

Interrupt mitigation/coalescing. Recommended value **0x0000_1010** (p.130).

| Bit | Field | Meaning (p.128-129) |
|-----|-------|---------------------|
| 31:16 | Reserved(0) | |
| 15 | TXINT_TIME_SEL | TX cycle-time period select (set→81.92 µs @100M, clear→5.12 µs) |
| 14:12 | TXINT_THR | Max pending TX interrupts before one is generated |
| 11:8 | TXINT_CNT | Max wait (TX cycle times) to raise a TX int; 0 = disabled |
| 7 | RXINT_TIME_SEL | RX cycle-time period select (set→81.92 µs @100M, clear→5.12 µs) |
| 6:4 | RXINT_THR | Max pending RX interrupts before one is generated |
| 3:0 | RXINT_CNT | Max wait (RX cycle times) to raise an RX int; 0 = disabled |

(`0x1010` ⇒ RXINT_THR=1, TXINT_THR=1, both timers off — batch 1 int per packet.)

### 1.6 APTC (0x34) — Automatic Polling Timer Control (p.131-132)

Recommended value **0x0000_0001** (p.132). Bit 12 `TXPOLL_TIME_SEL`, bits 11:8
`TXPOLL_CNT` (0 ⇒ no auto TX poll → software must write NPTXPD), bit 4
`RXPOLL_TIME_SEL`, bits 3:0 `RXPOLL_CNT` (0 ⇒ no auto RX poll → software must write
RXPD). Poll times @100M: set = 81.92 µs, clear = 5.12 µs.

### 1.7 DBLAC (0x38) — DMA Burst Length & Arbitration (p.132-134)

Init = **0x0002_2F00**; recommended **0x0002_2F72** (p.134).

| Bit | Field | Meaning |
|-----|-------|---------|
| 23 | IFG_INC | IFG increase (1) / decrease (0) |
| 22:20 | IFG_CNT | Inter-frame-gap count (unit = 1 TX clock) |
| 19:16 | TXDES_SIZE | TX descriptor size, **unit 8 bytes**; 0 illegal (2 ⇒ 16 B) |
| 15:12 | RXDES_SIZE | RX descriptor size, unit 8 bytes; 0 illegal (2 ⇒ 16 B) |
| 11:10 | TXBST_SIZE | TXDMA max burst: 00=64,01=128,10=256,11=512 B |
| 9:8 | RXBST_SIZE | RXDMA max burst: 00=64,01=128,10=256,11=512 B |
| 6 | RX_THR_EN | Enable RX FIFO threshold arbitration |
| 5:3 | RXFIFO_HTHR | RX FIFO high threshold (n/8 of FIFO) |
| 2:0 | RXFIFO_LTHR | RX FIFO low threshold (n/8 of FIFO); must be < HTHR |

Descriptor sizes are 8-byte units ⇒ the 16-byte (4-word) descriptor is `SIZE=2`.

### 1.8 RBSR (0x4C) — Receive Buffer Size (p.137)

Init = **0x0000_0640**. `RXBUF_SIZE[13:3]` = RX buffer size, **unit 1 byte,
8-byte aligned** (bits 2:0 and 31:14 Rsvd). The culvert capture's `RBSR = 0x600`
⇒ 1536-byte RX buffers (matches Linux's `RX_BUF_SIZE` for a 1522-byte max frame).

### 1.9 MACCR (0x50) — MAC Control Register (p.137-138) **[central register]**

Init = 0. **Full authoritative bit layout:**

| Bit | Field | Meaning (p.137-138) |
|-----|-------|---------------------|
| 31 | SW_RST | Software reset; auto-clears after **175 AHB clocks** |
| 30:20 | Reserved(0) | |
| 19 | **SPEED_100** | 1 = 100 Mbps, 0 = 10 Mbps (with GMAC_MODE=0). Not SW-resettable |
| 18 | DISCARD_CRCERR | Discard TX packet flagged CRC error |
| 17 | **RX_BROADPKT_EN** | Receive broadcast packets ("BROAD" filter) |
| 16 | **RX_MULTIPKT_EN** | Receive all multicast packets ("MULTI" filter) |
| 15 | **RX_HT_EN** | Store multicast passing hash-table filter ("HT") |
| 14 | **RX_ALLADDR** | Do not check destination address = promiscuous ("ALL") |
| 13 | JUMBO_LF | Jumbo long frame: set→9216(9220 VLAN); clear→1518(1522 VLAN) |
| 12 | **RX_RUNT** | Receive runt packets (< 64 B, but ≥ 10 B) |
| 11 | Reserved(0) | |
| 10 | **CRC_APD** | Append CRC to transmitted packets |
| 9 | **GMAC_MODE** | 1 = 1000 Mbps mode; else 10/100. **N/A on AST2050.** Not SW-resettable |
| 8 | **FULLDUP** | 1 = full duplex, 0 = half duplex |
| 7 | ENRX_IN_HALFTX | Enable RX while transmitting in half-duplex |
| 6 | **PHY_LINK_LEVEL** (PHY link status detection) | 1 = rising/falling-edge trigger, 0 = high-level sensitive |
| 5 | HPTXR_EN | Enable high-priority TX ring |
| 4 | REMOVE_VLAN | Strip VLAN tag from received VLAN-tagged packets |
| 3 | **RXMAC_EN** | Enable RXMAC (receive) |
| 2 | **TXMAC_EN** | Enable TXMAC (transmit) |
| 1 | **RXDMA_EN** | Enable RX DMA channel (0 ⇒ reception stops immediately) |
| 0 | **TXDMA_EN** | Enable TX DMA channel (0 ⇒ transmission stops immediately) |

Speed encoding (`{GMAC_MODE, SPEED_100}`, p.137): `01`=100M, `00`=10M, `1x`=1000M.
Ethernet address-filter mapping (p.149): ALL=bit14, MULTI=bit16, BROAD=bit17,
HT=bit15 — cross-checks the bit names above.

### 1.10 MACSR (0x54) — MAC Status Register (p.138-139)

Write-1-to-clear status. Bits: 11 COL_EXCEED (>16 collisions), 10 LATE_COL, 9
TPKT_LOST, 8 TPKT_OK, 7 RUNT, 6 FTL (frame too long), 5 CRC_ERR, 4 RPKT_LOST, 3
RPKT_SAVE, 2 COL, 1 BROADCAST, 0 MULTICAST.

### 1.11 PHYCR (0x60) / PHYDATA (0x64) — MDIO (p.139-140)  → see §3

### 1.12 FCR (0x68) — Flow Control (p.140-141)

Init = **0x0000_0400**. 31:16 PAUSE_TIME, 15:9 FC_HIGH/FC_LOW (RX-FIFO free-space
thresholds, unit 256 B, defaults 7'h5 / 7'h2), 8 FC_HTHR_SEL, 4 RX_PAUSE (W1C), 3
TXPAUSED (R), 2 FCTHR_EN, 1 TX_PAUSE (self-clearing), 0 FC_EN (flow-control enable).
BPR (0x6C, p.141) Init 0x0000_0200 governs half-duplex back-pressure jam.

---

## 2. TX / RX descriptor formats (p.144-149)

MAC engine uses **descriptor rings in system memory**. Each descriptor = **4 words
(16 bytes)**, **16-byte aligned** start address (p.144, p.146). des0=control/status
+ownership, des1=VLAN/interrupt control, des2=reserved, des3=buffer base address.
Max TX/RX packet = 9216 B (9220 with VLAN), but on the D16 with JUMBO_LF=0 the long-
frame limit is 1518/1522 B.

### 2.1 Transmit descriptor (p.144-146)

**TXDES#0 (0x00) — control + ownership (p.144):**
- **31 TXDMA_OWN** — ownership: **1 = owned by MAC engine**, 0 = owned by software.
  MAC clears it when it finishes the frame.
- **30 EDOTR** — **End Descriptor Of Transmit Ring** (wrap marker).
- 29 FTS — First TX Segment (first descriptor of a TX packet).
- 28 LTS — Last TX Segment (last descriptor of a TX packet).
- 19 CRC_ERR — with DISCARD_CRCERR (MACCR[18]=1) the packet is dropped.
- **13:0 TXBUF_SIZE** — transmit buffer size in bytes (non-zero).

**TXDES#1 (0x04) — VLAN + interrupt (p.145):** 31 TXIC (TX interrupt on
completion, valid when FTS=1 & ITC[14:8]=0), 30 TX2FIC (int when moved to FIFO),
22 LLC_PKT, 19 IPCS_EN, 18 UDPCS_EN, 17 TCPCS_EN, 16 INS_VLAN (insert 0x8100 +
tag), 15:0 VLAN_TAGC (priority[15:13]/CFI[12]/VID[11:0]).
**TXDES#2 (0x08)** = Reserved (p.145).
**TXDES#3 (0x0C)** — **TXBUF_BADR[27:1]**, buffer base ≥ 2-byte aligned (bit0 must
be 0); bits 31:28 Rsvd (p.146).

### 2.2 Receive descriptor (p.146-149)

**RXDES#0 (0x00) — frame status + ownership (p.146):**
- **31 RXPKT_RDY** — ownership: **0 = owned by MAC engine**, **1 = owned by
  software** (MAC sets it when reception completes / buffer full). *(Inverse sense
  of TXDMA_OWN.)*
- **30 EDORR** — **End Descriptor Of Receive Ring** (wrap marker).
- 29 FRS — First RX Segment; 28 LRS — Last RX Segment (status bits 25:0 valid only
  when FRS=1).
- 25 PAUSE_FRAME, 24 PAUSE_OPCODE, 23 FIFO_FULL, 22 RX_ODD_NB (odd nibbles), 21
  RUNT, 20 FTL, 19 CRC_ERR, 18 RX_ERR, 17 BROADCAST, 16 MULTICAST.
- **13:0 VDBC** — valid data byte count (unit 1 byte).

**RXDES#1 (0x04)** — RX VLAN/checksum status (p.147-148): 27 IPCS_FAIL, 26
UDPCS_FAIL, 25 TCPCS_FAIL, 24 VLAN_AVA, 23 DF, 22 LLC_PKT, 21:20 PROTL_TYPE
(00=non-IP,01=IP,10=TCP/IP,11=UDP/IP), 15:0 VLAN_TAGC.
**RXDES#2 (0x08)** = Reserved (p.148).
**RXDES#3 (0x0C)** — **RXBUF_BADR[27:1]**, buffer base ≥ 2-byte aligned (bit0 = 0);
bits 31:28 Rsvd (p.148-149).

---

## 3. MDIO / PHY access via PHYCR (0x60) & PHYDATA (0x64) — p.139-140

The AST2050 FTGMAC100 accesses PHY (MDIO/MDC) registers **only** through PHYCR +
PHYDATA — the "old" FTGMAC100 method. There is **no separate MDIO controller** on
the G3 (contrast AST2600, §5).

**PHYCR (0x60)** Init = **0x0000_0034** (p.139-140):

| Bit | Field | Meaning |
|-----|-------|---------|
| 27 | **MIIWR** | Write 1 → start a **write** sequence to PHY; auto-clears when done |
| 26 | **MIIRD** | Write 1 → start a **read** sequence from PHY; auto-clears when done |
| 25:21 | **REGAD** | PHY **register** address (5 bits) |
| 20:16 | **PHYAD** | PHY **(MDIO) address** (5 bits) |
| 5:0 | **MDC_CYCTHR** | MDC cycle threshold; MDC period = MDC_CYCTHR × RX-clock period |

MDC_CYCTHR: "When first reading/writing a PHY register, or on PHY link-status
change, software must set these bits to **6'h34**." Allowed 100 Mbps range 0x0B-0x3F
(10 Mbps 0x02-0x3F) — reset value 0x34 is the safe default (p.140).

**PHYDATA (0x64)** Init = 0 (p.140): `[31:16] MIIRDATA` = read data from PHY (R),
`[15:0] MIIWDATA` = write data to PHY (RW).

**Read a PHY register:** program PHYCR with `PHYAD`+`REGAD`+`MDC_CYCTHR`, set
**MIIRD=1**, poll PHYCR until MIIRD self-clears, then read `PHYDATA[31:16]`.
**Write a PHY register:** put value in `PHYDATA[15:0]` (MIIWDATA), program PHYCR
`PHYAD`+`REGAD`+`MDC_CYCTHR`, set **MIIWR=1**, poll until it self-clears.

**PHY discovery:** the driver auto-scans MDIO addresses 0-31, reading the PHY-ID
registers (MII reg 2/3) through PHYCR/PHYDATA; the responding address is the PHY.
The **RTL8201CP** is a 10/100 RMII PHY whose MDIO address is set by its PHYAD
strap pins — the ftgmac100 auto-scan finds it (no fixed address in the MAC).

> **RTL8201CP MII identity (ground truth, task #61).** MII reg 2 (PHYID1) = `0x0000`,
> MII reg 3 (PHYID2) = `0x8201` — combined **`0x0000_8201`**. Source: Realtek
> *RTL8201CP* datasheet (PHYID1 default `0000` @ reg 2, PHYID2 default `8201` @ reg 3),
> corroborated by mainline Linux `drivers/net/phy/realtek.c`
> (`PHY_ID_MATCH_EXACT(0x00008201)`, name "RTL8201CP Ethernet") and by the in-tree
> QEMU `include/hw/net/mii.h` (`RTL8201CP_PHYID1/2`). Reset-default basic registers:
> **BMCR (reg 0) = `0x3100`** (autoneg + 100M + full-duplex), **BMSR (reg 1) =
> `0x786D`-class** (100/10 FD+HD, MFPS, AN-able/complete, link, ext-cap; **no**
> extended-status/gigabit bit 8, since a 10/100 part has no reg-15). ANAR (reg 4)
> advertises 10/100 half+full only. The QEMU `kgpe-d16-bmc` MAC presents exactly this
> on the `aspeed-g3` path (`hw/net/ftgmac100.c`); the RTL8211E gigabit id
> (`0x001C_C915`) is retained only for the AST2400+/Dell-C410X path.

> A carrier/link model is required for the vendor driver: the prior C410X work
> (`qemu-firmware/AST2050-PERIPHERAL-MODELING.md` §6) had to implement the PHY-
> Specific Status register (reg 17) so the driver would see link. For the D16's
> RTL8201CP model the relevant link/status regs are the basic MII set (reg 0 BMCR,
> reg 1 BMSR, reg 2/3 ID) plus RTL8201CP-specific status.

---

## 4. Reconcile MACCR = 0x0002_D51F (culvert Linux "RX-broken" capture)

Bit decode against the §1.9 datasheet layout (p.137-138):

```
0x0002_D51F = 0000 0000 0000 0010  1101 0101 0001 1111
                 bit17│      bit15,14,12│  bit10│ bit8│ bit4,3,2,1,0
```

| Bit | Field | Set? | |
|-----|-------|------|-|
| 0 | TXDMA_EN | 1 | TX DMA enabled |
| 1 | RXDMA_EN | 1 | RX DMA enabled |
| 2 | TXMAC_EN | 1 | TX MAC enabled |
| 3 | RXMAC_EN | 1 | RX MAC enabled |
| 4 | REMOVE_VLAN | 1 | strip received VLAN tags |
| 8 | FULLDUP | 1 | full duplex |
| 10 | CRC_APD | 1 | append CRC on TX |
| 12 | RX_RUNT | 1 | accept runt frames |
| 14 | RX_ALLADDR | 1 | **promiscuous** (no dest-addr check) |
| 15 | RX_HT_EN | 1 | accept hash-table multicast |
| 17 | RX_BROADPKT_EN | 1 | accept broadcast |
| **9** | **GMAC_MODE** | **0** | 10/100 mode (correct — no gigabit) |
| **19** | **SPEED_100** | **0** | **10 Mbps mode selected** |
| 6 | PHY_LINK_LEVEL | 0 | high-level sensitive |
| 5 | HPTXR_EN | 0 | high-priority ring off |

**Every set bit maps cleanly to a documented MACCR field — the capture confirms
the datasheet MACCR layout.** ✔ The RX path is *fully opened* (promiscuous +
broadcast + multicast + runt), so the "RX-broken" symptom is **not** a filter
problem. The notable anomaly is **SPEED_100 = 0 (10 Mbps)** while the D16 link is
RMII 100M — a MAC-speed/PHY-speed mismatch is a plausible contributor to the broken
RX state and something a faithful model should let software observe (do not force
SPEED_100). Both `GMAC_MODE=0` and `SPEED_100=0` are consistent with a 10/100-only
part.

---

## 5. AST2050 (G3) vs AST2400 / 2500 / 2600 — what a faithful model must NOT expose

The datasheet register map is a **superset**; the AST2050 implements only the
10/100 subset (p.124). Differences a faithful **G3** FTGMAC100 model must respect:

1. **No gigabit / no RGMII / no GMII operation.** p.124 restricts AST2050/AST1100
   to "only 10M/100M interface". `GMAC_MODE` (MACCR[9]) and `SPEED_100` (MACCR[19])
   exist in the register but **1000 Mbps must not function**; the 1000 Mbps rows in
   ITC/APTC (p.128-132) are superset artifacts. The AST2400+ ftgmac100 adds a
   working `RGMII_ENABLE`/1000M path — **absent on G3**. Do not advertise RGMII.
2. **MAC interface strap is MII/RMII-only, no NCSI mode.** SCU70[8:6] (p.218, see
   §6) enumerates *only* `011`=MII(MAC#1), `100`=RMII(MAC#1), `110`=RMII(#1)+RMII(#2),
   `111`=Disable — **there is no NC-SI hardware mode**. The G3 MAC has **no NC-SI
   controller / NC-SI register block**; NC-SI on this SoC would be pure software over
   an RMII link (the vendor's `ncsi_protocol.ko`), not a MAC feature. A faithful G3
   model must not expose an NC-SI mode bit.
3. **No RMII RCLK / RGMII clock-delay control.** The RMII 50 MHz reference is the
   `RMIIRCLK` **input** pin (p.41-42); RMII timing is fixed (p.68, RMII TX/RX cycle
   = 20 ns typ). There is **no programmable RCLK/RGMII delay register** (the
   AST2400+/2500 SCU delay controls, and AST2600's per-MAC delay registers, do not
   exist here).
4. **MDIO is via PHYCR/PHYDATA (0x60/0x64) only.** The AST2600 introduced a
   **separate MDIO controller** (distinct register block); the G3 (like AST2400/2500
   ftgmac100) uses the in-MAC PHYCR/PHYDATA method exclusively (§3). No "new MDIO"
   registers at 0x40/0x44.
5. **IPv4-only checksum offload**, half & full duplex (p.144, p.146). Fine to model
   or stub; not gigabit-dependent.
6. **Register bases unchanged** across G3→G4: MAC1 0x1E66_0000 / MAC2 0x1E68_0000
   (p.124) are identical on AST2400 — so the register *offsets/bases* are shared;
   the *capabilities* (speed, RGMII, NCSI, MDIO block) are what differ.

**Summary for the QEMU model:** expose a 10/100 RMII/MII FTGMAC100 with the
PHYCR/PHYDATA MDIO path and the register map above; **do not** expose gigabit/RGMII,
an RCLK/RGMII delay register, a separate MDIO controller, or any NC-SI hardware
mode. Store descriptor-ring bases as full ≥[31:4] addresses (§1.3) so DRAM at
0x4000_0000+ is reachable.

---

## 6. RMII vs MII configuration — SCU70 MAC-interface strap (p.217-218)

RMII/MII selection is a **hardware strap in SCU70** ("Hardware Trapping Register",
base SCU 0x1E6E_2000, offset 0x70 → **0x1E6E_2070**), **bits [8:6] MAC interface
mode selection** (p.218):

| SCU70[8:6] | Mode |
|------------|------|
| 000/001/010/101 | Reserved |
| 011 | Select **MII (MAC#1) only** |
| **100** | **Select RMII (MAC#1) only** ← **the KGPE-D16 config** |
| 110 | Select RMII (MAC#1) and RMII (MAC#2) |
| 111 | Disable MAC |

The same strap is documented earlier as the boot-time `ROMA[8:6]` "MAC interface
mode selection" (p.44): `011`=MII(1), `100`=RMII(1), `110`=RMII(1)+RMII(2). So the
**D16 MAC1 = RMII** corresponds to `SCU70[8:6] = 100b` (ROMA[8]=1, ROMA[7:6]=00).

**There is no separate MACCR "RMII/MII" bit** — the interface mode is selected
solely by this SCU strap; MACCR only sets speed/duplex/enables. RMII signals
(p.41-42): `RMIITXD[1:0]`, `RMIITXEN`, `RMIIRCLK` (50 MHz reference **input**),
`RMIIRXD[1:0]`, `RMIICRSDV`, `RMIIRXER`. RMII timing (p.68): TX/RX cycle 20 ns typ,
TX setup 10 ns, hold 2.5 ns.

> **Faithful-model implication.** The vendor kernel's MAC bring-up reads the MAC
> interface mode; the C410X RE (`AST2050-PERIPHERAL-MODELING.md` §8-12) found the
> vendor `aess_ftgmac100` driver's `ndo_open` gates on a MAC-mode config word that
> stays 0 under QEMU, causing `-EACCES`. For the D16, modelling **SCU70[8:6]=100
> (RMII)** in the machine's `hw_strap`/SCU so the driver reads the real RMII mode is
> the corresponding faithful fix (rather than patching the driver).

---

## 7. Cross-reference validation summary

- **`hwreg.h`** (line 27-28): MAC1 0x1E660000 / MAC2 0x1E680000 — ✔ matches p.124.
- **Culvert capture register offsets** (0x08,0x0C,0x20,0x24,0x30,0x34,0x38,0x4C,
  0x50,0x60,0x68): every one confirmed by the datasheet register map — ✔ §1.
- **Culvert MACCR 0x0002_D51F**: all set bits decode to documented MACCR fields —
  ✔ §4 (notable: SPEED_100=0 ⇒ 10 Mbps; GMAC_MODE=0 ⇒ 10/100).
- **Culvert RBSR 0x600**: `RXBUF_SIZE[13:3]` ⇒ 1536-byte RX buffers — ✔ p.137.
- **Culvert RXR_BADR 0x41B1_0000**: 16-byte aligned but needs bits >[27]; datasheet
  documents only [27:4] → *faithful model must keep full [31:4]* — flagged §1.3.
- **RMII strap**: SCU70[8:6]=100b (RMII MAC#1) — ✔ p.218 / ROMA[8:6] p.44.

*Source: `AST2050_AST1100_A3_Datasheet_V1.05.pdf`, Chapter 14 (pp.124-158),
§4.7.2 MII/RMII Interface (p.68), SCU70 (pp.217-218), boot strap ROMA (p.44).*
