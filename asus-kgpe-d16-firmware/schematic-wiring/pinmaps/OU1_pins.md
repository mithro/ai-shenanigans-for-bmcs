# OU1 pin map  (128 pins)  C.S W83667HG-A-FAC QFP-128//NUVOTON (0.18UM) REV-FAC


## LPC host bus (7)

**Connected components** (chips / connectors these pins reach):

- `SU1` (528 pins, 7 nets) — C.S SP5100 (A15) FCBGA528//AMD 218-0660026
- `QU1` (355 pins, 6 nets) — C.S AST2050A3-GP TFBGA355//ASPEED
- `TPM1` (19 pins, 6 nets)

| Ball | Pin name (function) | Net | Connects to |
|---|---|---|---|
| 18 | `LDRQ#` | `LPC_DRQ0#` | SU1[H22] |
| 19 | `SERIRQ` | `LPC_SERIRQ` | QU1[C15], SU1[V15], TPM1[16] |
| 20 | `LAD3` | `LPC_LAD3` | QU1[C16], SU1[J24], TPM1[7] |
| 21 | `LAD2` | `LPC_LAD2` | QU1[D16], SU1[J25], TPM1[8] |
| 22 | `LAD1` | `LPC_LAD1` | QU1[A17], SU1[H23], TPM1[10] |
| 23 | `LAD0` | `LPC_LAD0` | QU1[B17], SU1[H24], TPM1[11] |
| 25 | `LFRAME#` | `LPC_FRAME#` | QU1[B16], SU1[H25], TPM1[3] |

## PCI (33MHz) (1)

**Connected components** (chips / connectors these pins reach):

- `SU1` (528 pins, 1 net) — C.S SP5100 (A15) FCBGA528//AMD 218-0660026

| Ball | Pin name (function) | Net | Connects to |
|---|---|---|---|
| 17 | `PCICLK` | `SB_PCI_CLK0` | SU1[P4] |

## I2C / SMBus (2)

**Connected components** (chips / connectors these pins reach):

- `LU1` (65 pins, 1 net) — C.S WG82574L A1 QFN64//INTEL 898553/SLBA9
- `LU2` (65 pins, 1 net) — C.S WG82574L A1 QFN64//INTEL 898553/SLBA9

| Ball | Pin name (function) | Net | Connects to |
|---|---|---|---|
| 75 | `IRRX/CIRRX/SCL/GP50` | `SIO_LAN2DISABLE#` | LAN_SW2[2], LU2[28] |
| 76 | `IRTX/CIRTX/SDA/GP37` | `SIO_LAN1DISABLE#` | LAN_SW1[2], LU1[28] |

## Serial / SOL (UART) (6)

**Connected components** (chips / connectors these pins reach):

- `QU8` (16 pins, 2 nets) — ANALOG SW. PI5C3257QE QS-16//PERICOM
- `SU1` (528 pins, 2 nets) — C.S SP5100 (A15) FCBGA528//AMD 218-0660026
- `SU2` (8 pins, 2 nets) — LOGIC 74LVC2G74DC VSSOP-8//NXP
- `U12` (20 pins, 2 nets) — INTERFACE AZ75232GTR-E1//BCD TSSOP-20

| Ball | Pin name (function) | Net | Connects to |
|---|---|---|---|
| 33 | `SINA/GP63` | `O_RXD1_R` | U12[17] |
| 34 | `SOUTA/GP62(FANSET)` | `O_TXD1_R` | U12[15] |
| 60 | `GP55/PSOUT#` | `N54412238` | Q9[3], SU1[D5,H2], SU2[7] |
| 61 | `GP54/PSIN#` | `SIO_FP_PWRBTN#` | Q9[3], SU1[D5,H2], SU2[7] |
| 71 | `SINB/GP43` | `O_RXD2_R` | QU8[7] |
| 72 | `SOUTB/GP42` | `O_TXD2_R` | QU8[4] |

## Power / reset / platform control (9)

**Connected components** (chips / connectors these pins reach):

- `SU1` (528 pins, 4 nets) — C.S SP5100 (A15) FCBGA528//AMD 218-0660026
- `QU4` (64 pins, 1 net) — C.S W83795G LQFP-64//WINBOND
- `TPM1` (19 pins, 1 net)
- `U27` (20 pins, 1 net) — C.S W83601G SSOP20//WINBOND MULTI-FUNCTION G.P.I/O
- `U28` (20 pins, 1 net) — C.S W83601G SSOP20//WINBOND MULTI-FUNCTION G.P.I/O
- `U6` (14 pins, 1 net) — LOGIC 74LVC07AD S-14//PHILIPS
- `U7` (14 pins, 1 net) — LOGIC TC74LCX74FT(EK2,M)//TOSHIBA TSSOP-14
- `U8` (14 pins, 1 net) — LOGIC 74LVC14APW-T TSSOP-14//PHILIPS

| Ball | Pin name (function) | Net | Connects to |
|---|---|---|---|
| 26 | `LRESET#` | `N54396360` | SU1[N2], TPM1[5] |
| 28 | `KBRST#/ENVIDO` | `SIO_KBRST#` | SU1[W15] |
| 42 | `PD7/GP97/PWROK2` | `N37987375` | — |
| 47 | `PD3/GP93/PWROK1` | `N37980610` | — |
| 63 | `GP52/PSON#` | `N54412916` | Q14[1] |
| 82 | `GP32/PWROK0` | `N54413373` | D7[1,2], PD58[2], PR321[2], PR322[2], R179[1], R180[1], R185[1], U6[5], U8[8] |
| 83 | `GP31/RESETCON#` | `SIO_RESETCON#` | — |
| 100 | `CASEOPEN#` | `INTRUDER#` | OQ1[3], QU4[27], SU1[C2] |
| 101 | `GP57/RSMRST#` | `SIO_RSMRST#` | QQ3[1], SU1[D3], U27[19], U28[19], U7[3] |

## LEDs / indicators (1)

| Ball | Pin name (function) | Net | Connects to |
|---|---|---|---|
| 62 | `SUSLED/GP53(EN_AS)` | `SIO_ENASIC` | — |

## Other / GPIO (32)

**Connected components** (chips / connectors these pins reach):

- `SU1` (528 pins, 6 nets) — C.S SP5100 (A15) FCBGA528//AMD 218-0660026
- `U12` (20 pins, 6 nets) — INTERFACE AZ75232GTR-E1//BCD TSSOP-20
- `CN23` (8 pins, 4 nets) — MLCC A 150PF/50V(1206) NPO 10%//WALSIN/Y4C3N151K500LT
- `PS2_KBMS1` (17 pins, 4 nets)
- `U13` (20 pins, 4 nets) — INTERFACE AZ75232GTR-E1//BCD TSSOP-20
- `PCI6` (122 pins, 2 nets)
- `QU8` (16 pins, 2 nets) — ANALOG SW. PI5C3257QE QS-16//PERICOM
- `TPM1` (19 pins, 2 nets)
- `ATXPWR1` (26 pins, 1 net)
- `CU1` (73 pins, 1 net) — CLOCK Gen. ICS932S890CKLFT//IDT MLF72
- `LU1` (65 pins, 1 net) — C.S WG82574L A1 QFN64//INTEL 898553/SLBA9
- `LU2` (65 pins, 1 net) — C.S WG82574L A1 QFN64//INTEL 898553/SLBA9
- `PANEL1` (19 pins, 1 net)
- `PCIE1` (166 pins, 1 net)
- `PCIE2` (166 pins, 1 net)
- `PCIE3` (100 pins, 1 net)
- `PCIE4` (166 pins, 1 net)
- `PCIE5` (166 pins, 1 net)
- `PIKE1` (100 pins, 1 net)
- `PIKE2` (66 pins, 1 net)
- `QU1` (355 pins, 1 net) — C.S AST2050A3-GP TFBGA355//ASPEED
- `QU4` (64 pins, 1 net) — C.S W83795G LQFP-64//WINBOND
- `U8` (14 pins, 1 net) — LOGIC 74LVC14APW-T TSSOP-14//PHILIPS
- `ZU1` (100 pins, 1 net) — C.S L-FW322-07-T100-DB TQFP100//LSI 1394A/711008303

| Ball | Pin name (function) | Net | Connects to |
|---|---|---|---|
| 15 | `IOCLK` | `CLKGEN_48M_SIO` | CU1[32] |
| 27 | `GA20M` | `SIO_A20M` | SU1[Y15] |
| 29 | `CTSA#/GP67` | `O_CTS1#_R` | U12[14] |
| 30 | `DSRA#/GP66` | `O_DSR1#_R` | U12[18] |
| 31 | `RTSA#/GP65(HEFRAS)` | `O_RTS1#_R` | U12[16] |
| 32 | `DTRA#/GP64(PENROM)` | `O_DTR1#_R` | U12[13] |
| 35 | `DCDA#/GP61` | `O_DCD1#_R` | U12[19] |
| 36 | `RIA#/GP60` | `O_RI1#_R` | U12[12] |
| 37 | `RSVD(SST)` | `N45641478` | — |
| 51 | `SLIN#/GP84(BEEP)` | `SIO_BEEP` | BUZZ1[2], PANEL1[20], Q43[3] |
| 56 | `GP23/MCLK` | `O_MS_CLK` | CN23[8], PS2_KBMS1[11] |
| 57 | `GP22/MDAT` | `O_MS_DATA` | CN23[4], PS2_KBMS1[7] |
| 58 | `GP21/KCLK` | `O_KB_CLK` | CN23[6], PS2_KBMS1[5] |
| 59 | `GP20/KDAT` | `O_KB_DATA` | CN23[2], PS2_KBMS1[1] |
| 64 | `GP51/SUSB#` | `N54412689` | PD58[1], PIKE2[A11], PQ59[1], QU1[D15], SU1[F5,K3], TPM1[19] |
| 65 | `PME#` | `N54426432` | LU1[16], LU2[16], PCI6[A19], PCIE1[B11], PCIE2[B11], PCIE3[B11], PCIE4[B11], PCIE5[B11], PIKE1[B11], SR127[1], SR133[1], SR168[1], SR73[1], SR74[1], SR77[1], SR81[1], SR82[1], SR89[1], SU1[E1,H6,K4], ZR19[1], ZR20[1], ZR21[1] |
| 67 | `CTSB#/GP47` | `O_CTS2#_R` | QU8[12] |
| 68 | `DSRB#/GP46` | `O_DSR2#_R` | U13[18] |
| 69 | `RTSB#/GP45` | `O_RTS2#_R` | QU8[9] |
| 70 | `DTRB#/GP44` | `O_DTR2#_R` | U13[13] |
| 73 | `DCDB#/GP41` | `O_DCD2#_R` | U13[19] |
| 74 | `RIB#/GP40` | `O_RI2#_R` | U13[12] |
| 77 | `RSTOUT2#` | `N54426440` | PCI6[A15], Q92[1], ZU1[7] |
| 78 | `GP36/RSTOUT1#` | `N54426438` | QU4[31] |
| 79 | `GP35/RSTOUT0#` | `N54426436` | SU1[N2], TPM1[5] |
| 80 | `GP34/ATXPGD` | `N54413144` | ATXPWR1[8], U8[5] |
| 81 | `3VSBSW#/GP33` | `N46433832` | — |
| 84 | `GP30/SUSC#` | `N54412463` | PD32[2], PD47[2], SU1[G1] |
| 102 | `GP56/SKTOCC` | `N45641504` | — |
| 103 | `VCORE_REFIN` | `SIO_VCORE_OVER` | — |
| 107 | `CPUVCORE` | `N45641752` | — |
| 128 | `OVT#/SMI#` | `N54458543` | SU1[K24,L5] |

## Power / decoupling (7)

| Rail | Count | Balls |
|---|---|---|
| `+3V3` | 3 | 1 24 106 |
| `+3V3_AUX` | 2 | 46 85 |
| `P0_VTT` | 1 | 114 |
| `VBAT` | 1 | 99 |

## Ground (2)

| Rail | Count | Balls |
|---|---|---|
| `GND` | 2 | 16 66 |

## No-connect (61)

| Ball | Pin name (function) | Net | Connects to |
|---|---|---|---|
| 2 | `DRVDEN0` | `` | — |
| 3 | `INDEX#` | `` | — |
| 4 | `MOA#` | `` | — |
| 5 | `DSA#` | `` | — |
| 6 | `DIR#` | `` | — |
| 7 | `STEP#` | `` | — |
| 8 | `WD#` | `` | — |
| 9 | `WE#` | `` | — |
| 10 | `TRAK0#` | `` | — |
| 11 | `WP#` | `` | — |
| 12 | `RDATA#` | `` | — |
| 13 | `HEAD#` | `` | — |
| 14 | `DSKCHG#` | `` | — |
| 38 | `GP24/CIRRXWB/SLCT` | `` | — |
| 39 | `PE/GP87` | `` | — |
| 40 | `BUSY/GP86` | `` | — |
| 41 | `ACK#/GP85` | `` | — |
| 43 | `PD6/GP96/BUSELO2` | `` | — |
| 44 | `PD5/GP95/BUSELO1` | `` | — |
| 45 | `PD4/GP94/BUSELO0` | `` | — |
| 48 | `PD2/GP92/BUSELI2` | `` | — |
| 49 | `PD1/GP91/BUSELI1` | `` | — |
| 50 | `PD0/GP90/BUSELI0` | `` | — |
| 52 | `INIT#/GP83(PLED)` | `` | — |
| 53 | `ERR#/GP82/VID_RST#` | `` | — |
| 54 | `AFD#/GP81/PECI_REQ#` | `` | — |
| 55 | `STB#/GP80` | `` | — |
| 86 | `VIDO7/GP77` | `` | — |
| 87 | `VIDO6/GP76` | `` | — |
| 88 | `VIDO5/GP75` | `` | — |
| 89 | `VIDO4/GP74` | `` | — |
| 90 | `VIDO3/GP73` | `` | — |
| 91 | `VIDO2/GP72` | `` | — |
| 92 | `VIDO1/GP71` | `` | — |
| 93 | `VIDO0/GP70` | `` | — |
| 94 | `SCK/GP27` | `` | — |
| 95 | `SCE#/(AUXFANIN2)GP26` | `` | — |
| 96 | `(AUXFANIN1)/GP25` | `` | — |
| 97 | `SI/AUXFANIN` | `` | — |
| 98 | `SO/AUXFANOUT` | `` | — |
| 104 | `VIN1` | `` | — |
| 105 | `VIN0` | `` | — |
| 108 | `VREF` | `` | — |
| 109 | `AUXTIN/VIN2` | `` | — |
| 110 | `CPUTIN` | `` | — |
| 111 | `SYSTIN` | `` | — |
| 112 | `CPUD-` | `` | — |
| 113 | `TSIC` | `` | — |
| 115 | `PECI/TSID` | `` | — |
| 116 | `VIDI7/GP17` | `` | — |
| 117 | `VIDI6/GP16` | `` | — |
| 118 | `VIDI5/GP15` | `` | — |
| 119 | `VIDI4/GP14` | `` | — |
| 120 | `VIDI3/GP13` | `` | — |
| 121 | `VIDI2/GP12` | `` | — |
| 122 | `VIDI1/GP11` | `` | — |
| 123 | `VIDI0/GP10` | `` | — |
| 124 | `CPUFANIN` | `` | — |
| 125 | `CPUFANOUT` | `` | — |
| 126 | `SYSFANIN` | `` | — |
| 127 | `SYSFANOUT` | `` | — |
