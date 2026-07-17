# SU1 pin map  (528 pins)  C.S SP5100 (A15) FCBGA528//AMD 218-0660026


## SPI / ROM flash (5)

**Connected components** (chips / connectors these pins reach):

- `FU1` (8 pins, 5 nets)

| Ball | Pin name (function) | Net | Connects to |
|---|---|---|---|
| D1 | `SPI_CLK/GPIO47` | `SB_SPI_CLK_SR` | FU1[6] |
| D2 | `SPI_DO/GPIO11` | `SB_SPI_MOSI` | FU1[5] |
| F3 | `SPI_CS1_L/GPIO32` | `SB_SPI_CS#` | FU1[1] |
| F4 | `SPI_HOLD_L/GPIO31` | `SB_SPI_HOLD#` | FU1[7] |
| G6 | `SPI_DI/GPIO12` | `SB_SPI_MISO` | FU1[2] |

## LPC host bus (11)

**Connected components** (chips / connectors these pins reach):

- `OU1` (128 pins, 9 nets) — C.S W83667HG-A-FAC QFP-128//NUVOTON (0.18UM) REV-FAC
- `QU1` (355 pins, 7 nets) — C.S AST2050A3-GP TFBGA355//ASPEED
- `TPM1` (19 pins, 7 nets)
- `LU1` (65 pins, 1 net) — C.S WG82574L A1 QFN64//INTEL 898553/SLBA9
- `LU2` (65 pins, 1 net) — C.S WG82574L A1 QFN64//INTEL 898553/SLBA9
- `PCI6` (122 pins, 1 net)
- `PCIE1` (166 pins, 1 net)
- `PCIE2` (166 pins, 1 net)
- `PCIE3` (100 pins, 1 net)
- `PCIE4` (166 pins, 1 net)
- `PCIE5` (166 pins, 1 net)
- `PIKE1` (100 pins, 1 net)

| Ball | Pin name (function) | Net | Connects to |
|---|---|---|---|
| E22 | `LPCCLK1` | `LPC_CLK1_C` | TPM1[1] |
| G22 | `LPCCLK0` | `LPC_CLK0_C` | QU1[A16] |
| H22 | `LDRQ0#` | `LPC_DRQ0#` | OU1[18] |
| H23 | `LAD1` | `LPC_LAD1` | OU1[22], QU1[A17], TPM1[10] |
| H24 | `LAD0` | `LPC_LAD0` | OU1[23], QU1[B17], TPM1[11] |
| H25 | `LFRAME#` | `LPC_FRAME#` | OU1[25], QU1[B16], TPM1[3] |
| J24 | `LAD3` | `LPC_LAD3` | OU1[20], QU1[C16], TPM1[7] |
| J25 | `LAD2` | `LPC_LAD2` | OU1[21], QU1[D16], TPM1[8] |
| K4 | `LPC_PME_L/GEVENT3_L` | `SIO_LPC_PME#` | LU1[16], LU2[16], OU1[65], PCI6[A19], PCIE1[B11], PCIE2[B11], PCIE3[B11], PCIE4[B11], PCIE5[B11], PIKE1[B11], ZR19[1], ZR20[1], ZR21[1] |
| K24 | `LPC_SMI_L/EXTEVNT1_L` | `SIO_LPC_SMI#` | OU1[128] |
| V15 | `SERIRQ` | `LPC_SERIRQ` | OU1[19], QU1[C15], TPM1[16] |

## PCI (33MHz) (60)

**Connected components** (chips / connectors these pins reach):

- `PCI6` (122 pins, 52 nets)
- `QU1` (355 pins, 45 nets) — C.S AST2050A3-GP TFBGA355//ASPEED
- `ZU1` (100 pins, 45 nets) — C.S L-FW322-07-T100-DB TQFP100//LSI 1394A/711008303
- `OU1` (128 pins, 2 nets) — C.S W83667HG-A-FAC QFP-128//NUVOTON (0.18UM) REV-FAC
- `LU1` (65 pins, 1 net) — C.S WG82574L A1 QFN64//INTEL 898553/SLBA9
- `LU2` (65 pins, 1 net) — C.S WG82574L A1 QFN64//INTEL 898553/SLBA9
- `PCIE1` (166 pins, 1 net)
- `PCIE2` (166 pins, 1 net)
- `PCIE3` (100 pins, 1 net)
- `PCIE4` (166 pins, 1 net)
- `PCIE5` (166 pins, 1 net)
- `PIKE1` (100 pins, 1 net)
- `QU4` (64 pins, 1 net) — C.S W83795G LQFP-64//WINBOND

| Ball | Pin name (function) | Net | Connects to |
|---|---|---|---|
| E1 | `PCI_PME_L/GEVENT4_L` | `SB_PCI_PME#` | LU1[16], LU2[16], OU1[65], PCI6[A19], PCIE1[B11], PCIE2[B11], PCIE3[B11], PCIE4[B11], PCIE5[B11], PIKE1[B11], ZR19[1], ZR20[1], ZR21[1] |
| N1 | `PCIRST#` | `SB_PCI_RST_SR#` | QU1[B10], SQ5[1], VGA_SW1[1] |
| P1 | `PCICLK2` | `SB_PCI_CLK2_SR` | — |
| P2 | `PCICLK3` | `SB_PCI_CLK3_SR` | QU4[32] |
| P3 | `PCICLK1` | `SB_PCI_CLK1_SR` | QU1[P22] |
| P4 | `PCICLK0` | `SB_PCI_CLK0_SR` | OU1[17] |
| P7 | `AD1` | `SB_PCI_AD1` | PCI6[B58], QU1[C21], ZU1[68] |
| R5 | `AD13` | `SB_PCI_AD13` | PCI6[A46], QU1[F20], ZU1[50] |
| R6 | `AD11` | `SB_PCI_AD11` | PCI6[A47], QU1[F22], ZU1[53] |
| R7 | `AD12` | `SB_PCI_AD12` | PCI6[B47], QU1[F21], ZU1[51] |
| T1 | `AD3` | `SB_PCI_AD3` | PCI6[B56], QU1[C19], ZU1[64] |
| T2 | `AD8` | `SB_PCI_AD8` | PCI6[B52], QU1[E21], ZU1[56] |
| T3 | `PCICLK5/GPIO41` | `SB_PCI_CLK5_SR` | ZU1[11] |
| T4 | `PCICLK4` | `SB_PCI_CLK4_SR` | PCI6[B16] |
| T9 | `AD10` | `SB_PCI_AD10` | PCI6[B48], QU1[E19], ZU1[54] |
| U1 | `AD5` | `SB_PCI_AD5` | PCI6[B55], QU1[D21], ZU1[61] |
| U2 | `AD0` | `SB_PCI_AD0` | PCI6[A58], QU1[C22], ZU1[69] |
| U5 | `AD15` | `SB_PCI_AD15` | PCI6[A44], QU1[G22], ZU1[48] |
| U6 | `PAR` | `SB_PCI_PAR` | PCI6[A43], QU1[G20], ZU1[46] |
| U7 | `CBE1#` | `SB_PCI_CBE1#` | PCI6[B44], QU1[G21], ZU1[47] |
| U8 | `AD14` | `SB_PCI_AD14` | PCI6[B45], QU1[F19], ZU1[49] |
| V1 | `AD6` | `SB_PCI_AD6` | PCI6[A54], QU1[D20], ZU1[60] |
| V2 | `AD7` | `SB_PCI_AD7` | PCI6[B53], QU1[D19], ZU1[59] |
| V3 | `AD4` | `SB_PCI_AD4` | PCI6[A55], QU1[D22], ZU1[63] |
| V4 | `AD2` | `SB_PCI_AD2` | PCI6[A57], QU1[C20], ZU1[65] |
| V5 | `LOCK#` | `SB_PCI_LOCK#` | PCI6[B39] |
| V7 | `SERR#` | `SB_PCI_SERR#` | PCI6[B42], ZU1[45] |
| V9 | `AD18` | `SB_PCI_AD18` | PCI6[A31], QU1[K22], ZR22[1], ZU1[31] |
| W1 | `AD9` | `SB_PCI_AD9` | PCI6[A49], QU1[E20], ZU1[55] |
| W2 | `CBE0#` | `SB_PCI_CBE0#` | PCI6[A52], QU1[E22], ZU1[58] |
| W5 | `DEVSEL#` | `SB_PCI_DEVSEL#` | PCI6[B37], QU1[H21], ZU1[41] |
| W6 | `STOP#` | `SB_PCI_STOP#` | PCI6[A38], QU1[H22], ZU1[42] |
| W8 | `AD17` | `SB_PCI_AD17` | PCI6[B32], QU1[J19,L20], ZU1[34] |
| Y1 | `CBE3#` | `SB_PCI_CBE3#` | PCI6[B26], QU1[L19], ZU1[23] |
| Y2 | `AD23` | `SB_PCI_AD23` | PCI6[B27], QU1[L21], ZU1[25] |
| Y3 | `AD22` | `SB_PCI_AD22` | PCI6[A28], QU1[L22], ZU1[26] |
| Y4 | `AD21` | `SB_PCI_AD21` | PCI6[B29], QU1[K19], ZU1[28] |
| Y5 | `TRDY#` | `SB_PCI_TRDY#` | PCI6[A36], QU1[H20], ZU1[40] |
| Y7 | `AD16` | `SB_PCI_AD16` | PCI6[A32], QU1[J20], ZU1[35] |
| Y8 | `AD19` | `SB_PCI_AD19` | PCI6[A26,B30], QU1[K21], ZU1[30] |
| AA1 | `AD26` | `SB_PCI_AD26` | PCI6[A23], QU1[M20], ZU1[19] |
| AA2 | `AD24` | `SB_PCI_AD24` | PCI6[A25], QU1[M22], ZU1[21] |
| AA5 | `IRDY#` | `SB_PCI_IRDY#` | PCI6[B35], QU1[H19], ZU1[39] |
| AA6 | `FRAME#` | `SB_PCI_FRAME#` | PCI6[A34], QU1[J22], ZU1[37] |
| AA7 | `CBE2#` | `SB_PCI_CBE2#` | PCI6[B33], QU1[J21], ZU1[36] |
| AA8 | `AD20` | `SB_PCI_AD20` | PCI6[A29], QU1[K20], ZU1[29] |
| AB2 | `AD28` | `SB_PCI_AD28` | PCI6[A22], QU1[N22], ZU1[16] |
| AB3 | `AD27` | `SB_PCI_AD27` | PCI6[B23], QU1[M19], ZU1[18] |
| AB4 | `AD25` | `SB_PCI_AD25` | PCI6[B24], QU1[M21], ZU1[20] |
| AB7 | `REQ2#` | `SB_PCI_REQ2#` | PCI6[B18] |
| AC1 | `AD29` | `SB_PCI_AD29` | PCI6[B21], QU1[N21], ZU1[15] |
| AC2 | `AD30` | `SB_PCI_AD30` | PCI6[A20], QU1[N20], ZU1[14] |
| AC3 | `REQ0#` | `SB_PCI_REQ0#` | ZR23[1] |
| AC4 | `INTF_L/GPIO34` | `SB_PCI_INTB#` | PCI6[B8], QU1[B11] |
| AD1 | `AD31` | `SB_PCI_AD31` | PCI6[B20], QU1[N19], ZU1[13] |
| AD2 | `GNT0#` | `SB_PCI_GNT0#` | ZR24[1] |
| AD3 | `INTE_L/GPIO33` | `SB_PCI_INTA#` | PCI6[A7], ZU1[6] |
| AD5 | `GNT2#` | `SB_PCI_GNT2#` | PCI6[A17] |
| AE2 | `INTG_L/GPIO35` | `SB_PCI_INTC#` | PCI6[A6] |
| AE3 | `INTH_L/GPIO36` | `SB_PCI_INTD#` | PCI6[B7] |

## PCI Express (34)

**Connected components** (chips / connectors these pins reach):

- `NU1` (692 pins, 8 nets) — C.S SR5690 (A21) FCBGA692//AMD 215-0716038
- `CU1` (73 pins, 2 nets) — CLOCK Gen. ICS932S890CKLFT//IDT MLF72
- `PCI6` (122 pins, 1 net)
- `PCIE1` (166 pins, 1 net)
- `PCIE2` (166 pins, 1 net)
- `PCIE3` (100 pins, 1 net)
- `PCIE4` (166 pins, 1 net)
- `PCIE5` (166 pins, 1 net)
- `ZU1` (100 pins, 1 net) — C.S L-FW322-07-T100-DB TQFP100//LSI 1394A/711008303

| Ball | Pin name (function) | Net | Connects to |
|---|---|---|---|
| J18 | `GPP_CLK0N` | `N35097683` | GPP_CLK0N1[1] |
| J19 | `GPP_CLK0P` | `N35097673` | GPP_CLK0P1[1] |
| L19 | `GPP_CLK1N` | `N35097687` | GPP_CLK1N1[1] |
| L20 | `GPP_CLK1P` | `N35097685` | GPP_CLK1P1[1] |
| M19 | `GPP_CLK2P` | `N35097675` | GPP_CLK2P1[1] |
| M20 | `GPP_CLK2N` | `N35097677` | GPP_CLK2N1[1] |
| N22 | `GPP_CLK3P` | `N35097679` | GPP_CLK3P1[1] |
| N24 | `PCIE_RCLKN/NB_LNK_CLKN` | `C_CLKGEN_A_LINK_REFCLK_L` | CU1[61] |
| N25 | `PCIE_RCLKP/NB_LNK_CLKP` | `C_CLKGEN_A_LINK_REFCLK_H` | CU1[62] |
| P22 | `GPP_CLK3N` | `N35097681` | GPP_CLK3N1[1] |
| R17 | `PCIE_RX3N` | `A_LINK_SB_TX_N3` | NC5[1] |
| R18 | `PCIE_RX3P` | `A_LINK_SB_TX_P3` | NC3[1] |
| R20 | `PCIE_RX2P` | `A_LINK_SB_TX_P2` | NC4[1] |
| R21 | `PCIE_RX2N` | `A_LINK_SB_TX_N2` | NC7[1] |
| T22 | `PCIE_TX3N` | `A_LINK_SB_RX_N3_C` | NU1[AD21] |
| T23 | `PCIE_TX3P` | `A_LINK_SB_RX_P3_C` | NU1[AC21] |
| T24 | `PCIE_CALRN` | `SB_PCIE_CALRN` | — |
| T25 | `PCIE_CALRP` | `SB_PCIE_CALRP` | — |
| U19 | `PCIE_RX1P` | `A_LINK_SB_TX_P1` | NC6[1] |
| U21 | `PCIE_RX0N` | `A_LINK_SB_TX_N0` | NC10[1] |
| U22 | `PCIE_RX0P` | `A_LINK_SB_TX_P0` | NC8[1] |
| U24 | `PCIE_TX2N` | `A_LINK_SB_RX_N2_C` | NU1[AE22] |
| U25 | `PCIE_TX2P` | `A_LINK_SB_RX_P2_C` | NU1[AD22] |
| V19 | `PCIE_RX1N` | `A_LINK_SB_TX_N1` | NC9[1] |
| V22 | `PCIE_TX0N` | `A_LINK_SB_RX_N0_C` | NU1[AH26] |
| V23 | `PCIE_TX0P` | `A_LINK_SB_RX_P0_C` | NU1[AG26] |
| V24 | `PCIE_TX1P` | `A_LINK_SB_RX_P1_C` | NU1[AF25] |
| V25 | `PCIE_TX1N` | `A_LINK_SB_RX_N1_C` | NU1[AG25] |
| W4 | `PERR#` | `SB_PCI_PERR#` | PCI6[B40], ZU1[44] |
| AC22 | `IDE_D3/GPIO18` | `PCIE4_PRSNT#` | PCIE4[B17,B31,B48,B81] |
| AD21 | `IDE_D4/GPIO19` | `PCIE5_PRSNT#` | EQ2[1], PCIE5[B17,B31,B48,B81], PCIE5_SW1[2] |
| AD23 | `IDE_D1/GPIO16` | `PCIE2_PRSNT#` | EQ1[1], PCIE2[B17,B31,B48,B81], PCIE2_SW1[2] |
| AD24 | `IDE_D0/GPIO15` | `PCIE1_PRSNT#` | PCIE1[B17,B31,B48,B81], XQ1[1], XQ18[1], XQ37[1], XQ39[1] |
| AE22 | `IDE_D2/GPIO17` | `PCIE3_PRSNT#` | PCIE3[B17,B31,B48] |

## SATA (34)

**Connected components** (chips / connectors these pins reach):

- `SATA1` (9 pins, 4 nets)
- `SATA2` (9 pins, 4 nets)
- `SATA3` (9 pins, 4 nets)
- `SATA4` (9 pins, 4 nets)
- `SATA5` (9 pins, 4 nets)
- `SATA6` (9 pins, 4 nets)
- `HDLED1` (4 pins, 1 net)
- `PIKE2` (66 pins, 1 net)
- `QU1` (355 pins, 1 net) — C.S AST2050A3-GP TFBGA355//ASPEED

| Ball | Pin name (function) | Net | Connects to |
|---|---|---|---|
| V12 | `SATA_CAL` | `SB_SATA_CAL` | — |
| V17 | `CLK_REQ1_L/SATA_IS4_L/FANOUT3` | `P0_MEM_EVENT#` | Q26[3] |
| W11 | `SATA_ACT_L/GPIO67` | `SB_SATA_ACT#` | HDLED1[2,3], PIKE2[B11], SQ4[1] |
| W17 | `CLK_REQ0_L/SATA_IS3_L/GPIO0` | `SB_RISERID0` | XQ1[3] |
| W20 | `CLK_REQ2_L/SATA_IS5_L/FANIN3` | `P1_MEM_EVENT#` | Q27[3] |
| Y12 | `SATA_X1` | `SB_SATA_X1` | SX3[1,2] |
| AA12 | `SATA_X2` | `SB_SATA_X2` | SX3[1,2] |
| AA19 | `SMARTVOLT1/SATA_IS2_L/GPIO4` | `SB_SKUID0` | — |
| AB10 | `SATA_RX0N` | `SATA_RX0_N` | SATA1[5] |
| AB12 | `SATA_TX2P` | `SATA_TX2_P` | SATA3[2] |
| AB14 | `SATA_RX3N` | `SATA_RX3_N` | SATA4[5] |
| AB16 | `SATA_TX5P` | `SATA_TX5_P` | SATA6[2] |
| AC10 | `SATA_RX0P` | `SATA_RX0_P` | SATA1[6] |
| AC12 | `SATA_TX2N` | `SATA_TX2_N` | SATA3[3] |
| AC14 | `SATA_RX3P` | `SATA_RX3_P` | SATA4[6] |
| AC16 | `SATA_TX5N` | `SATA_TX5_N` | SATA6[3] |
| AD9 | `SATA_TX0P` | `SATA_TX0_P` | SATA1[2] |
| AD10 | `SATA_TX1N` | `SATA_TX1_N` | SATA2[3] |
| AD11 | `SATA_RX1N` | `SATA_RX1_N` | SATA2[5] |
| AD12 | `SATA_RX2P` | `SATA_RX2_P` | SATA3[6] |
| AD13 | `SATA_TX3P` | `SATA_TX3_P` | SATA4[2] |
| AD14 | `SATA_TX4N` | `SATA_TX4_N` | SATA5[3] |
| AD15 | `SATA_RX4N` | `SATA_RX4_N` | SATA5[5] |
| AD16 | `SATA_RX5P` | `SATA_RX5_P` | SATA6[6] |
| AD18 | `CLK_REQ3_L/SATA_IS1_L/GPIO6` | `SB_SKUID2` | — |
| AE9 | `SATA_TX0N` | `SATA_TX0_N` | SATA1[3] |
| AE10 | `SATA_TX1P` | `SATA_TX1_P` | SATA2[2] |
| AE11 | `SATA_RX1P` | `SATA_RX1_P` | SATA2[6] |
| AE12 | `SATA_RX2N` | `SATA_RX2_N` | SATA3[5] |
| AE13 | `SATA_TX3N` | `SATA_TX3_N` | SATA4[3] |
| AE14 | `SATA_TX4P` | `SATA_TX4_P` | SATA5[2] |
| AE15 | `SATA_RX4P` | `SATA_RX4_P` | SATA5[6] |
| AE16 | `SATA_RX5N` | `SATA_RX5_N` | SATA6[5] |
| AE18 | `SATA_IS0_L/GPIO10` | `N84922931` | NQ5[3], NQ6[3], QR147[2], QU1[U3,U4] |

## USB (37)

**Connected components** (chips / connectors these pins reach):

- `D22` (6 pins, 4 nets) — DIODE IP4220CZ6 SOT457//PHILIPS
- `D23` (6 pins, 4 nets) — DIODE IP4220CZ6 SOT457//PHILIPS
- `D28` (6 pins, 4 nets) — DIODE IP4220CZ6 SOT457//PHILIPS
- `D39` (6 pins, 4 nets) — DIODE IP4220CZ6 SOT457//PHILIPS
- `SJ8` (13 pins, 4 nets)
- `USB12_LAN3` (30 pins, 4 nets)
- `USB34` (9 pins, 4 nets)
- `USB56` (9 pins, 4 nets)
- `USB78` (9 pins, 4 nets)
- `QU1` (355 pins, 3 nets) — C.S AST2050A3-GP TFBGA355//ASPEED
- `D38` (6 pins, 2 nets) — DIODE IP4220CZ6 SOT457//PHILIPS
- `L12` (4 pins, 2 nets)
- `L13` (4 pins, 2 nets)
- `L16` (4 pins, 2 nets)
- `L17` (4 pins, 2 nets)
- `L2` (4 pins, 2 nets)
- `L3` (4 pins, 2 nets)
- `L4` (4 pins, 2 nets)
- `L45` (4 pins, 2 nets)
- `L5` (4 pins, 2 nets)
- `USB9` (6 pins, 2 nets)
- `CU1` (73 pins, 1 net) — CLOCK Gen. ICS932S890CKLFT//IDT MLF72

| Ball | Pin name (function) | Net | Connects to |
|---|---|---|---|
| A8 | `USB_OC4_L/IR_RX0/GPM4_L` | `USB_OC_4_5#` | — |
| A9 | `USB_OC3_L/IR_RX1/GPM3_L` | `SB_IR_RX1_TDO` | SJ8[8] |
| A11 | `USB_HSD9P` | `USB9_P` | D38[1], L45[3,4], USB9[3] |
| A12 | `USB_HSD4N` | `USB4_N` | D28[6], L13[1,2], USB56[3] |
| A13 | `USB_HSD1P` | `USB1_P` | D22[3], L4[3,4], USB12_LAN3[4] |
| A14 | `USB_HSD0N` | `USB0_N` | D22[6], L2[1,2], USB12_LAN3[5] |
| B8 | `USB_OC5_L/IR_TX0/GPM5_L` | `N23964581` | NQ5[3], NQ6[3], QR147[2], QU1[U3,U4] |
| B9 | `USB_OC6_L/IR_TX1/GEVENT6_L` | `N30004187` | — |
| B11 | `USB_HSD9N` | `USB9_N` | D38[6], L45[1,2], USB9[2] |
| B12 | `USB_HSD4P` | `USB4_P` | D28[1], L13[3,4], USB56[5] |
| B13 | `USB_HSD1N` | `USB1_N` | D22[4], L4[1,2], USB12_LAN3[6] |
| B14 | `USB_HSD0P` | `USB0_P` | D22[1], L2[3,4], USB12_LAN3[3] |
| C8 | `USBCLK/14M_25M_48M_OSC` | `CLKGEN_48M_SB_USB` | CU1[31] |
| C10 | `USB_HSD8P` | `USB8_P` | QU1[A21,B22] |
| C12 | `USB_HSD5P` | `USB5_P` | D28[3], L12[3,4], USB56[6] |
| D10 | `USB_HSD8N` | `USB8_N` | QU1[A21,B22] |
| D12 | `USB_HSD5N` | `USB5_N` | D28[4], L12[1,2], USB56[4] |
| E4 | `USB_OC0_L/GPM0_L` | `SB_JTAG_RST#` | SJ8[10] |
| E5 | `USB_OC2_L/GPM2_L` | `USB_OC_2_3_L_TCK` | SJ8[2] |
| E6 | `USB_FSD13P` | `N13199376` | USB_FSD13P1[1] |
| E7 | `USB_FSD13N` | `N13199377` | USB_FSD13N1[1] |
| E8 | `USB_FSD12N` | `N13199379` | USB_FSD12N1[1] |
| E11 | `USB_HSD10P` | `N13199382` | USB_HSD10P1[1] |
| E12 | `USB_HSD6P` | `USB6_P` | D39[1], L17[3,4], USB78[5] |
| E14 | `USB_HSD6N` | `USB6_N` | D39[6], L17[1,2], USB78[3] |
| F7 | `USB_FSD12P` | `N13199378` | USB_FSD12P1[1] |
| F8 | `USB_OC1_L/GPM1_L` | `USB_OC_0_1_L_TDI` | SJ8[6] |
| F11 | `USB_HSD10N` | `N13199383` | USB_HSD10N1[1] |
| G8 | `USB_RCOMP` | `USB_RCOMP` | — |
| G11 | `USB_HSD7P` | `USB7_P` | D39[3], L16[3,4], USB78[6] |
| G12 | `USB_HSD3P` | `USB3_P` | D23[3], L5[3,4], USB34[6] |
| G14 | `USB_HSD3N` | `USB3_N` | D23[4], L5[1,2], USB34[4] |
| H11 | `USB_HSD11P` | `N13199380` | USB_HSD11P1[1] |
| H12 | `USB_HSD7N` | `USB7_N` | D39[4], L16[1,2], USB78[4] |
| H14 | `USB_HSD2P` | `USB2_P` | D23[1], L3[3,4], USB34[5] |
| H15 | `USB_HSD2N` | `USB2_N` | D23[6], L3[1,2], USB34[3] |
| J10 | `USB_HSD11N` | `N13199381` | USB_HSD11N1[1] |

## I2C / SMBus (11)

**Connected components** (chips / connectors these pins reach):

- `QU1` (355 pins, 5 nets) — C.S AST2050A3-GP TFBGA355//ASPEED
- `QU4` (64 pins, 2 nets) — C.S W83795G LQFP-64//WINBOND
- `QU9` (16 pins, 2 nets) — ANALOG SW. SN74CBTLV3125DBQR@G//TI QSOP-16

| Ball | Pin name (function) | Net | Connects to |
|---|---|---|---|
| D21 | `SCL2/IMC_GPIO11` | `N36791303` | QU1[B14] |
| E20 | `SCL3_LV/IMC_GPIO13` | `N20203806` | SB_SCL3[1] |
| E21 | `SDA3_LV/IMC_GPIO14` | `N20210661` | SB_SDA3[1] |
| F19 | `SDA2/IMC_GPIO12` | `N36791299` | QU1[A14] |
| J6 | `SMBALERT_L/THRMTRIP_L/GEVENT2_L` | `SB_THERMTRIP#` | Q7[3], Q8[3], QU1[V3,V4], SQ7[1] |
| K1 | `SCL1/GPOC2_L` | `N36483359` | QU1[D14], QU4[33], QU9[6] |
| K2 | `SDA1/GPOC3_L` | `N36483299` | QU1[C14], QU4[34], QU9[3] |
| W18 | `SDA0/GPOC1_L` | `N54253331` | — |
| Y18 | `DDC1_SDA/GPIO8` | `FANCURVE0` | — |
| AA18 | `SCL0/GPOC0_L` | `N54247001` | — |
| AA20 | `DDC1_SCL/GPIO9` | `FANCURVE1` | — |

## Serial / SOL (UART) (2)

| Ball | Pin name (function) | Net | Connects to |
|---|---|---|---|
| E2 | `RI_L/EXTEVNT0_L` | `SB_RI#` | Q41[3] |
| M8 | `FANOUT0/GPIO3` | `SB_RISERID1` | XQ17[3] |

## JTAG / test (2)

**Connected components** (chips / connectors these pins reach):

- `SJ8` (13 pins, 1 net)

| Ball | Pin name (function) | Net | Connects to |
|---|---|---|---|
| H4 | `TEST1` | `SB_TEST1_TMS` | SJ8[4] |
| Y19 | `SMARTVOLT2/SHUTDOWN_L/GPIO5` | `SB_SKUID1` | — |

## Hardware monitor / fans (IMC) (14)

**Connected components** (chips / connectors these pins reach):

- `QU1` (355 pins, 4 nets) — C.S AST2050A3-GP TFBGA355//ASPEED
- `U23` (14 pins, 2 nets) — LOGIC 74LVC125APW TSSOP-14//PHILIPS
- `BMC_FW1` (13 pins, 1 net)
- `FU1` (8 pins, 1 net)
- `OU1` (128 pins, 1 net) — C.S W83667HG-A-FAC QFP-128//NUVOTON (0.18UM) REV-FAC
- `PCIE1` (166 pins, 1 net)
- `QU4` (64 pins, 1 net) — C.S W83795G LQFP-64//WINBOND
- `QU8` (16 pins, 1 net) — ANALOG SW. PI5C3257QE QS-16//PERICOM
- `SU2` (8 pins, 1 net) — LOGIC 74LVC2G74DC VSSOP-8//NXP
- `TPM1` (19 pins, 1 net)
- `U6` (14 pins, 1 net) — LOGIC 74LVC07AD S-14//PHILIPS

| Ball | Pin name (function) | Net | Connects to |
|---|---|---|---|
| A4 | `VIN0/GPIO53` | `N34313017` | QU1[D12] |
| A5 | `TEMPIN2/GPIO63` | `N49090245` | Q39[1] |
| A6 | `TEMPIN1/GPIO62` | `N49051773` | PCIE1[A18] |
| A7 | `VIN6/GPIO59` | `N34311436` | U23[12] |
| B4 | `VIN1/GPIO54` | `N34312751` | QU1[C12], QU4[35] |
| B6 | `TEMPIN0/GPIO61` | `N49035599` | QU1[C9], RECOVERY1[2] |
| B7 | `VIN7/GPIO60` | `N34311176` | U23[9] |
| D4 | `VIN3/GPIO56` | `N34312222` | IBTN_SEL1[3] |
| D5 | `VIN4/GPIO57` | `N34311959` | OU1[60,61], Q9[3], SU2[7] |
| D6 | `VIN5/GPIO58` | `N34311697` | FU1[3] |
| D19 | `IMC_PWM2/IMC_GPO16` | `SB_IMC_PWM2` | — |
| E18 | `IMC_PWM3/IMC_GPO17` | `SB_IMC_PWM3` | — |
| F21 | `IMC_PWM0/IMC_GPIO10` | `TPM_GPIO` | TPM1[18] |
| R8 | `FANIN2/GPIO52` | `N49130097` | BMC_FW1[7], D7[3], D8[3], QQ1[1], QQ12[1], QQ9[1], QU1[D11], QU8[1], R180[2], R182[2], U6[5] |

## Power / reset / platform control (19)

**Connected components** (chips / connectors these pins reach):

- `OU1` (128 pins, 9 nets) — C.S W83667HG-A-FAC QFP-128//NUVOTON (0.18UM) REV-FAC
- `QU1` (355 pins, 4 nets) — C.S AST2050A3-GP TFBGA355//ASPEED
- `TPM1` (19 pins, 3 nets)
- `U3` (20 pins, 3 nets) — LOGIC 74LVC244APW TSS-20//PHILIPS
- `NU2` (14 pins, 2 nets) — LOGIC 74LVC125APW TSSOP-14//PHILIPS
- `PIKE2` (66 pins, 2 nets)
- `U8` (14 pins, 2 nets) — LOGIC 74LVC14APW-T TSSOP-14//PHILIPS
- `AU1` (20 pins, 1 net) — ANALOG SW. PI3B3244LEX//PERICOM TSSOP-20
- `QU4` (64 pins, 1 net) — C.S W83795G LQFP-64//WINBOND
- `SU2` (8 pins, 1 net) — LOGIC 74LVC2G74DC VSSOP-8//NXP
- `U27` (20 pins, 1 net) — C.S W83601G SSOP20//WINBOND MULTI-FUNCTION G.P.I/O
- `U28` (20 pins, 1 net) — C.S W83601G SSOP20//WINBOND MULTI-FUNCTION G.P.I/O
- `U30` (5 pins, 1 net) — LOGIC 74LVC1G08GW SOT353//PHILIPS
- `U7` (14 pins, 1 net) — LOGIC TC74LCX74FT(EK2,M)//TOSHIBA TSSOP-14

| Ball | Pin name (function) | Net | Connects to |
|---|---|---|---|
| C2 | `INTRUDER_ALERT#` | `INTRUDER#` | OQ1[3], OU1[100], QU4[27] |
| D3 | `RSMRST#` | `SIO_RSMRST#` | OU1[101], QQ3[1], U27[19], U28[19], U7[3] |
| F2 | `BLINK/GPM6_L` | `N27567239` | U30[2] |
| F5 | `SLP_S3#` | `SB_SLP_S3#` | OU1[64], PD58[1], PIKE2[A11], PQ59[1], QU1[D15], TPM1[19] |
| F24 | `PROCHOT#` | `SB_PROCHOT#` | Q5[3], Q6[3] |
| G1 | `SLP_S5#` | `SB_SLP_S5#` | OU1[84], PD32[2], PD47[2] |
| G5 | `DDR3_RST_L/GEVENT7_L` | `SB_NMI#` | NQ11[1] |
| G24 | `LDT_RST#` | `N34238395` | U3[11,13,15,17] |
| H1 | `PWR_GOOD` | `SYS_PWRGD` | NU2[5], Q34[3], QU1[D9], U3[14], U8[13] |
| H2 | `PWR_BTN#` | `FP_PWRBTN#` | OU1[60,61], Q9[3], SU2[7] |
| J2 | `SYS_RESET_L/GPM7_L` | `SYS_RST#` | CD1[1], Q12[3], Q33[1] |
| K3 | `SUS_STAT#` | `SB_SUS_STAT#` | OU1[64], PD58[1], PIKE2[A11], PQ59[1], QU1[D15], TPM1[19] |
| L5 | `AZ_DOCK_RST_L/GPM8_L` | `N36626743` | OU1[128] |
| M4 | `AZ_RST#` | `N27050827` | AU1[16] |
| N2 | `A_RST#` | `SB_A_RST_SR#` | OU1[26,79], TPM1[5] |
| U15 | `LAN_RST_L/GPIO13` | `N37320597` | — |
| W14 | `NB_PWRGD` | `NB_POWERGOOD` | NU2[5], Q34[3], QU1[D9], U3[14], U8[13] |
| W15 | `KBRST_L/GEVENT1_L` | `SIO_KBRST#` | OU1[28] |
| W21 | `SPKR/GPIO2` | `SB_SPKR_SR` | Q43[1] |

## Clocks (6)

**Connected components** (chips / connectors these pins reach):

- `CU3` (8 pins, 3 nets) — LOGIC GTL2002DP TSSOP-8//PHILIPS
- `SX2` (4 pins, 2 nets)

| Ball | Pin name (function) | Net | Connects to |
|---|---|---|---|
| A3 | `X1` | `SB_32K_X1` | SX2[1,2] |
| B3 | `X2` | `SB_32K_X2` | SX2[1,2] |
| C3 | `RTCCLK` | `N59274001` | RTCCLK1[1] |
| J20 | `14M_X2` | `SB_14M_X2_C` | CC29[1], CR55[1], CR56[1], CU3[6], SX1[1,2] |
| J21 | `14M_X1` | `SB_14M_X1_C` | CU3[6], SX1[1,2] |
| L18 | `25M_48M_66M_OSC` | `CLKGEN_SB700_14M_CLK` | CU3[6], SX1[1,2] |

## Other / GPIO (45)

**Connected components** (chips / connectors these pins reach):

- `HSTAT1` (8 pins, 6 nets)
- `AU1` (20 pins, 4 nets) — ANALOG SW. PI3B3244LEX//PERICOM TSSOP-20
- `SGPIO3` (7 pins, 4 nets)
- `SGPIO4` (7 pins, 4 nets)
- `OU1` (128 pins, 2 nets) — C.S W83667HG-A-FAC QFP-128//NUVOTON (0.18UM) REV-FAC
- `PIKE1` (100 pins, 2 nets)
- `QU8` (16 pins, 2 nets) — ANALOG SW. PI5C3257QE QS-16//PERICOM
- `U13` (20 pins, 2 nets) — INTERFACE AZ75232GTR-E1//BCD TSSOP-20
- `LU1` (65 pins, 1 net) — C.S WG82574L A1 QFN64//INTEL 898553/SLBA9
- `LU2` (65 pins, 1 net) — C.S WG82574L A1 QFN64//INTEL 898553/SLBA9
- `NU1` (692 pins, 1 net) — C.S SR5690 (A21) FCBGA692//AMD 215-0716038
- `PCI6` (122 pins, 1 net)
- `PCIE1` (166 pins, 1 net)
- `PCIE2` (166 pins, 1 net)
- `PCIE3` (100 pins, 1 net)
- `PCIE4` (166 pins, 1 net)
- `PCIE5` (166 pins, 1 net)
- `SJ8` (13 pins, 1 net)
- `TPM1` (19 pins, 1 net)
- `U3` (20 pins, 1 net) — LOGIC 74LVC244APW TSS-20//PHILIPS
- `U4` (20 pins, 1 net) — LOGIC 74LVC244APW TSS-20//PHILIPS

| Ball | Pin name (function) | Net | Connects to |
|---|---|---|---|
| A19 | `IMC_GPIO39` | `N85405918` | HSTAT1[8] |
| A20 | `IMC_GPIO36` | `N85382407` | HSTAT1[5] |
| B19 | `IMC_GPIO38` | `N85398079` | HSTAT1[7] |
| B20 | `IMC_GPIO37` | `N85390242` | HSTAT1[6] |
| C1 | `LLB_L/GPIO66` | `N85092099` | — |
| C18 | `IMC_GPIO41` | `N85421602` | HSTAT1[2] |
| D18 | `IMC_GPIO40` | `N85413759` | HSTAT1[1] |
| D22 | `IMC_GPIO4` | `N81331072` | SGPIO3[7], SGPIO4[7] |
| D23 | `IMC_GPIO7` | `N81354412` | SGPIO3[2] |
| D24 | `IMC_GPIO21` | `N84628298` | PQ46[1] |
| D25 | `IMC_GPIO20` | `N84628315` | PQ38[1] |
| E24 | `IMC_GPIO5` | `N81338850` | SGPIO3[5], SGPIO4[5] |
| E25 | `IMC_GPIO6` | `N81346630` | SGPIO4[2] |
| F22 | `LDT_PG` | `N34225333` | U3[2,4,6,8] |
| F23 | `ALLOW_LDTSTP` | `ALLOW_LDTSTOP` | NU1[D21] |
| G20 | `IMC_GPIO18` | `N85172781` | PQ37[1] |
| G21 | `IMC_GPIO19` | `N84573875` | PQ45[1] |
| G25 | `LDT_STP#` | `N34234198` | U4[2,4,6] |
| H3 | `TEST0` | `SB_TEST0` | — |
| H5 | `TEST2` | `SB_TEST2` | SJ8[12] |
| H6 | `WAKE_L/GEVENT8_L` | `SB_WAKE#` | LU1[16], LU2[16], OU1[65], PCI6[A19], PCIE1[B11], PCIE2[B11], PCIE3[B11], PCIE4[B11], PCIE5[B11], PIKE1[B11], ZR19[1], ZR20[1], ZR21[1] |
| H19 | `IMC_GPIO0` | `N36672589` | QU8[3], SGPIO4[4], U13[15] |
| H20 | `IMC_GPIO1` | `N36653985` | QU8[6], SGPIO3[4], U13[17] |
| J7 | `AZ_SDIN0/GPIO42` | `SB_HDASDIN0` | AU1[14] |
| K22 | `NB_DISP_CLKN` | `N35084473` | NB_DISP_CLKN1[1] |
| K23 | `NB_DISP_CLKP` | `N35080098` | NB_DISP_CLKP1[1] |
| L6 | `AZ_SYNC` | `N27029919` | AU1[17] |
| M1 | `AZ_BITCLK` | `N26995517` | AC1[1], AU1[11] |
| M2 | `AZ_SDOUT` | `N27002267` | AU1[18] |
| M18 | `CPU_HT_CLKN` | `N35093255` | CPU_HT_CLKN1[1] |
| M22 | `SLT_GFX_CLKN` | `N35093259` | SLT_GFX_CLKN1[1] |
| M23 | `SLT_GFX_CLKP` | `N35093257` | SLT_GFX_CLKP1[1] |
| M24 | `NB_HT_CLKP` | `N35088857` | NB_HT_CLKP1[1] |
| M25 | `NB_HT_CLKN` | `N35088859` | NB_HT_CLKN1[1] |
| P17 | `CPU_HT_CLKP` | `N35093253` | CPU_HT_CLKP1[1] |
| Y15 | `GA20IN/GEVENT0_L` | `SIO_A20M_SR` | OU1[27] |
| AB6 | `REQ4_L/GPIO71` | `REQ4#` | — |
| AC6 | `GNT3_L/GPIO72` | `N93925661` | — |
| AD4 | `REQ1#` | `N93909569` | — |
| AD6 | `CLKRUN#` | `SB_TPM_CLKRUN#` | TPM1[18] |
| AD7 | `BMREQ_L/REQ5_L/GPIO65` | `IDLEEXIT#` | Q82[3], Q84[3] |
| AE4 | `GNT1#` | `N93949218` | — |
| AE5 | `GNT4_L/GPIO73` | `GNT4#` | — |
| AE6 | `REQ3_L/GPIO70` | `N93901525` | — |
| AE20 | `IDE_D5/GPIO20` | `PIKE_PRSNT#` | PIKE1[B17,B31,B48] |

## Power / decoupling (75)

| Rail | Count | Balls |
|---|---|---|
| `+1V2` | 9 | L15 M12 M14 N13 P12 P14 R11 R15 T16 |
| `+1V2_AUX` | 4 | A10 B10 G2 G4 |
| `+3V3` | 16 | L9 M9 T15 U9 U16 U17 V8 W7 Y6 Y20 AA4 AA21 AA22 AB5 AB21 AE25 |
| `+3V3_AUX` | 7 | A17 A24 B17 J4 J5 L1 L2 |
| `SB_AVDD` | 1 | F6 |
| `SB_AVDDCK_1V2` | 1 | K17 |
| `SB_AVDDCK_3V3` | 1 | J16 |
| `SB_AVDDC_3V3DUAL` | 1 | E9 |
| `SB_AVDDTXRX_3V3DUAL` | 12 | A16 B16 C16 D16 D17 E17 F15 F17 F18 G15 G17 G18 |
| `SB_AVDD_SATA_1V2` | 7 | AA14 AA15 AA17 AB18 AC18 AD17 AE17 |
| `SB_CKVDD_1V2` | 4 | L21 L22 L24 L25 |
| `SB_PCIE_PVDD` | 1 | P24 |
| `SB_PCIE_VDDR_1V2` | 7 | P18 P19 P20 P21 R22 R24 R25 |
| `SB_PLLVDD_SATA` | 1 | AA11 |
| `SB_VDD_RTC` | 1 | B2 |
| `SB_VS_VREF_5V` | 1 | AE7 |
| `SB_XTLVDD_SATA` | 1 | W12 |

## Ground (120)

| Rail | Count | Balls |
|---|---|---|
| `GND` | 120 | A2 A15 A25 B1 B15 C6 C14 D7 D8 D9 D11 D13 D14 D15 E15 F9 F12 F14 F20 G7 G9 G19 H8 H9 H17 H18 J9 J11 J12 J14 J15 J17 J22 K9 K10 K11 K12 K14 K15 K16 K25 L4 L7 L10 L11 L12 L14 L16 L17 M6 M10 M11 M13 M15 M16 M17 M21 N4 N12 N14 P6 P9 P10 P11 P13 P15 P16 P23 P25 R1 R2 R4 R9 R10 R12 R14 R16 R19 T10 T11 T12 T14 T17 U4 U10 U11 U12 U14 U18 U20 V6 V11 V14 V18 V20 V21 W9 W19 W22 W24 W25 Y9 Y11 Y14 Y17 Y21 AA9 AB1 AB9 AB11 AB13 AB15 AB17 AB19 AB25 AC8 AD8 AE1 AE8 AE24 |

## No-connect (53)

| Ball | Pin name (function) | Net | Connects to |
|---|---|---|---|
| A18 | `IMC_GPIO8` | `` | — |
| A21 | `IMC_GPIO33` | `` | — |
| A22 | `IMC_GPIO30` | `` | — |
| A23 | `IMC_GPIO28` | `` | — |
| B5 | `TEMPIN3/TALERT_L/GPIO64` | `` | — |
| B18 | `IMC_GPIO9` | `` | — |
| B21 | `IMC_GPIO32` | `` | — |
| B22 | `IMC_GPIO31` | `` | — |
| B23 | `IMC_GPIO27` | `` | — |
| B24 | `IMC_GPIO26` | `` | — |
| B25 | `IMC_GPIO24` | `` | — |
| C4 | `VIN2/GPIO55` | `` | — |
| C20 | `IMC_GPIO35` | `` | — |
| C22 | `IMC_GPIO29` | `` | — |
| C23 | `IMC_GPIO25` | `` | — |
| C24 | `IMC_GPIO23` | `` | — |
| C25 | `IMC_GPIO22` | `` | — |
| D20 | `IMC_GPIO34` | `` | — |
| E19 | `IMC_PWM1/IMC_GPIO15` | `` | — |
| F1 | `S3_STATE/GEVENT5_L` | `` | — |
| F25 | `IDE_RST_L/F_RST_L/IMC_GPO3` | `` | — |
| H7 | `SLP_S2/GPM9_L` | `` | — |
| H21 | `SPI_CS2_L/IMC_GPIO2` | `` | — |
| J1 | `ROM_RST_L/GPIO14` | `` | — |
| J8 | `AZ_SDIN1/GPIO43` | `` | — |
| L8 | `AZ_SDIN2/GPIO44` | `` | — |
| M3 | `AZ_SDIN3/GPIO46` | `` | — |
| M5 | `FANOUT1/GPIO48` | `` | — |
| M7 | `FANOUT2/GPIO49` | `` | — |
| P5 | `FANIN0/GPIO50` | `` | — |
| P8 | `FANIN1/GPIO51` | `` | — |
| Y22 | `IDE_A0` | `` | — |
| Y23 | `IDE_A2` | `` | — |
| Y24 | `IDE_CS3#` | `` | — |
| Y25 | `IDE_CS1#` | `` | — |
| AA24 | `IDE_IORDY` | `` | — |
| AA25 | `IDE_IRQ` | `` | — |
| AB8 | `LDRQ1_L/GNT5_L/GPIO68` | `` | — |
| AB20 | `IDE_D6/GPIO21` | `` | — |
| AB22 | `IDE_D12/GPIO27` | `` | — |
| AB23 | `IDE_A1` | `` | — |
| AB24 | `IDE_DACK#` | `` | — |
| AC20 | `IDE_D9/GPIO24` | `` | — |
| AC23 | `IDE_D15/GPIO30` | `` | — |
| AC24 | `IDE_IOW#` | `` | — |
| AC25 | `IDE_IOR#` | `` | — |
| AD19 | `IDE_D7/GPIO22` | `` | — |
| AD20 | `IDE_D10/GPIO25` | `` | — |
| AD22 | `IDE_D13/GPIO28` | `` | — |
| AD25 | `IDE_DRQ` | `` | — |
| AE19 | `IDE_D8/GPIO23` | `` | — |
| AE21 | `IDE_D11/GPIO26` | `` | — |
| AE23 | `IDE_D14/GPIO29` | `` | — |
